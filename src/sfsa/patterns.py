"""Reproducible normal-operation profiles and operating-mode discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from .config import resolve_run_config
from .data.manifest import build_real_manifest
from .features import (
	add_physics_features,
    classify_columns,
    fit_numeric_imputer,
    select_feature_columns,
    transform_numeric_features,
)
from .training import _load_tables, _make_run_dir, _project_root_from_config
from .utils import capture_environment, set_seed, write_json


def _occupancy_window(timestamps: pd.Series, occupied_hours: dict[str, Any]) -> pd.Series:
    start = pd.to_datetime(occupied_hours["start"], format="%H:%M").time()
    end = pd.to_datetime(occupied_hours["end"], format="%H:%M").time()
    times = timestamps.dt.time
    occupied = (times >= start) & (times <= end) if start <= end else (times >= start) | (times <= end)
    return np.where(occupied, "occupied", "unoccupied")


def baseline_time_profile(
    baseline: pd.DataFrame, features: list[str], occupied_hours: dict[str, Any]
) -> pd.DataFrame:
    """Summarise normal observations by season, hour, and stated occupancy window."""
    profile = baseline[["timestamp", "season", *features]].copy()
    profile["hour"] = profile["timestamp"].dt.hour
    profile["occupancy_window"] = _occupancy_window(profile["timestamp"], occupied_hours)
    grouped = profile.groupby(["season", "hour", "occupancy_window"], dropna=False)[features]
    result = pd.concat([
        grouped.size().rename("rows"),
        grouped.mean().add_suffix("__mean"),
        grouped.median().add_suffix("__median"),
        grouped.std().add_suffix("__std"),
    ], axis=1).reset_index()
    return result.sort_values(["season", "hour", "occupancy_window"]).reset_index(drop=True)


def _sample_indices(length: int, limit: int, rng: np.random.Generator) -> np.ndarray:
    return rng.choice(length, size=min(length, limit), replace=False)


def _mode_quality(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    clusters: int,
    seed: int,
    silhouette_sample_rows: int,
    stability_sample_rows: int,
    stability_repeats: int,
) -> dict[str, float | int | None]:
    """Measure cluster separation and repeatability on deterministic samples."""
    rng = np.random.default_rng(seed)
    silhouette_indices = _sample_indices(len(features), silhouette_sample_rows, rng)
    silhouette = silhouette_score(features[silhouette_indices], labels[silhouette_indices])
    evaluation_indices = _sample_indices(len(features), stability_sample_rows, rng)
    repeat_labels: list[np.ndarray] = []
    for repeat in range(stability_repeats):
        train_indices = _sample_indices(len(features), stability_sample_rows, rng)
        model = KMeans(n_clusters=clusters, n_init=10, random_state=seed + repeat + 1)
        model.fit(features[train_indices])
        repeat_labels.append(model.predict(features[evaluation_indices]))
    aris = [
        adjusted_rand_score(first, second)
        for index, first in enumerate(repeat_labels)
        for second in repeat_labels[index + 1 :]
    ]
    return {
        "silhouette_score": float(silhouette),
        "silhouette_sample_rows": int(len(silhouette_indices)),
        "stability_ari_mean": float(np.mean(aris)) if aris else None,
        "stability_repeats": stability_repeats,
    }


def fit_normal_modes(
    baseline: pd.DataFrame,
    all_observations: pd.DataFrame,
    features: list[str],
    *,
    clusters: int,
    seed: int,
    silhouette_sample_rows: int,
    stability_sample_rows: int,
    stability_repeats: int,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Fit normal-only modes and compare each controlled-fault row to its nearest mode."""
    if clusters < 2:
        raise ValueError("normal_modes.clusters must be at least 2")
    if len(baseline) < clusters:
        raise ValueError("Not enough baseline observations for requested normal modes")
    imputer = fit_numeric_imputer(baseline, features)
    normal_values = transform_numeric_features(baseline, features, imputer)
    all_values = transform_numeric_features(all_observations, features, imputer)
    scaler = StandardScaler().fit(normal_values)
    normal_x = scaler.transform(normal_values)
    all_x = scaler.transform(all_values)
    model = KMeans(n_clusters=clusters, n_init=10, random_state=seed).fit(normal_x)
    pca = PCA(n_components=2, random_state=seed).fit(normal_x)
    normal_labels = model.labels_
    all_distances = model.transform(all_x)
    all_labels = all_distances.argmin(axis=1)

    assignment_columns = ["timestamp", "season", "date_folder", "scenario_file"]
    assignments = baseline[assignment_columns].copy()
    assignments["hour"] = assignments["timestamp"].dt.hour
    assignments["normal_mode"] = normal_labels
    assignments["mode_distance"] = model.transform(normal_x).min(axis=1)
    assignments[["pca_1", "pca_2"]] = pca.transform(normal_x)

    counts = pd.Series(normal_labels).value_counts().sort_index()
    centres_raw = scaler.inverse_transform(model.cluster_centers_)
    catalogue = pd.DataFrame({
        "normal_mode": range(clusters),
        "baseline_rows": [int(counts.get(mode, 0)) for mode in range(clusters)],
        "baseline_share": [float(counts.get(mode, 0) / len(baseline)) for mode in range(clusters)],
        "mean_mode_distance": [
            float(assignments.loc[assignments["normal_mode"] == mode, "mode_distance"].mean())
            for mode in range(clusters)
        ],
    })
    feature_profiles = pd.DataFrame({
        "normal_mode": np.repeat(np.arange(clusters), len(features)),
        "feature": features * clusters,
        "centre_raw_value": centres_raw.reshape(-1),
        "centre_standardised_value": model.cluster_centers_.reshape(-1),
    })

    comparisons = all_observations.loc[
        all_observations["is_fault"].astype(bool), assignment_columns + ["fault_type", "fault_intensity"]
    ].copy()
    fault_indices = np.flatnonzero(all_observations["is_fault"].astype(bool).to_numpy())
    comparisons["nearest_normal_mode"] = all_labels[fault_indices]
    comparisons["mode_distance"] = all_distances[fault_indices].min(axis=1)
    differences = all_x[fault_indices] - model.cluster_centers_[all_labels[fault_indices]]
    comparisons["top_mode_deviations"] = [
        " | ".join(
            f"{features[index]}={row[index]:.3f}"
            for index in np.argsort(np.abs(row))[::-1][:5]
        )
        for row in differences
    ]
    quality = _mode_quality(
        normal_x,
        normal_labels,
        clusters=clusters,
        seed=seed,
        silhouette_sample_rows=silhouette_sample_rows,
        stability_sample_rows=stability_sample_rows,
        stability_repeats=stability_repeats,
    )
    quality.update({
        "normal_observations": len(baseline),
        "controlled_fault_observations": len(comparisons),
        "feature_count": len(features),
        "clusters": clusters,
        "pca_explained_variance_ratio": [float(value) for value in pca.explained_variance_ratio_],
    })
    fitted = {"imputer": imputer, "scaler": scaler, "kmeans": model, "pca": pca, "feature_columns": features}
    return fitted, assignments, catalogue, feature_profiles, comparisons, quality


