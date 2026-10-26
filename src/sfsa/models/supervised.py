"""Supervised model implementations."""

from sklearn.ensemble import (
	HistGradientBoostingClassifier,
)
from xgboost import XGBClassifier


def gradient_boosting(*, seed: int = 42) -> HistGradientBoostingClassifier:
	"""Create the supervised histogram-gradient-boosting classifier."""
	return HistGradientBoostingClassifier(random_state=seed)


def xgboost_classifier(*, seed: int = 42, **parameters: object) -> XGBClassifier:
	"""Create the fixed XGBoost classifier used by the primary studies."""
	return XGBClassifier(
		n_estimators=100,
		max_depth=6,
		learning_rate=0.05,
		subsample=0.8,
		colsample_bytree=0.8,
		tree_method="hist",
		n_jobs=1,
		random_state=seed,
		eval_metric="mlogloss",
		verbosity=0,
		**parameters,
	)
