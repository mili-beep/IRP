# SFSA Project Delivery Plan

## Purpose

This plan converts the current Smart Facilities SA prototype into a defensible
master's Industry Research Project deliverable. It responds to the project
brief: identify normal operating patterns, unusual behaviour, and early signs
of equipment or security problems from facilities data, then present actionable
findings to facilities or security staff.

The present repository is a sound HVAC fault-detection foundation built on the
real RBC-ASHRAE1312 dataset. It must not yet be represented as a complete
multi-system facilities log platform or as evidence of general performance
across buildings.

## Success definition

By the final submission, the researcher should be able to demonstrate a
reproducible pipeline that:

1. Ingests and audits the HVAC source data and at least one additional
   facilities-log modality, or demonstrably supports that second modality
   through a documented canonical event schema and a small working adapter.
2. Profiles normal operation by time, season, operating mode, and relevant
   context.
3. Detects, groups, explains, and prioritises anomalous events rather than
   merely flagging isolated rows.
4. Evaluates models using pre-specified, leakage-safe scenario, season, and
   fault-family holdouts.
5. Reports performance, alert burden, limitations, and staff-facing
   interpretation honestly and reproducibly.
6. Delivers a usable visual investigation view and a written report supported
   by reproducible run artefacts.

## Non-negotiable research guardrails

- Keep the current first-release RBC scope real-only; do not silently mix its
  `Simulation/` files with its real facility data.
- Treat fault filenames as scenario labels, not exact fault-onset labels.
- Do not claim performance for all buildings, naturally occurring faults, or
  all Smart Facilities systems from the RBC experiment alone.
- Pre-specify headline splits, feature policies, thresholds, and metrics before
  comparing models.
- Keep notebooks as analysis/reporting consumers of package outputs; model
  training must remain in tested package code.
- Every reported result must identify its code version, config, data manifest,
  environment, feature list, split, thresholds, and random seed.

## Current-state baseline

### Working now

- Real RBC data discovery, filename taxonomy parsing, timestamp parsing, and
  paired baseline/fault validation.
- Dataset manifest generation with schema and SHA-256 values.
- Feature grouping, training-only median imputation, and scaling.
- Statistical, Isolation Forest, one-class SVM, and supervised gradient
  boosting benchmark implementations.
- Unit and contract tests covering configuration, data contracts, evaluation,
  training, patterns, events, canonical records, dashboard generation, and QA.
- Minimal notebooks and saved metrics/predictions/model artefacts.

### Remaining evidence gaps

- Headline experiments must still be executed without diagnostic `max_folds`
  limits before their results can be reported.
- The available evaluated data remains controlled HVAC faults from one facility.
  The access-control adapter is a synthetic architectural demonstration, not a
  second operational evaluation.
- No stakeholder usability review or live deployment validation has been
  performed; event actions and priority bands are transparent starting policy,
  not staff-validated procedures.
- Existing historical result folders were produced by different pipeline states
  and must not be mixed with final regenerated benchmark evidence.

## Solo-project delivery approach

This is a **single-person implementation plan**. Its scope remains equivalent
to the original five-person project expectation; the work is simply completed
in a deliberate sequence by one researcher. Each phase should be treated as a
small, reviewable milestone before moving to the next one.

The work naturally spans five areas:

| Area | Main outputs |
|---|---|
| Data and provenance | Canonical schema, adapters, manifests, data-quality report |
| Normal patterns and features | EDA, operating modes, feature studies, temporal/context features |
| Detection and diagnosis | Calibrated detectors, supervised benchmark, explanations |
| Evaluation and reproducibility | Split engine, metrics, experiment registry, statistical summaries |
| Operations and communication | Event prioritisation, dashboard, case studies, report and presentation |

## Delivery sequence

The ordering below deliberately fixes validity and reproducibility before
building a dashboard or adding more complex models. A visually appealing system
with a weak experiment design would not answer the research question.

### Phase 0 — Freeze the baseline and make execution repeatable

**Goal:** establish one known-good starting point before changing the pipeline.

Tasks:

1. Create an immutable baseline manifest for `Real/`, including the two local
   reference files and all source CSV hashes.
2. Record a short baseline note: current models, 37 symptom-only numeric
   features, data sizes, current single-date test scenario, and known limits.
