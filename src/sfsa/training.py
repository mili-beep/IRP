"""Generic real-dataset training orchestration for SFSA."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from .config import resolve_run_config
from .data.manifest import build_real_manifest
from .data.rbc_ashrae1312 import (
    discover_real_files,
    join_weather,
    load_scenario,
    load_weather,
)
from .evaluation.metrics import event_metrics
from .evaluation.splits import (
    assert_no_paired_timestamp_leakage,
    paired_holdout_splits,
    select_validation_dates,
)
from .features import (
	add_physics_features,
    add_temporal_features,
    classify_columns,
    fit_numeric_imputer,
    select_feature_columns,
    transform_numeric_features,
)
from .models import (
    ZScoreModel,
    gradient_boosting,
    isolation_forest,
    one_class_svm,
    xgboost_classifier,
)
from .utils import capture_environment, set_seed, write_json


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    normal = y_true == 0
    false_positive_rate = float(np.mean(y_pred[normal] == 1)) if normal.any() else 0.0
    return {
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "fpr": false_positive_rate,
    }


def _score_metrics(y_true: np.ndarray, scores: np.ndarray) -> dict[str, float]:
    """Report threshold-free discrimination only when both classes are present."""
    if len(np.unique(y_true)) < 2:
        return {"roc_auc": float("nan"), "pr_auc": float("nan")}
    return {
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "pr_auc": float(average_precision_score(y_true, scores)),
    }


def _scenario_metrics(frame: pd.DataFrame, predictions: np.ndarray) -> pd.DataFrame:
    """Compute detection rates separately for each held-out source file."""
    rows: list[dict[str, Any]] = []
    scored = frame.copy()
    scored["prediction"] = predictions
    group_columns = ["date_folder", "season", "scenario_file", "fault_type", "fault_intensity"]
    for keys, group in scored.groupby(group_columns, dropna=False):
        truth = group["is_fault"].astype(int).to_numpy()
        predicted = group["prediction"].to_numpy()
        rows.append({
            **dict(zip(group_columns, keys, strict=True)),
            "rows": len(group),
            "is_fault": int(group["is_fault"].iloc[0]),
            "flagged_rate": float(np.mean(predicted == 1)),
            "true_fault_rate": float(np.mean(truth == 1)),
        })
    return pd.DataFrame(rows).sort_values(["date_folder", "scenario_file"]).reset_index(drop=True)


def _fit_model(
    model_name: str,
    train_x: np.ndarray,
    train_y: np.ndarray,
    seed: int,
    parameters: dict[str, Any] | None = None,
):
    """Fit one configured model; supervised learning receives fault labels."""
    parameters = parameters or {}
    if model_name == "statistical":
        model = ZScoreModel().fit(train_x)
    elif model_name == "isolation_forest":
        model = isolation_forest(seed=seed, **parameters).fit(train_x)
    elif model_name == "one_class_svm":
        model = one_class_svm(seed=seed, **parameters).fit(train_x)
    elif model_name == "supervised":
        model = gradient_boosting(seed=seed, **parameters).fit(train_x, train_y)
    elif model_name == "xgboost":
        model = xgboost_classifier(seed=seed, **parameters).fit(train_x, train_y)
    else:
        raise ValueError(f"Unknown model configured: {model_name}")
    return model


def _anomaly_scores(model_name: str, model: Any, features: np.ndarray) -> np.ndarray:
    """Return scores oriented so larger values mean more anomalous."""
    if model_name == "statistical":
        return model.score_samples(features)
    if model_name in {"supervised", "xgboost"}:
        return model.predict_proba(features)[:, 1]
    return -model.decision_function(features)


def _calibrated_threshold(
    scores: np.ndarray, normal_mask: np.ndarray, alert_budget: float
) -> float:
    """Choose a threshold from validation normal observations only."""
    if not 0 < alert_budget < 1:
        raise ValueError("alert_budget must be between 0 and 1")
    normal_scores = scores[normal_mask]
    if len(normal_scores) == 0:
        raise ValueError("Validation partition contains no normal rows for threshold calibration")
    return float(np.quantile(normal_scores, 1 - alert_budget))


def _candidate_parameters(resolved: dict[str, Any], model_name: str) -> list[dict[str, Any]]:
    """Read a small, explicit validation grid for one model."""
    configured = resolved.get("model_candidates", {}).get(model_name, [{}])
    if not isinstance(configured, list) or not configured:
        raise ValueError(f"model_candidates.{model_name} must be a non-empty list")
    if not all(isinstance(candidate, dict) for candidate in configured):
        raise ValueError(f"model_candidates.{model_name} entries must be mappings")
    return configured


def _choose_validation_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Select by validation detection utility, then F1 as a transparent tie-break."""
    if not candidates:
        raise ValueError("At least one validation candidate is required")
    return max(
        candidates,
        key=lambda candidate: (
            candidate["validation_recall"] - candidate["validation_fpr"],
            candidate["validation_f1"],
            -candidate["validation_fpr"],
        ),
    )


