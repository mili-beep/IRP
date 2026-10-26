"""Supervised model implementations."""

from sklearn.ensemble import (
	HistGradientBoostingClassifier,
	HistGradientBoostingRegressor,
)


def gradient_boosting(*, seed: int = 42) -> HistGradientBoostingClassifier:
	"""Create the supervised histogram-gradient-boosting classifier."""
	return HistGradientBoostingClassifier(random_state=seed)


def gradient_boosting_regressor(*, seed: int = 42) -> HistGradientBoostingRegressor:
	"""Create the conditional, within-family fault-intensity regressor."""
	return HistGradientBoostingRegressor(random_state=seed)
