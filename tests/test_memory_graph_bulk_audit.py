"""Test memory graph bulk mutation invariant audit."""

from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode
from famulix.memory_graph_audit import audit_graph_invariants


def test_audit_passes_clean_graph():
    graph = MemoryGraph()
    graph.add_node(
        MemoryNode(
            node_id="n1",
            kind="fact",
            title="Test",
            body="Test body",
            created_at_s=1000,
        )
    )
    graph.add_node(
        MemoryNode(
            node_id="n2",
            kind="fact",
            title="Test2",
            body="Test body 2",
            created_at_s=1001,
        )
    )

    edge = MemoryEdge.create("n1", "n2", "mentions")
    graph.add_edge(edge)

    issues = audit_graph_invariants(graph)

    assert len(issues) == 0


def test_audit_detects_self_loop():
    graph = MemoryGraph()
    graph.add_node(
        MemoryNode(
            node_id="n1",
            kind="fact",
            title="Test",
            body="Test body",
            created_at_s=1000,
        )
    )

    edge = MemoryEdge.create("n1", "n1", "mentions")
    graph.add_edge(edge)

    issues = audit_graph_invariants(graph)

    assert len(issues) > 0
    assert any("self-loop" in i.lower() for i in issues)
