"""Tests for consolidation idempotency: running twice produces identical results."""

from famulix.consolidation import consolidate_graph
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history_with_truth


def test_consolidation_idempotent_node_count():
    events, _, _ = generate_history_with_truth(persona_id="alex", seed=42, days=14)
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    count_after_first = graph.node_count()
    consolidate_graph(graph)
    count_after_second = graph.node_count()
    assert count_after_first == count_after_second


def test_consolidation_idempotent_edge_count():
    events, _, _ = generate_history_with_truth(persona_id="alex", seed=42, days=14)
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    edges_after_first = len(list(graph.all_edges()))
    consolidate_graph(graph)
    edges_after_second = len(list(graph.all_edges()))
    assert edges_after_first == edges_after_second


def test_consolidation_idempotent_active_nodes():
    events, _, _ = generate_history_with_truth(persona_id="alex", seed=42, days=14)
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    active_after_first = {n.node_id for n in graph.active_nodes()}
    consolidate_graph(graph)
    active_after_second = {n.node_id for n in graph.active_nodes()}
    assert active_after_first == active_after_second


def test_consolidation_report_second_run_empty():
    """Second consolidation should report no changes."""
    events, _, _ = generate_history_with_truth(persona_id="alex", seed=42, days=14)
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    report = consolidate_graph(graph)
    assert report.contradictions_resolved == 0
    assert len(report.merged_pairs) == 0
