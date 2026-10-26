import pandas as pd
import pytest

from sfsa.features import (
	add_physics_features,
    add_temporal_features,
    classify_columns,
    fit_numeric_imputer,
    missingness_report,
    select_feature_columns,
    transform_numeric_features,
)


def test_feature_policies_keep_metadata_out():
    groups = classify_columns(
        ["timestamp", "SA-TEMP", "SA-SPT", "SF-SPD", "E_SF", "VAV-DAT", "WIND-VEL"]
    )
    symptoms = select_feature_columns(groups, "symptom_only")
    inclusive = select_feature_columns(
        groups, "control_inclusive", include_weather=True, include_vav=True
    )
    assert "timestamp" not in symptoms
    assert "SA-SPT" not in symptoms
    assert "SF-SPD" in inclusive
    assert "WIND-VEL" in inclusive
    assert "VAV-DAT" in inclusive


def test_reviewed_feature_exceptions_do_not_leak_into_symptom_only_policy():
    groups = classify_columns(["SAT_SPT", "RMCLGSPT", "SA-TEMP"])
    symptoms = select_feature_columns(groups, "symptom_only")
    assert groups.control == ("SAT_SPT",)
    assert groups.vav == ("RMCLGSPT",)
    assert symptoms == ["SA-TEMP"]


def test_context_policy_admits_only_reviewed_safe_control_fields():
	groups = classify_columns(["SA-TEMP", "SAT_SPT", "CHWC-VLV", "OA-DMPR", "SYS-CTL"])
	context = select_feature_columns(groups, "context_inclusive")
	assert {"SA-TEMP", "SAT_SPT", "SYS-CTL"}.issubset(context)
	assert "CHWC-VLV" not in context
	assert "OA-DMPR" not in context


def test_physics_features_are_opt_in_and_only_add_control_relationships_when_requested():
	frame = pd.DataFrame({
		"SA-TEMP": [60.0], "MA-TEMP": [70.0], "SAT_SPT": [55.0],
		"SA-CFM": [1000.0], "RMT-CFM": [900.0], "SF-SPD": [50.0],
	})
	passive = add_physics_features(frame)
	with_controls = add_physics_features(frame, include_control_relationships=True)
	assert passive["physics__supply_air_temperature_change"].iloc[0] == -10.0
	assert "physics__supply_air_setpoint_error" not in passive
	assert with_controls["physics__supply_air_setpoint_error"].iloc[0] == 5.0
	assert "physics__supply_airflow_per_fan_speed" not in with_controls
	groups = classify_columns(with_controls.columns)
	assert "physics__supply_air_temperature_change" not in select_feature_columns(groups, "symptom_only")
	assert "physics__supply_air_temperature_change" in select_feature_columns(
		groups, "symptom_only", include_physics=True
	)


def test_weather_join_prefixes_non_colliding_weather_columns():
    from sfsa.data.rbc_ashrae1312 import join_weather

    scenario = pd.DataFrame({"timestamp": [pd.Timestamp("2024-01-01")], "SA-TEMP": [70.0]})
    weather = pd.DataFrame({"timestamp": [pd.Timestamp("2024-01-01")], "WIND-VEL": [3.0]})
    joined = join_weather(scenario, weather)
    assert "weather__WIND-VEL" in joined
    assert "WIND-VEL" not in joined


def test_missingness_report_includes_fully_empty_columns():
    report = missingness_report(pd.DataFrame({"empty": [None, None], "partial": [1.0, None]}))
    values = report.set_index("column")
    assert values.loc["empty", "missing_rows"] == 2
    assert values.loc["empty", "missing_fraction"] == 1.0
    assert values.loc["partial", "missing_fraction"] == 0.5


def test_imputer_is_fit_and_applied_as_a_separate_step():
    train = pd.DataFrame({"sensor": [1.0, 3.0, None]})
    test = pd.DataFrame({"sensor": [None]})
    imputer = fit_numeric_imputer(train, ["sensor"])
    transformed = transform_numeric_features(test, ["sensor"], imputer)
    assert transformed.loc[0, "sensor"] == 2.0


def test_temporal_features_reset_at_boundaries():
    frame = pd.DataFrame({
        "scenario_file": ["a", "a", "b"],
        "date_folder": ["d", "d", "d"],
        "timestamp": pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:01", "2024-01-01 00:00"]),
        "SA-TEMP": [10.0, 12.0, 100.0],
    })
    result = add_temporal_features(frame, ["SA-TEMP"])
    assert result.loc[2, "SA-TEMP__roc"] == 0.0
    assert result.loc[1, "SA-TEMP__roc"] == 2.0


def test_unknown_feature_policy_fails():
    with pytest.raises(ValueError, match="Unknown feature policy"):
        select_feature_columns(classify_columns(["SA-TEMP"]), "all")