3. Resolve the local developer workflow: document one supported command for
   setup, testing, linting, and training. Make either package installation or
   `PYTHONPATH=src` explicit for developers who do not use `uv`.
4. Add a dependency lock/version capture to every run.
5. Mark the existing `results/runs/` folders as historical/preliminary, then
   regenerate final benchmark results only after the revised evaluation is in
   place.

Acceptance criteria:

- A fresh local setup can follow the README and run tests without manually
  guessing Python import paths.
- `make check` or its documented equivalent runs tests and linting.
- A baseline run folder includes an input manifest checksum, resolved config,
  package versions, seed, feature list, preprocessing artefacts, and model.

### Phase 1 — Make configuration and data preparation real

**Goal:** ensure documented options are actually enacted and tested.

Tasks:

1. Implement deterministic configuration composition: defaults + building +
   experiment + command-line overrides. Save the fully resolved config.
2. Validate dataset schema before training: required time/metadata fields,
   column consistency, duplicate timestamps, expected cadence, missingness,
   and paired baseline/fault alignment.
3. Move the audit acceptance gate into `train`: training should refuse to
   produce an accepted run if the audit fails, while allowing an explicit
   diagnostic override that is recorded.
4. Implement optional weather joining and ensure prefixed weather columns can
   become features only when an experiment requests them.
5. Connect occupied-hours filtering as an explicitly named sensitivity
   experiment; never make it implicit.
6. Connect boundary-safe temporal features and add tests proving no scenario,
   date, or train/test leakage.
7. Replace heuristic-only feature grouping with a reviewed feature map linked
   to the RBC feature dictionary. Keep heuristics only as a checked fallback.

Acceptance criteria:

- Changing `include_weather`, `include_vav`, temporal settings, or
  occupied-hours settings changes the saved resolved config and feature list.
- Every requested policy has a passing integration test.
- Training fails clearly on failed pairings, missing required fields, or an
  unknown feature policy.

### Phase 2 — Build a defensible evaluation framework

**Goal:** replace the one-scenario benchmark with pre-registered, leakage-safe
experiments.

Tasks:

1. Replace `_choose_holdout_date()` with a split factory controlled by
   `split_policy`.
2. Implement and compare these split families:
   - leave-one-date/scenario-out;
   - leave-one-fault-family-out;
   - leave-one-season-out;
   - leave-one-intensity-out where enough comparable cases exist;
   - occupied versus unoccupied sensitivity tests.
3. Enforce that paired baseline and fault timestamps never appear across train
   and test partitions.
4. Add a validation partition within training data for threshold selection;
   never select a threshold using headline test data.
5. Capture per-fold, aggregate mean/median, confidence intervals or bootstrap
   intervals, and variation across scenarios.
6. Save split membership and scenario counts, not only aggregate row counts.
7. Define a primary research comparison before running it. Suggested primary
   comparison: symptom-only, real RBC data, leave-one-scenario-out; secondary
   studies add feature policies and seasonal/family generalisation.

Acceptance criteria:

- The headline table includes results across all feasible real fault scenarios,
  not one selected date.
- Every fold has documented train/validation/test scenarios and passes leakage
  checks.
- The report identifies one primary metric and does not select the winning
  model after inspecting the test set.

### Phase 3 — Establish useful baselines and calibrated detection

**Goal:** produce a fair, operationally meaningful model comparison.

Tasks:

1. Retain simple transparent baselines: robust z-score/rule baseline,
   Isolation Forest, and one-class SVM or a computationally appropriate
   alternative.
2. Treat the supervised model as a separate fault-scenario classification
   experiment, not direct proof of unsupervised anomaly detection.
3. Tune contamination, `nu`, thresholds, and persistence settings on validation
   folds according to declared alert budgets.
4. Add probability/score normalisation where models expose continuous anomaly
   scores.
5. Add model explanations appropriate to each method:
   - per-feature deviation for statistical models;
   - feature attribution/permutation importance for supervised models;
   - top contributing changed variables for an anomaly event.
6. Compare symptom-only, control-inclusive, context/weather, and temporal
   feature policies.
7. Add computational cost and latency measurements so the proposed operational
   design is credible.

Phase 3 implementation status (2026-10-25):

- Each fold now evaluates the small, declared parameter grid using validation
  data only. It selects the candidate with the greatest validation recall minus
  false-positive rate; F1 is a tie-breaker, not the selection rule.
