"""Build the compact, Git-friendly evidence pack from accepted final runs."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

from sfsa.qa import audit_run_artifacts
from sfsa.utils import write_json

ROOT = Path(__file__).resolve().parents[1]
FINAL_RUNS = ROOT / "results" / "final_runs"
OUTPUT = ROOT / "results" / "final_evidence"

RUNS = [
    ("E01", "20261025T083058Z_rbc_ashrae1312_real_E01_baseline", "Statistical and Isolation Forest baseline"),
    ("E02", "20261025T090840Z_rbc_ashrae1312_real_E02_classical", "Classical anomaly-detection comparison"),
    ("E03", "20261025T093034Z_rbc_ashrae1312_real_E03_supervised", "Supervised binary benchmark"),
    ("E04a", "20261025T094812Z_rbc_ashrae1312_real_E04a_control_inclusive", "Control-inclusive comparison"),
    ("E04b", "20261025T095200Z_rbc_ashrae1312_real_E04b_control_weather", "Control and weather comparison"),
    ("E05", "20261025T110235Z_rbc_ashrae1312_real_E05_temporal", "Temporal-feature comparison"),
    ("E06", "20261025T113920Z_rbc_ashrae1312_real_E06_generalisation", "Season-generalisation baseline"),
    ("E09", "20261025T121801Z_rbc_ashrae1312_real_E09_fault_type_classification", "Flat fault-type classification"),
    ("E10", "20261025T130022Z_rbc_ashrae1312_real_E10_cooling_coil_intensity", "Conditional cooling-coil intensity regression"),
    ("E11", "20261026T005920Z_rbc_ashrae1312_real_E11_hierarchical_fault_type_classification", "Corrected hierarchical diagnosis"),
    ("E12", "20261026T012151Z_rbc_ashrae1312_real_E12_hierarchical_physics", "Hierarchical diagnosis with passive physics"),
    ("E13", "20261026T015250Z_rbc_ashrae1312_real_E13_hierarchical_safe_context", "Safe-context hierarchical diagnosis"),
    ("E14", "20261026T021210Z_rbc_ashrae1312_real_E14_hierarchical_safe_context_balanced", "Scenario-balanced diagnosis"),
    ("E16", "20261026T060104Z_rbc_ashrae1312_real_E16_hierarchical_instrumented_bms", "Instrumented-BMS diagnosis"),
    ("E17", "20261026T062832Z_rbc_ashrae1312_real_E17_hierarchical_full_bms", "Full-BMS/VAV diagnosis comparison"),
    ("E19", "20261026T094407Z_rbc_ashrae1312_real_E19_supervised_season_generalisation", "Supervised season generalisation"),
]

REQUIRED_FILES = [
    "config.json",
    "config.resolved.json",
    "data_manifest.json",
    "environment.json",
    "features.json",
    "metrics.csv",
    "metrics_by_fold.csv",
    "metrics_summary.csv",
    "thresholds.json",
]

OPTIONAL_FILES = [
    "alert_explanations.csv",
    "coarse_confusion_matrix.csv",
    "confusion_matrix.csv",
    "intensity_scope.json",
    "label_scope.json",
    "metrics_by_fault_group.csv",
    "model_comparison.csv",
    "split_diagnostics.json",
    "supervised_permutation_importance.csv",
    "validation_model_selection.csv",
]


def copy_file(source: Path, destination: Path, *, required: bool = False) -> None:
    if not source.exists():
        if required:
            raise FileNotFoundError(f"Required evidence artefact is missing: {source}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build_patterns(output: Path) -> None:
    source = FINAL_RUNS / "20261025T083004Z_rbc_ashrae1312_real_P01_normal_patterns"
    destination = output / "P01"
    required = [
        "config.resolved.json",
        "data_manifest.json",
        "features.json",
        "normal_mode_catalogue.csv",
        "normal_mode_feature_profiles.csv",
        "normal_mode_quality.json",
    ]
    for filename in required:
        copy_file(source / filename, destination / filename, required=True)
    for filename in ("normal_modes_by_hour.png", "normal_modes_pca.png"):
        copy_file(source / "figures" / filename, destination / "figures" / filename, required=True)


def build_benchmark_evidence(output: Path) -> list[dict[str, str]]:
    index: list[dict[str, str]] = []
    for study, run_name, purpose in RUNS:
        source = FINAL_RUNS / run_name
        destination = output / study
        for filename in REQUIRED_FILES:
            copy_file(source / filename, destination / filename, required=True)
        for filename in OPTIONAL_FILES:
            copy_file(source / filename, destination / filename)
        qa = audit_run_artifacts(source)
        write_json(destination / "qa_report.json", qa)
        if not qa["accepted"]:
            raise ValueError(f"Refusing to package a failed run: {run_name}")
        index.append({"study": study, "source_run": run_name, "purpose": purpose, "qa_accepted": "true"})
    return index


def build_operational_evidence(output: Path) -> None:
    e14 = FINAL_RUNS / "20261026T021210Z_rbc_ashrae1312_real_E14_hierarchical_safe_context_balanced"
    for filename in ("diagnosis_policy_summary.csv", "policy.json"):
        copy_file(e14 / "diagnosis_policy" / filename, output / "E14" / "diagnosis_policy" / filename, required=True)

    e16 = FINAL_RUNS / "20261026T060104Z_rbc_ashrae1312_real_E16_hierarchical_instrumented_bms"
    for filename in (
        "diagnosis_reports.csv",
        "fault_group_evidence.csv",
        "fault_type_evidence.csv",
        "policy.json",
        "summary.json",
    ):
        copy_file(e16 / "E18_reliability_gated" / filename, output / "E16" / "E18_reliability_gated" / filename, required=True)

    cards = FINAL_RUNS / "20261025T093034Z_rbc_ashrae1312_real_E03_supervised" / "audit_grouped_events" / "audit_priority_cards"
    for filename in ("priority_cards.csv", "priority_summary.json"):
        copy_file(cards / filename, output / "operational_priority_prototype" / filename, required=True)
    copy_file(ROOT / "configs" / "priority_policy.yaml", output / "operational_priority_prototype" / "priority_policy.yaml", required=True)


def write_readme(output: Path, index: list[dict[str, str]]) -> None:
    rows = "\n".join(
        f"| {item['study']} | `{item['source_run']}` | {item['purpose']} |"
        for item in index
    )
    (output / "README.md").write_text(
        "# Final evidence pack\n\n"
        "This is the compact, Git-friendly evidence package for report review. "
        "It is generated by `scripts/build_final_evidence.py` from the complete "
        "local `results/final_runs/` archive.\n\n"
        "It includes frozen configurations, manifests, selected features, fold-level "
        "and summary metrics, model-comparison tables, QA reports, diagnosis evidence, "
        "and report-ready P01 figures. It excludes raw predictions, fold-membership "
        "tables, and model binaries because those make the complete archive about 4.1 GB.\n\n"
        "## Authoritative runs\n\n"
        "| Study | Full source run | Purpose |\n"
        "| --- | --- | --- |\n"
        f"{rows}\n\n"
        "P01 is the normal-operation pattern-discovery artefact. E18 is retained under "
        "E16 because it is a reporting policy applied to E16 predictions, not a retrained model. "
        "The priority-card artefact is an operational prototype, not headline duration-validation evidence.\n\n"
        "## Important interpretation limits\n\n"
        "- Results are controlled HVAC-fault experiments from one facility, not multi-building deployment validation.\n"
        "- Fault sessions are labelled for the full recording day; zero delay is not a verified physical onset time.\n"
        "- E16/E17 are instrumented-BMS diagnosis sensitivity studies, not symptom-only diagnosis.\n"
        "- E18 reliability values are descriptive held-out evidence from this dataset, not probabilities guaranteed for a new building.\n"
        "- The complete generated archive should be shared separately with assessors who need predictions, models, or full split membership.\n",
        encoding="utf-8",
    )


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"Evidence output already exists: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    build_patterns(OUTPUT)
    index = build_benchmark_evidence(OUTPUT)
    build_operational_evidence(OUTPUT)
    with (OUTPUT / "run_index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["study", "source_run", "purpose", "qa_accepted"])
        writer.writeheader()
        writer.writerows(index)
    write_readme(OUTPUT, index)
    print(f"Built final evidence pack: {OUTPUT}")


if __name__ == "__main__":
    main()
