"""Build the compact evidence package from the accepted renamed final runs."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL_RUNS = ROOT / "results" / "final_runs"
OUTPUT = ROOT / "results" / "final_evidence"

RUNS = [
    ("D01", "D01_baseline", "Statistical and Isolation Forest baseline"),
    ("D02", "D02_classical", "Classical unsupervised comparison"),
    ("D03", "D03_supervised", "Supervised binary detection"),
    ("D04a", "D04a_control_inclusive", "Control-inclusive feature sensitivity"),
    ("D04b", "D04b_control_weather", "Control and weather sensitivity"),
    ("D05", "D05_temporal", "Temporal-feature sensitivity"),
    ("D06", "D06_classical_season_generalisation", "Classical seasonal robustness"),
    ("D07", "D07_xgboost_detection", "Primary XGBoost binary detection"),
    ("D08", "D08_xgboost_season_generalisation", "XGBoost seasonal robustness"),
    ("G01", "G01_fault_type_classification", "Flat fault-type classification"),
    ("G02a", "G02a_hierarchical_baseline", "Hierarchical diagnosis baseline"),
    ("G02b", "G02b_hierarchical_physics", "Hierarchical diagnosis with physics"),
    ("G02c", "G02c_hierarchical_safe_context", "Hierarchical diagnosis with safe context"),
    ("G02d", "G02d_hierarchical_safe_context_balanced", "Scenario-balanced diagnosis"),
    ("G03a", "G03a_xgboost_instrumented_bms", "Primary XGBoost instrumented-BMS diagnosis"),
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
    "label_scope.json",
    "metrics_by_fault_group.csv",
    "model_comparison.csv",
    "split_diagnostics.json",
    "supervised_permutation_importance.csv",
    "validation_model_selection.csv",
]


def find_run(experiment_name: str) -> Path:
    """Return the one final run whose directory ends with this config name."""
    matches = sorted(FINAL_RUNS.glob(f"*_{experiment_name}"))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one final run for {experiment_name}; found {len(matches)}: {matches}"
        )
    return matches[0]


def copy_file(source: Path, destination: Path, *, required: bool = False) -> None:
    if not source.exists():
        if required:
            raise FileNotFoundError(f"Required evidence artefact is missing: {source}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build_patterns(output: Path) -> None:
    source = find_run("P01_normal_operating_patterns")
    destination = output / "P01"
    for filename in (
        "config.resolved.json",
        "data_manifest.json",
        "features.json",
        "normal_mode_catalogue.csv",
        "normal_mode_feature_profiles.csv",
        "normal_mode_quality.json",
    ):
        copy_file(source / filename, destination / filename, required=True)
    for filename in ("normal_modes_by_hour.png", "normal_modes_pca.png"):
        copy_file(source / "figures" / filename, destination / "figures" / filename, required=True)


def build_experiment_evidence(output: Path) -> list[dict[str, str]]:
    index: list[dict[str, str]] = []
    for study, experiment_name, purpose in RUNS:
        source = find_run(experiment_name)
        destination = output / study
        for filename in REQUIRED_FILES:
            copy_file(source / filename, destination / filename, required=True)
        for filename in OPTIONAL_FILES:
            copy_file(source / filename, destination / filename)
        index.append({"study": study, "source_run": source.name, "purpose": purpose})
    return index


def build_operational_evidence(output: Path) -> None:
    diagnosis_run = find_run("G03a_xgboost_instrumented_bms")
    for filename in (
        "diagnosis_reports.csv",
        "fault_group_evidence.csv",
        "fault_type_evidence.csv",
        "policy.json",
        "summary.json",
    ):
        copy_file(
            diagnosis_run / "O01_reliability_gated" / filename,
            output / "O01" / filename,
            required=True,
        )

    detection_run = find_run("D07_xgboost_detection")
    for filename in ("priority_cards.csv", "priority_summary.json"):
        copy_file(
            detection_run / "O02_events" / "O02_priority_cards" / filename,
            output / "O02" / filename,
            required=True,
        )
    copy_file(
        ROOT / "configs" / "operational_policies" / "O02_priority_policy.yaml",
        output / "O02" / "O02_priority_policy.yaml",
        required=True,
    )


def write_readme(output: Path, index: list[dict[str, str]]) -> None:
    rows = "\n".join(
        f"| {item['study']} | `{item['source_run']}` | {item['purpose']} |" for item in index
    )
    (output / "README.md").write_text(
        "# Final evidence pack\n\n"
        "This compact Git-friendly package is generated from accepted renamed final runs. "
        "It contains frozen configurations, manifests, metrics, diagnosis evidence, "
        "and report-ready P01 figures.\n\n"
        "## Authoritative runs\n\n"
        "| Study | Full source run | Purpose |\n"
        "| --- | --- | --- |\n"
        f"{rows}\n\n"
        "P01 is normal-pattern discovery. O01 is a reporting policy applied to G03a XGBoost "
        "predictions, and O02 is a priority-policy demonstration using D07 XGBoost events "
        "and O01 diagnoses.\n\n"
        "## Important interpretation limits\n\n"
        "- Results are controlled HVAC-fault experiments from one facility, not multi-building deployment validation.\n"
        "- Fault sessions are labelled for the full recording day; zero delay is not a verified physical onset time.\n"
        "- G03a is an instrumented-BMS diagnosis study, not symptom-only diagnosis.\n"
        "- O01 reliability values are descriptive held-out evidence from this dataset, not guaranteed probabilities for a new building.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace", action="store_true", help="Replace an existing evidence package")
    args = parser.parse_args()
    if OUTPUT.exists():
        if not args.replace:
            raise FileExistsError(f"Evidence output already exists: {OUTPUT}; rerun with --replace")
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    build_patterns(OUTPUT)
    index = build_experiment_evidence(OUTPUT)
    build_operational_evidence(OUTPUT)
    with (OUTPUT / "run_index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["study", "source_run", "purpose"])
        writer.writeheader()
        writer.writerows(index)
    write_readme(OUTPUT, index)
    print(f"Built final evidence pack: {OUTPUT}")


if __name__ == "__main__":
    main()
