import pandas as pd

from sfsa.data.canonical import access_control_to_canonical, audit_canonical_records


def test_access_control_adapter_emits_auditable_canonical_records():
    source = pd.DataFrame({
        "timestamp": ["2026-01-01T10:00:00"],
        "door_id": ["Door-A"],
        "event": ["access_granted"],
        "status": ["normal"],
    })
    canonical = access_control_to_canonical(source, provenance="demonstration:test")
    audit = audit_canonical_records(canonical)
    assert audit["accepted"] is True
    assert canonical.loc[0, "source_system"] == "access_control"


def test_canonical_audit_rejects_unparseable_timestamp():
    source = pd.DataFrame({
        "timestamp": ["not-a-time"], "door_id": ["Door-A"], "event": ["access_denied"], "status": ["warning"],
    })
    assert audit_canonical_records(access_control_to_canonical(source, provenance="demo"))["accepted"] is False
