"""Tests for deletion semantics and tombstones."""

from __future__ import annotations

from famulix.deletion import (
    delete_memory,
    deleted_content_never_reappears,
    deletion_audit_report,
    is_deleted,
)
from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode


def test_delete_marks_tombstone() -> None:
    g = MemoryGraph()
    n = MemoryNode.create("fact", "a", "body", created_at_s=100)
    g.add_node(n)
    assert not is_deleted(g, n.node_id)
    report = delete_memory(g, n.node_id)
    assert is_deleted(g, n.node_id)
    assert n.node_id in report.deleted_nodes
    assert n.node_id in report.tombstone_nodes


def test_delete_nonexistent_noop() -> None:
    g = MemoryGraph()
    report = delete_memory(g, "nonexistent")
    assert report.total_deleted == 0


def test_delete_already_deleted_noop() -> None:
    g = MemoryGraph()
    n = MemoryNode.create("fact", "a", "body")
    g.add_node(n)
    delete_memory(g, n.node_id)
    report = delete_memory(g, n.node_id)
    assert report.total_deleted == 0


def test_delete_cascades_edges() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "aaa")
    b = MemoryNode.create("fact", "b", "bbb")
    g.add_node(a)
    g.add_node(b)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "derived_from"))
    edges_before = g.edge_count()
    delete_memory(g, b.node_id)
    assert g.edge_count() < edges_before
    # a is still there
    assert g.has_node(a.node_id)
    assert g.get_node(a.node_id).is_active
    assert all(
        edge.edge_id in {item.edge_id for item in g.all_edges()} for edge in g.out_edges(a.node_id)
    )
    assert all(edge.to_id != b.node_id for edge in g.out_edges(a.node_id))


def test_delete_keeps_all_adjacency_indexes_consistent() -> None:
    graph = MemoryGraph()
    nodes = [MemoryNode.create("fact", str(index), f"body {index}") for index in range(3)]
    for node in nodes:
        graph.add_node(node)
    graph.add_edge(MemoryEdge.create(nodes[0].node_id, nodes[1].node_id, "mentions"))
    graph.add_edge(MemoryEdge.create(nodes[1].node_id, nodes[2].node_id, "part_of"))

    delete_memory(graph, nodes[1].node_id)
    live_edge_ids = {edge.edge_id for edge in graph.all_edges()}
    for node in graph.all_nodes():
        assert {edge.edge_id for edge in graph.out_edges(node.node_id)} <= live_edge_ids
        assert {edge.edge_id for edge in graph.in_edges(node.node_id)} <= live_edge_ids


def test_audit_report_counts() -> None:
    g = MemoryGraph()
    for i in range(5):
        g.add_node(MemoryNode.create("fact", f"f{i}", f"body {i}"))
    # Delete 2
    nodes = g.all_nodes()
    delete_memory(g, nodes[0].node_id)
    delete_memory(g, nodes[1].node_id)
    audit = deletion_audit_report(g)
    assert audit["total_nodes"] == 5
    assert audit["deleted_count"] == 2
    assert len(audit["deleted_ids"]) == 2


def test_deleted_content_never_reappears_property() -> None:
    from famulix.retrieval import RetrievalResult

    g = MemoryGraph()
    n1 = MemoryNode.create("fact", "a", "aaa")
    n2 = MemoryNode.create("fact", "b", "bbb")
    g.add_node(n1)
    g.add_node(n2)
    delete_memory(g, n1.node_id)
    deleted = {n1.node_id}

    # Simulated query results
    results = [RetrievalResult(node_id=n2.node_id, score=0.9, citation="b")]
    assert deleted_content_never_reappears(g, deleted, results) is True

    bad_results = [RetrievalResult(node_id=n1.node_id, score=0.5, citation="a")]
    assert deleted_content_never_reappears(g, deleted, bad_results) is False


def test_deleted_content_never_reappears_dict_form() -> None:
    g = MemoryGraph()
    n = MemoryNode.create("fact", "a", "aaa")
    g.add_node(n)
    delete_memory(g, n.node_id)
    deleted = {n.node_id}
    assert deleted_content_never_reappears(g, deleted, [{"node_id": "other"}]) is True
    assert deleted_content_never_reappears(g, deleted, [{"node_id": n.node_id}]) is False


def test_deletion_report_cascade_depth() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "aaa")
    b = MemoryNode.create("fact", "b", "bbb")
    g.add_node(a)
    g.add_node(b)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "derived_from"))
    report = delete_memory(g, b.node_id, cascade=True)
    assert report.cascade_depth >= 1


def test_delete_without_cascade_preserves_edges() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "aaa")
    b = MemoryNode.create("fact", "b", "bbb")
    g.add_node(a)
    g.add_node(b)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "derived_from"))
    edges_before = g.edge_count()
    delete_memory(g, b.node_id, cascade=False)
    # Edge count unchanged (cascade off)
    assert g.edge_count() == edges_before
