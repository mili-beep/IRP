"""Run-artifact checks for report preparation and final quality assurance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .utils import write_json


def audit_run_artifacts(run_dir: str | Path) -> dict[str, Any]:
    """Check provenance and internal consistency without changing a run."""
    run = Path(run_dir)
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str, severity: str = "error") -> None:
        checks.append({"name": name, "passed": passed, "severity": severity, "detail": detail})

    required = [
        "config.resolved.json", "data_manifest.json", "environment.json", "features.json",
        "split_membership.csv", "predictions.csv", "metrics.csv", "metrics_by_fold.csv",
        "metrics_summary.csv", "thresholds.json", "preprocessing.joblib",
    ]
    for filename in required:
        record(f"required:{filename}", (run / filename).exists(), "present" if (run / filename).exists() else "missing")
    model_files = list((run / "models").glob("fold_*/*.joblib")) if (run / "models").exists() else []
    record("saved-models", bool(model_files), f"{len(model_files)} fold-model files found" if model_files else "no fold-model files found")
    if not (run / "config.resolved.json").exists():
        return {"run": str(run), "accepted": False, "checks": checks}
    config = json.loads((run / "config.resolved.json").read_text())
    resolved = config.get("resolved", {})
    record("audit-gate", not config.get("runtime", {}).get("allow_audit_failures", False), "accepted audit gate" if not config.get("runtime", {}).get("allow_audit_failures", False) else "diagnostic run allowed audit failures", "warning")
    record("complete-folds", "max_folds" not in resolved, "all configured folds" if "max_folds" not in resolved else "diagnostic max_folds limit present", "warning")
    if (run / "data_manifest.json").exists():
        manifest = json.loads((run / "data_manifest.json").read_text())
        record("data-manifest", bool(manifest.get("validation", {}).get("accepted")), "manifest accepted" if manifest.get("validation", {}).get("accepted") else "manifest not accepted")
    if (run / "predictions.csv").exists() and (run / "metrics.csv").exists():
        predictions = pd.read_csv(run / "predictions.csv", low_memory=False)
        metrics = pd.read_csv(run / "metrics.csv")
        prediction_models = set(predictions.get("model", pd.Series(dtype=str)).dropna())
        metric_models = set(metrics.get("model", pd.Series(dtype=str)).dropna())
        record("model-consistency", prediction_models == metric_models, f"predictions={sorted(prediction_models)}, metrics={sorted(metric_models)}")
        record("prediction-fields", {"score", "threshold", "prediction", "y_true"}.issubset(predictions.columns), "continuous-score and decision fields saved")
    selection_path = run / "validation_model_selection.csv"
    if selection_path.exists():
        selection = pd.read_csv(selection_path)
        selected = selection.groupby(["fold", "model"])["selected"].sum().eq(1).all()
        record("candidate-selection", bool(selected), "exactly one validation candidate selected per model/fold")
    else:
        record("candidate-selection", False, "selection artefact missing", "warning")
    accepted = not any(not item["passed"] and item["severity"] == "error" for item in checks)
    return {"run": str(run), "accepted": accepted, "checks": checks}


def write_run_qa(run_dir: str | Path) -> Path:
    report = audit_run_artifacts(run_dir)
    path = Path(run_dir) / "qa_report.json"
    write_json(path, report)
    return path
