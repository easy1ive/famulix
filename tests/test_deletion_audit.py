"""Test deletion audit trail."""

from famulix.deletion_audit import DeletionAuditEntry, DeletionAuditLog


def test_deletion_audit_records():
    log = DeletionAuditLog()

    entry = DeletionAuditEntry(
        timestamp_s=1000,
        node_id="n1",
        node_kind="fact",
        reason="user_request",
        cascaded_to=["n2", "n3"],
        tombstone_id="t1",
    )

    log.record(entry)

    assert log.count() == 1
    assert log.entries[0].node_id == "n1"


def test_deletion_audit_by_kind():
    log = DeletionAuditLog()

    log.record(DeletionAuditEntry(1000, "n1", "fact", "user_request"))
    log.record(DeletionAuditEntry(1001, "n2", "fact", "user_request"))
    log.record(DeletionAuditEntry(1002, "n3", "episode", "user_request"))

    counts = log.by_kind()

    assert counts["fact"] == 2
    assert counts["episode"] == 1


def test_deletion_audit_to_dict():
    entry = DeletionAuditEntry(
        timestamp_s=1000,
        node_id="n1",
        node_kind="fact",
        reason="user_request",
        cascaded_to=["n2"],
        tombstone_id="t1",
    )

    d = entry.to_dict()

    assert d["timestamp_s"] == 1000
    assert d["node_id"] == "n1"
    assert d["cascaded_to"] == ["n2"]
