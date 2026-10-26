# Phase 0 Baseline Record

## Purpose

This document freezes the starting point before the evaluation and feature
pipeline are expanded. It is a factual record of the implementation on
2026-10-25, not a final research result.

## Dataset baseline

- Dataset: real-only RBC-ASHRAE1312 facility-fault collection.
- Data location: `data/raw/01_RBC-ASHRAE1312/Real/`.
- Coverage found by the data audit: 98 scenario/baseline CSVs, comprising 49
  normal baseline files and 49 controlled-fault files.
- Seasons: Summer, Transition, and Winter.
- Source cadence: one-minute observations.
- Pairing audit: 49 fault/baseline pairs; zero missing baseline files and zero
  timestamp-misaligned pairs at the time of review.
- Reference files: `00_explanations.pdf` and `FeaturesNames.xls`. New
  manifests record their size and SHA-256 hash alongside every source CSV.

## Current modelling baseline

The runnable experiments currently provide these models:

- statistical maximum absolute z-score detector;
- Isolation Forest;
- one-class SVM with Nystroem kernel approximation;
- supervised histogram gradient-boosting classifier.

The standard symptom-only feature policy selected 37 numeric features in the
review run. Missing numeric values are median-imputed using training baseline
data only, then standardised.

## Current evaluation baseline and limitation

The current trainer uses a single, hard-coded lexicographically last paired
date as its test set. At the Phase 0 baseline this was `20080601`, containing
one fault scenario, `ConSupFan_Unst.csv`, and its same-day baseline:

| Partition | Normal rows | Fault rows | Held-out fault scenarios |
|---|---:|---:|---|
| Training | 69,120 | 69,120 | 48 |
| Test | 1,440 | 1,440 | 1 |

This split avoids paired-timestamp leakage but is not sufficiently broad for a
headline model-performance claim. Results from it are preliminary only. Phase
2 of the delivery plan replaces it with configurable, repeated scenario,
fault-family, season, and intensity holdouts.

## Verification completed at the baseline

- `PYTHONPATH=src pytest -q` completed successfully with 21 tests passing.
- An end-to-end real-data audit completed successfully.
- An E01 training smoke test completed and produced model, metrics,
  predictions, feature, split, and scenario-metric artefacts.

## Phase 0 changes

New runs now save:

- `data_manifest.json`: raw CSV audit plus reference-document checksums;
- `environment.json`: Python/platform details, package versions, and hashes of
  `pyproject.toml` and `uv.lock` where present;
- `preprocessing.joblib`: fitted imputer, scaler, and selected feature list.

Existing folders in `results/runs/` are intentionally retained, but are marked
as historical preliminary artefacts in `results/runs/README.md`.

## What is deliberately not claimed

- Detection of exact fault onset or true early-warning lead time.
- Generalisation to naturally occurring faults, other buildings, or other
  facilities systems.
- Operationally acceptable alert burden or staff-ready prioritisation.
- A complete access-control, lift, power-management, or BMS-server analytics
  solution.
