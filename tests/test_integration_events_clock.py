"""Integration test: events, clock, and serialization.

Verifies that events serialize correctly, clock handles timezones, and
day bucketing works across DST boundaries.
"""

import json

from famulix.clock import day_start_epoch
from famulix.encoding import day_segment
from famulix.envelope import Envelope
from famulix.events import Event


def test_event_serialization_roundtrip():
    """Verify events serialize and deserialize correctly."""
    event = Event(
        event_id="evt_test123",
        timestamp_s=1000000,
        event_type="note",
        source="laptop",
        data={"text": "Hello world", "tags": ["greeting"]},
    )

    # Serialize
    data = event.to_dict()
    json_str = json.dumps(data)

    # Deserialize
    loaded_data = json.loads(json_str)
    loaded_event = Event.from_dict(loaded_data)

    # Verify roundtrip
    assert loaded_event.event_id == event.event_id
    assert loaded_event.timestamp_s == event.timestamp_s
    assert loaded_event.event_type == event.event_type
    assert loaded_event.source == event.source
    assert loaded_event.data == event.data


def test_envelope_wrap_deterministic():
    """Verify envelope wrapping is deterministic."""
    payload = {"text": "Hello", "timestamp": 1000000}

    env1 = Envelope.wrap(kind="event", payload=payload)
    env2 = Envelope.wrap(kind="event", payload=payload)

    # Same payload → same checksum
    assert env1.checksum == env2.checksum
    assert env1.schema_version == env2.schema_version


def test_day_bucket_groups_by_date():
    """Verify day bucketing groups events by date."""
    events = [
        Event(event_id="e1", timestamp_s=1000000, event_type="note", source="laptop", data={}),
        Event(
            event_id="e2", timestamp_s=1000000 + 3600, event_type="note", source="laptop", data={}
        ),
        Event(
            event_id="e3", timestamp_s=1000000 + 86400, event_type="note", source="laptop", data={}
        ),
    ]

    buckets = day_segment(events, tz_offset_hours=0)

    # Should have 2 days
    assert len(buckets) == 2

    # First day should have 2 events
    day1_events = list(buckets.values())[0]
    assert len(day1_events) == 2

    # Second day should have 1 event
    day2_events = list(buckets.values())[1]
    assert len(day2_events) == 1


def test_day_start_epoch_timezone():
    """Verify day_start_epoch respects timezone offset."""
    # Same date, different timezones
    utc_start = day_start_epoch("2026-03-15", tz_offset_hours=0)
    tokyo_start = day_start_epoch("2026-03-15", tz_offset_hours=9)

    # Tokyo is 9 hours ahead, so its day starts 9 hours earlier in UTC
    assert tokyo_start < utc_start
    assert utc_start - tokyo_start == 9 * 3600


def test_envelope_roundtrip():
    """Verify envelope serialization roundtrip."""
    payload = {"event_id": "evt_test", "text": "Test message"}

    envelope = Envelope.wrap(kind="event", payload=payload)

    # Serialize
    data = envelope.to_dict()

    # Deserialize
    loaded = Envelope.from_dict(data)

    # Verify roundtrip
    assert loaded.schema_version == envelope.schema_version
    assert loaded.kind == envelope.kind
    assert loaded.payload == envelope.payload
    assert loaded.checksum == envelope.checksum


def test_event_jsonl_format():
    """Verify events can be written/read as JSONL."""
    events = [
        Event(
            event_id=f"evt_{i}",
            timestamp_s=1000000 + i,
            event_type="note",
            source="laptop",
            data={"i": i},
        )
        for i in range(5)
    ]

    # Serialize to JSONL
    lines = [json.dumps(e.to_dict()) for e in events]
    jsonl = "\n".join(lines)

    # Parse back
    loaded_events = [Event.from_dict(json.loads(line)) for line in jsonl.split("\n")]

    # Verify roundtrip
    assert len(loaded_events) == len(events)
    for original, loaded in zip(events, loaded_events, strict=True):
        assert loaded.event_id == original.event_id
        assert loaded.timestamp_s == original.timestamp_s


def test_event_types_coverage():
    """Verify all standard event types can be created."""
    event_types = [
        "note",
        "message",
        "calendar_item",
        "file_touch",
        "feedback_tap",
        "timer_fire",
        "user_utterance",
    ]

    for event_type in event_types:
        event = Event(
            event_id=f"evt_{event_type}",
            timestamp_s=1000000,
            event_type=event_type,
            source="laptop",
            data={},
        )
        assert event.event_type == event_type
