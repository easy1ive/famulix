"""Test event type counts."""

from famulix.events import Event, event_type_counts


def test_empty_events():
    """Empty list should have zero counts."""
    assert event_type_counts([]) == {}


def test_event_counts():
    """Should count by type."""
    events = [
        Event.create(event_type="note", timestamp_s=1000, source="test", data={}),
        Event.create(event_type="note", timestamp_s=2000, source="test", data={}),
        Event.create(event_type="message", timestamp_s=3000, source="test", data={}),
    ]
    result = event_type_counts(events)
    assert result["note"] == 2
    assert result["message"] == 1
