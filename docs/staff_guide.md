# Staff Guide

## Run a benchmark

From `IRP/`:

```bash
sfsa audit-rbc --data-root data/raw/01_RBC-ASHRAE1312/Real
sfsa audit-rbc \
  --data-root data/raw/01_RBC-ASHRAE1312/Real \
  --manifest /tmp/rbc_manifest.json
sfsa train \
  --building-config configs/buildings/rbc_ashrae1312_real.yaml \
  --experiment-config configs/experiments/D01_baseline.yaml
```

The trainer creates a timestamped directory under `results/runs/`. For a
repeated evaluation, use `metrics_by_fold.csv` for individual held-out results,
`metrics_summary.csv` for aggregate means/medians/confidence intervals,
`thresholds.json` for validation-calibrated thresholds, and
`split_membership.csv` to inspect partitions. `metrics.csv` remains a compact
mean-metric table for simple visualisations.

Phase 3 also writes `validation_model_selection.csv`, which records every
declared candidate and the validation-only selection result, and
`model_comparison.csv`, which includes cost measures alongside test metrics.
Use `alert_explanations.csv` for the feature-deviation evidence behind the
three highest-scoring true detections and false alarms in each fold. The
supervised experiment additionally writes
`supervised_permutation_importance.csv`; it explains the labelled fault
classification task and must not be described as proof of unsupervised
anomaly-detection performance.

The manifest records each source file's checksum, schema, missing-cell count, timestamp quality, and baseline/fault pairing status. Review it before accepting model results.

## Explicit sensitivity settings

The default benchmark does not add weather, temporal, or occupied-hours
features. Request these settings explicitly, and confirm the saved
`config.resolved.json` records them:

```bash
sfsa train \
  --building-config configs/buildings/rbc_ashrae1312_real.yaml \
  --experiment-config configs/experiments/D01_baseline.yaml \
  --set include_weather=true \
  --set temporal.enabled=true \
  --set occupied_hours.apply=true
```

## Use pattern outputs in the report

Run `sfsa patterns` with `P01_normal_operating_patterns.yaml`. Use
`normal_mode_catalogue.csv` with `normal_mode_feature_profiles.csv` to describe
each mode, cite `normal_mode_quality.json` for stability/separation, and use
the two PNG files under `figures/` in the report or presentation.
`fault_mode_comparisons.csv` contains controlled-fault observations rather than
production alerts.

## Create operational artefacts from a completed run

```bash
sfsa events \
  --run-dir results/final_runs/<D07-run> \
  --output-name O02_events
sfsa calibrate-diagnosis \
  --run-dir results/final_runs/<G03a-run> \
  --policy configs/operational_policies/O01_reliability_gated.yaml
sfsa prioritise-events \
  --events-dir results/final_runs/<D07-run>/O02_events \
  --diagnosis-dir results/final_runs/<G03a-run>/O01_reliability_gated
```

`O02_events/events.csv` is rate-limited by
`configs/operational_policies/event_grouping.yaml`; it groups
adjacent alert rows but does not assign a staff priority. `priority_cards.csv`
is the one authoritative priority output. It uses the documented configurable
severity, duration, and asset-criticality policy in
`configs/operational_policies/O02_priority_policy.yaml`.
