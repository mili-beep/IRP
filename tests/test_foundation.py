from pathlib import Path

import pandas as pd

from sfsa.config import load_yaml
from sfsa.data.clean import coerce_numeric_columns
from sfsa.data.labels import normal_mask
from sfsa.evaluation.metrics import metric_names

ROOT = Path(__file__).parents[1]


def test_auditorium_config_loads():
    config = load_yaml(ROOT / "configs" / "buildings" / "auditorium.yaml")
    assert config["label_column"] == "labeling"


def test_numeric_whitespace_is_coerced():
    frame = coerce_numeric_columns(pd.DataFrame({"sensor": ["28.0 ", "29.0"]}))
    assert frame["sensor"].tolist() == [28.0, 29.0]


def test_normal_label_matching_is_case_insensitive():
    labels = pd.Series(["Normal condition", "Heating pump fault"])
    assert normal_mask(labels, "normal condition").tolist() == [True, False]


def test_required_metrics_are_declared():
    assert metric_names() == ("f1", "precision", "recall", "fpr")
