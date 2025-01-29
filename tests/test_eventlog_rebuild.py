"""Property-style test: rebuild-from-log produces identical state."""

from __future__ import annotations

from famulix.eventlog import EventLog
from famulix.events import calendar_event, message_event, note_event


def test_rebuild_from_log_idempotent() -> None:
    """Replaying a log into an empty log produces the same event sequence."""
    with EventLog(":memory:") as log:
        events = [
            note_event(100, "cli", "first note"),
            message_event(200, "chat", "out", "bob", "hey"),
            calendar_event(
                300,
                "cal",
                "standup",
                start_s=400,
                end_s=430,
                attendees=["alice"],
            ),
            note_event(500, "cli", "second note"),
            message_event(600, "chat", "in", "bob", "bye"),
        ]
        for i, evt in enumerate(events):
            log.append(evt, inserted_at_s=100 + i * 100)

        # Rebuild in two fresh logs from the same source — results match
        with EventLog(":memory:") as a, EventLog(":memory:") as b:
            log.replay_into(a)
            log.replay_into(b)
            assert a.count() == b.count() == log.count()
            list_a = list(a.iter_events())
            list_b = list(b.iter_events())
            assert list_a == list_b
            # Event ids match the source
            src_ids = [e.event_id for e in log.iter_events()]
            assert [e.event_id for e in list_a] == src_ids


def test_event_data_roundtrip_through_log() -> None:
    """Event data dicts survive a round-trip through the log intact."""
    with EventLog(":memory:") as log:
        data = {
            "text": "multi-line\ntext\nwith unicode 你好",
            "tags": ["a", "b", "c"],
            "meta": {"k": "v", "n": 42},
        }
        from famulix.events import Event

        custom = Event.create("note", 100, "test", data)
        log.append(custom, inserted_at_s=100)
        retrieved = log.get_by_id(custom.event_id)
        assert retrieved is not None
        assert retrieved.data == data
