"""Feature grouping, selection, and boundary-safe engineering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer

METADATA_COLUMNS = {
	"DATE", "TIME", "timestamp", "source_type", "season", "date_folder",
	"scenario_file", "scenario_abbreviation", "fault_type", "fault_intensity",
	"is_fault", "controlled_device", "weather_file",
}
CONTROL_EXACT = {
	"SYS-CTL", "ACCH-SEL", "ECONCTRL", "RF-CTRL", "SF-SST", "RF-SST",
	"SF-SPD", "RF-SPD", "RF-SFSPD", "SF-WAT", "RF-WAT", "HWC-VLV", "CHWC-VLV",
	"OA-DMPR", "RA-DMPR", "EA-DMPR", "VAV-DMPR", "VAVHCVLV",
	"SAT_SPT", "SA_SPSPT",
}
SAFE_CONTEXT_EXACT = {
	"SYS-CTL", "ACCH-SEL", "ECONCTRL", "SAT_SPT", "SAT-SPT", "SA_SPSPT", "SA-SPT",
}
CONTROL_TOKENS = ("-SP", "-SPT", "SPT", "-SEL", "-CTL", "-CTRL", "-DMPR", "-VLV")
WEATHER_COLUMNS = {
	"BAR-PRES", "IR-RADIA", "OA-HUMD", "SOL-ALM", "SOL-BEAM", "SOL-HORZ", "WIND-DIR", "WIND-VEL"
}
VAV_TOKENS = ("VAV", "RM-TEMP", "PLN-TEMP", "OCC-", "ABBHT", "BBHT", "LITE", "LITWAT", "AMPS")

# These exceptions were reviewed against docs/reference/rbc_ashrae1312/
# feature_dictionary.md. They prevent setpoints and VAV fields from being
# accidentally admitted through the heuristic ``unclassified`` group.
REVIEWED_EXACT_GROUPS = {
	"SAT_SPT": "control",
	"SA_SPSPT": "control",
	"RMT-CFM": "symptom",
	"RMCLGSPT": "vav",
	"RMHTGSPT": "vav",
	"VAVCFMDP": "vav",
	"VAVHCEWT": "vav",
	"VAVHCLWT": "vav",
	"VAVHCGPM": "vav",
}


@dataclass(frozen=True)
class FeatureGroups:
	"""Column groups derived from raw RBC names."""

	metadata: tuple[str, ...]
	control: tuple[str, ...]
	symptom: tuple[str, ...]
	weather: tuple[str, ...]
	energy: tuple[str, ...]
	physics: tuple[str, ...]
	vav: tuple[str, ...]
	unclassified: tuple[str, ...]

	def as_dict(self) -> dict[str, list[str]]:
		return {name: list(getattr(self, name)) for name in self.__dataclass_fields__}


def classify_columns(columns: Iterable[str]) -> FeatureGroups:
	"""Classify raw columns without renaming or dropping them."""
	groups: dict[str, list[str]] = {name: [] for name in FeatureGroups.__dataclass_fields__}
	for column in columns:
		if column in METADATA_COLUMNS:
			group = "metadata"
		elif column.startswith("physics__"):
			group = "physics"
		elif column in WEATHER_COLUMNS or column.startswith("weather__"):
			group = "weather"
		elif column.rstrip(".123") in REVIEWED_EXACT_GROUPS:
			group = REVIEWED_EXACT_GROUPS[column.rstrip(".123")]
		elif column.startswith("E_"):
			group = "energy"
		elif column in CONTROL_EXACT or any(token in column for token in CONTROL_TOKENS):
			group = "control"
		elif any(token in column for token in VAV_TOKENS):
			group = "vav"
		elif any(
			token in column
			for token in (
				"TEMP", "HUMD", "CFM", "DP", "GPM", "DAT", "EWT", "LWT", "MWT", "LAH", "EAH"
			)
		):
			group = "symptom"
		else:
			group = "unclassified"
		groups[group].append(column)
	return FeatureGroups(**{name: tuple(values) for name, values in groups.items()})


def select_feature_columns(
	groups: FeatureGroups,
	policy: str,
	*,
	include_weather: bool = False,
	include_vav: bool = False,
	include_physics: bool = False,
) -> list[str]:
	"""Select model columns for an explicit feature policy."""
	if policy not in {"symptom_only", "context_inclusive", "control_inclusive"}:
		raise ValueError(f"Unknown feature policy: {policy}")
	selected = list(groups.symptom) + list(groups.energy) + list(groups.unclassified)
	if policy == "control_inclusive":
		selected += list(groups.control)
	if policy == "context_inclusive":
		selected += [column for column in groups.control if column in SAFE_CONTEXT_EXACT]
	if include_weather:
		selected += list(groups.weather)
	if include_vav:
		selected += list(groups.vav)
	if include_physics:
		selected += list(groups.physics)
	return list(dict.fromkeys(selected))


def add_physics_features(
	frame: pd.DataFrame,
	*,
	include_control_relationships: bool = False,
) -> pd.DataFrame:
	"""Add documented, row-local HVAC residuals without inferring missing signals."""
	result = frame.copy()

	def difference(name: str, left: str, right: str) -> None:
		if {left, right}.issubset(result.columns):
			result[name] = result[left] - result[right]

	difference("physics__supply_air_temperature_change", "SA-TEMP", "MA-TEMP")
	difference("physics__heating_coil_air_delta", "HWC-DAT", "MA-TEMP")
	difference("physics__cooling_coil_air_delta", "CHWC-DAT", "MA-TEMP")
	difference("physics__heating_water_delta_t", "HWC-EWT", "HWC-LWT")
	difference("physics__cooling_water_delta_t", "CHWC-EWT", "CHWC-LWT")
	difference("physics__supply_return_airflow_residual", "SA-CFM", "RMT-CFM")
	if {"SA-CFM", "OA-CFM", "RA-CFM"}.issubset(result.columns):
		result["physics__airflow_mass_balance_residual"] = (
			result["SA-CFM"] - result["OA-CFM"] - result["RA-CFM"]
		)
	if {"MA-TEMP", "OA-CFM", "RA-CFM", "RA-TEMP"}.issubset(result.columns):
		outdoor_temperature = "OAD-TEMP" if "OAD-TEMP" in result.columns else "OA-TEMP"
		if outdoor_temperature in result.columns:
			total_airflow = result["OA-CFM"] + result["RA-CFM"]
			expected_mixed = (
				result["OA-CFM"] * result[outdoor_temperature]
				+ result["RA-CFM"] * result["RA-TEMP"]
			) / total_airflow.where(total_airflow.abs() > 1e-9)
			result["physics__mixed_air_temperature_residual"] = result["MA-TEMP"] - expected_mixed

	if include_control_relationships:
		setpoint = next(
			(column for column in ("SAT_SPT", "SA_SPSPT", "SA-SPT") if column in result.columns),
			None,
		)
		if setpoint and "SA-TEMP" in result.columns:
			result["physics__supply_air_setpoint_error"] = result["SA-TEMP"] - result[setpoint]
	return result


def fit_numeric_imputer(frame: pd.DataFrame, columns: Iterable[str]) -> SimpleImputer:
	"""Fit a median imputer on training data only."""
	selected = list(columns)
	if not selected:
		raise ValueError("Cannot fit an imputer with no feature columns")
	imputer = SimpleImputer(strategy="median", keep_empty_features=True)
	training_values = frame[selected].replace([np.inf, -np.inf], np.nan)
	imputer.fit(training_values)
	return imputer


def transform_numeric_features(
	frame: pd.DataFrame, columns: Iterable[str], imputer: SimpleImputer
) -> pd.DataFrame:
	"""Apply a fitted imputer while restoring feature names and row indexes."""
	selected = list(columns)
	values = frame[selected].replace([np.inf, -np.inf], np.nan)
	transformed = imputer.transform(values)
	return pd.DataFrame(transformed, columns=selected, index=frame.index)


def add_temporal_features(
	frame: pd.DataFrame,
	columns: Iterable[str],
	*,
	boundary_columns: Iterable[str] = ("scenario_file", "date_folder"),
	rolling_window: int = 5,
) -> pd.DataFrame:
	"""Add rate-of-change and rolling means without crossing scenario boundaries."""
	if rolling_window < 2:
		raise ValueError("rolling_window must be at least 2")
	result = frame.copy()
	selected = list(columns)
	boundaries = [column for column in boundary_columns if column in result.columns]
	if "timestamp" in result.columns:
		result = result.sort_values(boundaries + ["timestamp"], kind="stable")
	grouped = result.groupby(boundaries, sort=False, dropna=False) if boundaries else None
	for column in selected:
		if column not in result.columns:
			raise KeyError(column)
		if grouped is not None:
			result[f"{column}__roc"] = grouped[column].diff().fillna(0)
			result[f"{column}__roll_mean{rolling_window}"] = grouped[column].transform(
				lambda values: values.rolling(rolling_window, min_periods=1).mean()
			)
		else:
			result[f"{column}__roc"] = result[column].diff().fillna(0)
			result[f"{column}__roll_mean{rolling_window}"] = result[column].rolling(
				rolling_window, min_periods=1
			).mean()
	return result.sort_index()
