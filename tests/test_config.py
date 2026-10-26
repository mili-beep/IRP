from pathlib import Path

import pytest

from sfsa.config import parse_overrides, resolve_run_config

ROOT = Path(__file__).parents[1]
BUILDING = ROOT / "configs" / "buildings" / "rbc_ashrae1312_real.yaml"
EXPERIMENT = ROOT / "configs" / "experiments" / "E01_baseline.yaml"


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


def test_future_experiment_configs_keep_declared_study_settings():
    temporal = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "E05_temporal.yaml"
    )["resolved"]
    assert temporal["temporal"]["enabled"] is True
    generalisation = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "E06_generalisation.yaml"
    )["resolved"]
    assert generalisation["split_policy"] == "leave_season_out"


def test_e19_keeps_e03_model_and_features_but_holds_out_each_season():
    season_supervised = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "E19_supervised_season_generalisation.yaml"
    )["resolved"]
    assert season_supervised["models"] == ["supervised"]
    assert season_supervised["feature_policy"] == "symptom_only"
    assert season_supervised["split_policy"] == "leave_season_out"


def test_control_comparison_variants_are_explicit():
    control = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "E04a_control_inclusive.yaml"
    )["resolved"]
    weather = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "E04b_control_weather.yaml"
    )["resolved"]
    assert control["include_weather"] is False
    assert weather["include_weather"] is True


def test_instrumented_diagnosis_is_explicitly_scoped():
    instrumented = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "E16_hierarchical_instrumented_bms.yaml"
    )["resolved"]
    assert instrumented["task"] == "hierarchical_fault_type_classification"
    assert instrumented["feature_policy"] == "control_inclusive"
    assert instrumented["include_weather"] is False
    assert instrumented["physics_features"]["enabled"] is True
    assert instrumented["scenario_balancing"] is False


def test_full_building_diagnosis_adds_only_vav_telemetry_to_e16_scope():
    full_bms = resolve_run_config(
        BUILDING, ROOT / "configs" / "experiments" / "E17_hierarchical_full_bms.yaml"
    )["resolved"]
    assert full_bms["feature_policy"] == "control_inclusive"
    assert full_bms["include_vav"] is True
    assert full_bms["include_weather"] is False
    assert full_bms["scenario_balancing"] is False