def _write_figures(assignments: pd.DataFrame, mode_by_hour: pd.DataFrame, figures_dir: Path) -> None:
    """Create two report-ready normal-mode figures without notebook-only code."""
    import os

    cache_dir = figures_dir / ".matplotlib_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)
    sampled = assignments.sample(n=min(5000, len(assignments)), random_state=42)
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(sampled["pca_1"], sampled["pca_2"], c=sampled["normal_mode"], s=4, alpha=0.45)
    ax.set(title="Normal operating modes (PCA projection)", xlabel="Principal component 1", ylabel="Principal component 2")
    fig.colorbar(scatter, ax=ax, label="Normal mode")
    fig.tight_layout()
    fig.savefig(figures_dir / "normal_modes_pca.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for mode, group in mode_by_hour.groupby("normal_mode"):
        ax.plot(group["hour"], group["share"], marker="o", label=f"Mode {mode}")
    ax.set(title="Normal-mode prevalence by hour", xlabel="Hour of day", ylabel="Share of baseline observations")
    ax.set_xticks(range(0, 24, 2))
    ax.legend(title="Normal mode")
    fig.tight_layout()
    fig.savefig(figures_dir / "normal_modes_by_hour.png", dpi=180)
    plt.close(fig)


def run_pattern_discovery(
    building_config: str | Path,
    experiment_config: str | Path,
    *,
    results_root: str | Path = "results/runs",
    override_values: list[str] | None = None,
    allow_audit_failures: bool = False,
) -> Path:
    """Create one immutable normal-operation analysis run from real RBC data."""
    bundle = resolve_run_config(building_config, experiment_config, override_values=override_values or [])
    resolved = bundle["resolved"]
    if resolved.get("source_type") != "real":
        raise ValueError("Pattern discovery currently supports source_type=real")
    project_root = _project_root_from_config(building_config)
    data_root = Path(resolved["data_path"])
    if not data_root.is_absolute():
        data_root = project_root / data_root
    manifest = build_real_manifest(data_root)
    if not manifest["validation"]["accepted"] and not allow_audit_failures:
        raise ValueError(f"Dataset audit failed: {'; '.join(manifest['validation']['blockers'])}")
    seed = int(resolved.get("seed", 42))
    set_seed(seed)
    baseline, faults = _load_tables(data_root, include_weather=bool(resolved["include_weather"]))
    physics = resolved.get("physics_features", {})
    if physics.get("enabled", False):
        baseline = add_physics_features(
            baseline,
            include_control_relationships=bool(physics.get("include_control_relationships", False)),
        )
        faults = add_physics_features(
            faults,
            include_control_relationships=bool(physics.get("include_control_relationships", False)),
        )
    groups = classify_columns(baseline.columns)
    selected = select_feature_columns(
        groups,
        resolved["feature_policy"],
        include_weather=bool(resolved["include_weather"]),
        include_vav=bool(resolved["include_vav"]),
        include_physics=bool(resolved.get("physics_features", {}).get("enabled", False)),
    )
    features = [column for column in selected if pd.api.types.is_numeric_dtype(baseline[column])]
    if not features:
        raise ValueError("No numeric features available for normal-mode analysis")
    settings = resolved.get("normal_modes", {})
    profile = baseline_time_profile(baseline, features, resolved["occupied_hours"])
    fitted, assignments, catalogue, feature_profiles, comparisons, quality = fit_normal_modes(
        baseline,
        pd.concat([baseline, faults], ignore_index=True),
        features,
        clusters=int(settings.get("clusters", 4)),
        seed=seed,
        silhouette_sample_rows=int(settings.get("silhouette_sample_rows", 2000)),
        stability_sample_rows=int(settings.get("stability_sample_rows", 5000)),
        stability_repeats=int(settings.get("stability_repeats", 2)),
    )
    mode_by_hour = assignments.groupby(["normal_mode", "hour"]).size().rename("rows").reset_index()
    mode_by_hour["share"] = mode_by_hour["rows"] / mode_by_hour.groupby("hour")["rows"].transform("sum")
    run_dir = _make_run_dir(Path(results_root), bundle["building"]["name"], bundle["experiment"]["name"])
    write_json(run_dir / "data_manifest.json", manifest)
    write_json(run_dir / "environment.json", capture_environment(project_root))
    write_json(run_dir / "config.resolved.json", {**bundle, "runtime": {"allow_audit_failures": allow_audit_failures}})
    write_json(run_dir / "normal_mode_quality.json", quality)
    write_json(run_dir / "features.json", {"policy": resolved["feature_policy"], "columns": features})
    profile.to_csv(run_dir / "baseline_profile_by_time.csv", index=False)
    assignments.to_csv(run_dir / "normal_mode_assignments.csv", index=False)
    catalogue.to_csv(run_dir / "normal_mode_catalogue.csv", index=False)
    feature_profiles.to_csv(run_dir / "normal_mode_feature_profiles.csv", index=False)
    comparisons.to_csv(run_dir / "fault_mode_comparisons.csv", index=False)
    mode_by_hour.to_csv(run_dir / "normal_mode_by_hour.csv", index=False)
    _write_figures(assignments, mode_by_hour, run_dir / "figures")
    import joblib

    joblib.dump(fitted, run_dir / "normal_mode_model.joblib")
    return run_dir
