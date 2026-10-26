"""Turn saved anomaly rows into explainable, rate-limited operational events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .config import load_yaml
from .utils import write_json


def group_events(predictions: pd.DataFrame, policy: dict[str, Any]) -> pd.DataFrame:
    """Group adjacent flagged rows into one event within a model/fold/scenario stream."""
    required = {
        "fold", "model", "timestamp", "date_folder", "scenario_file", "score",
        "threshold", "prediction", "y_true",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Predictions are missing event fields: {sorted(missing)}")
    flagged = predictions.loc[predictions["prediction"].astype(int) == 1].copy()
    if flagged.empty:
        return pd.DataFrame()
    flagged["timestamp"] = pd.to_datetime(flagged["timestamp"])
    grouping = ["fold", "model", "date_folder", "scenario_file"]
    flagged = flagged.sort_values(grouping + ["timestamp"])
    gap = pd.Timedelta(minutes=int(policy["gap_tolerance_minutes"]))
    flagged["_new_event"] = (
        flagged.groupby(grouping, dropna=False)["timestamp"].diff().gt(gap).fillna(True)
    )
    flagged["_event_sequence"] = flagged.groupby(grouping, dropna=False)["_new_event"].cumsum()
    rows: list[dict[str, Any]] = []
    event_groups = flagged.groupby(
        grouping + ["_event_sequence"], dropna=False, sort=False
    )
    for keys, event_rows in event_groups:
        fold, model, date_folder, scenario_file, sequence = keys
        active_rows = len(event_rows)
        if active_rows < int(policy["minimum_alert_rows"]):
            continue
        start = event_rows["timestamp"].min()
        end = event_rows["timestamp"].max()
        maximum = event_rows.loc[event_rows["score"].idxmax()]
        truth = event_rows["y_true"].astype(int).to_numpy()
        rows.append({
            "event_id": (
                f"{model}-f{fold}-{date_folder}-{Path(str(scenario_file)).stem}-"
                f"{int(sequence):03d}"
            ),
            "fold": fold,
            "model": model,
            "date_folder": date_folder,
            "scenario_file": scenario_file,
            "fault_type": maximum.get("fault_type"),
            "fault_intensity": maximum.get("fault_intensity"),
            "start_timestamp": start,
            "end_timestamp": end,
            "duration_minutes": float((end - start).total_seconds() / 60 + 1),
            "alert_rows": active_rows,
            "max_score": float(maximum["score"]),
            "threshold": float(maximum["threshold"]),
            "event_outcome": "true_detection" if truth.any() else "false_alarm",
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("start_timestamp").reset_index(drop=True)


def event_case_studies(predictions: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Select evidence for one true, false, and missed/weak scenario without fabrication."""
    records: list[dict[str, Any]] = []
    if not events.empty:
        for outcome in ("true_detection", "false_alarm"):
            candidates = events.loc[events["event_outcome"] == outcome]
            if not candidates.empty:
                row = candidates.sort_values("max_score", ascending=False).iloc[0].to_dict()
                row["case_type"] = outcome
                records.append(row)
    scenario_columns = [
        "fold", "model", "date_folder", "scenario_file", "fault_type", "fault_intensity",
    ]
    fault_groups = predictions.loc[
        predictions["y_true"].astype(int) == 1
    ].groupby(scenario_columns, dropna=False)
    missed = []
    for keys, group in fault_groups:
        if not group["prediction"].astype(int).any():
            missed.append(dict(zip(scenario_columns, keys, strict=True)) | {
                "case_type": "missed_or_weak", "max_score": float(group["score"].max()),
                "threshold": float(group["threshold"].iloc[0]),
                "explanation": (
                    "No anomaly row exceeded the calibrated threshold for this "
                    "controlled scenario."
                ),
            })
    if missed:
        records.append(max(missed, key=lambda row: row["max_score"]))
    return pd.DataFrame(records)


