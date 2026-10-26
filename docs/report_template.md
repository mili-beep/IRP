# Industry Research Project report template

Use this as a writing structure after completing the headline runs. Replace
every bracketed placeholder with a named run directory, table, figure, or
source. Do not create a numerical claim that cannot be traced to an artefact.

## 1. Industry problem and research questions

State the Smart Facilities SA monitoring problem and define normal-pattern
discovery, anomalous behaviour, and actionable event outputs.

## 2. Data provenance, ethics, and scope

Describe the RBC controlled HVAC dataset, manifest `[run/data_manifest.json]`,
privacy handling, and exclusions. State that the access-control example is an
architectural demonstration only.

## 3. Method

Describe preprocessing, feature policies, paired-safe holdouts, validation-only
candidate/threshold selection, normal modes, event policy, and saved artefacts.

## 4. Results

For each claim cite a run ID and table: model comparison `[model_comparison.csv]`,
uncertainty `[metrics_summary.csv]`, fault breakdown `[metrics_by_fault_group.csv]`,
normal modes `[normal_mode_quality.json]`, and events `[events/events.csv]`.

## 5. Operational interpretation

Use selected case studies from `[events/event_case_studies.csv]`; explain
priority components and recommended actions, not just model scores.

## 6. Limitations and recommendations

Prominently state controlled faults, one facility, scenario labels rather than
onset labels, limited real modalities, no live deployment, and any incomplete
headline experiments. Recommend validation with approved operational data.

## Appendix: reproducibility

List setup command, audit command, each experiment/config/run ID, manifest,
environment, feature list, model settings, and the result of `sfsa report-qa`.