def _explanation_rows(
    *,
    frame: pd.DataFrame,
    scaled_features: np.ndarray,
    feature_columns: list[str],
    scores: np.ndarray,
    predictions: np.ndarray,
    fold: int,
    model_name: str,
    threshold: float,
    cases_per_type: int,
    top_features: int,
) -> list[dict[str, Any]]:
    """Save the largest standardised deviations behind representative alerts."""
    rows: list[dict[str, Any]] = []
    truth = frame["is_fault"].astype(int).to_numpy()
    case_masks = {
        "true_detection": (truth == 1) & (predictions == 1),
        "false_alarm": (truth == 0) & (predictions == 1),
    }
    for case_type, mask in case_masks.items():
        selected = np.flatnonzero(mask)
        selected = selected[np.argsort(scores[selected])[::-1]][:cases_per_type]
        for rank, row_index in enumerate(selected, start=1):
            feature_indices = np.argsort(np.abs(scaled_features[row_index]))[::-1][:top_features]
            deviations = " | ".join(
                f"{feature_columns[index]}={scaled_features[row_index, index]:.3f}"
                for index in feature_indices
            )
            rows.append({
                "fold": fold,
                "model": model_name,
                "case_type": case_type,
                "rank": rank,
                "timestamp": frame.iloc[row_index]["timestamp"],
                "date_folder": frame.iloc[row_index]["date_folder"],
                "scenario_file": frame.iloc[row_index]["scenario_file"],
                "fault_type": frame.iloc[row_index]["fault_type"],
                "score": float(scores[row_index]),
                "threshold": threshold,
                "top_standardised_deviations": deviations,
            })
    return rows


def _metric_summary(metrics: pd.DataFrame, *, seed: int, iterations: int) -> pd.DataFrame:
    """Summarise fold metrics with deterministic bootstrap intervals."""
    metric_columns = [
        "f1",
        "precision",
        "recall",
        "fpr",
        "roc_auc",
        "pr_auc",
        "event_recall",
        "mean_detection_delay_minutes",
        "false_alarms_per_day",
        "fit_seconds",
        "score_seconds",
    ]
    rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(seed)
    for model_name, group in metrics.groupby("model", sort=True):
        for metric in metric_columns:
            values = group[metric].dropna().to_numpy(dtype=float)
            if not len(values):
                continue
            samples = np.array([
                rng.choice(values, size=len(values), replace=True).mean() for _ in range(iterations)
            ])
            rows.append({
                "model": model_name,
                "metric": metric,
                "folds": len(values),
                "mean": float(values.mean()),
                "median": float(np.median(values)),
                "ci_95_low": float(np.quantile(samples, 0.025)),
                "ci_95_high": float(np.quantile(samples, 0.975)),
            })
    return pd.DataFrame(rows)


def _load_tables(
    data_root: Path, *, include_weather: bool = False
) -> tuple[pd.DataFrame, pd.DataFrame]:
    records = discover_real_files(data_root)
    baseline_tables: list[pd.DataFrame] = []
    fault_tables: list[pd.DataFrame] = []
    for record in records:
        scenario_path = data_root / record.season / record.date_folder / record.scenario_file
        frame, _ = load_scenario(scenario_path)
        if include_weather:
            weather_path = scenario_path.parent / "weather.csv"
            if not weather_path.exists():
                raise FileNotFoundError(f"Weather requested but not found: {weather_path}")
            frame = join_weather(frame, load_weather(weather_path))
        if record.is_fault:
            fault_tables.append(frame)
        else:
            baseline_tables.append(frame)
    if not baseline_tables or not fault_tables:
        raise ValueError("The real dataset requires both baseline and fault files")
    return pd.concat(baseline_tables, ignore_index=True), pd.concat(fault_tables, ignore_index=True)


