"""Tests for event dataclasses and serialization."""

from __future__ import annotations

import pytest

from famulix.envelope import Envelope
from famulix.events import (
    Event,
    calendar_event,
    feedback_event,
    message_event,
    note_event,
)


def test_note_event_has_content_id() -> None:
    evt = note_event(1_700_000_000, "manual", "hello world")
    assert evt.event_id.startswith("evt_")
    assert evt.event_type == "note"
    assert evt.data["text"] == "hello world"


def test_same_content_same_id() -> None:
    a = note_event(100, "src", "text")
    b = note_event(100, "src", "text")
    assert a.event_id == b.event_id


def test_different_text_different_id() -> None:
    a = note_event(100, "src", "a")
    b = note_event(100, "src", "b")
    assert a.event_id != b.event_id


def test_envelope_round_trip() -> None:
    evt = message_event(200, "chat", "in", "alice", "hi there")
    env = evt.to_envelope()
    evt2 = Event.from_envelope(env)
    assert evt == evt2


def test_calendar_event_structure() -> None:
    evt = calendar_event(
        1000,
        "calendar",
        "team sync",
        start_s=2000,
        end_s=2700,
        attendees=["alice", "bob"],
    )
    assert evt.event_type == "calendar_item"
    assert evt.data["title"] == "team sync"
    assert evt.data["attendees"] == ["alice", "bob"]


def test_from_envelope_wrong_kind_raises() -> None:
    env = Envelope.wrap("memory", {"foo": "bar"})
    with pytest.raises(ValueError, match="Expected event envelope"):
        Event.from_envelope(env)


def test_event_to_dict_and_back() -> None:
    evt = note_event(500, "cli", "a note")
    d = evt.to_dict()
    env = Envelope.wrap("event", d)
    evt2 = Event.from_envelope(env)
    assert evt == evt2


def test_feedback_event_rating() -> None:
    evt = feedback_event(900, "ui", "suggestion_1", "up")
    assert evt.event_type == "feedback_tap"
    assert evt.data["rating"] == "up"
    assert evt.data["target_id"] == "suggestion_1"


def test_event_create_generates_deterministic_id() -> None:
    from famulix.events import Event

    e1 = Event.create("note", timestamp_s=1000, source="test", data={"text": "hello"})
    e2 = Event.create("note", timestamp_s=1000, source="test", data={"text": "hello"})
    assert e1.event_id == e2.event_id


def test_event_create_different_data_produces_different_ids() -> None:
    from famulix.events import Event

    e1 = Event.create("note", timestamp_s=1000, source="test", data={"text": "hello"})
    e2 = Event.create("note", timestamp_s=1000, source="test", data={"text": "world"})
    assert e1.event_id != e2.event_id


def test_event_create_assigns_version() -> None:
    from famulix.events import Event

    event = Event.create("note", timestamp_s=1000, source="test", data={})
    assert event.version == 1


def test_event_to_envelope_wraps_with_checksum() -> None:
    from famulix.events import Event

    event = Event.create("note", timestamp_s=1000, source="test", data={"key": "value"})
    envelope = event.to_envelope()
    assert envelope.kind == "event"
    assert envelope.checksum is not None
    assert len(envelope.checksum) > 0


def test_event_from_envelope_roundtrip() -> None:
    from famulix.events import Event

    original = Event.create(
        "calendar", timestamp_s=2000, source="google", data={"title": "Meeting"}
    )
    envelope = original.to_envelope()
    restored = Event.from_envelope(envelope)
    assert restored.event_id == original.event_id
    assert restored.timestamp_s == original.timestamp_s
    assert restored.data == original.data


def test_validate_event_valid() -> None:
    from famulix.events import Event, validate_event

    event = Event.create("note", timestamp_s=100, source="test", data={"text": "hello"})
    problems = validate_event(event)
    assert problems == []


def test_validate_event_detects_problems() -> None:
    from famulix.events import Event, validate_event

    event = Event.create("note", timestamp_s=100, source="test", data={"text": "hello"})
    # Create a broken event
    broken = Event(
        event_id="",
        event_type=event.event_type,
        timestamp_s=-1,
        source="",
        data=event.data,
    )
    problems = validate_event(broken)
    assert len(problems) >= 2
    assert any("event_id" in p for p in problems)
    assert any("timestamp_s" in p for p in problems)


def test_batch_validate_events_all_valid() -> None:
    from famulix.events import Event, batch_validate_events

    events = [
        Event.create("note", timestamp_s=100, source="s1", data={}),
        Event.create("note", timestamp_s=200, source="s2", data={}),
    ]
    valid_count, errors = batch_validate_events(events)
    assert valid_count == 2
    assert errors == []


def test_batch_validate_events_with_invalid() -> None:
    from famulix.events import Event, batch_validate_events

    good = Event.create("note", timestamp_s=100, source="s1", data={})
    bad = Event(event_id="", event_type="note", timestamp_s=-1, source="", data={})
    valid_count, errors = batch_validate_events([good, bad])
    assert valid_count == 1
    assert len(errors) >= 2


def test_event_statistics_empty() -> None:
    from famulix.events import event_statistics

    stats = event_statistics([])
    assert stats["count"] == 0
    assert stats["event_types"] == set()


def test_event_statistics_with_data() -> None:
    from famulix.events import Event, event_statistics

    events = [
        Event.create("note", timestamp_s=100, source="s1", data={}),
        Event.create("calendar", timestamp_s=200, source="s2", data={}),
    ]
    stats = event_statistics(events)
    assert stats["count"] == 2
    assert "note" in stats["event_types"]
    assert "calendar" in stats["event_types"]
    assert stats["timestamp_range"] == (100, 200)
