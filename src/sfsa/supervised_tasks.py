"""Scenario-held-out supervised diagnosis and conditional severity studies."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
	accuracy_score,
	balanced_accuracy_score,
	confusion_matrix,
	f1_score,
	mean_absolute_error,
	mean_squared_error,
	precision_score,
	recall_score,
)
from sklearn.preprocessing import LabelEncoder, StandardScaler

from .config import resolve_run_config
from .data.manifest import build_real_manifest
from .evaluation.splits import leave_one_group_out, paired_holdout_splits
from .features import (
	add_physics_features,
	classify_columns,
	fit_numeric_imputer,
	select_feature_columns,
)
from .models import gradient_boosting, gradient_boosting_regressor
from .training import (
	_load_tables,
	_make_run_dir,
	_prepare_model_frame,
	_project_root_from_config,
	filter_occupied_hours,
)
from .utils import capture_environment, set_seed, write_json

# Every parsed RBC fault type has one operationally meaningful parent group.
# E11 learns the parent first, then distinguishes types within that group.
FAULT_GROUPS = {
	"air_filter_blockage": "airflow_distribution",
	"cooling_coil_valve_stuck": "cooling_coil",
	"cooling_coil_valve_reverse_action": "cooling_coil",
	"exhaust_air_damper_stuck": "airside_damper",
	"exhaust_air_damper_leak": "airside_damper",
	"heating_coil_fouling": "heating_coil",
	"heating_coil_reduced_capacity": "heating_coil",
	"heating_coil_valve_leak": "heating_coil",
	"outdoor_air_damper_stuck": "airside_damper",
	"outdoor_air_damper_leak": "airside_damper",
	"return_fan_failure": "return_fan",
	"return_fan_fixed_speed": "return_fan",
	"supply_duct_leak": "airflow_distribution",
	"unstable_supply_fan_control": "supply_fan_control",
	"unstable_cooling_coil_valve_control": "cooling_coil",
	"unstable_mixed_air_damper": "airside_damper",
	"unstable_mixed_air_damper_cooling_coil_control": "airside_control",
	"unstable_heating_cooling_sequence": "thermal_control",
	"outdoor_temperature_sensor_bias_positive": "sensor_fault",
	"outdoor_temperature_sensor_bias_negative": "sensor_fault",
}


def _context(
	building_config: str | Path,
	experiment_config: str | Path,
	*,
	override_values: list[str],
	allow_audit_failures: bool,
) -> tuple[dict[str, Any], Path, Path, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
	bundle = resolve_run_config(building_config, experiment_config, override_values=override_values)
	resolved = bundle["resolved"]
	project_root = _project_root_from_config(building_config)
	data_root = Path(resolved["data_path"])
	if not data_root.is_absolute():
		data_root = project_root / data_root
	manifest = build_real_manifest(data_root)
	if not manifest["validation"]["accepted"] and not allow_audit_failures:
		raise ValueError(f"Dataset audit failed: {'; '.join(manifest['validation']['blockers'])}")
	baseline, faults = _load_tables(data_root, include_weather=bool(resolved["include_weather"]))
	occupied_hours = resolved.get("occupied_hours", {})
	baseline = filter_occupied_hours(baseline, occupied_hours)
	faults = filter_occupied_hours(faults, occupied_hours)
	physics = resolved.get("physics_features", {})
	if physics.get("enabled", False):
		baseline = add_physics_features(
			baseline,
			include_control_relationships=bool(physics.get("include_control_relationships", False)),
		)
		faults = add_physics_features(
			faults,
			include_control_relationships=bool(physics.get("include_control_relationships", False)),
		)
	if baseline.empty or faults.empty:
		raise ValueError("Occupied-hours filter removed all required rows")
	return bundle, project_root, data_root, baseline, faults, manifest


def _feature_columns(frame: pd.DataFrame, resolved: dict[str, Any]) -> list[str]:
	groups = classify_columns(frame.columns)
	selected = select_feature_columns(
		groups,
		resolved["feature_policy"],
		include_weather=bool(resolved["include_weather"]),
		include_vav=bool(resolved["include_vav"]),
		include_physics=bool(resolved.get("physics_features", {}).get("enabled", False)),
	)
	columns = [column for column in selected if pd.api.types.is_numeric_dtype(frame[column])]
	if not columns:
		raise ValueError("No numeric model features remain after feature policy")
	return columns


def _limit_folds(splits: list[Any], resolved: dict[str, Any]) -> list[Any]:
	max_folds = resolved.get("max_folds")
	if max_folds is None:
		return splits
	max_folds = int(max_folds)
	if max_folds < 1:
		raise ValueError("max_folds must be at least 1 when specified")
	return splits[:max_folds]


def _scenario_balanced_weights(frame: pd.DataFrame, labels: np.ndarray) -> np.ndarray:
	"""Give each label equal weight, then each complete source scenario equal weight."""
	columns = ["season", "date_folder", "scenario_file"]
	missing = set(columns) - set(frame.columns)
	if missing:
		raise ValueError(f"Scenario-balanced training requires: {sorted(missing)}")
	weights = frame[columns].copy()
	weights["label"] = labels
	scenario_rows = weights.groupby(["label", *columns], dropna=False).size().rename("rows")
	scenario_rows = scenario_rows.reset_index()
	scenario_rows["scenarios_for_label"] = scenario_rows.groupby("label")["rows"].transform("size")
	scenario_rows["weight"] = 1 / (scenario_rows["scenarios_for_label"] * scenario_rows["rows"])
	weights = weights.merge(scenario_rows[["label", *columns, "weight"]], on=["label", *columns], how="left")
	result = weights["weight"].to_numpy(dtype=float)
	if not np.isfinite(result).all() or (result <= 0).any():
		raise ValueError("Could not calculate positive scenario-balanced sample weights")
	return result / result.mean()


def _prepare(
	train: pd.DataFrame,
	test: pd.DataFrame,
	base_columns: list[str],
	resolved: dict[str, Any],
	*,
	imputer_source: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, list[str], dict[str, Any]]:
	imputer = fit_numeric_imputer(imputer_source, base_columns)
	train_prepared, columns = _prepare_model_frame(
		train, base_columns, imputer, temporal=resolved["temporal"]
	)
	test_prepared, test_columns = _prepare_model_frame(
		test, base_columns, imputer, temporal=resolved["temporal"]
	)
	if columns != test_columns:
		raise ValueError("Feature columns differ between train and test partitions")
	scaler = StandardScaler().fit(train_prepared[columns])
	return (
		scaler.transform(train_prepared[columns]),
		scaler.transform(test_prepared[columns]),
		columns,
		{"imputer": imputer, "scaler": scaler, "feature_columns": columns},
	)


def _write_common(
	*,
	run_dir: Path,
	bundle: dict[str, Any],
	manifest: dict[str, Any],
	project_root: Path,
	allow_audit_failures: bool,
	features: list[str],
	metric_rows: list[dict[str, Any]],
	predictions: list[pd.DataFrame],
	membership: list[pd.DataFrame],
	preprocessing: dict[str, Any],
	thresholds: dict[str, Any],
) -> None:
	metrics_by_fold = pd.DataFrame(metric_rows)
	metrics_by_fold.to_csv(run_dir / "metrics_by_fold.csv", index=False)
	metric_columns = [
		column for column in metrics_by_fold.columns
		if column not in {"fold", "model", "held_out_groups", "fit_seconds", "score_seconds"}
		and pd.api.types.is_numeric_dtype(metrics_by_fold[column])
	]
	summary_rows: list[dict[str, Any]] = []
	for model_name, group in metrics_by_fold.groupby("model", sort=True):
		for metric in metric_columns:
			values = group[metric].dropna().to_numpy(dtype=float)
			if len(values):
				summary_rows.append({
					"model": model_name,
					"metric": metric,
					"folds": len(values),
					"mean": float(values.mean()),
					"median": float(np.median(values)),
				})
	summary = pd.DataFrame(summary_rows)
	summary.to_csv(run_dir / "metrics_summary.csv", index=False)
	wide = summary.pivot(index="model", columns="metric", values="mean").reset_index()
	wide.to_csv(run_dir / "metrics.csv", index=False)
	pd.concat(predictions, ignore_index=True).to_csv(run_dir / "predictions.csv", index=False)
	pd.concat(membership, ignore_index=True).to_csv(run_dir / "split_membership.csv", index=False)
	write_json(run_dir / "thresholds.json", thresholds)
	write_json(run_dir / "data_manifest.json", manifest)
	write_json(run_dir / "environment.json", capture_environment(project_root))
	write_json(
		run_dir / "config.resolved.json",
		{**bundle, "runtime": {"allow_audit_failures": allow_audit_failures}},
	)
	write_json(run_dir / "features.json", {"model_columns": features})
	write_json(
		run_dir / "config.json",
		{
			"building": bundle["building"],
			"experiment": bundle["experiment"],
			"resolved": bundle["resolved"],
		},
	)
	joblib.dump(preprocessing, run_dir / "preprocessing.joblib")


def run_fault_type_classification(
	building_config: str | Path,
	experiment_config: str | Path,
	*,
	results_root: str | Path = "results/runs",
	override_values: list[str] | None = None,
	allow_audit_failures: bool = False,
) -> Path:
	"""Classify normal operation and repeatedly observed fault families."""
	bundle, project_root, _, baseline, faults, manifest = _context(
		building_config,
		experiment_config,
		override_values=override_values or [],
		allow_audit_failures=allow_audit_failures,
	)
	resolved = bundle["resolved"]
	if resolved.get("split_policy") != "leave_date_out":
		raise ValueError("Fault-type classification requires split_policy=leave_date_out")
	hierarchical = resolved.get("task") == "hierarchical_fault_type_classification"
	scenario_balancing = bool(resolved.get("scenario_balancing", False))
	minimum = int(resolved.get("minimum_scenarios_per_type", 2))
	scenarios = faults[["fault_type", "date_folder", "scenario_file"]].drop_duplicates()
	counts = scenarios.groupby("fault_type").size()
	supported = sorted(counts[counts >= minimum].index)
	if not supported:
		raise ValueError("No fault types meet minimum_scenarios_per_type")
	faults = faults[faults["fault_type"].isin(supported)].copy()
	if hierarchical:
		unmapped = sorted(set(supported) - set(FAULT_GROUPS))
		if unmapped:
			raise ValueError(f"No parent fault group defined for: {unmapped}")
		faults["fault_group"] = faults["fault_type"].map(FAULT_GROUPS)
	dates = faults["date_folder"].unique()
	baseline = baseline[baseline["date_folder"].isin(dates)].copy()
	if hierarchical:
		baseline["fault_group"] = "normal"
	frame = pd.concat([baseline, faults], ignore_index=True)
	base_columns = _feature_columns(frame, resolved)
	splits = _limit_folds(paired_holdout_splits(frame, "leave_date_out"), resolved)
	set_seed(int(resolved.get("seed", 42)))
	run_dir = _make_run_dir(Path(results_root), bundle["building"]["name"], bundle["experiment"]["name"])
	metric_rows: list[dict[str, Any]] = []
	prediction_tables: list[pd.DataFrame] = []
	membership_tables: list[pd.DataFrame] = []
	preprocessing: dict[str, Any] = {}
	confusion_rows: list[dict[str, Any]] = []
	group_confusion_rows: list[dict[str, Any]] = []
	model_name = "supervised_hierarchical_fault_type" if hierarchical else "supervised_fault_type"
	for fold, split in enumerate(splits, start=1):
		train = frame.loc[split.train_index].copy()
		test = frame.loc[split.test_index].copy()
		train_y = train["fault_type"].fillna("normal").to_numpy(dtype=str)
		test_y = test["fault_type"].fillna("normal").to_numpy(dtype=str)
		unseen = set(test_y) - set(train_y)
		if unseen:
			raise ValueError(f"Fold {fold} has fault types absent from training: {sorted(unseen)}")
		train_normal = train[~train["is_fault"].astype(bool)]
		train_x, test_x, columns, prep = _prepare(
			train, test, base_columns, resolved, imputer_source=train_normal
		)
		started = perf_counter()
		if hierarchical:
			train_groups = train["fault_group"].to_numpy(dtype=str)
			test_groups = test["fault_group"].to_numpy(dtype=str)
			group_encoder = LabelEncoder().fit(train_groups)
			group_model = gradient_boosting(seed=int(resolved.get("seed", 42))).fit(
				train_x,
				group_encoder.transform(train_groups),
				sample_weight=_scenario_balanced_weights(train, train_groups) if scenario_balancing else None,
			)
			fine_models: dict[str, dict[str, Any]] = {}
			for group in sorted(set(train_groups) - {"normal"}):
				train_mask = train_groups == group
				types = np.unique(train_y[train_mask])
				if len(types) == 1:
					fine_models[group] = {"single_type": types[0]}
					continue
				fine_encoder = LabelEncoder().fit(train_y[train_mask])
				fine_model = gradient_boosting(seed=int(resolved.get("seed", 42))).fit(
					train_x[train_mask],
					fine_encoder.transform(train_y[train_mask]),
					sample_weight=(
						_scenario_balanced_weights(train.loc[train_mask], train_y[train_mask])
						if scenario_balancing else None
					),
				)
				fine_models[group] = {"model": fine_model, "label_encoder": fine_encoder}
			model_bundle = {
				"group_model": group_model,
				"group_label_encoder": group_encoder,
				"fine_models": fine_models,
			}
		else:
			encoder = LabelEncoder().fit(train_y)
			model = gradient_boosting(seed=int(resolved.get("seed", 42))).fit(
				train_x,
				encoder.transform(train_y),
				sample_weight=_scenario_balanced_weights(train, train_y) if scenario_balancing else None,
			)
			model_bundle = {"model": model, "label_encoder": encoder}
		fit_seconds = perf_counter() - started
		started = perf_counter()
		if hierarchical:
			group_probabilities = group_model.predict_proba(test_x)
			predicted_groups = group_encoder.inverse_transform(group_probabilities.argmax(axis=1))
			# Fine labels are longer than several parent-group labels; object dtype avoids truncation.
			predicted = predicted_groups.astype(object)
			confidence = group_probabilities.max(axis=1)
			for group, fine_bundle in fine_models.items():
				test_mask = predicted_groups == group
				if not test_mask.any():
					continue
				if "single_type" in fine_bundle:
					predicted[test_mask] = fine_bundle["single_type"]
					continue
				fine_probabilities = fine_bundle["model"].predict_proba(test_x[test_mask])
				predicted[test_mask] = fine_bundle["label_encoder"].inverse_transform(
					fine_probabilities.argmax(axis=1)
				)
				confidence[test_mask] *= fine_probabilities.max(axis=1)
		else:
			probabilities = model.predict_proba(test_x)
			predicted = encoder.inverse_transform(probabilities.argmax(axis=1))
			confidence = probabilities.max(axis=1)
		score_seconds = perf_counter() - started
		metrics = {
			"fold": fold,
			"model": model_name,
			"held_out_groups": "|".join(split.held_out_groups),
			"fit_seconds": fit_seconds,
			"score_seconds": score_seconds,
			"accuracy": float(accuracy_score(test_y, predicted)),
			"balanced_accuracy": float(balanced_accuracy_score(test_y, predicted)),
			"macro_f1": float(f1_score(test_y, predicted, average="macro", zero_division=0)),
			"macro_precision": float(precision_score(test_y, predicted, average="macro", zero_division=0)),
			"macro_recall": float(recall_score(test_y, predicted, average="macro", zero_division=0)),
		}
		if hierarchical:
			fault_rows = test_groups != "normal"
			correct_group = (predicted_groups == test_groups) & fault_rows
			metrics.update({
				"coarse_accuracy": float(accuracy_score(test_groups, predicted_groups)),
				"coarse_macro_f1": float(f1_score(test_groups, predicted_groups, average="macro", zero_division=0)),
				"fault_type_accuracy": float(accuracy_score(test_y[fault_rows], predicted[fault_rows])),
				"fine_accuracy_given_correct_group": float(
					accuracy_score(test_y[correct_group], predicted[correct_group])
				) if correct_group.any() else np.nan,
			})
		metric_rows.append(metrics)
		prediction_data: dict[str, Any] = {
			"fold": fold,
			"model": model_name,
			"timestamp": test["timestamp"].to_numpy(),
			"date_folder": test["date_folder"].to_numpy(),
			"scenario_file": test["scenario_file"].to_numpy(),
			"true_fault_type": test_y,
			"predicted_fault_type": predicted,
			"confidence": confidence,
			"y_true": test_y,
			"prediction": predicted,
			"score": confidence,
			"threshold": np.nan,
		}
		if hierarchical:
			prediction_data.update({
				"true_fault_group": test_groups,
				"predicted_fault_group": predicted_groups,
			})
		prediction_tables.append(pd.DataFrame(prediction_data))
		labels = sorted(set(test_y) | set(predicted))
		matrix = confusion_matrix(test_y, predicted, labels=labels)
		for true_index, true_label in enumerate(labels):
			for predicted_index, predicted_label in enumerate(labels):
				confusion_rows.append({
					"fold": fold,
					"true_fault_type": true_label,
					"predicted_fault_type": predicted_label,
					"rows": int(matrix[true_index, predicted_index]),
				})
		if hierarchical:
			group_labels = sorted(set(test_groups) | set(predicted_groups))
			group_matrix = confusion_matrix(test_groups, predicted_groups, labels=group_labels)
			for true_index, true_label in enumerate(group_labels):
				for predicted_index, predicted_label in enumerate(group_labels):
					group_confusion_rows.append({
						"fold": fold,
						"true_fault_group": true_label,
						"predicted_fault_group": predicted_label,
						"rows": int(group_matrix[true_index, predicted_index]),
					})
		membership = frame.loc[split.train_index.union(split.test_index), [
			"season", "date_folder", "scenario_file", "fault_type", "fault_intensity", "is_fault",
		]].copy()
		membership["partition"] = "train"
		membership.loc[membership.index.isin(split.test_index), "partition"] = "test"
		membership.insert(0, "fold", fold)
		membership_tables.append(membership)
		fold_dir = run_dir / "models" / f"fold_{fold:03d}"
		fold_dir.mkdir(parents=True, exist_ok=True)
		joblib.dump(model_bundle, fold_dir / "supervised_fault_type.joblib")
		joblib.dump(prep, fold_dir / "preprocessing.joblib")
		preprocessing[f"fold_{fold:03d}"] = prep
	_write_common(
		run_dir=run_dir,
		bundle=bundle,
		manifest=manifest,
		project_root=project_root,
		allow_audit_failures=allow_audit_failures,
		features=columns,
		metric_rows=metric_rows,
		predictions=prediction_tables,
		membership=membership_tables,
		preprocessing=preprocessing,
		thresholds={"task": resolved["task"], "thresholds": []},
	)
	pd.DataFrame(confusion_rows).to_csv(run_dir / "confusion_matrix.csv", index=False)
	if hierarchical:
		pd.DataFrame(group_confusion_rows).to_csv(run_dir / "coarse_confusion_matrix.csv", index=False)
	write_json(
		run_dir / "label_scope.json",
		{
			"task": resolved["task"],
			"included_fault_types": supported,
			"excluded_fault_types": sorted(set(counts.index) - set(supported)),
			"minimum_scenarios_per_type": minimum,
			"scenario_balancing": scenario_balancing,
			"split_policy": "leave_date_out",
			"fault_groups": {fault_type: FAULT_GROUPS[fault_type] for fault_type in supported}
			if hierarchical else None,
		},
	)
	return run_dir


def run_fault_intensity_regression(
	building_config: str | Path,
	experiment_config: str | Path,
	*,
	results_root: str | Path = "results/runs",
	override_values: list[str] | None = None,
	allow_audit_failures: bool = False,
) -> Path:
	"""Estimate numeric severity within one known fault family only."""
	bundle, project_root, _, _, faults, manifest = _context(
		building_config,
		experiment_config,
		override_values=override_values or [],
		allow_audit_failures=allow_audit_failures,
	)
	resolved = bundle["resolved"]
	if resolved.get("split_policy") != "leave_fault_intensity_out":
		raise ValueError("Intensity regression requires split_policy=leave_fault_intensity_out")
	fault_type = str(resolved.get("intensity_fault_type", ""))
	frame = faults[faults["fault_type"] == fault_type].copy()
	if frame.empty:
		raise ValueError(f"No rows found for intensity_fault_type={fault_type!r}")
	frame["target_intensity"] = pd.to_numeric(frame["fault_intensity"], errors="coerce")
	frame = frame.dropna(subset=["target_intensity"]).copy()
	if frame["target_intensity"].nunique() < 3:
		raise ValueError("Intensity regression requires at least three numeric intensity levels")
	base_columns = _feature_columns(frame, resolved)
	splits = _limit_folds(leave_one_group_out(frame, "target_intensity"), resolved)
	set_seed(int(resolved.get("seed", 42)))
	run_dir = _make_run_dir(Path(results_root), bundle["building"]["name"], bundle["experiment"]["name"])
	metric_rows: list[dict[str, Any]] = []
	prediction_tables: list[pd.DataFrame] = []
	membership_tables: list[pd.DataFrame] = []
	preprocessing: dict[str, Any] = {}
	model_name = f"supervised_intensity_{fault_type}"
	for fold, split in enumerate(splits, start=1):
		train = frame.loc[split.train_index].copy()
		test = frame.loc[split.test_index].copy()
		train_x, test_x, columns, prep = _prepare(
			train, test, base_columns, resolved, imputer_source=train
		)
		started = perf_counter()
		model = gradient_boosting_regressor(seed=int(resolved.get("seed", 42))).fit(
			train_x, train["target_intensity"].to_numpy(dtype=float)
		)
		fit_seconds = perf_counter() - started
		started = perf_counter()
		predicted = model.predict(test_x)
		score_seconds = perf_counter() - started
		actual = test["target_intensity"].to_numpy(dtype=float)
		metric_rows.append({
			"fold": fold,
			"model": model_name,
			"held_out_groups": "|".join(split.held_out_groups),
			"fit_seconds": fit_seconds,
			"score_seconds": score_seconds,
			"mae": float(mean_absolute_error(actual, predicted)),
			"rmse": float(mean_squared_error(actual, predicted) ** 0.5),
			"mean_error": float(np.mean(predicted - actual)),
		})
		prediction_tables.append(pd.DataFrame({
			"fold": fold,
			"model": model_name,
			"timestamp": test["timestamp"].to_numpy(),
			"date_folder": test["date_folder"].to_numpy(),
			"scenario_file": test["scenario_file"].to_numpy(),
			"predicted_fault_type": fault_type,
			"true_intensity": actual,
			"predicted_intensity": predicted,
			"routing": "conditional_on_known_fault_type",
			"y_true": actual,
			"prediction": predicted,
			"score": predicted,
			"threshold": np.nan,
		}))
		membership = frame.loc[split.train_index.union(split.test_index), [
			"season", "date_folder", "scenario_file", "fault_type", "fault_intensity",
		]].copy()
		membership["partition"] = "train"
		membership.loc[membership.index.isin(split.test_index), "partition"] = "test"
		membership.insert(0, "fold", fold)
		membership_tables.append(membership)
		fold_dir = run_dir / "models" / f"fold_{fold:03d}"
		fold_dir.mkdir(parents=True, exist_ok=True)
		joblib.dump(model, fold_dir / "supervised_intensity.joblib")
		joblib.dump(prep, fold_dir / "preprocessing.joblib")
		preprocessing[f"fold_{fold:03d}"] = prep
	_write_common(
		run_dir=run_dir,
		bundle=bundle,
		manifest=manifest,
		project_root=project_root,
		allow_audit_failures=allow_audit_failures,
		features=columns,
		metric_rows=metric_rows,
		predictions=prediction_tables,
		membership=membership_tables,
		preprocessing=preprocessing,
		thresholds={"task": "fault_intensity_regression", "thresholds": []},
	)
	all_predictions = pd.concat(prediction_tables, ignore_index=True)
	write_json(
		run_dir / "intensity_scope.json",
		{
			"task": "fault_intensity_regression",
			"fault_type": fault_type,
			"intensity_levels": sorted(frame["target_intensity"].unique().tolist()),
			"routing": "conditional_on_known_fault_type",
			"global_mae": float(mean_absolute_error(all_predictions["true_intensity"], all_predictions["predicted_intensity"])),
			"global_rmse": float(mean_squared_error(all_predictions["true_intensity"], all_predictions["predicted_intensity"]) ** 0.5),
		},
	)
	return run_dir