def filter_occupied_hours(frame: pd.DataFrame, occupied_hours: dict[str, Any]) -> pd.DataFrame:
    """Apply an explicit occupied-hours sensitivity filter to timestamped rows."""
    apply_filter = occupied_hours.get("apply", occupied_hours.get("apply_by_default", False))
    if not apply_filter:
        return frame
    if "timestamp" not in frame.columns:
        raise KeyError("timestamp")
    start = pd.to_datetime(occupied_hours["start"], format="%H:%M").time()
    end = pd.to_datetime(occupied_hours["end"], format="%H:%M").time()
    times = frame["timestamp"].dt.time
    if start <= end:
        mask = (times >= start) & (times <= end)
    else:
        mask = (times >= start) | (times <= end)
    return frame.loc[mask].copy()


def _prepare_model_frame(
    frame: pd.DataFrame,
    base_columns: list[str],
    imputer: Any,
    *,
    temporal: dict[str, Any],
) -> tuple[pd.DataFrame, list[str]]:
    """Impute numeric inputs and add boundary-safe temporal features when requested."""
    prepared = frame.copy()
    prepared[base_columns] = transform_numeric_features(frame, base_columns, imputer)
    if not temporal.get("enabled", False):
        return prepared, base_columns
    boundaries = temporal.get("boundary_columns", ["scenario_file", "date_folder"])
    if not isinstance(boundaries, list):
        raise ValueError("temporal.boundary_columns must be a list")
    prepared = add_temporal_features(
        prepared,
        base_columns,
        boundary_columns=boundaries,
        rolling_window=int(temporal.get("rolling_window", 5)),
    )
    temporal_columns = [
        column
        for base in base_columns
        for column in (f"{base}__roc", f"{base}__roll_mean{int(temporal.get('rolling_window', 5))}")
    ]
    return prepared, base_columns + temporal_columns


