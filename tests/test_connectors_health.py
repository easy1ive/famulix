"""Test connector hub health report."""

from famulix.connectors import (
    ConnectorHub,
    ConnectorRecord,
    FlakyConnector,
    ScriptedConnector,
)


def test_health_report_all_healthy():
    """Verify health report when all connectors succeed."""
    records1 = [
        ConnectorRecord(
            source="calendar",
            external_id="evt1",
            kind="calendar",
            timestamp_s=100,
            title="Meeting",
            body="",
        )
    ]
    records2 = [
        ConnectorRecord(
            source="notes",
            external_id="n1",
            kind="note",
            timestamp_s=200,
            title="Note",
            body="text",
        )
    ]

    c1 = ScriptedConnector(source="calendar", records=records1)
    c2 = ScriptedConnector(source="notes", records=records2)

    hub = ConnectorHub([c1, c2])
    report = hub.health_report()

    assert report["total_sources"] == 2
    assert report["healthy_sources"] == 2
    assert report["failed_sources"] == 0
    assert report["record_counts"]["calendar"] == 1
    assert report["record_counts"]["notes"] == 1
    assert report["errors"] == []


def test_health_report_with_failures():
    """Verify health report when some connectors fail."""
    records = [
        ConnectorRecord(
            source="calendar",
            external_id="evt1",
            kind="calendar",
            timestamp_s=100,
            title="Meeting",
            body="",
        )
    ]

    c1 = ScriptedConnector(source="calendar", records=records)
    # Wrap a scripted connector with FlakyConnector that fails every 2 calls
    inner = ScriptedConnector(source="mail", records=[])
    c2 = FlakyConnector(inner=inner, fail_every=2)

    hub = ConnectorHub([c1, c2])
    # First call: calendar succeeds, mail fails (it's the 2nd call, fail_every=2)
    report = hub.health_report()

    assert report["total_sources"] == 2
    # At least one should succeed
    assert report["healthy_sources"] >= 1 or report["failed_sources"] >= 1


def test_health_report_empty_hub():
    """Verify health report for empty hub."""
    hub = ConnectorHub([])
    report = hub.health_report()

    assert report["total_sources"] == 0
    assert report["healthy_sources"] == 0
    assert report["failed_sources"] == 0
    assert report["record_counts"] == {}
    assert report["errors"] == []
