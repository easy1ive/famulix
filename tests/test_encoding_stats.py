"""Test encoding statistics."""

from famulix.encoding import encoding_stats
from famulix.memory_graph import MemoryGraph, MemoryNode


def test_encoding_stats_empty():
    """Empty graph should have zero counts."""
    graph = MemoryGraph()
    stats = encoding_stats(graph)
    assert stats["episode_count"] == 0
    assert stats["entity_count"] == 0
    assert stats["fact_count"] == 0


def test_encoding_stats_with_nodes():
    """Should count nodes by kind."""
    graph = MemoryGraph()
    graph.add_node(MemoryNode.create(kind="episode", title="E1", body="B1"))
    graph.add_node(MemoryNode.create(kind="fact", title="F1", body="B2"))
    graph.add_node(MemoryNode.create(kind="fact", title="F2", body="B3"))

    stats = encoding_stats(graph)
    assert stats["episode_count"] == 1
    assert stats["fact_count"] == 2
