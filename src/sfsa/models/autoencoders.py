"""Autoencoder model implementations."""

from __future__ import annotations

import numpy as np


def make_windows(
	values: np.ndarray,
	window: int,
	*,
	groups: np.ndarray | None = None,
) -> np.ndarray:
	"""Create contiguous windows without crossing group boundaries."""
	if window < 2:
		raise ValueError("window must be at least 2")
	if values.ndim != 2:
		raise ValueError("values must be a two-dimensional array")
	group_values = np.zeros(len(values), dtype=int) if groups is None else np.asarray(groups)
	if len(group_values) != len(values):
		raise ValueError("groups must align with values")
	windows = [
		values[start : start + window]
		for start in range(len(values) - window + 1)
		if len(set(group_values[start : start + window])) == 1
	]
	if not windows:
		return np.empty((0, window, values.shape[1]))
	return np.stack(windows)
