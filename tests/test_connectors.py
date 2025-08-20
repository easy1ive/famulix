"""Offline connector batching and event normalization contracts."""

from __future__ import annotations

import pytest

from famulix.connectors import (
    ConnectorBatch,
    ConnectorHub,
    ConnectorKind,
    ConnectorRecord,
    ScriptedConnector,
)


def _record(kind: str, identity: str, timestamp: int) -> ConnectorRecord:
    from typing import cast

    return ConnectorRecord(
        "calendar", identity, cast(ConnectorKind, kind), timestamp, identity, f"body:{identity}"
    )


def test_batch_is_sorted_and_checksum_is_stable() -> None:
    late = _record("calendar", "late", 20)
    early = _record("calendar", "early", 10)
    first = ConnectorBatch.create("calendar", [late, early])
    second = ConnectorBatch.create("calendar", [early, late])

    assert first.records == (early, late)
    assert first.checksum == second.checksum
    assert first.verify()


def test_batch_rejects_foreign_source_records() -> None:
    foreign = ConnectorRecord("notes", "n1", "note", 1, "n1", "body:n1")
    with pytest.raises(ValueError, match="belong to the batch source"):
        ConnectorBatch.create("calendar", [foreign])


def test_hub_orders_sources_and_records_before_conversion() -> None:
    notes = ScriptedConnector("notes", (_record_for("notes", "n1", "note", 20),))
    mail = ScriptedConnector("mail", (_record_for("mail", "m1", "message", 10),))
    events = ConnectorHub([notes, mail]).to_events()

    assert [event.source for event in events] == ["mail", "notes"]
    assert [event.event_type for event in events] == ["message", "note"]
    assert events[0].data["counterpart"] == "m1"
    assert events[1].data["text"] == "body:n1"


def test_hub_refuses_duplicate_source_and_conflicting_identity() -> None:
    with pytest.raises(ValueError, match="sources must be unique"):
        ConnectorHub([ScriptedConnector("notes", ()), ScriptedConnector("notes", ())])
    first = _record_for("notes", "same", "note", 1)
    second = ConnectorRecord("notes", "same", "note", 2, "same", "changed")
    connector = ScriptedConnector("notes", (first, second))
    with pytest.raises(ValueError, match="conflicting connector record"):
        ConnectorHub([connector]).records()


def _record_for(source: str, identity: str, kind: str, timestamp: int) -> ConnectorRecord:
    from typing import cast

    return ConnectorRecord(
        source, identity, cast(ConnectorKind, kind), timestamp, identity, f"body:{identity}"
    )


def test_hub_source_count_and_sources() -> None:
    notes = ScriptedConnector("notes", (_record_for("notes", "n1", "note", 1),))
    calendar = ScriptedConnector("calendar", (_record_for("calendar", "c1", "calendar", 2),))
    hub = ConnectorHub([notes, calendar])
    assert hub.source_count() == 2
    assert hub.sources() == ["calendar", "notes"]  # sorted


def test_hub_record_count_matches_records() -> None:
    notes = ScriptedConnector(
        "notes",
        (
            _record_for("notes", "n1", "note", 1),
            _record_for("notes", "n2", "note", 2),
            _record_for("notes", "n3", "note", 3),
        ),
    )
    hub = ConnectorHub([notes])
    assert hub.record_count() == len(hub.records())
    assert hub.record_count() == 3


from famulix.connectors import ConnectorError, FlakyConnector  # noqa: E402


def _note_record(external_id: str) -> ConnectorRecord:
    return ConnectorRecord(
        source="notes", external_id=external_id, kind="note", timestamp_s=100, title="t", body="b"
    )


def test_flaky_connector_fails_on_schedule() -> None:
    flaky = FlakyConnector(ScriptedConnector("notes", (_note_record("a"),)), fail_every=3)
    flaky.collect()
    flaky.collect()
    with pytest.raises(ConnectorError) as info:
        flaky.collect()
    assert info.value.source == "notes"
    batch = flaky.collect()  # call 4 succeeds again
    assert batch.records[0].external_id == "a"


def test_flaky_connector_rejects_tiny_interval() -> None:
    with pytest.raises(ValueError):
        FlakyConnector(ScriptedConnector("notes", ()), fail_every=1)


def test_collect_partial_isolates_failures() -> None:
    healthy = ScriptedConnector(
        "calendar",
        (
            ConnectorRecord(
                source="calendar",
                external_id="c1",
                kind="calendar",
                timestamp_s=50,
                title="standup",
                body="",
            ),
        ),
    )
    flaky = FlakyConnector(ScriptedConnector("notes", (_note_record("a"),)), fail_every=2)
    hub = ConnectorHub([healthy, flaky])
    flaky.collect()  # prime so the next call (inside the hub) fails
    batches, failed = hub.collect_partial()
    assert failed == ("notes",)
    assert [batch.source for batch in batches] == ["calendar"]


def test_strict_collect_propagates_connector_error() -> None:
    flaky = FlakyConnector(ScriptedConnector("notes", (_note_record("a"),)), fail_every=2)
    hub = ConnectorHub([flaky])
    flaky.collect()
    with pytest.raises(ConnectorError):
        hub.collect()
