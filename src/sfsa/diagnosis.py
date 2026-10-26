"""Confidence-aware operational triage for saved hierarchical diagnoses."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import load_yaml
from .utils import write_json


def apply_diagnosis_policy(
	run_dir: str | Path,
	policy_path: str | Path,
	*,
	output_name: str = "diagnosis_policy",
) -> Path:
	"""Turn fixed model predictions into high/medium/low-confidence triage advice."""
	run = Path(run_dir)
	policy = load_yaml(policy_path)
	medium = float(policy.get("medium_threshold", 0.50))
	high = float(policy.get("high_threshold", 0.80))
	if not 0 <= medium < high <= 1:
		raise ValueError("Require 0 <= medium_threshold < high_threshold <= 1")
	predictions = pd.read_csv(run / "predictions.csv")
	required = {"true_fault_type", "predicted_fault_type", "predicted_fault_group", "confidence"}
	missing = required - set(predictions.columns)
	if missing:
		raise ValueError(f"Diagnosis policy requires prediction columns: {sorted(missing)}")
	result = predictions.copy()
	normal = result["predicted_fault_type"].eq("normal")
	high_mask = ~normal & result["confidence"].ge(high)
	medium_mask = ~normal & ~high_mask & result["confidence"].ge(medium)
	result["diagnosis_level"] = "low"
	result.loc[normal, "diagnosis_level"] = "normal"
	result.loc[medium_mask, "diagnosis_level"] = "medium"
	result.loc[high_mask, "diagnosis_level"] = "high"
	result["diagnosis_recommendation"] = "fault type uncertain; investigate the affected AHU"
	result.loc[normal, "diagnosis_recommendation"] = "normal operation"
	result.loc[medium_mask, "diagnosis_recommendation"] = (
		"inspect " + result.loc[medium_mask, "predicted_fault_group"] + " subsystem"
	)
	result.loc[high_mask, "diagnosis_recommendation"] = (
		"likely " + result.loc[high_mask, "predicted_fault_type"].str.replace("_", " ")
	)
	output = run / output_name
	output.mkdir(parents=True, exist_ok=False)
	result.to_csv(output / "diagnosis_recommendations.csv", index=False)
	faults = result[result["true_fault_type"].ne("normal")].copy()
	summary = faults.groupby("diagnosis_level", dropna=False).agg(
		rows=("fold", "size"),
		type_accuracy=("predicted_fault_type", lambda values: (values == faults.loc[values.index, "true_fault_type"]).mean()),
		group_accuracy=("predicted_fault_group", lambda values: (values == faults.loc[values.index, "true_fault_group"]).mean()),
	).reset_index()
	summary.to_csv(output / "diagnosis_policy_summary.csv", index=False)
	write_json(output / "policy.json", policy)
	return output


def _modal_prediction(report: pd.DataFrame) -> tuple[str, str]:
	"""Return the most frequent joint group/type prediction for one report."""
	counts = (
		report.groupby(["predicted_fault_group", "predicted_fault_type"], dropna=False)
		.size()
		.rename("rows")
		.reset_index()
		.sort_values(
			["rows", "predicted_fault_group", "predicted_fault_type"],
			ascending=[False, True, True],
		)
	)
	chosen = counts.iloc[0]
	return str(chosen["predicted_fault_group"]), str(chosen["predicted_fault_type"])


def _event_reports(predictions: pd.DataFrame) -> pd.DataFrame:
	"""Collapse minute rows into one diagnosis report per held-out fault day."""
	required = {
		"fold",
		"date_folder",
		"scenario_file",
		"true_fault_group",
		"true_fault_type",
		"predicted_fault_group",
		"predicted_fault_type",
	}
	missing = required - set(predictions.columns)
	if missing:
		raise ValueError(f"Reliability policy requires prediction columns: {sorted(missing)}")
	reports: list[dict[str, object]] = []
	for keys, report in predictions.groupby(["fold", "date_folder", "scenario_file"], sort=True):
		true_groups = report["true_fault_group"].dropna().unique()
		true_types = report["true_fault_type"].dropna().unique()
		if len(true_groups) != 1 or len(true_types) != 1:
			raise ValueError("A diagnosis report must have exactly one true group and type")
		predicted_group, predicted_type = _modal_prediction(report)
		reports.append({
			"fold": int(keys[0]),
			"date_folder": keys[1],
			"scenario_file": keys[2],
			"rows": len(report),
			"true_fault_group": true_groups[0],
			"true_fault_type": true_types[0],
			"predicted_fault_group": predicted_group,
			"predicted_fault_type": predicted_type,
		})
	return pd.DataFrame(reports)


def apply_reliability_policy(
	run_dir: str | Path,
	policy_path: str | Path,
	*,
	output_name: str = "reliability_policy",
) -> Path:
	"""Gate diagnosis labels using complete held-out report evidence.

	This is a reporting policy evaluation, not a replacement for model training.
	Its evidence table uses the saved out-of-fold E16-style predictions and never
	uses minute rows as independent reports.
	"""
	run = Path(run_dir)
	policy = load_yaml(policy_path)
	minimum_reliability = float(policy.get("minimum_reliability", 0.70))
	minimum_reports = int(policy.get("minimum_reports", 5))
	if not 0 < minimum_reliability <= 1:
		raise ValueError("minimum_reliability must be in (0, 1]")
	if minimum_reports < 1:
		raise ValueError("minimum_reports must be at least 1")
	reports = _event_reports(pd.read_csv(run / "predictions.csv"))

	# Diagnosis is evaluated only after an anomaly has been detected. Normal
	# reference days are retained in the output but cannot support a diagnosis.
	fault_reports = reports[reports["true_fault_type"].ne("normal")].copy()
	if fault_reports.empty:
		raise ValueError("Reliability policy requires at least one held-out fault report")
	fault_reports["group_correct"] = fault_reports["predicted_fault_group"].eq(
		fault_reports["true_fault_group"]
	)
	fault_reports["type_correct"] = fault_reports["predicted_fault_type"].eq(
		fault_reports["true_fault_type"]
	)

	group_evidence = (
		fault_reports.groupby("predicted_fault_group", dropna=False)
		.agg(
			reports=("fold", "size"),
			correct_reports=("group_correct", "sum"),
			observed_reliability=("group_correct", "mean"),
		)
		.reset_index()
	)
	type_evidence = (
		fault_reports.groupby(["predicted_fault_group", "predicted_fault_type"], dropna=False)
		.agg(
			reports=("fold", "size"),
			correct_reports=("type_correct", "sum"),
			observed_reliability=("type_correct", "mean"),
		)
		.reset_index()
	)
	group_evidence["eligible"] = (
		group_evidence["reports"].ge(minimum_reports)
		& group_evidence["observed_reliability"].ge(minimum_reliability)
	)
	type_evidence["eligible"] = (
		type_evidence["reports"].ge(minimum_reports)
		& type_evidence["observed_reliability"].ge(minimum_reliability)
	)

	result = reports.merge(group_evidence, on="predicted_fault_group", how="left")
	result = result.rename(columns={
		"reports": "group_evidence_reports",
		"correct_reports": "group_correct_reports",
		"observed_reliability": "group_observed_reliability",
		"eligible": "group_reliable",
	})
	result = result.merge(
		type_evidence,
		on=["predicted_fault_group", "predicted_fault_type"],
		how="left",
	)
	result = result.rename(columns={
		"reports": "type_evidence_reports",
		"correct_reports": "type_correct_reports",
		"observed_reliability": "type_observed_reliability",
		"eligible": "type_reliable",
	})
	normal = result["predicted_fault_type"].eq("normal")
	result["status"] = "Anomaly detected"
	result.loc[normal, "status"] = "Normal"
	result["fault_group"] = "Uncertain"
	result.loc[~normal & result["group_reliable"].fillna(False), "fault_group"] = result.loc[
		~normal & result["group_reliable"].fillna(False), "predicted_fault_group"
	]
	result["fault_type"] = "Uncertain"
	type_mask = ~normal & result["group_reliable"].fillna(False) & result["type_reliable"].fillna(False)
	result.loc[type_mask, "fault_type"] = result.loc[type_mask, "predicted_fault_type"]
	result.loc[normal, ["fault_group", "fault_type"]] = "Not applicable"

	output = run / output_name
	output.mkdir(parents=True, exist_ok=False)
	result.to_csv(output / "diagnosis_reports.csv", index=False)
	group_evidence.to_csv(output / "fault_group_evidence.csv", index=False)
	type_evidence.to_csv(output / "fault_type_evidence.csv", index=False)
	anomaly_reports = result[result["status"].eq("Anomaly detected")]
	summary = {
		"report_unit": "one held-out date/scenario fault session",
		"fault_reports": int(len(fault_reports)),
		"anomaly_reports": int(len(anomaly_reports)),
		"fault_group_shown": int(anomaly_reports["fault_group"].ne("Uncertain").sum()),
		"fault_group_uncertain": int(anomaly_reports["fault_group"].eq("Uncertain").sum()),
		"fault_type_shown": int(anomaly_reports["fault_type"].ne("Uncertain").sum()),
		"fault_type_uncertain": int(anomaly_reports["fault_type"].eq("Uncertain").sum()),
		"minimum_reliability": minimum_reliability,
		"minimum_reports": minimum_reports,
		"limitation": (
			"Reliability is descriptive cross-validated evidence from this source dataset; "
			"it is not a guaranteed probability for a new building."
		),
	}
	write_json(output / "summary.json", summary)
	write_json(output / "policy.json", policy)
	return output
