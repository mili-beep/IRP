# Evaluation Protocol

## Scope

The first release uses only `IRP/data/raw/01_RBC-ASHRAE1312/Real/`. The Simulation tree is excluded. The source contains controlled faults injected into the ERS facility, with a same-day baseline and real weather data where provided.

## Labels

`baseline.csv` rows are normal reference rows. Rows from named fault files inherit scenario-level labels parsed from the fault taxonomy and filename. This does not establish the exact fault onset timestamp; onset analysis is a separate task.

## Pairing and leakage

The source states that baseline and fault files share timestamps. The ingestion layer must verify timestamp alignment before paired comparisons. A headline split must not place paired baseline/fault observations from the same timestamp or scenario into opposing partitions.

## Time and occupancy

The native sampling rate is one minute. The source describes 06:00-18:00 as occupied hours, but the first audit retains full-day data. Occupied-hours analysis is a configured sensitivity experiment, not an implicit filter.

## Features

Experiments must declare `symptom_only`, `control_inclusive`, or a context-augmented feature policy. Weather is optional and must not be silently joined into every experiment. Raw columns and units are preserved.

`context_inclusive` is the approved safe-context policy. It includes only
occupancy, chiller/economiser mode, and supply-air/static-pressure setpoints;
it excludes valve, damper, and fan-position fields that can encode a controlled
fault setting. `control_inclusive` remains available only for explicitly scoped
instrumented-telemetry sensitivity studies.

G03a is the primary XGBoost instrumented-telemetry diagnosis study. It includes
direct valve, damper, and fan-speed/control fields alongside the passive
symptom and physics features. These fields are valid only when equivalent BMS
telemetry is available at prediction time; the result must not be interpreted
as diagnosis from symptoms alone or as command-versus-feedback fault proof.

Physics-informed features are opt-in and are saved alongside each run's selected
columns. The passive set contains supply/mixed-air and coil/water temperature
differences plus airflow-balance residuals. Control-response features add
supply-air setpoint error and airflow-per-fan-speed only when explicitly
enabled. Valve and damper command-feedback residuals are not created unless
both independently documented command and feedback signals are available.

## Headline splits

Random row splits are diagnostic only. Primary evaluations use complete date,
season, or fault-scenario holdouts. Temporal features are computed within
scenario/date boundaries and never across baseline/fault boundaries.

The configured split policy creates repeated folds. Each test fold includes all
fault rows for the held-out unit and the paired same-date normal baseline rows.
Within the remaining training data, complete dates are reserved for validation.
Validation normal rows select each model's alert threshold; headline test rows
are never used to choose that threshold.

Where a model has a declared parameter grid, candidates are also compared on
the validation partition only. The selection measure is validation recall minus
false-positive rate at the configured alert budget; F1 only breaks an exact
tie. Test results are reserved for reporting, not model selection.

## Metrics

Report row-level precision, recall, F1, false-positive rate, ROC-AUC, and
PR-AUC, plus event recall, detection delay, false alarms per day, and
performance by fault type and season. ROC-AUC and PR-AUC are
reported from continuous held-out scores only when both classes are present.

Save per-fold values, aggregate means and medians, bootstrap confidence
intervals, scenario-level results, threshold records, split membership, the
validation candidate table, fit/scoring times, and representative alert
explanations. For supervised experiments, retain validation permutation
importance as a separate, scenario-classification explanation.

## Supervised diagnosis extension

The binary D03 supervised benchmark predicts only `normal` or `fault`. The
separate G01 fault-type study predicts `normal` plus a fault-family label.
It uses complete date holdouts and includes only families with at least two
separate scenarios; singleton families are explicitly recorded as unsupported,
not silently treated as learned classes.

G02 is a hierarchical version of G01. It first predicts `normal` or a broad
operational group (airside damper, heating coil, cooling coil, return fan, or
airflow distribution), then predicts the fine-grained type only within the
predicted group. It retains G01 as the flat-classification benchmark and saves
both fine- and coarse-group confusion matrices.

O01 is a reporting-policy evaluation applied to G03a's saved complete-date
held-out predictions. It creates one report per fault day rather than treating
minute rows as independent evidence. A predicted fault group or type is shown
only where that predicted label has at least five held-out reports and at least
70% observed correctness. Otherwise the relevant report field is `Uncertain`.
The saved reliability values are descriptive evidence for this dataset and
must not be presented as guaranteed probabilities for an unseen building.

D08 evaluates the frozen D07 XGBoost binary configuration with each season
held out in turn. It isolates seasonal generalisation from changes in model,
feature policy, or alert budget. It remains a one-facility controlled-fault
test and does not establish external-building deployment performance.

## Acceptance gate

Before accepting a result, generate and review a manifest with `sfsa audit-rbc --manifest ...`. The manifest must cover all intended real files, contain checksums and schemas, report timestamp quality, and show no unexpected missing baseline or unaligned pair.
