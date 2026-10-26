from pathlib import Path

import pandas as pd
import pytest

from sfsa.data.manifest import build_real_manifest
from sfsa.data.rbc_ashrae1312 import parse_scenario_filename, validate_timestamps

ROOT = Path(__file__).parents[1]
REAL_ROOT = ROOT / "data" / "raw" / "01_RBC-ASHRAE1312" / "Real"


def test_real_manifest_contains_checksums_and_schema():
    manifest = build_real_manifest(REAL_ROOT)
    assert manifest["file_count"] == 98
    assert manifest["fault_file_count"] == 49
    assert all(len(item["sha256"]) == 64 for item in manifest["files"])
    assert all(item["columns"] for item in manifest["files"])
    assert [item["name"] for item in manifest["reference_files"]] == [
        "00_explanations.pdf",
        "FeaturesNames.xls",
    ]
    assert all(item["present"] for item in manifest["reference_files"])
    assert all(len(item["sha256"]) == 64 for item in manifest["reference_files"])
    assert manifest["validation"]["accepted"]
    assert manifest["validation"]["schema_variants"] == 1
    assert not manifest["validation"]["timestamp_issue_files"]


def test_unknown_fault_filename_fails_loudly():
    with pytest.raises(ValueError, match="Unknown RBC fault"):
        parse_scenario_filename(
            "InventedFault_1.csv",
            season="Summer",
            date_folder="20070820",
            weather_file=None,
        )


def test_timestamp_audit_reports_minute_gap():
    frame = pd.DataFrame({"DATE": [8202007, 8202007, 8202007], "TIME": [0, 1, 3]})
    quality = validate_timestamps(frame)
    assert quality["modal_cadence_seconds"] == 60.0
    assert quality["non_minute_intervals"] == 1
