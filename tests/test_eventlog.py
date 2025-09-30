"""Tests for the append-only SQLite event log."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from famulix.eventlog import EventLog
from famulix.events import message_event, note_event


def test_append_and_count() -> None:
    with EventLog(":memory:") as log:
        assert log.count() == 0
        log.append(note_event(100, "s", "a"), inserted_at_s=100)
        assert log.count() == 1


def test_get_by_seq_and_id() -> None:
    with EventLog(":memory:") as log:
        evt = note_event(100, "s", "hello")
        seq = log.append(evt, inserted_at_s=100)
        assert seq == 1
        assert log.get_by_seq(1) == evt
        assert log.get_by_id(evt.event_id) == evt


def test_get_missing_returns_none() -> None:
    with EventLog(":memory:") as log:
        assert log.get_by_seq(1) is None
        assert log.get_by_id("nonexistent") is None


def test_iter_events_in_order() -> None:
    with EventLog(":memory:") as log:
        a = note_event(100, "s", "first")
        b = message_event(200, "chat", "in", "alice", "hi")
        c = note_event(300, "s", "third")
        log.append(a, inserted_at_s=100)
        log.append(b, inserted_at_s=200)
        log.append(c, inserted_at_s=300)
        items = list(log.iter_events())
        assert [e.event_id for e in items] == [a.event_id, b.event_id, c.event_id]


def test_replay_reproduces_state() -> None:
    with EventLog(":memory:") as src:
        for i in range(10):
            src.append(note_event(i, "s", f"note {i}"), inserted_at_s=i)
        with EventLog(":memory:") as dst:
            n = src.replay_into(dst)
            assert n == 10
            assert dst.count() == src.count()
            src_events = list(src.iter_events())
            dst_events = list(dst.iter_events())
            assert src_events == dst_events


def test_duplicate_event_id_rejected() -> None:
    with EventLog(":memory:") as log:
        evt = note_event(100, "s", "x")
        log.append(evt, inserted_at_s=100)
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError):
            log.append(evt, inserted_at_s=200)


def test_stored_envelope_is_verifiable() -> None:
    from famulix.envelope import Envelope

    with EventLog(":memory:") as log:
        evt = note_event(100, "s", "verify me")
        log.append(evt, inserted_at_s=100)
        # Raw row: parse envelope, it should verify cleanly
        cur = log._conn.execute(  # noqa: SLF001
            "SELECT envelope_json FROM event_log WHERE seq = 1"
        )
        line = cur.fetchone()[0]
        env = Envelope.from_jsonl_line(line)
        assert env.verify() is True


def test_frame_checksum_column_is_verified_on_read() -> None:
    with EventLog(":memory:") as log:
        evt = note_event(100, "s", "verify stored frame")
        log.append(evt, inserted_at_s=100)
        log._conn.execute(  # noqa: SLF001
            "UPDATE event_log SET checksum = ? WHERE event_id = ?", ("0" * 64, evt.event_id)
        )

        with pytest.raises(ValueError, match="does not match stored checksum"):
            log.get_by_id(evt.event_id)


def test_v1_database_migrates_and_backfills_source(tmp_path: Path) -> None:
    from famulix.envelope import Envelope

    path = tmp_path / "legacy.sqlite"
    evt = message_event(100, "legacy-chat", "in", "Mina", "hello")
    line = evt.to_envelope().to_jsonl_line()
    checksum = Envelope.from_jsonl_line(line).checksum
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE event_log (seq INTEGER PRIMARY KEY AUTOINCREMENT, "
        "event_id TEXT NOT NULL UNIQUE, envelope_json TEXT NOT NULL, "
        "checksum TEXT NOT NULL, inserted_at_s INTEGER NOT NULL); "
        "CREATE TABLE schema_version (version INTEGER PRIMARY KEY); "
        "INSERT INTO schema_version(version) VALUES (1);"
    )
    connection.execute(
        "INSERT INTO event_log(event_id,envelope_json,checksum,inserted_at_s) VALUES(?,?,?,?)",
        (evt.event_id, line, checksum, 100),
    )
    connection.commit()
    connection.close()

    with EventLog(path) as migrated:
        assert migrated.get_by_id(evt.event_id) == evt
        source_row = migrated._conn.execute(  # noqa: SLF001
            "SELECT source FROM event_log WHERE event_id = ?", (evt.event_id,)
        ).fetchone()
        schema_version = migrated._conn.execute(  # noqa: SLF001
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0]

    assert source_row == ("legacy-chat",)
    assert schema_version == 2


def test_sources_returns_distinct_sorted() -> None:
    with EventLog(":memory:") as log:
        log.append(note_event(100, "s", "a"), inserted_at_s=100)
        log.append(message_event(200, "chat", "in", "alice", "hi"), inserted_at_s=200)
        log.append(note_event(300, "s", "b"), inserted_at_s=300)
        sources = log.sources()
        assert sources == sorted(sources)
        assert "s" in sources
        assert "chat" in sources


def test_type_counts_matches_event_types() -> None:
    with EventLog(":memory:") as log:
        log.append(note_event(100, "s", "a"), inserted_at_s=100)
        log.append(note_event(200, "s", "b"), inserted_at_s=200)
        log.append(message_event(300, "chat", "in", "alice", "hi"), inserted_at_s=300)
        counts = log.type_counts()
        assert counts.get("note", 0) == 2
        assert counts.get("message", 0) == 1
        assert sum(counts.values()) == log.count()


def test_eventlog_append_increments_count() -> None:
    from famulix.eventlog import EventLog
    from famulix.events import Event

    log = EventLog()
    assert log.count() == 0
    e1 = Event.create("note", timestamp_s=100, source="test", data={"text": "first"})
    log.append(e1, inserted_at_s=1000)
    assert log.count() == 1
    e2 = Event.create("note", timestamp_s=200, source="test", data={"text": "second"})
    log.append(e2, inserted_at_s=2000)
    assert log.count() == 2


def test_eventlog_get_by_seq_returns_event() -> None:
    from famulix.eventlog import EventLog
    from famulix.events import Event

    log = EventLog()
    e1 = Event.create("note", timestamp_s=100, source="test", data={"text": "first"})
    seq = log.append(e1, inserted_at_s=1000)
    retrieved = log.get_by_seq(seq)
    assert retrieved is not None
    assert retrieved.event_id == e1.event_id


def test_eventlog_get_by_id_returns_event() -> None:
    from famulix.eventlog import EventLog
    from famulix.events import Event

    log = EventLog()
    e1 = Event.create("note", timestamp_s=100, source="test", data={"text": "first"})
    log.append(e1, inserted_at_s=1000)
    retrieved = log.get_by_id(e1.event_id)
    assert retrieved is not None
    assert retrieved.timestamp_s == 100


def test_eventlog_iter_yields_all_events() -> None:
    from famulix.eventlog import EventLog
    from famulix.events import Event

    log = EventLog()
    for i in range(5):
        e = Event.create("note", timestamp_s=i * 100, source="test", data={"index": i})
        log.append(e, inserted_at_s=i * 1000)
    events = list(log.iter_events())
    assert len(events) == 5


def test_eventlog_sources_lists_distinct_sources() -> None:
    from famulix.eventlog import EventLog
    from famulix.events import Event

    log = EventLog()
    log.append(
        Event.create("note", timestamp_s=100, source="calendar", data={}), inserted_at_s=1000
    )
    log.append(Event.create("note", timestamp_s=200, source="notes", data={}), inserted_at_s=2000)
    log.append(
        Event.create("note", timestamp_s=300, source="calendar", data={}), inserted_at_s=3000
    )
    sources = log.sources()
    assert "calendar" in sources
    assert "notes" in sources
    assert len(sources) == 2
