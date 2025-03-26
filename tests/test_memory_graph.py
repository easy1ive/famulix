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


def test_provenance_cycle_is_rejected_at_insertion() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "a")
    b = MemoryNode.create("fact", "b", "b")
    g.add_node(a)
    g.add_node(b)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "derived_from"))
    with pytest.raises(ValueError, match="acyclic"):
        g.add_edge(MemoryEdge.create(b.node_id, a.node_id, "derived_from"))
    assert not g.has_cycle_along("derived_from")


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


def test_edge_weight_is_quantized_at_creation_and_round_trips() -> None:
    edge = MemoryEdge.create("source", "target", "mentions", 0.123456789)
    assert edge.weight == 0.123457

    graph = MemoryGraph()
    graph.add_node(MemoryNode.create("fact", "source", "body"))
    graph.add_node(MemoryNode.create("fact", "target", "body"))
    source, target = graph.all_nodes()
    graph.add_edge(MemoryEdge.create(source.node_id, target.node_id, "mentions", 0.123456789))
    restored = MemoryGraph.from_dict(graph.to_dict())
    assert restored.all_edges()[0].weight == graph.all_edges()[0].weight


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


def test_graph_schema_round_trip_is_deterministic() -> None:
    graph = MemoryGraph()
    fact = MemoryNode.create("fact", "meeting", "Tuesday", metadata={"source": "calendar"})
    episode = MemoryNode.create("episode", "day", "A meeting was planned", created_at_s=42)
    graph.add_node(fact)
    graph.add_node(episode)
    graph.add_edge(MemoryEdge.create(episode.node_id, fact.node_id, "derived_from", 0.875))

    encoded = graph.to_dict()
    decoded = MemoryGraph.from_dict(encoded)

    assert encoded["schema_version"] == 1
    assert decoded.to_dict() == encoded
    assert list(encoded["nodes"]) == sorted(encoded["nodes"], key=lambda item: item["node_id"])


def test_graph_loader_rejects_cycles_and_dangling_edges() -> None:
    left = MemoryNode.create("fact", "left", "a")
    right = MemoryNode.create("fact", "right", "b")
    nodes = [
        {
            "node_id": node.node_id,
            "kind": node.kind,
            "title": node.title,
            "body": node.body,
            "metadata": {},
            "created_at_s": 0,
            "is_active": True,
            "version": 1,
        }
        for node in (left, right)
    ]
    one = MemoryEdge.create(left.node_id, right.node_id, "derived_from")
    two = MemoryEdge.create(right.node_id, left.node_id, "derived_from")
    cyclic = {"schema_version": 1, "nodes": nodes, "edges": [one.__dict__, two.__dict__]}
    with pytest.raises(ValueError, match="acyclic"):
        MemoryGraph.from_dict(cyclic)

    dangling = {"schema_version": 1, "nodes": nodes[:1], "edges": [one.__dict__]}
    with pytest.raises(ValueError, match="dangling"):
        MemoryGraph.from_dict(dangling)


def test_graph_loader_rejects_duplicate_ids_and_malformed_metadata() -> None:
    node = MemoryNode.create("fact", "one", "body")
    raw = {
        "node_id": node.node_id,
        "kind": node.kind,
        "title": node.title,
        "body": node.body,
        "metadata": {},
        "created_at_s": 0,
        "is_active": True,
        "version": 1,
    }
    with pytest.raises(ValueError, match="duplicate"):
        MemoryGraph.from_dict({"schema_version": 1, "nodes": [raw, raw], "edges": []})

    malformed = {**raw, "metadata": {"source": 3}}
    with pytest.raises(ValueError, match="metadata"):
        MemoryGraph.from_dict({"schema_version": 1, "nodes": [malformed], "edges": []})
