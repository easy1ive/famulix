"""Test memory graph summary method."""

from famulix.memory_graph import MemoryGraph, MemoryNode


def test_summary_empty_graph():
    """Empty graph should have zero counts."""
    graph = MemoryGraph()
    summary = graph.summary()
    assert summary["node_count"] == 0
    assert summary["edge_count"] == 0
    assert summary["active_node_count"] == 0
    assert summary["kind_counts"] == {}


def test_summary_with_nodes():
    """Graph with nodes should report counts."""
    graph = MemoryGraph()
    graph.add_node(MemoryNode.create(kind="fact", title="Test", body="Body"))
    graph.add_node(MemoryNode.create(kind="episode", title="Day 1", body="Events"))

    summary = graph.summary()
    assert summary["node_count"] == 2
    assert summary["active_node_count"] == 2
    assert "fact" in summary["kind_counts"]
    assert "episode" in summary["kind_counts"]
    assert summary["kind_counts"]["fact"] == 1
    assert summary["kind_counts"]["episode"] == 1
