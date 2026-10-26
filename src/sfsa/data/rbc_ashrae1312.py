"""Ingestion contracts for the real RBC-ASHRAE1312 dataset."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

SCENARIO_TYPES = {
    "OADamStuck": "outdoor_air_damper_stuck",
    "OADamLea": "outdoor_air_damper_leak",
    "EADamStuck": "exhaust_air_damper_stuck",
    "EADamLea": "exhaust_air_damper_leak",
    "CooCoiValStuck": "cooling_coil_valve_stuck",
    "HeaCoiValLea": "heating_coil_valve_leak",
    "SupDucLea": "supply_duct_leak",
    "HeaCoiFou": "heating_coil_fouling",
    "HeaCoiReduCapa": "heating_coil_reduced_capacity",
    "RetFan_Fail": "return_fan_failure",
    "RetFanFixed": "return_fan_fixed_speed",
    "AirFilBlock": "air_filter_blockage",
    "ConSupFan_Unst": "unstable_supply_fan_control",
    "ConCooCoiVal_Unst": "unstable_cooling_coil_valve_control",
    "CooCoiVal_Reverse": "cooling_coil_valve_reverse_action",
    "MADam_Unst": "unstable_mixed_air_damper",
    "Con_MADamCooCoi_Unst": "unstable_mixed_air_damper_cooling_coil_control",
    "HeaCooSeq_Unst": "unstable_heating_cooling_sequence",
    "TOut_p3": "outdoor_temperature_sensor_bias_positive",
    "TOut_m3": "outdoor_temperature_sensor_bias_negative",
}

# The distributed CSVs contain spelling/separator variants of the taxonomy
# names. Keep aliases explicit so a new typo does not become a false label.
SCENARIO_ALIASES = {
    "OADamLeak": "OADamLea",
    "EADamLeak": "EADamLea",
    "CooCoilValStuck": "CooCoiValStuck",
    "CooCoiVal_Stuck": "CooCoiValStuck",
    "HeaCoiValLeak": "HeaCoiValLea",
    "HeaCoiValLa": "HeaCoiValLea",
    "HeatCoiReduCapa": "HeaCoiReduCapa",
    "Con_MADam_CooCoi_Unst": "Con_MADamCooCoi_Unst",
}


@dataclass(frozen=True)
class ScenarioMetadata:
    """Metadata inherited by every row from one source CSV."""

    source_type: str
    season: str
    date_folder: str
    scenario_file: str
    scenario_abbreviation: str
    fault_type: str | None
    fault_intensity: str | None
    is_fault: bool
    controlled_device: str | None
    weather_file: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_real_files(data_root: str | Path) -> list[ScenarioMetadata]:
    """Discover real RBC files without entering the Simulation tree."""
    root = Path(data_root)
    if root.name == "Simulation" or "Simulation" in root.parts:
        raise ValueError("The real-only adapter refuses Simulation data")
    if root.name != "Real":
        raise ValueError(f"Expected the Real dataset directory, got {root}")

    records: list[ScenarioMetadata] = []
    for season_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if season_dir.name not in {"Summer", "Transition", "Winter"}:
            continue
        for date_dir in sorted(path for path in season_dir.iterdir() if path.is_dir()):
            csv_names = {path.name for path in date_dir.glob("*.csv")}
            weather_file = "weather.csv" if "weather.csv" in csv_names else None
            for path in sorted(date_dir.glob("*.csv")):
                if path.name == "weather.csv":
                    continue
                metadata = parse_scenario_filename(
                    path.name,
                    season=season_dir.name,
                    date_folder=date_dir.name,
                    weather_file=weather_file,
                )
                records.append(metadata)
    if not records:
        raise FileNotFoundError(f"No real RBC CSV files found under {root}")
    return records


def parse_scenario_filename(
    filename: str,
    *,
    season: str,
    date_folder: str,
    weather_file: str | None,
) -> ScenarioMetadata:
    """Parse a baseline or fault filename into explicit scenario metadata."""
    if filename == "baseline.csv":
        return ScenarioMetadata(
            source_type="real",
            season=season,
            date_folder=date_folder,
            scenario_file=filename,
            scenario_abbreviation="baseline",
            fault_type=None,
            fault_intensity=None,
            is_fault=False,
            controlled_device=None,
            weather_file=weather_file,
        )
    if not filename.endswith(".csv"):
        raise ValueError(f"Expected a CSV scenario file, got {filename}")

    abbreviation = filename[:-4]
    matched = next(
        (
            key
            for key in sorted(SCENARIO_TYPES, key=len, reverse=True)
            if abbreviation.startswith(key)
        ),
        None,
    )
    if matched is None:
        alias = next(
            (
                key
                for key in sorted(SCENARIO_ALIASES, key=len, reverse=True)
                if abbreviation.startswith(key)
            ),
            None,
        )
        matched = SCENARIO_ALIASES.get(alias) if alias else None
        matched_prefix = alias if alias else None
    else:
        matched_prefix = matched
    if matched is None:
        raise ValueError(f"Unknown RBC fault abbreviation in {filename}")
    suffix = abbreviation[len(matched_prefix):].lstrip("_") or None
    return ScenarioMetadata(
        source_type="real",
        season=season,
        date_folder=date_folder,
        scenario_file=filename,
        scenario_abbreviation=abbreviation,
        fault_type=SCENARIO_TYPES[matched],
        fault_intensity=suffix,
        is_fault=True,
        controlled_device=matched,
        weather_file=weather_file,
    )


def parse_timestamp(frame: pd.DataFrame) -> pd.Series:
    """Parse compact AHU or conventional weather date/time values into timestamps."""
    required = {"DATE", "TIME"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"RBC file is missing timestamp columns: {sorted(missing)}")
    numeric_dates = pd.to_numeric(frame["DATE"], errors="coerce")
    if numeric_dates.notna().all():
        date_text = numeric_dates.astype("Int64").astype(str).str.zfill(8)
        dates = pd.to_datetime(date_text, format="%m%d%Y", errors="coerce")
    else:
        dates = pd.to_datetime(frame["DATE"], errors="coerce")
    time_values = pd.to_numeric(frame["TIME"], errors="coerce")
    if time_values.notna().all():
        hours = time_values // 100
        minutes = time_values % 100
        invalid_time = (hours > 23) | (minutes > 59) | (time_values < 0)
        time_delta = pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="min")
    else:
        time_delta = pd.to_timedelta(frame["TIME"].astype(str), errors="coerce")
        invalid_time = time_delta.isna()
    timestamps = dates + time_delta
    if timestamps.isna().any() or invalid_time.any():
        invalid_count = int((timestamps.isna() | invalid_time).sum())
        raise ValueError(f"Could not parse {invalid_count} RBC timestamps")
    return timestamps.rename("timestamp")


def validate_timestamps(frame: pd.DataFrame) -> dict[str, Any]:
    """Report ordering, duplicates, gaps, and modal cadence for one CSV."""
    timestamps = parse_timestamp(frame)
    deltas = timestamps.sort_values().diff().dropna().dt.total_seconds()
    modal_cadence = float(deltas.mode().iloc[0]) if not deltas.empty else None
    return {
        "rows": int(len(frame)),
        "first_timestamp": timestamps.min().isoformat(),
        "last_timestamp": timestamps.max().isoformat(),
        "duplicate_timestamps": int(timestamps.duplicated().sum()),
        "out_of_order_rows": int((timestamps.diff().dropna() < pd.Timedelta(0)).sum()),
        "modal_cadence_seconds": modal_cadence,
        "non_minute_intervals": int((deltas != 60).sum()),
    }


def validate_pairing(data_root: str | Path) -> list[dict[str, Any]]:
    """Validate baseline presence and timestamp alignment per fault file."""
    root = Path(data_root)
    results: list[dict[str, Any]] = []
    for metadata in discover_real_files(root):
        if not metadata.is_fault:
            continue
        date_dir = root / metadata.season / metadata.date_folder
        fault_path = date_dir / metadata.scenario_file
        baseline_path = date_dir / "baseline.csv"
        result: dict[str, Any] = {
            **metadata.as_dict(),
            "baseline_present": baseline_path.exists(),
            "timestamps_aligned": False,
        }
        if baseline_path.exists():
            fault_ts = parse_timestamp(pd.read_csv(fault_path, usecols=["DATE", "TIME"]))
            baseline_ts = parse_timestamp(pd.read_csv(baseline_path, usecols=["DATE", "TIME"]))
            result["fault_rows"] = len(fault_ts)
            result["baseline_rows"] = len(baseline_ts)
            result["timestamps_aligned"] = fault_ts.equals(baseline_ts)
        results.append(result)
    return results


def load_scenario(path: str | Path) -> tuple[pd.DataFrame, ScenarioMetadata]:
    """Load one real scenario CSV and attach parsed metadata columns."""
    source = Path(path)
    real_root = next(parent for parent in source.parents if parent.name == "Real")
    relative = source.relative_to(real_root)
    season, date_folder = relative.parts[:2]
    metadata = parse_scenario_filename(
        source.name,
        season=season,
        date_folder=date_folder,
        weather_file="weather.csv" if (source.parent / "weather.csv").exists() else None,
    )
    frame = pd.read_csv(source)
    metadata_columns = {
        key: value for key, value in metadata.as_dict().items() if key not in frame.columns
    }
    timestamp_frame = pd.DataFrame({"timestamp": parse_timestamp(frame)})
    metadata_frame = pd.DataFrame(metadata_columns, index=frame.index)
    return pd.concat([timestamp_frame, frame, metadata_frame], axis=1), metadata


def load_weather(path: str | Path) -> pd.DataFrame:
    """Load a real weather file with the same canonical timestamp contract."""
    frame = pd.read_csv(path)
    frame.insert(0, "timestamp", parse_timestamp(frame))
    return frame


def join_weather(frame: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Left-join weather context with a prefix to keep feature provenance explicit."""
    if "timestamp" not in frame or "timestamp" not in weather:
        raise ValueError("Both scenario and weather frames require a timestamp column")
    weather_columns = {
        column: f"weather__{column}" for column in weather.columns if column != "timestamp"
    }
    weather = weather.rename(columns=weather_columns)
    return frame.merge(weather, on="timestamp", how="left", validate="many_to_one")
