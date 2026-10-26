"""Statistical anomaly baseline."""

from __future__ import annotations

import numpy as np


class ZScoreModel:
	"""Flag a row when its largest absolute standardized value is unusual."""

	def __init__(self, contamination: float = 0.1) -> None:
		if not 0 < contamination < 1:
			raise ValueError("contamination must be between 0 and 1")
		self.contamination = contamination
		self.threshold_: float | None = None

	def fit(self, features: np.ndarray) -> "ZScoreModel":
		scores = np.max(np.abs(features), axis=1)
		self.threshold_ = float(np.quantile(scores, 1 - self.contamination))
		return self

	def predict(self, features: np.ndarray) -> np.ndarray:
		if self.threshold_ is None:
			raise RuntimeError("Model must be fitted before predict")
		scores = self.score_samples(features)
		return (scores > self.threshold_).astype(int)

	def score_samples(self, features: np.ndarray) -> np.ndarray:
		"""Return larger values for observations farther from the normal baseline."""
		return np.max(np.abs(features), axis=1)
