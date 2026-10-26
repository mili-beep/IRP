# Remaining phases: implementation plan

This document records the completion approach for Phases 5--8. It keeps
operational artefacts separate from model training so previous results remain
reproducible.

## Phase 5: operational events

- Read only saved `predictions.csv` and optional Phase 3/4 artefacts.
- Group adjacent alerts within the same model, fold, date, and scenario using a
  configured gap tolerance and minimum active-row count.
- Save an auditable event table, selected case studies, and a summary in a
  derived `events/` directory below the source run.
- Use a transparent priority formula with separately saved severity,
  persistence, confidence, and asset-criticality components. It is a policy,
  not a learned risk score.

## Phase 6: cross-domain architecture

- Use the generic-schema fallback because no approved second Smart Facilities
  dataset is present in this repository.
- Provide a small synthetic access-control example solely to exercise the
  adapter and audit. It is labelled demonstration data everywhere.
- Validate canonical required fields and timestamps before writing records.

## Phase 7: investigation view

- Generate static HTML and PNG evidence from saved artefacts only; no dashboard
  retrains models or accesses raw data.
- Provide model and priority filters in the HTML table, plus visible evidence
  limitations and source-artifact names.

## Phase 8: research QA

- Provide a report template and reproducibility checklist instead of inventing
  final numerical findings before all headline experiments have been run.
- Check a selected run for manifest acceptance, required provenance, consistent
  models, saved thresholds, candidate selection, and diagnostic-only settings.
- Treat warnings as report-review items rather than hiding them.
