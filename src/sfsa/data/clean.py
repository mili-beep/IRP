"""Data validation and cleaning contracts."""

import pandas as pd
from pandas.api.types import is_numeric_dtype

from sfsa.features import missingness_report


def coerce_numeric_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Copy a frame and coerce numeric-looking object columns safely."""
    cleaned = frame.copy()
    for column in cleaned.columns:
        if is_numeric_dtype(cleaned[column]):
            continue
        converted = pd.to_numeric(cleaned[column].astype(str).str.strip(), errors="coerce")
        if converted.notna().sum() >= cleaned[column].notna().sum() * 0.95:
            cleaned[column] = converted
    return cleaned


def validate_numeric_columns(frame: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Report numeric missingness without filling or changing the input."""
    selected = columns or [column for column in frame.columns if is_numeric_dtype(frame[column])]
    return missingness_report(frame[selected])
