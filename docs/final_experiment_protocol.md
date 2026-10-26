# Final experiment protocol

Freeze these configurations before generating report evidence. Do not rerun an
experiment because its result is disappointing; rerun only after documenting a
technical failure or an approved configuration correction.

| Study | Run/configuration | Comparison |
|---|---|---|
| E01 | `E01_baseline.yaml` | Symptom-only statistical baseline vs Isolation Forest |
| E02 | `E02_classical.yaml` | Isolation Forest vs one-class SVM under family holdout |
| E03 | `E03_supervised.yaml` | Supervised binary normal-versus-fault benchmark |
| E04 | E01, `E04a_control_inclusive.yaml`, `E04b_control_weather.yaml` | Symptom-only vs controls vs controls plus weather |
| E05 | E01, `E05_temporal.yaml` | Static symptom features vs boundary-safe temporal features |
| E06 | `E06_generalisation.yaml` | Season holdout generalisation |
| E09 | `E09_fault_type_classification.yaml` | Supervised normal-plus-fault-type classification on repeatedly observed families |
| E10 | `E10_cooling_coil_intensity.yaml` | Conditional cooling-coil-valve intensity regression across numeric severity levels |
| E11 | `E11_hierarchical_fault_type_classification.yaml` | Coarse operational-group diagnosis followed by within-group fault-type diagnosis |
| E12 | `E12_hierarchical_physics.yaml` | E11 with opt-in, passive HVAC physical-relationship features |
| E13 | `E13_hierarchical_safe_context.yaml` | E12 plus safe BMS operating context and weather |
| E14 | `E14_hierarchical_safe_context_balanced.yaml` | E13 plus equal scenario influence during hierarchical training |
| E15 | `E15_hierarchical_confidence.yaml` | Confidence-based triage policy applied to saved E14 predictions; no model retraining |
| E16 | `E16_hierarchical_instrumented_bms.yaml` | E12 plus direct BMS actuator and control telemetry, as an instrumented-diagnosis sensitivity study |
| E17 | `E17_hierarchical_full_bms.yaml` | E16 plus VAV and zone-level BMS telemetry, as a full-building instrumented-diagnosis study |
| E18 | `E18_reliability_gated.yaml` applied to E16 | Report-level reliability gate: show a fault group/type only if its predicted label has at least five held-out fault-day reports and at least 70% observed correctness |
| E19 | `E19_supervised_season_generalisation.yaml` | E03 supervised binary detector under leave-one-season-out generalisation evaluation |

P01 normal patterns is a supporting artefact, not a comparable model benchmark.

E09 and E10 are an approved supervised-diagnosis extension. E10 must always
be described as conditional on a known fault type; it is not a global intensity
model and it is not an end-to-end cascade result.

E16 is not a replacement for the symptom-and-physics diagnosis result in E12.
It tests the practical upper bound when direct valve, damper, fan-speed, and
other BMS control telemetry are available. Its results must be described as
instrumented BMS diagnosis, not as fault inference from physical symptoms
alone. No weather fields are included, so the comparison isolates this added
telemetry from the E13 context/weather study.

E17 adds the VAV and zone measurements to E16, while retaining the same
features, no-weather policy, model, and complete-date holdouts. Its comparison
with E16 therefore measures the incremental value of downstream zone telemetry.
It remains an instrumented BMS diagnosis result, not symptom-only inference.

E18 does not retrain E16 or change its frozen predictions. It collapses the
one-minute held-out predictions into complete fault-day reports and applies a
pre-declared reliability gate to predicted groups and types. Its percentages
are descriptive cross-validated evidence from this dataset, not guaranteed
probabilities for a new building.

E19 keeps E03's supervised model, symptom-only inputs, validation-based
threshold selection, and all other settings unchanged. It only replaces E03's
scenario holdout with leave-one-season-out folds. It is the direct test of
whether E03's strong same-facility performance remains when operating season
changes; it is not an external-building validation.

The configurable priority layer is an operational policy artefact, not a model
experiment. It combines grouped E03 events, E18 diagnosis fields where
available, duration, a documented severity mapping, and an explicit
asset-criticality assumption. See `docs/priority_scoring_policy.md`.