- The default grids make the Isolation Forest contamination and one-class SVM
  `nu` explicit. The chosen parameters, threshold, validation performance, fit
  time, and scoring time are saved for every fold.
- `alert_explanations.csv` records the top five standardised feature deviations
  for up to three true detections and three false alarms per model/fold.
  `supervised_permutation_importance.csv` adds one-repeat validation permutation
  importance for the supervised experiment.
- `model_comparison.csv` combines the held-out model metrics with an explicit
  reminder that operational selection considers alert burden, not F1 alone.
  The next feature-policy experiments will reuse these same artefacts.
- Continuous held-out scores additionally produce ROC-AUC and PR-AUC when a
  fold contains both normal and controlled-fault observations.

Acceptance criteria:

- A model is never selected only on F1; alert burden and false alarms are also
  considered.
- Model configuration and threshold values are saved in each run.
- Each selected model has an explanation artefact for at least three true
  detections and three false alarms.

### Phase 4 — Normal-pattern discovery

**Goal:** satisfy the brief's requirement to identify normal operational
patterns, not only fault labels.

Tasks:

1. Profile baseline data by hour, day/season, occupancy window, and weather.
2. Build interpretable operating-mode methods, for example clustering of
   baseline windows, PCA/UMAP for exploratory visualisation, and a normal-mode
   catalogue.
3. Quantify stability and separability of discovered modes.
4. Associate every anomaly with its nearest normal operating mode and identify
   the features that differ materially from that mode.
5. Create a normal-behaviour case study that is valuable even without a fault
   label.

Phase 4 implementation status (2026-10-25):

- `sfsa patterns` creates a separate, immutable normal-operation run from
  baseline records only. It profiles selected features by season, hour, and
  stated occupied/unoccupied window; the P01 configuration also includes
  weather context.
- A deterministic K-means model creates a compact normal-mode catalogue, with
  PCA coordinates for a report-ready visualisation. Silhouette score and
  repeated-sample adjusted Rand index document separation and stability.
- Every controlled-fault observation is compared with its nearest normal mode;
  the saved comparison includes the five largest standardised deviations from
  that mode. This is an appropriate diagnostic reference, rather than a single
  global normal average.

Acceptance criteria:

- The report contains normal-mode visuals and an explanation of what each
  recurring mode represents.
- Anomaly explanations compare against an appropriate normal mode rather than
  an undifferentiated global average.

### Phase 5 — Convert anomalous minutes into actionable events

**Goal:** make outputs usable by facilities or security staff.

Tasks:

1. Implement event grouping: combine adjacent anomalous rows with configurable
   gap tolerance, minimum duration, and de-duplication.
2. Implement event properties: start/end, duration, maximum score, persistence,
   affected sensors, asset/system, operating context, and model confidence.
3. Define and test one transparent, configurable priority score after event
   grouping. It should combine documented severity, duration, and equipment
   criticality; do not present it as a learned risk model without ground truth.
4. Map priority bands to staff actions such as monitor, inspect next shift,
   investigate today, or escalate immediately.
5. Include alert suppression/rate limiting, so many anomalous minutes produce
   one well-formed event instead of hundreds of alerts.
6. Run a structured stakeholder interpretation review, if access to staff is
   available: ask whether the alert fields, priority categories, and suggested
   actions are understandable and useful.

Phase 5 implementation status (2026-10-25):

- `sfsa events` reads a completed run's saved predictions and writes grouped
  event artefacts under `events/`; it never retrains or changes row-level
  predictions.
- The event policy defines only grouping and rate-limiting. The separate
  priority policy defines severity, duration, criticality, bands, and staff
  actions, so the pipeline has one authoritative priority score.
- Case-study selection writes the strongest available true detection, false
  alarm, and missed/weak scenario. A category is absent rather than fabricated
  when the selected run provides no evidence for it.

Acceptance criteria:

- One incident produces one event card/timeline rather than 1,440 independent
  notifications.
- The final output includes at least three event case studies: true detection,
  false alarm, and missed/weak detection.
- Priority rationale is auditable from saved event properties.

### Phase 6 — Broaden the facilities-management claim carefully

**Goal:** align the project more closely with the multi-system brief while
remaining honest about available data.

Choose one of these paths after confirming what data is legally and practically
available:

