"""Machine-readable audit manifests for real RBC data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..utils import sha256_file
from .rbc_ashrae1312 import discover_real_files, validate_pairing, validate_timestamps


def _reference_files(dataset_root: Path) -> list[dict[str, Any]]:
    """Record the local documents that define the RBC source dataset."""
    references = ("00_explanations.pdf", "FeaturesNames.xls")
    files: list[dict[str, Any]] = []
    for name in references:
        path = dataset_root / name
        files.append({
            "name": name,
            "path": path.as_posix(),
            "present": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
            "sha256": sha256_file(path) if path.exists() else None,
        })
    return files


def validate_real_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Summarise audit checks that must pass before an accepted training run."""
    files = manifest["files"]
    schema_signatures = {tuple(item["columns"]) for item in files}
    pairing_issues = [
        item["scenario_file"]
        for item in manifest["pairings"]
        if not item["baseline_present"] or not item["timestamps_aligned"]
    ]
    timestamp_issues = [
        item["path"]
        for item in files
        if (
            quality := item.get("timestamp_quality", {})
        )
        and (
            quality.get("duplicate_timestamps", 0) > 0
            or quality.get("out_of_order_rows", 0) > 0
            or quality.get("non_minute_intervals", 0) > 0
        )
    ]
    missing_reference_files = [
        item["name"] for item in manifest["reference_files"] if not item["present"]
    ]
    blockers: list[str] = []
    if len(schema_signatures) != 1:
        blockers.append(f"inconsistent scenario schemas ({len(schema_signatures)} variants)")
    if pairing_issues:
        blockers.append(f"invalid baseline/fault pairs ({len(pairing_issues)})")
    if timestamp_issues:
        blockers.append(f"timestamp-quality failures ({len(timestamp_issues)})")
    if missing_reference_files:
        blockers.append(f"missing reference files ({', '.join(missing_reference_files)})")
    return {
        "accepted": not blockers,
        "blockers": blockers,
        "schema_variants": len(schema_signatures),
        "pairing_issue_files": pairing_issues,
        "timestamp_issue_files": timestamp_issues,
        "missing_reference_files": missing_reference_files,
        "files_with_missing_cells": sum(item["missing_cells"] > 0 for item in files),
        "total_missing_cells": sum(item["missing_cells"] for item in files),
    }


def build_real_manifest(data_root: str | Path) -> dict[str, Any]:
    """Audit every real CSV and return JSON-serializable metadata."""
    root = Path(data_root)
    records = discover_real_files(root)
    pairings = validate_pairing(root)
    files: list[dict[str, Any]] = []
    for record in records:
        path = root / record.season / record.date_folder / record.scenario_file
        frame = pd.read_csv(path)
        file_info = {
            **record.as_dict(),
            "path": path.as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "columns": list(frame.columns),
            "missing_cells": int(frame.isna().sum().sum()),
        }
        if {"DATE", "TIME"}.issubset(frame.columns):
            file_info["timestamp_quality"] = validate_timestamps(frame)
        files.append(file_info)
    manifest = {
        "dataset": "RBC-ASHRAE1312",
        "source_type": "real",
        "data_root": root.as_posix(),
        "file_count": len(files),
        "fault_file_count": sum(record.is_fault for record in records),
        "reference_files": _reference_files(root.parent),
        "pairings": pairings,
        "files": files,
    }
    manifest["validation"] = validate_real_manifest(manifest)
    return manifest
