"""Tests for the append-only SQLite event log."""

from __future__ import annotations

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
