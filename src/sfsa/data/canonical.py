"""Canonical records for cross-domain facilities-log demonstrations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

CANONICAL_COLUMNS = [
    "timestamp", "source_system", "asset_id", "event_type", "measurements", "status", "provenance",
]


def access_control_to_canonical(frame: pd.DataFrame, *, provenance: str) -> pd.DataFrame:
    """Adapt a small access-control log to the generic facilities record contract."""
    required = {"timestamp", "door_id", "event", "status"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Access-control input is missing columns: {sorted(missing)}")
    result = pd.DataFrame({
        "timestamp": pd.to_datetime(frame["timestamp"], errors="coerce"),
        "source_system": "access_control",
        "asset_id": frame["door_id"].astype(str),
        "event_type": frame["event"].astype(str),
        "measurements": frame.get("measurements", pd.Series("{}", index=frame.index)).fillna("{}").astype(str),
        "status": frame["status"].astype(str),
        "provenance": provenance,
    })
    return result[CANONICAL_COLUMNS]


def audit_canonical_records(frame: pd.DataFrame) -> dict[str, Any]:
    """Validate canonical required fields and report basic timestamp quality."""
    missing_columns = sorted(set(CANONICAL_COLUMNS) - set(frame.columns))
    work = frame.copy()
    if "timestamp" in work:
        work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    null_fields = {
        column: int(work[column].isna().sum()) if column in work else len(work)
        for column in CANONICAL_COLUMNS
    }
    blockers = []
    if missing_columns:
        blockers.append(f"missing required columns: {', '.join(missing_columns)}")
    if null_fields.get("timestamp", 0):
        blockers.append("unparseable or missing timestamps")
    for column in ("source_system", "asset_id", "event_type", "status", "provenance"):
        if null_fields.get(column, 0):
            blockers.append(f"missing required values in {column}")
    return {
        "accepted": not blockers,
        "blockers": blockers,
        "rows": len(work),
        "null_fields": null_fields,
        "source_systems": sorted(work["source_system"].dropna().astype(str).unique().tolist()) if "source_system" in work else [],
        "assets": int(work["asset_id"].nunique()) if "asset_id" in work else 0,
        "timestamp_start": str(work["timestamp"].min()) if "timestamp" in work and work["timestamp"].notna().any() else None,
        "timestamp_end": str(work["timestamp"].max()) if "timestamp" in work and work["timestamp"].notna().any() else None,
    }


def canonicalise_access_file(input_path: str | Path, output_dir: str | Path) -> tuple[Path, Path]:
    """Write canonical records and an audit beside an explicit demonstration input."""
    source = Path(input_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    canonical = access_control_to_canonical(pd.read_csv(source), provenance=f"demonstration:{source.name}")
    audit = audit_canonical_records(canonical)
    records_path = output / "canonical_records.csv"
    audit_path = output / "canonical_audit.json"
    canonical.to_csv(records_path, index=False)
    from ..utils import write_json

    write_json(audit_path, audit)
    return records_path, audit_path
