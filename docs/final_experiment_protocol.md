# Final Study Protocol

Freeze these configurations before generating report evidence. Do not rerun a
study because its result is disappointing; rerun only after documenting a
technical failure or approved configuration correction.

| Study | Configuration(s) | Purpose |
|---|---|---|
| P01 | `P01_normal_operating_patterns.yaml` | Discover and profile normal HVAC operating modes. |
| D01 | `D01_baseline.yaml` | Statistical baseline versus Isolation Forest. |
| D02 | `D02_classical.yaml` | Isolation Forest versus one-class SVM under fault-family holdout. |
| D03 | `D03_supervised.yaml` | Supervised binary normal-versus-fault detection. |
| D04a/D04b | `D04a_control_inclusive.yaml`, `D04b_control_weather.yaml` | Feature-context sensitivity: symptoms, controls, and controls plus weather. |
| D05 | `D05_temporal.yaml` | Boundary-safe temporal-feature sensitivity. |
| D06 | `D06_classical_season_generalisation.yaml` | Seasonal robustness of the classical detectors. |
| D07 | `D07_xgboost_detection.yaml` | Primary XGBoost binary normal-versus-fault detection. |
| D08 | `D08_xgboost_season_generalisation.yaml` | Seasonal robustness of the frozen D07 XGBoost detector. |
| G01 | `G01_fault_type_classification.yaml` | Flat normal-plus-fault-type classification. |
| G02a–G02d | `G02a_hierarchical_baseline.yaml` through `G02d_hierarchical_safe_context_balanced.yaml` | Hierarchical diagnosis development: baseline, physics, safe context, and scenario balancing. |
| G03a | `G03a_instrumented_bms.yaml` | Primary XGBoost instrumented-BMS diagnosis. |
| O01 | `O01_reliability_gated.yaml` applied to G03a | Reliability-gated staff-facing fault-group and fault-type reporting. |
| O02 | `O02_priority_policy.yaml` applied to D07 events and O01 diagnoses | Configurable event prioritisation from grouped events and O01 diagnoses. |

## Interpretation rules

D07 is the selected primary detector after its XGBoost comparison achieved a
higher F1 and materially lower false-positive rate than D03 under the same
scenario-held-out evaluation. D08 keeps its model, symptom-only features, and
threshold procedure fixed while holding out each season in turn.

G03a is an instrumented-BMS study, not diagnosis from symptoms alone. Direct
valve, damper, and fan-speed telemetry must be available at prediction time for
this configuration to be applicable.

O01 does not retrain G03a or change its predictions. It creates one report per
held-out fault-day session and shows a group/type only where the predicted label
has at least five held-out reports and at least 70% observed correctness. The
saved reliability is descriptive evidence for this dataset, not a guaranteed
probability for a new building.

O02 is an operational policy layer, not a machine-learning experiment. It
combines grouped D07 events, O01 diagnosis fields where available, event
duration, a documented severity mapping, and an explicit asset-criticality
assumption. See `docs/priority_scoring_policy.md`.
