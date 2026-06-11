"""Golden fixture tests for consolidation determinism."""

from famulix.consolidation import consolidate_graph
from famulix.memory_graph import MemoryGraph, MemoryNode


def test_consolidation_golden_dedup():
    graph = MemoryGraph()
    graph.add_node(
        MemoryNode(
            node_id="n1",
            kind="fact",
            title="Meeting at 3pm",
            body="Team meeting scheduled for 3pm",
            created_at_s=1000,
        )
    )
    graph.add_node(
        MemoryNode(
            node_id="n2",
            kind="fact",
            title="Meeting at 3pm",
            body="Team meeting scheduled for 3pm",
            created_at_s=1001,
        )
    )

    report = consolidate_graph(graph)

    assert len(report.merged_pairs) >= 1

    report2 = consolidate_graph(graph)
    assert len(report2.merged_pairs) == 0


def test_consolidation_golden_contradiction():
    graph = MemoryGraph()
    graph.add_node(
        MemoryNode(
            node_id="n1",
            kind="fact",
            title="My current home address",
            body="My address is 123 Main St",
            created_at_s=1000,
        )
    )
    graph.add_node(
        MemoryNode(
            node_id="n2",
            kind="fact",
            title="My current home address",
            body="My address is 456 Oak Ave",
            created_at_s=2000,
        )
    )

    report = consolidate_graph(graph)

    assert report.contradictions_resolved >= 1
