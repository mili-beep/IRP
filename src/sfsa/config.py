"""Configuration loading and deterministic composition for SFSA runs."""

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load one YAML mapping and fail clearly for non-mapping documents."""
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {config_path}")
    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge mappings recursively without modifying either input mapping."""
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def parse_overrides(values: Iterable[str]) -> dict[str, Any]:
    """Parse ``dotted.key=value`` command-line overrides using YAML values."""
    overrides: dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Expected KEY=VALUE override, got {value!r}")
        dotted_key, raw_value = value.split("=", 1)
        keys = [part for part in dotted_key.split(".") if part]
        if not keys:
            raise ValueError(f"Expected a non-empty override key, got {value!r}")
        target = overrides
        for key in keys[:-1]:
            existing = target.get(key)
            if existing is None:
                target[key] = {}
            elif not isinstance(existing, dict):
                raise ValueError(f"Conflicting override key: {dotted_key}")
            target = target[key]
        target[keys[-1]] = yaml.safe_load(raw_value)
    return overrides


def resolve_run_config(
    building_path: str | Path,
    experiment_path: str | Path,
    *,
    override_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Compose defaults, building, experiment, and explicit CLI overrides.

    Experiment files historically used ``features: symptom_only`` while
    building files use ``features`` as a mapping. The legacy experiment value is
    normalised to ``feature_policy`` before merging so building feature settings
    remain available.
    """
    building_config_path = Path(building_path)
    experiment_config_path = Path(experiment_path)
    defaults_path = building_config_path.parent.parent / "defaults.yaml"
    defaults = load_yaml(defaults_path)
    building = load_yaml(building_config_path)
    experiment = load_yaml(experiment_config_path)
    experiment_for_merge = deepcopy(experiment)
    legacy_policy = experiment_for_merge.get("features")
    if isinstance(legacy_policy, str):
        experiment_for_merge.pop("features")
        experiment_for_merge["feature_policy"] = legacy_policy

    overrides = parse_overrides(override_values)
    resolved = deep_merge(defaults, building)
    resolved = deep_merge(resolved, experiment_for_merge)
    resolved = deep_merge(resolved, overrides)

    feature_settings = resolved.get("features", {})
    if not isinstance(feature_settings, dict):
        raise ValueError("Resolved features settings must be a mapping")
    resolved.setdefault("feature_policy", feature_settings.get("default_policy", "symptom_only"))
    resolved.setdefault("include_weather", False)
    resolved.setdefault("include_vav", bool(feature_settings.get("include_vav", False)))
    resolved["temporal"] = deep_merge(
        feature_settings.get("temporal", {}), resolved.get("temporal", {})
    )

    return {
        "sources": {
            "defaults": str(defaults_path),
            "building": str(building_config_path),
            "experiment": str(experiment_config_path),
        },
        "defaults": defaults,
        "building": building,
        "experiment": experiment,
        "overrides": overrides,
        "resolved": resolved,
    }