- **Preferred: second real modality.** Add a small, de-identified dataset from
  access control, environmental sensors, power management, lift telemetry, or
  BMS/server logs. Build an adapter and evaluate at least data quality, normal
  pattern discovery, and event grouping.
- **Fallback: generic schema demonstration.** Define a canonical log/event
  contract with `timestamp`, `source_system`, `asset_id`, `event_type`,
  `measurements`, `status`, and provenance fields. Implement a second adapter
  using an open/de-identified example and explicitly call the result an
  architectural demonstration, not Smart Facilities validation.

Acceptance criteria:

- A second modality can pass the same audit and produce canonical records.
- The report distinguishes HVAC experimental findings from cross-domain system
  architecture.

Phase 6 implementation status (2026-10-25):

- E08 implements the generic-schema fallback through a canonical access-control
  adapter and audit. Its tiny synthetic input is explicitly an architectural
  demonstration and must never be reported as Smart Facilities or cross-domain
  detection validation.

### Phase 7 — Visualisation and delivery interface

**Goal:** provide understandable evidence for researchers and operational
staff.

Tasks:

1. Expand notebooks into reproducible report figures, with no training code in
   notebooks.
2. Implement a lightweight dashboard consuming completed run artefacts only.
3. Include at minimum:
   - dataset quality and coverage;
   - normal operating modes;
   - model comparison and uncertainty;
   - alert burden / false alarms per day;
   - fault family, intensity, and season breakdown;
   - event timeline and event-detail explanation;
   - filters for building/system, season, model, and priority.
4. Conduct usability review with independent reviewers and, if possible,
   intended staff.
5. Make the dashboard explicitly a demonstration, unless deployed and evaluated
   in a live environment.

Acceptance criteria:

- Every chart is generated from a saved run artefact and can be regenerated.
- A non-technical reviewer can locate the most important event, understand its
  priority, and see why it was flagged.

Phase 7 implementation status (2026-10-25):

- `sfsa dashboard` builds a static investigation page and comparison figure
  from saved run/event artefacts only. Its table filters model and priority,
  and the page carries a visible demonstration/controlled-label disclaimer.
- The four notebooks now remain read-only consumers of saved audit, pattern,
  benchmark, and event artefacts; none repeats package training logic.

### Phase 8 — Research report and final quality assurance

**Goal:** turn implementation into a high-quality academic/industry outcome.

Tasks:

1. Write the report around research questions, not a chronological diary.
2. Include dataset provenance, ethics/privacy considerations, methods,
   pre-specified evaluation, results, failures, validity threats, and practical
   recommendations.
3. State limitations prominently: controlled faults, one facility, scenario
   labels rather than onset labels, limited modality coverage, and lack of live
   deployment validation.
4. Assemble reproducibility appendix: commands, configs, manifests, feature
   maps, result IDs, environment versions, and known exclusions.
5. Re-run all headline experiments from a clean environment before submission.
6. Conduct a final code review, test run, data-leakage audit, figure audit, and
   reference check.

Acceptance criteria:

- Every numeric claim in the report links to a named run directory/table.
- No claim exceeds the evidence available from the data and evaluation design.
- A clean clone/setup can reproduce headline tables and figures.

Phase 8 implementation status (2026-10-25):

- `sfsa report-qa` writes a named run's provenance and internal-consistency
  checks to `qa_report.json`; it flags diagnostic max-fold runs and accepted
  audit overrides for report review.

## Experiment register

Create one YAML experiment file and one result folder per experiment. Use stable
IDs in the report.

| ID | Question | Required comparison |
|---|---|---|
| E01 | Can simple baselines detect controlled HVAC faults? | Robust statistical baseline vs Isolation Forest |
| E02 | Do classical one-class models improve detection/alert burden? | Isolation Forest vs one-class SVM with validation tuning |
| E03 | How does supervised fault-scenario classification compare? | Supervised model, clearly separated from anomaly claims |
| E04 | Does feature choice affect validity and performance? | Symptom-only vs control-inclusive vs context/weather |
| E05 | Do temporal features improve early or persistent-event detection? | Static vs boundary-safe temporal features |
| E06 | Can models generalise to unseen scenarios/families/seasons? | Scenario, family, and season holdouts |
| E07 | What alert policy is operationally viable? | Threshold/persistence/event-grouping sensitivity study |
| E08 | Can the architecture process a second facilities modality? | HVAC adapter vs second-modality adapter/schema |

