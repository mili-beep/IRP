# SFSA

Smart facility fault and anomaly analysis.

This repository is the clean-room rebuild of the building fault-detection project. The primary dataset is the real-only RBC-ASHRAE1312 collection from the Iowa Energy Center Energy Resource Station. Modeling and evaluation implementations are being added in phases.

## Setup

Use Python 3.12 or later. The supported local workflow is to install this
package, including its quality tools, into an isolated environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[quality]"
make check
```

If you use `uv`, the equivalent setup is `uv sync --extra quality`, followed
by `uv run pytest` and `uv run ruff check .`. `uv` is optional; do not rely on
an uninstalled global `uv` command.

## CLI smoke test

```bash
sfsa --help
sfsa run-info --config configs/buildings/auditorium.yaml
```

## Structure

- `configs/`: defaults, RBC building metadata, and experiment definitions.
- `data/`: local raw/interim/processed data; contents are ignored by Git.
- `src/sfsa/`: installable package code.
- `notebooks/`: analysis and reporting notebooks that consume package outputs.
- `results/runs/`: immutable per-run artifacts.
- `tests/`: unit and contract tests with small synthetic fixtures.
- `docs/`: protocol, data dictionary, decisions, claims, and staff guidance.

## Dataset scope

Raw data belongs under `data/raw/01_RBC-ASHRAE1312/`. The first release uses only `Real/Summer`, `Real/Transition`, and `Real/Winter`. The `Simulation/` tree is intentionally excluded until a separate transfer experiment is designed.

See [the RBC reference notes](docs/reference/rbc_ashrae1312/README.md), [the fault taxonomy](docs/reference/rbc_ashrae1312/fault_taxonomy.md), and [the feature dictionary](docs/reference/rbc_ashrae1312/feature_dictionary.md) before interpreting raw columns or scenario filenames.

## Reporting workflow

Run training once, then use the notebooks as read-only analysis layers over `results/runs/`. This keeps training and reporting reproducible and prevents notebooks from becoming a second model implementation.

## Run an experiment

Audit the source data first, then run a configured experiment:

```bash
sfsa audit-rbc \
  --data-root data/raw/01_RBC-ASHRAE1312/Real \
  --manifest results/manifests/rbc_real_manifest.json

sfsa train \
  --building-config configs/buildings/rbc_ashrae1312_real.yaml \
  --experiment-config configs/experiments/E01_baseline.yaml
```

Use `--set KEY=VALUE` only for named sensitivity experiments. Values are parsed
as YAML, so booleans and numbers retain their type:

```bash
sfsa train \
  --building-config configs/buildings/rbc_ashrae1312_real.yaml \
  --experiment-config configs/experiments/E01_baseline.yaml \
  --set include_weather=true \
  --set temporal.enabled=true \
  --set occupied_hours.apply=true
```

Training repeats the required data audit and stops on schema, timestamp,
baseline/fault-pairing, or reference-file failures. `--allow-audit-failures`
creates a diagnostic-only run and records that override; it must not be used
for accepted results.

## Discover normal operating modes

Run the Phase 4 normal-operation analysis separately from fault detection:

```bash
sfsa patterns \
  --building-config configs/buildings/rbc_ashrae1312_real.yaml \
  --experiment-config configs/experiments/P01_normal_patterns.yaml
```

Its run folder contains time/occupancy/weather profiles, a normal-mode
catalogue, PCA figures, stability measures, and the nearest-normal-mode
comparison for each controlled-fault observation.

## Turn a completed run into events and an investigation view

These downstream commands consume saved artefacts only; they do not rerun a
model or access live facilities data:

```bash
sfsa events --run-dir results/runs/<benchmark-run> \
  --patterns-run results/runs/<P01-normal-pattern-run>
sfsa dashboard --run-dir results/runs/<benchmark-run> \
  --patterns-run results/runs/<P01-normal-pattern-run>
sfsa report-qa --run-dir results/runs/<benchmark-run>
```

The event policy is in `configs/event_policy.yaml`. The generated event table,
case studies, static dashboard, and QA report make a run suitable for report
and presentation review, subject to the documented controlled-fault limits.
For the frozen final comparison sequence, use
[the final experiment protocol](docs/final_experiment_protocol.md).

## Cross-domain architecture demonstration

The following adapts a **synthetic demonstration** access-control log to the
canonical event schema. It is not a second operational dataset or an
access-control model evaluation:

```bash
sfsa canonicalise-access \
  --input data/examples/access_control_demo.csv \
  --output-dir results/canonical_access_demo
```

See [cross-domain architecture notes](docs/cross_domain_architecture.md) for
the schema and reporting limitation.

## Run provenance

Every newly created run records its source-data manifest, local reference-file
hashes, Python/runtime package versions, configuration snapshot, selected
features, fitted preprocessing objects, trained models, predictions, and
metrics. The folders already present under `results/runs/` are historical
preliminary experiments; they must not be used as final evidence without being
regenerated under the final evaluation protocol. See
[the project delivery plan](docs/project_delivery_plan.md).

## GitHub evidence package

Run `python scripts/build_final_evidence.py` after final experiments to create
`results/final_evidence/`. It is the compact, Git-friendly package for team and
examiner review: frozen configurations, manifests, metrics, QA evidence, and
selected report figures. The complete generated `results/final_runs/` archive
is intentionally kept outside ordinary Git because it is several gigabytes and
contains large prediction and split-membership artefacts.
