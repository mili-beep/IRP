"""Shared model protocol contracts."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class AnomalyModel(Protocol):
	"""Minimal interface required by the benchmark runner."""

	def fit(self, features: np.ndarray) -> "AnomalyModel": ...

	def predict(self, features: np.ndarray) -> np.ndarray: ...
