from pathlib import Path

import pandas as pd
import pytest

from sfsa.data.rbc_ashrae1312 import (
    discover_real_files,
    join_weather,
    parse_scenario_filename,
    parse_timestamp,
    validate_pairing,
)

ROOT = Path(__file__).parents[1]
REAL_ROOT = ROOT / "data" / "raw" / "01_RBC-ASHRAE1312" / "Real"


def test_rbc_compact_date_and_hhmm_parse():
    timestamps = parse_timestamp(pd.DataFrame({"DATE": [8202007, 8202007], "TIME": [0, 1]}))
    assert timestamps.iloc[0] == pd.Timestamp("2007-08-20 00:00:00")
    assert timestamps.iloc[1] == pd.Timestamp("2007-08-20 00:01:00")


def test_rbc_hhmm_parse_does_not_roll_over_to_the_next_day():
    timestamps = parse_timestamp(pd.DataFrame({"DATE": [8202007], "TIME": [2359]}))
    assert timestamps.iloc[0] == pd.Timestamp("2007-08-20 23:59:00")


def test_known_filename_alias_is_explicitly_supported():
    metadata = parse_scenario_filename(
        "HeaCoiValLa_2.csv",
        season="Winter",
        date_folder="20080202",
        weather_file=None,
    )
    assert metadata.fault_type == "heating_coil_valve_leak"
    assert metadata.fault_intensity == "2"


def test_real_discovery_rejects_simulation_path():
    with pytest.raises(ValueError, match="refuses Simulation"):
        discover_real_files(ROOT / "data" / "raw" / "01_RBC-ASHRAE1312" / "Simulation")


def test_local_real_dataset_has_complete_pairs():
    records = discover_real_files(REAL_ROOT)
    pairings = validate_pairing(REAL_ROOT)
    assert len(records) == 98
    assert sum(record.is_fault for record in records) == 49
    assert all(item["baseline_present"] and item["timestamps_aligned"] for item in pairings)


def test_weather_join_prefixes_colliding_columns():
    scenario = pd.DataFrame({"timestamp": [pd.Timestamp("2024-01-01")], "OA-TEMP": [70.0]})
    weather = pd.DataFrame({"timestamp": [pd.Timestamp("2024-01-01")], "OA-TEMP": [65.0]})
    joined = join_weather(scenario, weather)
    assert joined.loc[0, "OA-TEMP"] == 70.0
    assert joined.loc[0, "weather__OA-TEMP"] == 65.0
