import json
from pathlib import Path

import pandas as pd
import pytest

from sfsa.training import (
    _choose_validation_candidate,
    _score_metrics,
    filter_occupied_hours,
    run_training,
)

ROOT = Path(__file__).parents[1]


def test_real_training_writes_a_run(tmp_path):
    run_dir = run_training(
        ROOT / "configs" / "buildings" / "rbc_ashrae1312_real.yaml",
        ROOT / "configs" / "experiments" / "D01_baseline.yaml",
        results_root=tmp_path,
        override_values=["max_folds=1"],
    )
    assert (run_dir / "config.json").exists()
    assert (run_dir / "features.json").exists()
    assert (run_dir / "metrics.csv").exists()
    assert (run_dir / "predictions.csv").exists()
    assert (run_dir / "scenario_metrics.csv").exists()
    assert (run_dir / "split_diagnostics.json").exists()
    assert (run_dir / "data_manifest.json").exists()
    assert (run_dir / "environment.json").exists()
    assert (run_dir / "preprocessing.joblib").exists()
    assert (run_dir / "config.resolved.json").exists()
    assert (run_dir / "metrics_by_fold.csv").exists()
    assert (run_dir / "metrics_summary.csv").exists()
    assert (run_dir / "split_membership.csv").exists()
    assert (run_dir / "thresholds.json").exists()
    assert (run_dir / "validation_model_selection.csv").exists()
    assert (run_dir / "model_comparison.csv").exists()
    assert (run_dir / "alert_explanations.csv").exists()
    assert (run_dir / "supervised_permutation_importance.csv").exists()
    assert (run_dir / "models" / "fold_001" / "statistical.joblib").exists()

    resolved = json.loads((run_dir / "config.resolved.json").read_text())
    assert resolved["resolved"]["feature_policy"] == "symptom_only"
    selection = pd.read_csv(run_dir / "validation_model_selection.csv")
    assert selection.groupby("model")["selected"].sum().eq(1).all()
    assert {"roc_auc", "pr_auc"}.issubset(pd.read_csv(run_dir / "metrics_by_fold.csv").columns)


def test_validation_candidate_selection_is_not_f1_only():
    selected = _choose_validation_candidate([
        {"validation_recall": 0.8, "validation_fpr": 0.4, "validation_f1": 0.9},
        {"validation_recall": 0.7, "validation_fpr": 0.1, "validation_f1": 0.2},
    ])
    assert selected["validation_f1"] == 0.2


def test_continuous_score_metrics_are_available_for_binary_labels():
    metrics = _score_metrics(pd.Series([0, 0, 1, 1]).to_numpy(), pd.Series([0.1, 0.2, 0.8, 0.9]).to_numpy())
    assert metrics == {"roc_auc": 1.0, "pr_auc": 1.0}


def test_training_applies_weather_and_temporal_overrides(tmp_path):
    run_dir = run_training(
        ROOT / "configs" / "buildings" / "rbc_ashrae1312_real.yaml",
        ROOT / "configs" / "experiments" / "D01_baseline.yaml",
        results_root=tmp_path,
        override_values=["include_weather=true", "temporal.enabled=true", "max_folds=1"],
    )
    features = json.loads((run_dir / "features.json").read_text())
    assert any(column.startswith("weather__") for column in features["base_columns"])
    assert any(column.endswith("__roc") for column in features["model_columns"])


def test_occupied_hours_filter_only_applies_when_explicitly_enabled():
    frame = pd.DataFrame({
        "timestamp": pd.to_datetime(["2024-01-01 05:59", "2024-01-01 06:00", "2024-01-01 18:01"]),
        "value": [1, 2, 3],
    })
    unchanged = filter_occupied_hours(frame, {"start": "06:00", "end": "18:00"})
    filtered = filter_occupied_hours(
        frame, {"start": "06:00", "end": "18:00", "apply": True}
    )
    assert len(unchanged) == 3
    assert filtered["value"].tolist() == [2]


