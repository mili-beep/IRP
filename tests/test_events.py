import json
from pathlib import Path

import pandas as pd
import pytest

from sfsa.events import build_events, event_case_studies, group_events

ROOT = Path(__file__).parents[1]

POLICY = {
    "gap_tolerance_minutes": 5,
    "minimum_alert_rows": 2,
}


def test_event_grouping_suppresses_adjacent_alert_rows_and_preserves_missed_case():

    predictions = pd.DataFrame({
        "fold": [1, 1, 1, 1, 1],
        "model": ["statistical"] * 5,
        "timestamp": pd.to_datetime([
            "2024-01-01 00:00", "2024-01-01 00:03", "2024-01-01 00:15",
            "2024-01-02 00:00", "2024-01-02 00:01",
        ]),
        "date_folder": ["20240101"] * 3 + ["20240102"] * 2,
        "scenario_file": ["fan.csv"] * 3 + ["coil.csv"] * 2,
        "fault_type": ["fan"] * 3 + ["coil"] * 2,
        "fault_intensity": ["10"] * 5,
        "score": [3.0, 2.0, 4.0, 0.2, 0.3],
        "threshold": [1.0] * 5,
        "prediction": [1, 1, 1, 0, 0],
        "y_true": [1, 1, 1, 1, 1],
    })

    events = group_events(predictions, POLICY)
    assert len(events) == 1
    assert events.loc[0, "alert_rows"] == 2
    assert events.loc[0, "event_outcome"] == "true_detection"
    assert "priority_score" not in events.columns
    cases = event_case_studies(predictions, events)
    assert {"true_detection", "missed_or_weak"}.issubset(cases["case_type"])


def test_event_output_name_cannot_escape_the_run_directory(tmp_path):

    with pytest.raises(ValueError, match="safe directory"):
        build_events(
            tmp_path,
            "configs/operational_policies/event_grouping.yaml",
            output_name="../events",
        )


def test_priority_cards_use_configured_duration_severity_and_asset_policy(tmp_path):

    from sfsa.priorities import build_priority_cards

    events_dir = tmp_path / "events"
    events_dir.mkdir()

    pd.DataFrame({
        "event_id": ["long", "brief"],
        "date_folder": ["d1", "d2"],
        "scenario_file": ["cooling.csv", "unknown.csv"],
        "duration_minutes": [600, 10],
        "start_timestamp": ["2024-01-01", "2024-01-02"],
        "priority_score": [1.0, 1.0],
        "priority_band": ["low", "low"],
        "recommended_action": ["monitor", "monitor"],
    }).to_csv(events_dir / "events.csv", index=False)

    diagnosis_dir = tmp_path / "diagnosis"
    diagnosis_dir.mkdir()

    pd.DataFrame({
        "date_folder": ["d1", "d2"],
        "scenario_file": ["cooling.csv", "unknown.csv"],
        "status": ["Anomaly detected", "Anomaly detected"],
        "fault_group": ["cooling_coil", "Uncertain"],
        "fault_type": ["cooling_coil_valve_stuck", "Uncertain"],
    }).to_csv(diagnosis_dir / "diagnosis_reports.csv", index=False)

    policy = ROOT / "configs" / "operational_policies" / "O02_priority_policy.yaml"
    output = build_priority_cards(events_dir, diagnosis_dir, policy)
    cards = pd.read_csv(output / "priority_cards.csv")
    long_event = cards.loc[cards["event_id"].eq("long")].iloc[0]
    brief_event = cards.loc[cards["event_id"].eq("brief")].iloc[0]
    assert long_event["severity_level"] == 4
    assert long_event["duration_level"] == 5
    assert long_event["priority_band"] == "High"
    assert "anomaly_priority_score" not in cards.columns
    assert brief_event["severity_basis"] == "uncertain diagnosis"
    assert brief_event["priority_band"] == "Low"
    summary = json.loads((output / "priority_summary.json").read_text())
    assert summary["diagnosis_available"] == 1
