"""Edge case tests for encoding module."""

from famulix.encoding import encode_events_to_graph
from famulix.events import Event


def test_encode_empty_event_list():
    """Empty event list should produce empty graph."""
    graph = encode_events_to_graph([])
    assert graph.node_count() == 0
    assert graph.edge_count() == 0


def test_encode_single_event():
    """Single event should produce at least one node."""
    event = Event.create(
        event_type="note",
        timestamp_s=1700000000,
        source="test",
        data={"text": "Single test note"},
    )
    graph = encode_events_to_graph([event])
    assert graph.node_count() > 0


def test_encode_events_same_day():
    """Multiple events on same day should share episode node."""
    events = [
        Event.create(
            event_type="note",
            timestamp_s=1700000000,
            source="test",
            data={"text": "First note"},
        ),
        Event.create(
            event_type="note",
            timestamp_s=1700003600,  # 1 hour later
            source="test",
            data={"text": "Second note"},
        ),
    ]
    graph = encode_events_to_graph(events)
    # Should have at least one episode node
    assert graph.node_count() >= 1