def _make_run_dir(results_root: Path, building: str, experiment: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = results_root / f"{stamp}_{building}_{experiment}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _project_root_from_config(building_config: str | Path) -> Path:
    """Find the repository root for standard ``configs/buildings/*.yaml`` paths."""
    config_path = Path(building_config).resolve()
    if config_path.parent.name == "buildings" and config_path.parent.parent.name == "configs":
        return config_path.parent.parent.parent
    return Path.cwd().resolve()


def run_training(
    building_config: str | Path,
    experiment_config: str | Path,
    *,
    results_root: str | Path = "results/runs",
    override_values: list[str] | None = None,
    allow_audit_failures: bool = False,
) -> Path:
    """Run a configured baseline/fault benchmark and save its complete run."""
    config_bundle = resolve_run_config(
        building_config, experiment_config, override_values=override_values or []
    )
    resolved = config_bundle["resolved"]
    if resolved.get("task") in {
        "fault_type_classification",
        "hierarchical_fault_type_classification",
    }:
        from .supervised_tasks import run_fault_type_classification

        return run_fault_type_classification(
            building_config,
            experiment_config,
            results_root=results_root,
            override_values=override_values,
            allow_audit_failures=allow_audit_failures,
        )
    building = config_bundle["building"]
    experiment = config_bundle["experiment"]
    if resolved.get("source_type") != "real":
        raise ValueError("Training currently supports source_type=real only")
    project_root = _project_root_from_config(building_config)
    data_root = Path(resolved["data_path"])
    if not data_root.is_absolute():
        data_root = project_root / data_root
    data_manifest = build_real_manifest(data_root)
    validation = data_manifest["validation"]
    if not validation["accepted"] and not allow_audit_failures:
        raise ValueError(f"Dataset audit failed: {'; '.join(validation['blockers'])}")
    set_seed(int(resolved.get("seed", 42)))
    baseline, faults = _load_tables(data_root, include_weather=bool(resolved["include_weather"]))
    occupied_hours = resolved.get("occupied_hours", {})
    baseline = filter_occupied_hours(baseline, occupied_hours)
    faults = filter_occupied_hours(faults, occupied_hours)
    physics = resolved.get("physics_features", {})
    if physics.get("enabled", False):
        baseline = add_physics_features(
            baseline,
            include_control_relationships=bool(physics.get("include_control_relationships", False)),
        )
        faults = add_physics_features(
            faults,
            include_control_relationships=bool(physics.get("include_control_relationships", False)),
        )
    if baseline.empty or faults.empty:
        raise ValueError("Occupied-hours filter removed all baseline or fault rows")
    frame = pd.concat([baseline, faults], ignore_index=True)
    groups = classify_columns(frame.columns)
    policy = resolved["feature_policy"]
    feature_columns = select_feature_columns(
        groups,
        policy,
        include_weather=bool(resolved["include_weather"]),
        include_vav=bool(resolved["include_vav"]),
        include_physics=bool(resolved.get("physics_features", {}).get("enabled", False)),
    )
    numeric_columns = [
        column for column in feature_columns if pd.api.types.is_numeric_dtype(frame[column])
    ]
    if not numeric_columns:
        raise ValueError("No numeric model features remain after feature policy")

    splits = paired_holdout_splits(frame, str(resolved["split_policy"]))
    max_folds = resolved.get("max_folds")
    if max_folds is not None:
        max_folds = int(max_folds)
        if max_folds < 1:
            raise ValueError("max_folds must be at least 1 when specified")
        splits = splits[:max_folds]

    run_dir = _make_run_dir(Path(results_root), building["name"], experiment["name"])
    write_json(run_dir / "data_manifest.json", data_manifest)
    write_json(run_dir / "environment.json", capture_environment(project_root))
    write_json(
        run_dir / "config.resolved.json",
        {**config_bundle, "runtime": {"allow_audit_failures": allow_audit_failures}},
    )
    models = resolved.get("models", ["statistical"])
    seed = int(resolved.get("seed", 42))
    alert_budget = float(resolved.get("alert_budget", 0.1))
    validation_fraction = float(resolved.get("validation_fraction", 0.2))
    metric_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    prediction_tables: list[pd.DataFrame] = []
    scenario_tables: list[pd.DataFrame] = []
    membership_tables: list[pd.DataFrame] = []
    candidate_rows: list[dict[str, Any]] = []
    explanation_rows: list[dict[str, Any]] = []
    importance_rows: list[dict[str, Any]] = []
    preprocessing_by_fold: dict[str, dict[str, Any]] = {}
    model_columns: list[str] | None = None

    import joblib

    for fold_number, split in enumerate(splits, start=1):
        assert_no_paired_timestamp_leakage(frame, split.train_index, split.test_index)
        fit_index, validation_index, validation_dates = select_validation_dates(
            frame, split.train_index, fraction=validation_fraction
        )
        assert_no_paired_timestamp_leakage(frame, fit_index, validation_index)
        fit_frame = frame.loc[fit_index]
        validation_frame = frame.loc[validation_index]
        test_frame = frame.loc[split.test_index]
        fit_normal = fit_frame[~fit_frame["is_fault"].astype(bool)]
        if fit_normal.empty:
            raise ValueError(f"Fold {fold_number} contains no normal training rows")

        imputer = fit_numeric_imputer(fit_normal, numeric_columns)
        fit_normal_prepared, fold_columns = _prepare_model_frame(
            fit_normal, numeric_columns, imputer, temporal=resolved["temporal"]
        )
        validation_prepared, validation_columns = _prepare_model_frame(
            validation_frame, numeric_columns, imputer, temporal=resolved["temporal"]
        )
        test_prepared, test_columns = _prepare_model_frame(
            test_frame, numeric_columns, imputer, temporal=resolved["temporal"]
        )
        if fold_columns != validation_columns or fold_columns != test_columns:
            raise ValueError("Feature columns differ across fit, validation, and test partitions")
        if model_columns is None:
            model_columns = fold_columns
        elif model_columns != fold_columns:
            raise ValueError("Feature columns differ between evaluation folds")

        scaler = StandardScaler().fit(fit_normal_prepared[fold_columns])
        normal_x = scaler.transform(fit_normal_prepared[fold_columns])
        validation_x = scaler.transform(validation_prepared[fold_columns])
        test_x = scaler.transform(test_prepared[fold_columns])
        fit_prepared, fit_columns = _prepare_model_frame(
            fit_frame, numeric_columns, imputer, temporal=resolved["temporal"]
        )
        if fit_columns != fold_columns:
            raise ValueError(
                "Supervised training feature columns differ from normal-training columns"
            )
        fit_x = scaler.transform(fit_prepared[fold_columns])
        fit_y = fit_frame["is_fault"].astype(int).to_numpy()
        validation_normal = ~validation_frame["is_fault"].astype(bool).to_numpy()
        y_test = test_frame["is_fault"].astype(int).to_numpy()

        membership_source = frame.loc[
            split.train_index.union(split.test_index),
            ["season", "date_folder", "scenario_file", "fault_type", "fault_intensity", "is_fault"],
        ].copy()
        membership_source["partition"] = "fit"
        membership_source.loc[
            membership_source.index.isin(validation_index), "partition"
        ] = "validation"
        membership_source.loc[membership_source.index.isin(split.test_index), "partition"] = "test"
        membership = (
            membership_source.groupby(
                [
                    "partition", "season", "date_folder", "scenario_file", "fault_type",
                    "fault_intensity", "is_fault",
                ],
                dropna=False,
            )
            .size()
            .rename("rows")
            .reset_index()
        )
        membership.insert(0, "fold", fold_number)
        membership_tables.append(membership)

        fold_dir = run_dir / "models" / f"fold_{fold_number:03d}"
        fold_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"imputer": imputer, "scaler": scaler, "feature_columns": fold_columns},
            fold_dir / "preprocessing.joblib",
        )
        preprocessing_by_fold[f"fold_{fold_number:03d}"] = {
            "imputer": imputer,
            "scaler": scaler,
            "feature_columns": fold_columns,
        }
        for model_name in models:
            validation_candidates: list[dict[str, Any]] = []
            for candidate_number, parameters in enumerate(
                _candidate_parameters(resolved, model_name), start=1
            ):
                started = perf_counter()
                candidate_model = _fit_model(
                    model_name,
                    fit_x if model_name in {"supervised", "xgboost"} else normal_x,
                    fit_y,
                    seed,
                    parameters,
                )
                fit_seconds = perf_counter() - started
                validation_scores = _anomaly_scores(model_name, candidate_model, validation_x)
                candidate_threshold = _calibrated_threshold(
                    validation_scores, validation_normal, alert_budget
                )
                validation_predictions = (validation_scores > candidate_threshold).astype(int)
                candidate = {
                    "fold": fold_number,
                    "model": model_name,
                    "candidate": candidate_number,
                    "parameters": parameters,
                    "fit_seconds": fit_seconds,
                    "threshold": candidate_threshold,
                    "validation_fpr": float(
                        np.mean(validation_scores[validation_normal] > candidate_threshold)
                    ),
                    **{
                        f"validation_{key}": value
                        for key, value in _metrics(
                            validation_frame["is_fault"].astype(int).to_numpy(),
                            validation_predictions,
                        ).items()
                    },
                    "model_object": candidate_model,
                }
                validation_candidates.append(candidate)
            selected = _choose_validation_candidate(validation_candidates)
            for candidate in validation_candidates:
                candidate_rows.append({
                    key: value
                    for key, value in candidate.items()
                    if key != "model_object"
                } | {"selected": candidate is selected})
            model = selected["model_object"]
            threshold = selected["threshold"]
            started = perf_counter()
            test_scores = _anomaly_scores(model_name, model, test_x)
            score_seconds = perf_counter() - started
            predictions = (test_scores > threshold).astype(int)
            event_frame = test_prepared.copy()
            event_frame["event_id"] = (
                event_frame["date_folder"].astype(str)
                + "::"
                + event_frame["scenario_file"].astype(str)
            )
            event = event_metrics(event_frame, predictions, event_column="event_id")
            metric_rows.append({
                "fold": fold_number,
                "model": model_name,
                "held_out_dates": "|".join(split.held_out_groups),
                "validation_dates": "|".join(validation_dates),
                "fit_seconds": selected["fit_seconds"],
                "score_seconds": score_seconds,
                **_metrics(y_test, predictions),
                **_score_metrics(y_test, test_scores),
                **event,
            })
            threshold_rows.append({
                "fold": fold_number,
                "model": model_name,
                "parameters": selected["parameters"],
                "alert_budget": alert_budget,
                "threshold": threshold,
                "validation_normal_rows": int(validation_normal.sum()),
                "validation_fpr": selected["validation_fpr"],
            })
            scenario_table = _scenario_metrics(test_prepared, predictions)
            scenario_table.insert(0, "model", model_name)
            scenario_table.insert(0, "fold", fold_number)
            scenario_tables.append(scenario_table)
            prediction_table = test_prepared[
                [
                    "timestamp", "season", "date_folder", "scenario_file", "fault_type",
                    "fault_intensity", "is_fault",
                ]
            ].copy()
            prediction_table.insert(0, "fold", fold_number)
            prediction_table.insert(1, "model", model_name)
            prediction_table["y_true"] = y_test
            prediction_table["score"] = test_scores
            prediction_table["threshold"] = threshold
            prediction_table["prediction"] = predictions
            prediction_tables.append(prediction_table)
            explanation_rows.extend(_explanation_rows(
                frame=test_prepared,
                scaled_features=test_x,
                feature_columns=fold_columns,
                scores=test_scores,
                predictions=predictions,
                fold=fold_number,
                model_name=model_name,
                threshold=threshold,
                cases_per_type=int(resolved.get("explanation_cases_per_type", 3)),
                top_features=int(resolved.get("explanation_top_features", 5)),
            ))
            if model_name in {"supervised", "xgboost"} and validation_frame["is_fault"].nunique() == 2:
                sample_size = min(
                    len(validation_x), int(resolved.get("importance_sample_rows", 1000))
                )
                sample_indices = np.random.default_rng(seed).choice(
                    len(validation_x), size=sample_size, replace=False
                )
                importance = permutation_importance(
                    model,
                    validation_x[sample_indices],
                    validation_frame["is_fault"].astype(int).to_numpy()[sample_indices],
                    scoring="f1",
                    n_repeats=1,
                    random_state=seed,
                    n_jobs=1,
                )
                importance_rows.extend({
                    "fold": fold_number,
                    "model": model_name,
                    "feature": feature,
                    "permutation_importance_f1": float(value),
                } for feature, value in zip(fold_columns, importance.importances_mean, strict=True))
            joblib.dump(model, fold_dir / f"{model_name}.joblib")

    metrics_by_fold = pd.DataFrame(metric_rows)
    metrics_summary = _metric_summary(
        metrics_by_fold, seed=seed, iterations=int(resolved.get("bootstrap_iterations", 1000))
    )
    metrics_wide = (
        metrics_summary.pivot(index="model", columns="metric", values="mean").reset_index()
        if not metrics_summary.empty
        else pd.DataFrame()
    )
    metrics_by_fold.to_csv(run_dir / "metrics_by_fold.csv", index=False)
    metrics_summary.to_csv(run_dir / "metrics_summary.csv", index=False)
    metrics_wide.to_csv(run_dir / "metrics.csv", index=False)
    comparison = metrics_wide.copy()
    if not comparison.empty:
        comparison["selection_basis"] = (
            "validation recall minus false-positive rate; F1 breaks ties"
        )
    comparison.to_csv(run_dir / "model_comparison.csv", index=False)
    predictions_frame = pd.concat(prediction_tables, ignore_index=True)
    predictions_frame.to_csv(run_dir / "predictions.csv", index=False)
    pd.concat(scenario_tables, ignore_index=True).to_csv(
        run_dir / "scenario_metrics.csv", index=False
    )
    pd.concat(membership_tables, ignore_index=True).to_csv(
        run_dir / "split_membership.csv", index=False
    )
    pd.DataFrame(candidate_rows).to_csv(run_dir / "validation_model_selection.csv", index=False)
    pd.DataFrame(explanation_rows).to_csv(run_dir / "alert_explanations.csv", index=False)
    pd.DataFrame(importance_rows).to_csv(
        run_dir / "supervised_permutation_importance.csv", index=False
    )
    fault_group_rows: list[dict[str, Any]] = []
    for group_column in ("fault_type", "fault_intensity", "season"):
        for keys, group in predictions_frame.groupby(["model", "fold", group_column], dropna=False):
            model_name, fold, group_value = keys
            fault_group_rows.append({
                "group_column": group_column,
                "group_value": "baseline" if pd.isna(group_value) else str(group_value),
                "model": model_name,
                "fold": fold,
                "rows": len(group),
                **_metrics(group["y_true"].to_numpy(), group["prediction"].to_numpy()),
            })
    pd.DataFrame(fault_group_rows).to_csv(run_dir / "metrics_by_fault_group.csv", index=False)
    write_json(run_dir / "thresholds.json", {"thresholds": threshold_rows})
    write_json(
        run_dir / "split_diagnostics.json",
        {
            "policy": resolved["split_policy"],
            "fold_count": len(splits),
            "validation_fraction": validation_fraction,
            "alert_budget": alert_budget,
            "folds": [
                {"fold": number, "held_out_dates": list(split.held_out_groups)}
                for number, split in enumerate(splits, start=1)
            ],
        },
    )
    write_json(
        run_dir / "features.json",
        {
            "policy": policy,
            "base_columns": numeric_columns,
            "model_columns": model_columns or [],
            "temporal": resolved["temporal"],
        },
    )
    write_json(
        run_dir / "config.json",
        {
            "building": building,
            "experiment": experiment,
            "resolved": resolved,
            "split_policy": resolved["split_policy"],
            "fold_count": len(splits),
        },
    )
    joblib.dump(preprocessing_by_fold, run_dir / "preprocessing.joblib")
    return run_dir
