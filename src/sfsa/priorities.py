"""Transparent operational priority cards from saved events and diagnoses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .config import load_yaml
from .utils import write_json


def _level(value: Any, *, name: str) -> int:
    level = int(value)
    if not 1 <= level <= 5:
        raise ValueError(f"{name} must be an integer from 1 to 5")
    return level


def _priority_band(score: float, policy: dict[str, Any]) -> tuple[str, str]:
    bands = policy["priority_bands"]
    if score >= float(bands["critical_min"]):
        return "Critical", str(policy["actions"]["critical"])
    if score >= float(bands["high_min"]):
        return "High", str(policy["actions"]["high"])
    if score >= float(bands["medium_min"]):
        return "Medium", str(policy["actions"]["medium"])
    return "Low", str(policy["actions"]["low"])


def _duration_level(minutes: float, policy: dict[str, Any]) -> tuple[int, str]:
    levels = policy["duration_levels"]
    eligible = [item for item in levels if minutes >= float(item["min_minutes"])]
    if not eligible:
        raise ValueError("duration_levels must start at min_minutes: 0")
    chosen = max(eligible, key=lambda item: float(item["min_minutes"]))
    return _level(chosen["level"], name="duration level"), str(chosen["label"])


def _severity(record: pd.Series, policy: dict[str, Any]) -> tuple[int, str, str]:
    mapping = policy["severity"]
    fault_type = str(record.get("fault_type", "Uncertain"))
    fault_group = str(record.get("fault_group", "Uncertain"))
    if fault_type not in {"Uncertain", "Not applicable"} and fault_type in mapping["fault_types"]:
        item = mapping["fault_types"][fault_type]
        return _level(item["level"], name="fault-type severity"), str(item["label"]), "fault type"
    if fault_group not in {"Uncertain", "Not applicable"} and fault_group in mapping["fault_groups"]:
        item = mapping["fault_groups"][fault_group]
        return _level(item["level"], name="fault-group severity"), str(item["label"]), "fault group"
    item = mapping["default"]
    return _level(item["level"], name="default severity"), str(item["label"]), "uncertain diagnosis"


def _asset(policy: dict[str, Any]) -> tuple[str, int, str]:
    asset_key = str(policy["default_asset"])
    try:
        asset = policy["assets"][asset_key]
    except KeyError as error:
        raise ValueError(f"No asset mapping exists for default_asset={asset_key!r}") from error
    return asset_key, _level(asset["criticality"], name="asset criticality"), str(asset["label"])


def _validate_policy(policy: dict[str, Any]) -> dict[str, float]:
    weights = {name: float(value) for name, value in policy["weights"].items()}
    required = {"severity", "duration", "criticality"}
    if set(weights) != required:
        raise ValueError(f"weights must contain exactly {sorted(required)}")
    if any(value < 0 for value in weights.values()) or abs(sum(weights.values()) - 1) > 1e-9:
        raise ValueError("priority weights must be non-negative and sum to 1")
    _asset(policy)
    _duration_level(0, policy)
    for item in policy["severity"]["fault_groups"].values():
        _level(item["level"], name="fault-group severity")
    for item in policy["severity"]["fault_types"].values():
        _level(item["level"], name="fault-type severity")
    _level(policy["severity"]["default"]["level"], name="default severity")
    return weights


def _diagnosis_lookup(diagnosis_dir: Path) -> pd.DataFrame:
    path = diagnosis_dir / "diagnosis_reports.csv"
    if not path.exists():
        raise FileNotFoundError(f"Diagnosis reports not found: {path}")
    reports = pd.read_csv(path)
    required = {"date_folder", "scenario_file", "status", "fault_group", "fault_type"}
    missing = required - set(reports.columns)
    if missing:
        raise ValueError(f"Diagnosis reports are missing: {sorted(missing)}")
    lookup = reports[list(required)].copy()
    lookup["date_folder"] = lookup["date_folder"].astype(str)
    lookup["scenario_file"] = lookup["scenario_file"].astype(str)
    if lookup.duplicated(["date_folder", "scenario_file"]).any():
        raise ValueError("Diagnosis reports must contain one report per date and scenario")
    return lookup.rename(columns={
        "status": "diagnosis_status",
        "fault_group": "diagnosed_fault_group",
        "fault_type": "diagnosed_fault_type",
    })


def build_priority_cards(
    events_dir: str | Path,
    diagnosis_dir: str | Path,
    policy_path: str | Path,
    *,
    output_name: str = "priority_cards",
) -> Path:
    """Attach a documented priority policy to saved anomaly events."""
    events_source = Path(events_dir)
    if Path(output_name).name != output_name or output_name in {"", ".", ".."}:
        raise ValueError("output_name must be one safe directory name")
    events_path = events_source / "events.csv"
    if not events_path.exists():
        raise FileNotFoundError(f"Event table not found: {events_path}")
    policy = load_yaml(policy_path)
    weights = _validate_policy(policy)
    events = pd.read_csv(events_path)
    required = {"date_folder", "scenario_file", "duration_minutes"}
    missing = required - set(events.columns)
    if missing:
        raise ValueError(f"Event table is missing: {sorted(missing)}")
    events["date_folder"] = events["date_folder"].astype(str)
    events["scenario_file"] = events["scenario_file"].astype(str)
    legacy_priority_columns = [
        column for column in ("priority_score", "priority_band", "recommended_action")
        if column in events
    ]
    # Historical event outputs used a detector-score priority rule. Drop it so
    # this documented policy is the only priority shown on new cards.
    events = events.drop(columns=legacy_priority_columns)
    cards = events.merge(
        _diagnosis_lookup(Path(diagnosis_dir)),
        on=["date_folder", "scenario_file"],
        how="left",
    )
    cards["diagnosis_status"] = cards["diagnosis_status"].fillna("Anomaly detected")
    cards["fault_group"] = cards["diagnosed_fault_group"].fillna("Uncertain")
    cards["fault_type"] = cards["diagnosed_fault_type"].fillna("Uncertain")
    asset_key, criticality, criticality_label = _asset(policy)
    scored: list[dict[str, Any]] = []
    for _, card in cards.iterrows():
        severity, severity_label, severity_basis = _severity(card, policy)
        duration, duration_label = _duration_level(float(card["duration_minutes"]), policy)
        score = 100 * (
            weights["severity"] * (severity - 1) / 4
            + weights["duration"] * (duration - 1) / 4
            + weights["criticality"] * (criticality - 1) / 4
        )
        band, action = _priority_band(score, policy)
        scored.append({
            "severity_level": severity,
            "severity_label": severity_label,
            "severity_basis": severity_basis,
            "duration_level": duration,
            "duration_label": duration_label,
            "asset_key": asset_key,
            "asset_criticality_level": criticality,
            "asset_criticality_label": criticality_label,
            "priority_score": round(score, 1),
            "priority_band": band,
            "recommended_action": action,
        })
    cards = pd.concat([cards.reset_index(drop=True), pd.DataFrame(scored)], axis=1)
    cards = cards.sort_values(["priority_score", "start_timestamp"], ascending=[False, True])
    output = events_source / output_name
    output.mkdir(exist_ok=False)
    cards.to_csv(output / "priority_cards.csv", index=False)
    write_json(output / "priority_summary.json", {
        "source_events": str(events_source),
        "source_diagnoses": str(diagnosis_dir),
        "event_count": int(len(cards)),
        "priority_bands": cards["priority_band"].value_counts().to_dict(),
        "diagnosis_available": int((
            ~cards["fault_group"].isin(["Uncertain", "Not applicable"])
        ).sum()),
        "policy": policy,
        "limitation": (
            "Severity and criticality are configurable prototype assumptions. "
            "This controlled-fault dataset does not provide client-approved criticality "
            "ratings or varied real fault durations."
        ),
    })
    return output
