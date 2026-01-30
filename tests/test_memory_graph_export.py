"""Test memory graph export helper."""

from famulix.memory_graph import MemoryGraph, MemoryNode, export_graph_summary


def test_export_empty_graph():
    """Empty graph should have zero counts."""
    graph = MemoryGraph()
    summary = export_graph_summary(graph)
    assert "Nodes: 0" in summary
    assert "Edges: 0" in summary


def test_export_with_nodes():
    """Should include node counts."""
    graph = MemoryGraph()
    graph.add_node(MemoryNode.create(kind="fact", title="F1", body="B1"))
    summary = export_graph_summary(graph)
    assert "Nodes: 1" in summary
    assert "fact: 1" in summary
