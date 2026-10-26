"""Classical anomaly detectors."""

from sklearn.ensemble import IsolationForest
from sklearn.kernel_approximation import Nystroem
from sklearn.linear_model import SGDOneClassSVM
from sklearn.pipeline import make_pipeline


def isolation_forest(*, contamination: float = 0.1, seed: int = 42) -> IsolationForest:
	"""Create a reproducible Isolation Forest detector."""
	return IsolationForest(contamination=contamination, random_state=seed, n_jobs=1)


def one_class_svm(*, nu: float = 0.1, components: int = 100, seed: int = 42):
	"""Create a scalable RBF approximation plus one-class SGD detector."""
	return make_pipeline(
		Nystroem(kernel="rbf", n_components=components, random_state=seed),
		SGDOneClassSVM(nu=nu, random_state=seed),
	)
