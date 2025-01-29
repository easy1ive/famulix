"""Tests for the memory graph."""

from __future__ import annotations

import pytest

from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode


def test_node_create_deterministic() -> None:
    a = MemoryNode.create("fact", "title", "body")
    b = MemoryNode.create("fact", "title", "body")
    assert a.node_id == b.node_id
    assert a.node_id.startswith("mem_")


def test_node_different_content_different_id() -> None:
    a = MemoryNode.create("fact", "t", "body a")
    b = MemoryNode.create("fact", "t", "body b")
    assert a.node_id != b.node_id


def test_add_node_and_count() -> None:
    g = MemoryGraph()
    assert g.node_count() == 0
    n = MemoryNode.create("entity", "alice", "person")
    g.add_node(n)
    assert g.node_count() == 1
    assert g.has_node(n.node_id)
    assert g.get_node(n.node_id) == n


def test_add_edge_requires_both_nodes() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "body a")
    b = MemoryNode.create("fact", "b", "body b")
    g.add_node(a)
    with pytest.raises(ValueError, match="dangling"):
        g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "derived_from"))
    g.add_node(b)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "derived_from"))
    assert g.edge_count() == 1


def test_neighbors_filter_by_kind() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("episode", "ep1", "content")
    b = MemoryNode.create("entity", "alice", "person")
    c = MemoryNode.create("fact", "f1", "something about alice")
    g.add_node(a)
    g.add_node(b)
    g.add_node(c)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "mentions"))
    g.add_edge(MemoryEdge.create(a.node_id, c.node_id, "derived_from"))
    mentions = g.neighbors(a.node_id, kind="mentions")
    assert len(mentions) == 1
    assert mentions[0].node_id == b.node_id
    all_neighbors = g.neighbors(a.node_id)
    assert len(all_neighbors) == 2


def test_no_cycle_in_dag() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "a")
    b = MemoryNode.create("fact", "b", "b")
    c = MemoryNode.create("fact", "c", "c")
    g.add_node(a)
    g.add_node(b)
    g.add_node(c)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "derived_from"))
    g.add_edge(MemoryEdge.create(b.node_id, c.node_id, "derived_from"))
    assert not g.has_cycle_along("derived_from")


def test_cycle_detected() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "a")
    b = MemoryNode.create("fact", "b", "b")
    g.add_node(a)
    g.add_node(b)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "derived_from"))
    g.add_edge(MemoryEdge.create(b.node_id, a.node_id, "derived_from"))
    assert g.has_cycle_along("derived_from")


def test_cycle_check_only_considers_requested_kind() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "a")
    b = MemoryNode.create("fact", "b", "b")
    g.add_node(a)
    g.add_node(b)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "contradicts"))
    g.add_edge(MemoryEdge.create(b.node_id, a.node_id, "contradicts"))
    # contradicts cycles are allowed (facts contradict each other)
    assert g.has_cycle_along("contradicts")
    # derived_from is still acyclic
    assert not g.has_cycle_along("derived_from")


def test_edge_id_deterministic() -> None:
    e1 = MemoryEdge.create("a", "b", "mentions", 0.5)
    e2 = MemoryEdge.create("a", "b", "mentions", 0.5)
    assert e1.edge_id == e2.edge_id
    assert e1.edge_id.startswith("edg_")


def test_in_edges_and_out_edges() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "a")
    b = MemoryNode.create("fact", "b", "b")
    g.add_node(a)
    g.add_node(b)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "part_of"))
    assert len(g.out_edges(a.node_id)) == 1
    assert len(g.in_edges(b.node_id)) == 1
    assert len(g.in_edges(a.node_id)) == 0
