"""Performance tests for consolidation."""

import time

from famulix.consolidation import consolidate_graph
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history_with_truth


def test_consolidation_performance_small():
    """Verify consolidation handles 7-day history efficiently."""
    events, _, _ = generate_history_with_truth(persona_id="alex", seed=42, days=7)
    graph = encode_events_to_graph(events)

    start = time.perf_counter()
    report = consolidate_graph(graph, dedup_threshold=0.85)
    elapsed = time.perf_counter() - start

    # Should complete in under 2 seconds for 7 days
    assert elapsed < 2.0
    assert report is not None


def test_consolidation_performance_medium():
    """Verify consolidation handles 30-day history efficiently."""
    events, _, _ = generate_history_with_truth(persona_id="alex", seed=42, days=30)
    graph = encode_events_to_graph(events)

    start = time.perf_counter()
    report = consolidate_graph(graph, dedup_threshold=0.85)
    elapsed = time.perf_counter() - start

    # Should complete in under 5 seconds for 30 days
    assert elapsed < 5.0
    assert report is not None


def test_consolidation_idempotence():
    """Running consolidation twice should produce same result."""
    events, _, _ = generate_history_with_truth(persona_id="alex", seed=99, days=7)
    graph = encode_events_to_graph(events)

    consolidate_graph(graph, dedup_threshold=0.85)
    count1 = graph.node_count()

    consolidate_graph(graph, dedup_threshold=0.85)
    count2 = graph.node_count()

    # Second run should not change anything
    assert count1 == count2
