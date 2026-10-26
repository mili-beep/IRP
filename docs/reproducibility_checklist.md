# Submission reproducibility requirements

Before making a release or reporting a result:

1. Create a clean virtual environment and install `.[quality]`.
2. Run `python -m pytest -q` and `python -m ruff check .`.
3. Audit the raw RBC data and save a manifest.
4. Use only complete-fold headline experiments without `max_folds`.
5. Record run IDs beside every report number, table, and figure.
6. State the controlled-fault, one-facility, and full-day-label limitations.
