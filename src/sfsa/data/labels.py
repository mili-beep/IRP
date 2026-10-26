"""Label validation and normal/fault mapping contracts."""

import pandas as pd


def normal_mask(labels: pd.Series, normal_label: str) -> pd.Series:
    """Return rows matching the configured normal label."""
    return labels.astype(str).str.casefold().eq(normal_label.casefold())
