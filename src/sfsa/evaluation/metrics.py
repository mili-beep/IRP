"""Row-level and event-level evaluation metric contracts."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def metric_names() -> tuple[str, ...]:
    """Return the required binary detection metrics."""
    return ("f1", "precision", "recall", "fpr")


def event_metrics(
    frame: pd.DataFrame,
    predictions: Iterable[int],
    *,
    event_column: str = "scenario_file",
    timestamp_column: str = "timestamp",
    normal_value: str = "baseline.csv",
	label_column: str = "is_fault",
) -> dict[str, float | int]:
    """Summarize event recall, detection delay, and false alarms per day.

    Scenario files define evaluation events. Since onset is not inferred, delay is
    measured from the first timestamp in each non-normal scenario.
    """
    predictions = np.asarray(list(predictions), dtype=int)
    if len(frame) != len(predictions):
        raise ValueError("frame and predictions must have equal length")
    required = {event_column, timestamp_column}
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(sorted(missing)[0])
    columns = [event_column, timestamp_column]
    if label_column in frame.columns:
        columns.append(label_column)
    work = frame[columns].copy()
    work["prediction"] = predictions
    work = work.sort_values([event_column, timestamp_column])
    if label_column in work.columns:
        fault_events = work.loc[work[label_column].astype(bool), event_column].dropna().unique().tolist()
        normal = work[~work[label_column].astype(bool)]
    else:
        fault_events = [name for name in work[event_column].dropna().unique() if name != normal_value]
        normal = work[work[event_column] == normal_value]
    detected = 0
    delays: list[float] = []
    for _, event in work[work[event_column].isin(fault_events)].groupby(event_column, sort=False):
        positives = event[event["prediction"] == 1]
        if positives.empty:
            continue
        detected += 1
        delay = positives[timestamp_column].iloc[0] - event[timestamp_column].iloc[0]
        delays.append(delay.total_seconds() / 60)
    normal_days = int(normal[timestamp_column].dt.normalize().nunique()) if not normal.empty else 1
    false_alarms = int((normal["prediction"] == 1).sum())
    return {
        "events": len(fault_events),
        "detected_events": detected,
        "event_recall": detected / len(fault_events) if fault_events else 0.0,
        "mean_detection_delay_minutes": float(np.mean(delays)) if delays else float("nan"),
        "false_alarms_per_day": false_alarms / normal_days,
    }
