"""Small, side-effect-free helpers for notebooks and reports."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_run_metrics(run_dir: str | Path) -> pd.DataFrame:
	"""Load metrics from a completed run and fail clearly if absent."""
	path = Path(run_dir) / "metrics.csv"
	if not path.exists():
		raise FileNotFoundError(f"Run metrics not found: {path}")
	return pd.read_csv(path)


def load_run_predictions(run_dir: str | Path) -> pd.DataFrame:
	"""Load saved predictions from a completed run."""
	path = Path(run_dir) / "predictions.csv"
	if not path.exists():
		raise FileNotFoundError(f"Run predictions not found: {path}")
	return pd.read_csv(path)


def load_run_config(run_dir: str | Path) -> dict:
	"""Load the resolved configuration stored with a run."""
	import json

	path = Path(run_dir) / "config.json"
	if not path.exists():
		raise FileNotFoundError(f"Run configuration not found: {path}")
	return json.loads(path.read_text(encoding="utf-8"))


def plot_metrics(metrics: pd.DataFrame, *, ax=None):
	"""Plot comparable binary metrics without choosing a notebook style."""
	import matplotlib.pyplot as plt

	if ax is None:
		_, ax = plt.subplots(figsize=(9, 5))
	plot_frame = metrics.set_index("model")[["f1", "precision", "recall", "fpr"]]
	plot_frame.plot(kind="bar", ax=ax)
	ax.set_ylim(0, 1)
	ax.set_ylabel("Score")
	ax.set_title("RBC-ASHRAE1312 real-data model metrics")
	return ax
