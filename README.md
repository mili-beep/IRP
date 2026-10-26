# SFSA HVAC Fault Analysis

This repository contains the completed reproducible analysis pipeline for the
Smart Facilities SA Industry Research Project. It evaluates normal-operation
patterns, anomaly detection, fault diagnosis, and operational prioritisation
using the real RBC-ASHRAE1312 controlled HVAC-fault dataset.

The project is intentionally scoped to HVAC. Results are controlled-fault
experiments from one facility and must not be represented as multi-building or
live-deployment performance.

## Setup

Use Python 3.12 or later:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[quality]"
make check
```

`uv` is optional. Its equivalent setup is `uv sync --extra quality`, followed
by `uv run pytest` and `uv run ruff check .`.

## Verify the installation

```bash
sfsa --help
sfsa run-info --config configs/buildings/rbc_ashrae1312_real.yaml
```

## Dataset

Place the real source data under `data/raw/01_RBC-ASHRAE1312/Real/`. The
pipeline uses the Summer, Transition, and Winter data only; simulation data is
out of scope.

Read the [dataset notes](docs/reference/rbc_ashrae1312/README.md),
[fault taxonomy](docs/reference/rbc_ashrae1312/fault_taxonomy.md), and
[feature dictionary](docs/reference/rbc_ashrae1312/feature_dictionary.md)
before interpreting the source columns.

## Run an experiment

Audit the source data first, then run a configured experiment:

```bash
sfsa audit-rbc \
  --data-root data/raw/01_RBC-ASHRAE1312/Real \
  --manifest results/manifests/rbc_real_manifest.json

sfsa train \
  --building-config configs/buildings/rbc_ashrae1312_real.yaml \
  --experiment-config configs/experiments/D07_xgboost_detection.yaml
```

Training repeats the required data audit and stops on schema, timestamp,
baseline/fault-pairing, or reference-file failures. `--allow-audit-failures`
creates a diagnostic-only run and must not be used for report evidence.

D07 is the selected XGBoost primary binary detector; D03 remains its
histogram-gradient-boosting comparison. D08 tests D07 under season holdout.
G03a is the selected XGBoost instrumented-BMS diagnosis study.

## Notebooks

The four notebooks in [notebooks/](notebooks/) are a readable companion to the
saved experiment artefacts. They do not replace the tested Python pipeline or
YAML configurations:

1. `01_normal_patterns.ipynb` — P01 normal modes and visual profiles.
2. `02_detection_experiments.ipynb` — D01–D08 detection comparisons.
3. `03_diagnosis_experiments.ipynb` — G01–G03a diagnosis comparisons.
4. `04_operational_outputs.ipynb` — O01 reliability gating and O02 priority cards.

## Normal patterns and operational outputs

```bash
sfsa patterns \
  --building-config configs/buildings/rbc_ashrae1312_real.yaml \
  --experiment-config configs/experiments/P01_normal_operating_patterns.yaml

sfsa events --run-dir results/runs/<benchmark-run>
```

The downstream commands consume saved artefacts only; they do not retrain a
model or access a live building system. See [the staff guide](docs/staff_guide.md)
for the event, diagnosis, and priority workflow.

## Final evidence

`results/final_evidence/` is the compact, Git-friendly evidence package for
team and examiner review. It contains frozen configurations, manifests,
metrics, diagnosis artefacts, and selected report figures. Build
it from the complete local results archive with:

```bash
python scripts/build_final_evidence.py --replace
```

The complete generated `results/final_runs/` archive is intentionally excluded
from Git because it contains large predictions, split-membership files, and
model binaries. See [the final evidence README](results/final_evidence/README.md)
and [evaluation protocol](docs/evaluation_protocol.md) for interpretation
limits.