def _attach_supporting_evidence(events: pd.DataFrame, run_dir: Path) -> pd.DataFrame:
    explanations_path = run_dir / "alert_explanations.csv"
    if events.empty or not explanations_path.exists():
        events["supporting_feature_evidence"] = pd.NA
        return events
    explanations = pd.read_csv(explanations_path)
    explanations["timestamp"] = pd.to_datetime(explanations["timestamp"])
    evidence: list[str | None] = []
    for event in events.itertuples(index=False):
        selected = explanations.loc[
            (explanations["fold"] == event.fold)
            & (explanations["model"] == event.model)
            & (explanations["timestamp"] >= event.start_timestamp)
            & (explanations["timestamp"] <= event.end_timestamp),
            "top_standardised_deviations",
        ]
        evidence.append(selected.iloc[0] if not selected.empty else None)
    events["supporting_feature_evidence"] = evidence
    return events


def _attach_normal_mode_context(events: pd.DataFrame, patterns_run: Path | None) -> pd.DataFrame:
    if events.empty or patterns_run is None:
        events["nearest_normal_mode"] = pd.NA
        events["normal_mode_distance"] = pd.NA
        events["normal_mode_deviations"] = pd.NA
        return events
    path = patterns_run / "fault_mode_comparisons.csv"
    if not path.exists():
        raise FileNotFoundError(f"Normal-mode comparisons not found: {path}")
    comparisons = pd.read_csv(path, low_memory=False)
    comparisons["timestamp"] = pd.to_datetime(comparisons["timestamp"])
    mode_rows: list[dict[str, Any]] = []
    for event in events.itertuples(index=False):
        selected = comparisons.loc[
            (comparisons["date_folder"].astype(str) == str(event.date_folder))
            & (comparisons["scenario_file"].astype(str) == str(event.scenario_file))
            & (comparisons["timestamp"] >= event.start_timestamp)
            & (comparisons["timestamp"] <= event.end_timestamp)
        ]
        if selected.empty:
            mode_rows.append({})
        else:
            row = selected.loc[selected["mode_distance"].idxmax()]
            mode_rows.append({
                "nearest_normal_mode": int(row["nearest_normal_mode"]),
                "normal_mode_distance": float(row["mode_distance"]),
                "normal_mode_deviations": row["top_mode_deviations"],
            })
    mode_frame = pd.DataFrame(mode_rows)
    return pd.concat([events.reset_index(drop=True), mode_frame], axis=1)


def build_events(
    run_dir: str | Path,
    policy_path: str | Path,
    *,
    patterns_run: str | Path | None = None,
    output_name: str = "events",
) -> Path:
    """Write event artefacts under a completed benchmark run without retraining."""
    source = Path(run_dir)
    if Path(output_name).name != output_name or output_name in {"", ".", ".."}:
        raise ValueError("output_name must be one safe directory name")
    predictions_path = source / "predictions.csv"
    if not predictions_path.exists():
        raise FileNotFoundError(f"Run predictions not found: {predictions_path}")
    policy = load_yaml(policy_path)
    events = group_events(pd.read_csv(predictions_path, low_memory=False), policy)
    events = _attach_supporting_evidence(events, source)
    events = _attach_normal_mode_context(events, Path(patterns_run) if patterns_run else None)
    cases = event_case_studies(pd.read_csv(predictions_path, low_memory=False), events)
    output = source / output_name
    output.mkdir(exist_ok=True)
    events.to_csv(output / "events.csv", index=False)
    cases.to_csv(output / "event_case_studies.csv", index=False)
    summary = {
        "source_run": str(source),
        "event_count": int(len(events)),
        "events_by_outcome": (
            events["event_outcome"].value_counts().to_dict() if not events.empty else {}
        ),
        "policy": policy,
        "patterns_run": str(patterns_run) if patterns_run else None,
    }
    write_json(output / "event_summary.json", summary)
    return output
