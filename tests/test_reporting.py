import pandas as pd

from sfsa.reporting import build_investigation_view


def test_dashboard_is_generated_from_saved_artefacts_without_events(tmp_path):
    pd.DataFrame({"model": ["statistical"], "f1": [0.5]}).to_csv(tmp_path / "metrics.csv", index=False)
    output = build_investigation_view(tmp_path)
    page = output.read_text()
    assert "Smart Facilities investigation view" in page
    assert "No event artefact exists yet" in page
    assert (tmp_path / "dashboard" / "dashboard_manifest.json").exists()
