# Final evidence pack

This compact Git-friendly package is generated from accepted renamed final runs. It contains frozen configurations, manifests, metrics, diagnosis evidence, and report-ready P01 figures.

## Authoritative runs

| Study | Full source run | Purpose |
| --- | --- | --- |
| D01 | `20261026T140336Z_rbc_ashrae1312_real_D01_baseline` | Statistical and Isolation Forest baseline |
| D02 | `20261026T140513Z_rbc_ashrae1312_real_D02_classical` | Classical unsupervised comparison |
| D03 | `20261026T140618Z_rbc_ashrae1312_real_D03_supervised` | Supervised binary detection |
| D04a | `20261026T141000Z_rbc_ashrae1312_real_D04a_control_inclusive` | Control-inclusive feature sensitivity |
| D04b | `20261026T141212Z_rbc_ashrae1312_real_D04b_control_weather` | Control and weather sensitivity |
| D05 | `20261026T141352Z_rbc_ashrae1312_real_D05_temporal` | Temporal-feature sensitivity |
| D06 | `20261026T141718Z_rbc_ashrae1312_real_D06_classical_season_generalisation` | Classical seasonal robustness |
| D07 | `20261026T141733Z_rbc_ashrae1312_real_D07_xgboost_detection` | Primary XGBoost binary detection |
| D08 | `20261026T141906Z_rbc_ashrae1312_real_D08_xgboost_season_generalisation` | XGBoost seasonal robustness |
| G01 | `20261026T141920Z_rbc_ashrae1312_real_G01_fault_type_classification` | Flat fault-type classification |
| G02a | `20261026T143020Z_rbc_ashrae1312_real_G02a_hierarchical_baseline` | Hierarchical diagnosis baseline |
| G02b | `20261026T144453Z_rbc_ashrae1312_real_G02b_hierarchical_physics` | Hierarchical diagnosis with physics |
| G02c | `20261026T145619Z_rbc_ashrae1312_real_G02c_hierarchical_safe_context` | Hierarchical diagnosis with safe context |
| G02d | `20261026T150945Z_rbc_ashrae1312_real_G02d_hierarchical_safe_context_balanced` | Scenario-balanced diagnosis |
| G03a | `20261026T153634Z_rbc_ashrae1312_real_G03a_xgboost_instrumented_bms` | Primary XGBoost instrumented-BMS diagnosis |

P01 is normal-pattern discovery. O01 is a reporting policy applied to G03a XGBoost predictions, and O02 is a priority-policy demonstration using D07 XGBoost events and O01 diagnoses.

## Important interpretation limits

- Results are controlled HVAC-fault experiments from one facility, not multi-building deployment validation.
- Fault sessions are labelled for the full recording day; zero delay is not a verified physical onset time.
- G03a is an instrumented-BMS diagnosis study, not symptom-only diagnosis.
- O01 reliability values are descriptive held-out evidence from this dataset, not guaranteed probabilities for a new building.