## Required metrics and reporting rules

Report all of the following for every headline experiment where meaningful:

- Row level: precision, recall, F1, false-positive rate, PR-AUC/ROC-AUC where
  continuous scores are available.
- Event level: event recall, event precision if ground truth permits, time to
  first alert relative to the stated reference point, event duration, and
  duplicate alerts per event.
- Operational: false alarms per observed day, alerts per day, alert-event count,
  percentage of alerts in each priority band, and computational runtime.
- Generalisation: results by fault type, intensity, season, operating period,
  and held-out scenario.
- Uncertainty: fold distribution and an interval for headline metrics.

Never label time from the first file timestamp as true fault-onset detection
delay. Call it `time from scenario observation start` unless onset is supported
by independent ground truth.

## Run-artifact contract

Each accepted run directory should contain at least:

```text
config.resolved.json
data_manifest.json
environment.json
split_membership.csv
features.json
preprocessing.joblib
models/fold_###/<model_name>.joblib
thresholds.json
validation_model_selection.csv
metrics_by_fold.csv
metrics_summary.csv
metrics_by_fault_group.csv
model_comparison.csv
predictions.csv
alert_explanations.csv
supervised_permutation_importance.csv
baseline_profile_by_time.csv
normal_mode_catalogue.csv
normal_mode_feature_profiles.csv
normal_mode_assignments.csv
fault_mode_comparisons.csv
normal_mode_quality.json
normal_mode_model.joblib
figures/
README.md
```

The `README.md` should state the research question, source data, exclusions,
feature policy, split policy, selected threshold, and the correct interpretation
of the result.

## Risk register

| Risk | Consequence | Mitigation |
|---|---|---|
| Single-scenario headline result | Overstated performance | Multi-fold held-out scenario/family/season evaluation |
| Scenario label is not onset label | Invalid early-detection claim | Use careful terminology; obtain onset metadata or do not claim it |
| Controlled, single-site faults | Weak external validity | State limitation; use second modality/site if available |
| High false-alarm rate | Operationally unusable system | Validation-calibrated thresholds, persistence, event grouping |
| Feature leakage from controls/context | Inflated performance | Feature policies, reviewed map, split and leakage tests |
| Configuration drift | Non-reproducible results | Resolved configs and immutable run contract |
| Incomplete second-modality data access | Scope cannot broaden | Decide early; use canonical-schema fallback |
| Dashboard consumes live/untracked logic | Inconsistent results | Dashboard reads saved artefacts only |
| Time pressure near submission | Incomplete validation/report | Freeze headline experiments before final report writing |

## Research communication and scope strategy

### Core project narrative

Present the work as a reproducible facilities anomaly-detection pipeline, not
as a collection of disconnected machine-learning models. The central claim to
support is:

> The project designs and evaluates a reproducible pipeline that learns normal
> facilities operation, identifies anomalous behaviour across conditions, and
> turns detections into prioritised, explainable events for staff.

This framing makes the scope credible because it connects data engineering,
normal-pattern analysis, detection, rigorous evaluation, visualisation, and
operational decision support. Do not inflate the scope with decorative figures
or unnecessary models. Every figure, model, and experiment should answer a
research or operational question.

### Implementation components to demonstrate

The completed project should provide evidence for these connected components:

1. **Data engineering and provenance:** source inventory, timestamp and
   pairing validation, missing-data analysis, feature dictionary, canonical
   metadata, and immutable manifests.
2. **Normal-operation analysis:** patterns by time, season, operating mode,
   occupancy window, and relevant weather/context.
3. **Feature engineering:** controlled comparisons of symptom-only,
   control-inclusive, weather/context, and temporal feature policies.
4. **Detection and diagnosis:** transparent statistical baselines, classical
   anomaly detectors, and a separately interpreted supervised benchmark.
5. **Rigorous evaluation:** scenario, family, season, and intensity holdouts;
   alert burden; uncertainty; and failure analysis.
6. **Operationalisation:** grouped anomaly events, explanations, priority
   rules, recommended staff actions, and alert suppression.
7. **Communication:** reproducible figures, case studies, a dashboard or
   investigation view, report, and presentation.

### Planned experiment matrix

Use a small, purposeful set of experiments rather than an uncontrolled search
over many models. The following matrix complements the E01--E08 experiment
register and should be refined before headline runs begin.

