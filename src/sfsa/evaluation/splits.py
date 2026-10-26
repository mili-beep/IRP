"""Scenario-aware evaluation split contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class Split:
    """One train/test partition with its held-out group values."""

    train_index: pd.Index
    test_index: pd.Index
    held_out_groups: tuple[str, ...]
    policy: str


def leave_group_out(frame: pd.DataFrame, group_column: str, held_out: Iterable[str]) -> Split:
    """Hold out complete group values, preserving the original row indexes."""
    if group_column not in frame.columns:
        raise KeyError(group_column)
    held_out_values = tuple(str(value) for value in held_out)
    if not held_out_values:
        raise ValueError("At least one group must be held out")
    membership = frame[group_column].astype(str).isin(held_out_values)
    if not membership.any():
        raise ValueError(f"None of the requested groups exist in {group_column}")
    if membership.all():
        raise ValueError("The split cannot leave the entire dataset out")
    return Split(
        train_index=frame.index[~membership],
        test_index=frame.index[membership],
        held_out_groups=held_out_values,
        policy=f"leave_{group_column}_out",
    )


def leave_one_group_out(frame: pd.DataFrame, group_column: str) -> list[Split]:
    """Create one complete holdout split for every group value."""
    groups = frame[group_column].dropna().astype(str).drop_duplicates().tolist()
    return [leave_group_out(frame, group_column, [group]) for group in groups]


def paired_holdout_splits(frame: pd.DataFrame, policy: str) -> list[Split]:
    """Build complete paired-date holdouts for one declared evaluation policy.

    Every test fold includes both the fault rows and their same-date baseline
    rows. This prevents paired observations from appearing on opposing sides of
    a split even when the requested generalisation unit is a scenario, family,
    season, or intensity.
    """
    required = {"date_folder", "is_fault", "scenario_file", "fault_type", "fault_intensity", "season"}
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(sorted(missing)[0])
    if policy == "leave_date_out":
        held_out_sets = [(date,) for date in sorted(frame["date_folder"].astype(str).unique())]
    else:
        column_by_policy = {
            "leave_scenario_out": "scenario_file",
            "leave_fault_type_out": "fault_type",
            "leave_season_out": "season",
        }
        if policy not in column_by_policy:
            raise ValueError(f"Unknown split policy: {policy}")
        group_column = column_by_policy[policy]
        fault_rows = frame[frame["is_fault"].astype(bool)]
        held_out_sets = []
        for value, group in fault_rows.groupby(group_column, dropna=True, sort=True):
            dates = tuple(sorted(group["date_folder"].astype(str).unique()))
            if dates:
                held_out_sets.append(dates)

    splits: list[Split] = []
    for held_out_dates in held_out_sets:
        split = leave_group_out(frame, "date_folder", held_out_dates)
        splits.append(
            Split(
                train_index=split.train_index,
                test_index=split.test_index,
                held_out_groups=tuple(held_out_dates),
                policy=policy,
            )
        )
    if not splits:
        raise ValueError(f"Split policy produced no folds: {policy}")
    return splits


def select_validation_dates(
    frame: pd.DataFrame, train_index: pd.Index, *, fraction: float = 0.2
) -> tuple[pd.Index, pd.Index, tuple[str, ...]]:
    """Reserve complete trailing dates from one training fold for calibration."""
    if not 0 < fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")
    train_dates = sorted(frame.loc[train_index, "date_folder"].astype(str).unique())
    if len(train_dates) < 2:
        raise ValueError("At least two training dates are required for validation")
    validation_count = max(1, round(len(train_dates) * fraction))
    validation_count = min(validation_count, len(train_dates) - 1)
    validation_dates = tuple(train_dates[-validation_count:])
    validation_mask = frame.loc[train_index, "date_folder"].astype(str).isin(validation_dates)
    validation_index = train_index[validation_mask]
    fit_index = train_index[~validation_mask]
    return fit_index, validation_index, validation_dates


def assert_no_paired_timestamp_leakage(
    frame: pd.DataFrame,
    train_index: pd.Index,
    test_index: pd.Index,
    *,
    timestamp_column: str = "timestamp",
    pair_column: str = "date_folder",
) -> None:
    """Reject train/test rows sharing a timestamp within a pairing group."""
    required = {timestamp_column, pair_column}
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(sorted(missing)[0])
    train_keys = set(
        zip(frame.loc[train_index, pair_column], frame.loc[train_index, timestamp_column])
    )
    test_keys = set(
        zip(frame.loc[test_index, pair_column], frame.loc[test_index, timestamp_column])
    )
    overlap = train_keys & test_keys
    if overlap:
        raise ValueError(f"Paired timestamp leakage detected ({len(overlap)} overlapping keys)")
