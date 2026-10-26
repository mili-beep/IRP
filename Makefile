PYTHON ?= python3

.PHONY: sync test lint format check cli

sync:
	$(PYTHON) -m pip install -e ".[quality]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

check: lint test

cli:
	$(PYTHON) -m sfsa.cli --help
	$(PYTHON) -m sfsa.cli run-info --config configs/buildings/auditorium.yaml