| Study | Research question | Expected comparison |
|---|---|---|
| Baseline comparison | Do ML detectors improve on a transparent rule/statistical baseline? | Robust z-score vs Isolation Forest vs one-class SVM |
| Supervised comparison | What changes when controlled fault labels are available during training? | Supervised gradient boosting, reported separately from unsupervised claims |
| Feature ablation | Which information sources contribute useful signal? | Symptom-only vs controls vs weather/context vs temporal features |
| Generalisation | Can the approach handle conditions not seen during training? | Held-out scenario, fault family, season, and intensity tests |
| Operating context | Does performance vary by operating period? | Occupied vs unoccupied and time-of-day sensitivity |
| Alert calibration | What threshold/persistence policy is operationally viable? | Validation-selected thresholds, alert budget, and false-alarm comparison |
| Event grouping | Can raw anomaly flags become lower-noise actionable events? | Row-level alerts vs grouped-event alerts |
| Cross-domain architecture | Can the pipeline accept more than HVAC data? | HVAC adapter plus second-modality adapter or canonical-schema demonstration |

### Report evidence plan

The report should be organised around research questions and evidence, not a
chronological implementation diary. A recommended chapter structure is:

1. Introduction and industry problem.
2. Background and related work.
3. Research questions, scope, and success criteria.
4. Dataset provenance and data-quality assessment.
5. Pipeline architecture and implementation.
6. Feature engineering and normal-operation patterns.
7. Detection models and evaluation design.
8. Results, model comparison, and error analysis.
9. Event prioritisation, staff interpretation, and visual interface.
10. Discussion, limitations, recommendations, and future work.
11. Conclusion.

Include these evidence tables where relevant:

- dataset inventory: files, rows, sensors, seasons, fault families, and
  intensities;
- data-quality audit: missingness, duplicates, cadence, and pair alignment;
- feature-policy rationale and selected columns;
- experiment register: model, features, split, threshold policy, and run ID;
- main model comparison: precision, recall, F1, false-positive rate,
  event recall, and alerts/false alarms per day;
- results by fault family, intensity, season, and operating context;
- error analysis: representative false alarms, missed events, causes, and
  mitigation;
- documented priority policy and associated staff actions;
- limitations and validity threats.

Include these figures where they add evidence:

- end-to-end architecture/pipeline diagram;
- data coverage by season and fault family;
- missingness or data-quality visual;
- normal operating-mode plot, such as PCA or clustering;
- normal-versus-fault sensor timelines;
- model-comparison and alert-burden charts;
- performance heatmap by fault family and season;
- anomaly-score timeline with grouped event boundaries;
- event-detail explanation showing changed sensors, context, priority, and
  suggested staff action;
- dashboard or investigation-view screenshots;
- case studies covering a true detection, false alarm, and missed/weak event.

### Presentation narrative

The presentation should be visual, concise, and operationally focused:

1. Facilities monitoring problem and project objective.
2. Proposed pipeline architecture.
3. Dataset and data-quality evidence.
4. Normal operating patterns.
5. Evaluation design and why it avoids misleading results.
6. Model comparison and selection rationale.
7. One end-to-end anomaly-event case study.
8. Dashboard or investigation interface.
9. Limitations and responsible interpretation.
10. Practical recommendations and next steps for Smart Facilities SA.

The best final message is not simply that one model achieved the highest F1.
It is that the selected approach balances detection quality, generalisation,
false-alarm burden, explainability, and staff usefulness.

## First implementation sprint

The first step should be small, testable, and high value:

1. Add resolved configuration loading and save it to runs.
2. Replace the hard-coded held-out date with a configurable split interface.
3. Write event metrics into the result artefacts.
4. Save preprocessing objects and the input data manifest with every run.
5. Add integration tests for those behaviours.
6. Regenerate E01–E03 as clearly versioned preliminary benchmark runs.

Do not begin dashboard work or introduce deep-learning models until this sprint
has passed review. The strongest immediate gain is a valid, repeatable
evaluation pipeline.

## Decision log protocol

For each substantive decision, add a dated entry to `docs/decisions.md` with:

- the decision and rationale;
- alternatives considered;
- evidence or experiment ID;
- expected effect on validity, scope, or operations;
- resulting config or code location.

This will make the final report much easier to write and defend.