def test_supervised_diagnosis_tasks_write_task_specific_outputs(tmp_path):
    type_run = run_training(
        ROOT / "configs" / "buildings" / "rbc_ashrae1312_real.yaml",
        ROOT / "configs" / "experiments" / "G01_fault_type_classification.yaml",
        results_root=tmp_path,
        override_values=["max_folds=1"],
    )
    assert (type_run / "confusion_matrix.csv").exists()
    assert (type_run / "label_scope.json").exists()
    type_predictions = pd.read_csv(type_run / "predictions.csv")
    assert {"true_fault_type", "predicted_fault_type", "confidence"}.issubset(
        type_predictions.columns
    )

    hierarchical_run = run_training(
        ROOT / "configs" / "buildings" / "rbc_ashrae1312_real.yaml",
        ROOT / "configs" / "experiments" / "G02a_hierarchical_baseline.yaml",
        results_root=tmp_path,
        override_values=["max_folds=1"],
    )
    assert (hierarchical_run / "coarse_confusion_matrix.csv").exists()
    hierarchical_predictions = pd.read_csv(hierarchical_run / "predictions.csv")
    assert {"true_fault_group", "predicted_fault_group"}.issubset(
        hierarchical_predictions.columns
    )
    scope = json.loads((hierarchical_run / "label_scope.json").read_text())
    assert set(hierarchical_predictions["predicted_fault_type"]).issubset(
        {"normal", *scope["included_fault_types"]}
    )

def test_reliability_policy_gates_reports_at_the_session_level(tmp_path):
    from sfsa.diagnosis import apply_reliability_policy

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows = []
    for fold in range(1, 7):
        correct = fold <= 5
        for minute in range(2):
            rows.append({
                "fold": fold,
                "date_folder": f"d{fold}",
                "scenario_file": f"fault_{fold}.csv",
                "true_fault_type": "cooling_coil_valve_stuck" if correct else "air_filter_blockage",
                "predicted_fault_type": "cooling_coil_valve_stuck",
                "true_fault_group": "cooling_coil" if correct else "airflow_distribution",
                "predicted_fault_group": "cooling_coil",
            })
    pd.DataFrame(rows).to_csv(run_dir / "predictions.csv", index=False)
    policy = tmp_path / "policy.yaml"
    policy.write_text("minimum_reliability: 0.70\nminimum_reports: 5\n", encoding="utf-8")
    output = apply_reliability_policy(run_dir, policy)
    reports = pd.read_csv(output / "diagnosis_reports.csv")
    assert len(reports) == 6
    assert set(reports["status"]) == {"Anomaly detected"}
    assert set(reports["fault_group"]) == {"cooling_coil"}
    assert set(reports["fault_type"]) == {"cooling_coil_valve_stuck"}
    summary = json.loads((output / "summary.json").read_text())
    assert summary["fault_reports"] == 6
    assert summary["fault_type_uncertain"] == 0


def test_scenario_balancing_gives_equal_total_weight_to_each_label_and_session():
    from sfsa.supervised_tasks import _scenario_balanced_weights

    frame = pd.DataFrame({
        "season": ["summer"] * 8,
        "date_folder": ["d1"] * 2 + ["d2"] * 4 + ["d3"] * 2,
        "scenario_file": ["a.csv"] * 2 + ["b.csv"] * 4 + ["c.csv"] * 2,
    })
    labels = pd.Series(["airside"] * 6 + ["cooling"] * 2).to_numpy()
    weights = _scenario_balanced_weights(frame, labels)
    weighted = frame.assign(label=labels, weight=weights)
    label_totals = weighted.groupby("label")["weight"].sum()
    scenario_totals = weighted.groupby("scenario_file")["weight"].sum()
    assert label_totals["airside"] == pytest.approx(label_totals["cooling"])
    assert scenario_totals["a.csv"] == pytest.approx(scenario_totals["b.csv"])
