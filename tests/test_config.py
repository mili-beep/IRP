from pathlib import Path

import pytest

from sfsa.config import parse_overrides, resolve_run_config

ROOT = Path(__file__).parents[1]
BUILDING = ROOT / "configs" / "buildings" / "rbc_ashrae1312_real.yaml"
EXPERIMENT = ROOT / "configs" / "experiments" / "D01_baseline.yaml"


def test_resolve_run_config_preserves_building_features_and_experiment_policy():

    bundle = resolve_run_config(BUILDING, EXPERIMENT)
    resolved = bundle["resolved"]
    assert resolved["feature_policy"] == "symptom_only"
    assert resolved["split_policy"] == "leave_scenario_out"
    assert resolved["features"]["weather_optional"] is True
    assert resolved["temporal"]["enabled"] is False
    assert resolved["occupied_hours"]["start"] == "06:00"


def test_resolve_run_config_applies_typed_dotted_overrides():

    bundle = resolve_run_config(
        BUILDING,
        EXPERIMENT,
        override_values=[
            "include_weather=true",
            "occupied_hours.apply=true",
            "temporal.enabled=true",
            "temporal.rolling_window=3",
        ],
    )

    resolved = bundle["resolved"]
    assert resolved["include_weather"] is True
    assert resolved["occupied_hours"]["apply"] is True
    assert resolved["temporal"]["enabled"] is True
    assert resolved["temporal"]["rolling_window"] == 3


def test_invalid_override_fails_clearly():

    with pytest.raises(ValueError, match="KEY=VALUE"):
        parse_overrides(["include_weather"])


def test_detection_sensitivity_configs_keep_declared_study_settings():

    temporal = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "D05_temporal.yaml"
    )["resolved"]
    assert temporal["temporal"]["enabled"] is True

    generalisation = resolve_run_config(
        BUILDING,
        ROOT / "configs" / "experiments" / "D06_classical_season_generalisation.yaml",
    )["resolved"]
    assert generalisation["split_policy"] == "leave_season_out"


def test_xgboost_primary_studies_have_declared_scopes():
    detection = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "D07_xgboost_detection.yaml"
    )["resolved"]
    season = resolve_run_config(
        BUILDING,
        ROOT / "configs" / "experiments" / "D08_xgboost_season_generalisation.yaml",
    )["resolved"]
    diagnosis = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "G03a_instrumented_bms.yaml"
    )["resolved"]

    assert detection["models"] == ["xgboost"]
    assert detection["feature_policy"] == "symptom_only"
    assert detection["split_policy"] == "leave_scenario_out"
    assert season["models"] == ["xgboost"]
    assert season["split_policy"] == "leave_season_out"
    assert diagnosis["classifier"] == "xgboost"
    assert diagnosis["feature_policy"] == "control_inclusive"
    assert diagnosis["physics_features"]["include_control_relationships"] is True


def test_control_comparison_variants_are_explicit():

    control = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "D04a_control_inclusive.yaml"
    )["resolved"]
    weather = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "D04b_control_weather.yaml"
    )["resolved"]

    assert control["include_weather"] is False
    assert weather["include_weather"] is True


def test_instrumented_diagnosis_is_explicitly_scoped():

    instrumented = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "G03a_instrumented_bms.yaml"
    )["resolved"]

    assert instrumented["task"] == "hierarchical_fault_type_classification"
    assert instrumented["classifier"] == "xgboost"
    assert instrumented["feature_policy"] == "control_inclusive"
    assert instrumented["include_weather"] is False
    assert instrumented["physics_features"]["enabled"] is True
    assert instrumented["scenario_balancing"] is False
