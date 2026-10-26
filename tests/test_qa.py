import json

import pandas as pd

from sfsa.qa import audit_run_artifacts


def test_run_qa_accepts_a_minimal_consistent_run(tmp_path):
    (tmp_path / "config.resolved.json").write_text(json.dumps({"resolved": {}, "runtime": {}}))
    (tmp_path / "data_manifest.json").write_text(json.dumps({"validation": {"accepted": True}}))
    (tmp_path / "environment.json").write_text("{}")
    (tmp_path / "features.json").write_text("{}")
    (tmp_path / "split_membership.csv").write_text("partition,rows\nfit,1\n")
    (tmp_path / "metrics_by_fold.csv").write_text("fold,model\n1,statistical\n")
    (tmp_path / "metrics_summary.csv").write_text("model,metric\nstatistical,f1\n")
    (tmp_path / "thresholds.json").write_text("{}")
    (tmp_path / "models" / "fold_001").mkdir(parents=True)
    (tmp_path / "models" / "fold_001" / "statistical.joblib").write_text("test")
    (tmp_path / "preprocessing.joblib").write_text("test")
    pd.DataFrame({"model": ["statistical"], "score": [2.0], "threshold": [1.0], "prediction": [1], "y_true": [1]}).to_csv(tmp_path / "predictions.csv", index=False)
    pd.DataFrame({"model": ["statistical"], "f1": [1.0]}).to_csv(tmp_path / "metrics.csv", index=False)
    pd.DataFrame({"fold": [1], "model": ["statistical"], "selected": [True]}).to_csv(tmp_path / "validation_model_selection.csv", index=False)
    assert audit_run_artifacts(tmp_path)["accepted"] is True
