import pandas as pd
import pytest

from sfsa.evaluation.metrics import event_metrics
from sfsa.evaluation.splits import (
    assert_no_paired_timestamp_leakage,
    leave_group_out,
    paired_holdout_splits,
    select_validation_dates,
)


def test_leave_group_out_keeps_complete_groups_together():
    frame = pd.DataFrame({"date_folder": ["a", "a", "b", "b"]})
    split = leave_group_out(frame, "date_folder", ["b"])
    assert split.train_index.tolist() == [0, 1]
    assert split.test_index.tolist() == [2, 3]


def test_pairing_leakage_is_rejected():
    frame = pd.DataFrame({
        "date_folder": ["a", "a"],
        "timestamp": pd.to_datetime(["2024-01-01", "2024-01-01"]),
    })
    with pytest.raises(ValueError, match="leakage"):
        assert_no_paired_timestamp_leakage(frame, frame.index[:1], frame.index[1:])


def test_event_metrics_reports_detection_and_delay():
    frame = pd.DataFrame({
        "scenario_file": ["baseline.csv", "baseline.csv", "fault.csv", "fault.csv"],
        "timestamp": pd.to_datetime([
            "2024-01-01 00:00", "2024-01-01 00:01", "2024-01-01 00:00", "2024-01-01 00:01"
        ]),
    })
    result = event_metrics(frame, [0, 1, 0, 1])
    assert result["event_recall"] == 1.0
    assert result["mean_detection_delay_minutes"] == 1.0


def test_fault_family_holdout_keeps_paired_baselines_with_faults():
    frame = pd.DataFrame({
        "date_folder": ["d1", "d1", "d2", "d2", "d3", "d3"],
        "timestamp": pd.to_datetime([
            "2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02", "2024-01-03", "2024-01-03"
        ]),
        "scenario_file": ["baseline.csv", "fan.csv", "baseline.csv", "fan.csv", "baseline.csv", "coil.csv"],
        "is_fault": [False, True, False, True, False, True],
        "fault_type": [None, "fan", None, "fan", None, "coil"],
        "fault_intensity": [None, "1", None, "2", None, "1"],
        "season": ["Summer", "Summer", "Summer", "Summer", "Winter", "Winter"],
    })
    splits = paired_holdout_splits(frame, "leave_fault_type_out")
    fan_split = next(split for split in splits if set(split.held_out_groups) == {"d1", "d2"})
    assert set(frame.loc[fan_split.test_index, "scenario_file"]) == {"baseline.csv", "fan.csv"}
    assert_no_paired_timestamp_leakage(frame, fan_split.train_index, fan_split.test_index)


def test_validation_selection_reserves_complete_dates():
    frame = pd.DataFrame({
        "date_folder": ["d1", "d1", "d2", "d2", "d3", "d3"],
        "timestamp": pd.date_range("2024-01-01", periods=6, freq="min"),
    })
    fit, validation, dates = select_validation_dates(frame, frame.index, fraction=0.34)
    assert dates == ("d3",)
    assert frame.loc[fit, "date_folder"].tolist() == ["d1", "d1", "d2", "d2"]
    assert frame.loc[validation, "date_folder"].tolist() == ["d3", "d3"]
