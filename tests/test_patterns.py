import pandas as pd

from sfsa.patterns import baseline_time_profile, fit_normal_modes


def _observations() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01 05:00", periods=12, freq="h")
    return pd.DataFrame({
        "timestamp": timestamps,
        "season": ["Summer"] * 12,
        "date_folder": ["20240101"] * 12,
        "scenario_file": ["baseline.csv"] * 8 + ["fault.csv"] * 4,
        "fault_type": [None] * 8 + ["fan"] * 4,
        "fault_intensity": [None] * 8 + ["10"] * 4,
        "is_fault": [False] * 8 + [True] * 4,
        "temperature": [20.0, 20.1, 19.9, 20.2, 30.0, 30.1, 29.9, 30.2, 35.0, 35.2, 34.9, 35.1],
        "flow": [1.0, 1.1, 0.9, 1.0, 5.0, 5.1, 4.9, 5.0, 8.0, 8.1, 7.9, 8.0],
    })


def test_baseline_profile_and_normal_modes_are_reportable():
    observations = _observations()
    baseline = observations.loc[~observations["is_fault"]].copy()
    profile = baseline_time_profile(
        baseline, ["temperature", "flow"], {"start": "06:00", "end": "18:00"}
    )
    assert {"occupancy_window", "temperature__mean", "flow__median"}.issubset(profile.columns)
    assert set(profile["occupancy_window"]) == {"occupied", "unoccupied"}

    _, assignments, catalogue, feature_profiles, comparisons, quality = fit_normal_modes(
        baseline,
        observations,
        ["temperature", "flow"],
        clusters=2,
        seed=42,
        silhouette_sample_rows=8,
        stability_sample_rows=8,
        stability_repeats=2,
    )
    assert len(assignments) == len(baseline)
    assert len(catalogue) == 2
    assert len(feature_profiles) == 4
    assert len(comparisons) == 4
    assert comparisons["top_mode_deviations"].str.contains("temperature").all()
    assert -1 <= quality["silhouette_score"] <= 1
    assert -1 <= quality["stability_ari_mean"] <= 1
