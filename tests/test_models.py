import numpy as np

from sfsa.models import xgboost_classifier


def test_xgboost_factory_fits_binary_and_multiclass_labels():
    features = np.array([[0.0], [0.1], [0.9], [1.0], [2.0], [2.1]])
    binary = xgboost_classifier(seed=42).fit(features, np.array([0, 0, 1, 1, 1, 1]))
    multiclass = xgboost_classifier(seed=42).fit(features, np.array([0, 0, 1, 1, 2, 2]))
    assert binary.predict_proba(features).shape == (6, 2)
    assert multiclass.predict_proba(features).shape == (6, 3)
