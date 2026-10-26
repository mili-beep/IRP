# Submission reproducibility checklist

- [ ] Create a clean virtual environment and install `.[quality]`.
- [ ] Run `python -m pytest -q` and `python -m ruff check .`.
- [ ] Audit the raw RBC data and save a manifest.
- [ ] Run each required headline experiment without `max_folds`.
- [ ] Run Phase 4 normal-mode discovery and Phase 5 events for selected runs.
- [ ] Build the dashboard and regenerate figures from saved artefacts.
- [ ] Run `sfsa report-qa --run-dir ...` for every cited benchmark.
- [ ] Record run IDs beside every report number, table, and figure.
- [ ] Confirm limitations and E08's demonstration-only status are stated.
