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


def test_active_nodes_excludes_inactive() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "active")
    b = MemoryNode.create("fact", "b", "inactive")
    # create inactive version by replacing
    from dataclasses import replace

    b_inactive = replace(b, is_active=False)
    g.add_node(a)
    g._nodes[b_inactive.node_id] = b_inactive
    assert g.node_count() == 2
    assert g.active_node_count() == 1
    active = g.active_nodes()
    assert len(active) == 1
    assert active[0].node_id == a.node_id


def test_nodes_by_kind_filters_kind_and_active() -> None:
    g = MemoryGraph()
    facts = [MemoryNode.create("fact", f"f{i}", f"body{i}") for i in range(3)]
    goals = [MemoryNode.create("goal", f"g{i}", f"goal{i}") for i in range(2)]
    for n in facts + goals:
        g.add_node(n)
    assert len(g.nodes_by_kind("fact")) == 3
    assert len(g.nodes_by_kind("goal")) == 2
    assert len(g.nodes_by_kind("reminder")) == 0


def test_remove_node_cascades_edges() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "source")
    b = MemoryNode.create("fact", "b", "target")
    c = MemoryNode.create("fact", "c", "other")
    g.add_node(a)
    g.add_node(b)
    g.add_node(c)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "derived_from"))
    g.add_edge(MemoryEdge.create(b.node_id, c.node_id, "mentions"))
    assert g.edge_count() == 2
    result = g.remove_node(b.node_id)
    assert result is True
    assert g.node_count() == 2
    assert g.edge_count() == 0
    assert not g.has_node(b.node_id)


def test_reachable_from_traverses_chain() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "start")
    b = MemoryNode.create("fact", "b", "mid")
    c = MemoryNode.create("fact", "c", "end")
    g.add_node(a)
    g.add_node(b)
    g.add_node(c)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "derived_from"))
    g.add_edge(MemoryEdge.create(b.node_id, c.node_id, "derived_from"))
    reached = g.reachable_from([a.node_id])
    assert a.node_id in reached
    assert b.node_id in reached
    assert c.node_id in reached


def test_reachable_from_respects_edge_kind_filter() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("episode", "a", "ep")
    b = MemoryNode.create("entity", "b", "mentioned")
    c = MemoryNode.create("fact", "c", "derived")
    g.add_node(a)
    g.add_node(b)
    g.add_node(c)
    g.add_edge(MemoryEdge.create(a.node_id, b.node_id, "mentions"))
    g.add_edge(MemoryEdge.create(a.node_id, c.node_id, "derived_from"))
    mentions = g.reachable_from([a.node_id], edge_kinds={"mentions"})
    assert a.node_id in mentions
    assert b.node_id in mentions
    assert c.node_id not in mentions


def test_reachable_from_respects_max_depth() -> None:
    g = MemoryGraph()
    nodes = [MemoryNode.create("fact", f"n{i}", f"body{i}") for i in range(6)]
    for n in nodes:
        g.add_node(n)
    for i in range(5):
        g.add_edge(MemoryEdge.create(nodes[i].node_id, nodes[i + 1].node_id, "derived_from"))
    # max_depth bounds expansion rounds; depth 0 covers seeds, each round adds one hop
    reached = g.reachable_from([nodes[0].node_id], max_depth=2)
    assert nodes[0].node_id in reached
    assert nodes[1].node_id in reached
    # depth=2 means seed processed + 1 round finished before loop exits at depth==max_depth
    assert nodes[2].node_id not in reached
    assert nodes[5].node_id not in reached

    reached_deep = g.reachable_from([nodes[0].node_id], max_depth=10)
    assert nodes[5].node_id in reached_deep


def test_remove_nonexistent_node_returns_false() -> None:
    g = MemoryGraph()
    assert g.remove_node("nonexistent") is False


def test_kind_counts_matches_active_nodes() -> None:
    g = MemoryGraph()
    for i in range(3):
        g.add_node(MemoryNode.create("fact", f"f{i}", f"body{i}"))
    for i in range(2):
        g.add_node(MemoryNode.create("goal", f"g{i}", f"goal{i}"))
    counts = g.kind_counts()
    assert counts.get("fact") == 3
    assert counts.get("goal") == 2
    assert sum(counts.values()) == g.active_node_count()


def test_graph_no_dangling_edges_after_bulk_deletion() -> None:
    from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode

    graph = MemoryGraph()
    nodes = [
        MemoryNode.create("fact", f"node{i}", f"content {i}", created_at_s=i * 100)
        for i in range(10)
    ]
    for node in nodes:
        graph.add_node(node)
    for i in range(9):
        graph.add_edge(MemoryEdge.create(nodes[i].node_id, nodes[i + 1].node_id, "related"))
    for node in nodes[:5]:
        from dataclasses import replace

        graph._nodes[node.node_id] = replace(node, is_active=False)  # noqa: SLF001
    all_edges = graph._edges  # noqa: SLF001
    for edge in all_edges.values():
        from_node = graph.get_node(edge.from_id)
        to_node = graph.get_node(edge.to_id)
        assert from_node is not None
        assert to_node is not None


def test_graph_acyclic_provenance_under_bulk_addition() -> None:
    from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode

    graph = MemoryGraph()
    nodes = [MemoryNode.create("fact", f"n{i}", f"body {i}", created_at_s=i) for i in range(5)]
    for node in nodes:
        graph.add_node(node)
    graph.add_edge(MemoryEdge.create(nodes[0].node_id, nodes[1].node_id, "derived_from"))
    graph.add_edge(MemoryEdge.create(nodes[1].node_id, nodes[2].node_id, "derived_from"))
    graph.add_edge(MemoryEdge.create(nodes[2].node_id, nodes[3].node_id, "derived_from"))
    provenance_edges = [e for e in graph._edges.values() if e.kind == "derived_from"]  # noqa: SLF001
    adjacency: dict[str, list[str]] = {}
    for edge in provenance_edges:
        adjacency.setdefault(edge.from_id, []).append(edge.to_id)

    def has_cycle(start: str, visited: set[str], path: set[str]) -> bool:
        visited.add(start)
        path.add(start)
        for neighbor in adjacency.get(start, []):
            if neighbor in path:
                return True
            if neighbor not in visited and has_cycle(neighbor, visited, path):
                return True
        path.remove(start)
        return False

    visited: set[str] = set()
    for node_id in adjacency:
        if node_id not in visited:
            assert not has_cycle(node_id, visited, set())


def test_graph_single_active_version_per_fact_key() -> None:
    import re

    from famulix.memory_graph import MemoryGraph, MemoryNode

    graph = MemoryGraph()
    fact1 = MemoryNode.create("fact", "user address", "123 Main St", created_at_s=100)
    fact2 = MemoryNode.create("fact", "user address", "456 Oak Ave", created_at_s=200)
    graph.add_node(fact1)
    graph.add_node(fact2)

    def fact_key(node: MemoryNode) -> str:
        words = re.findall(r"[\w]+", node.title.lower())
        return "_".join(words[:5])

    by_key: dict[str, list[MemoryNode]] = {}
    for node in graph.all_nodes():
        if node.kind == "fact" and node.is_active:
            key = fact_key(node)
            by_key.setdefault(key, []).append(node)
    for _key, nodes in by_key.items():
        assert len(nodes) <= 2


def test_memory_graph_node_count_tracks_active_and_inactive() -> None:
    from dataclasses import replace

    from famulix.memory_graph import MemoryGraph, MemoryNode

    graph = MemoryGraph()
    n1 = MemoryNode.create("fact", "active", "content", created_at_s=100)
    n2 = MemoryNode.create("fact", "inactive", "content", created_at_s=200)
    graph.add_node(n1)
    graph.add_node(n2)
    assert graph.node_count() == 2
    graph._nodes[n2.node_id] = replace(n2, is_active=False)  # noqa: SLF001
    assert graph.node_count() == 2
    active_count = sum(1 for n in graph.all_nodes() if n.is_active)
    assert active_count == 1


def test_memory_graph_neighbors_returns_connected_nodes() -> None:
    from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode

    graph = MemoryGraph()
    n1 = MemoryNode.create("fact", "n1", "content", created_at_s=100)
    n2 = MemoryNode.create("fact", "n2", "content", created_at_s=200)
    n3 = MemoryNode.create("fact", "n3", "content", created_at_s=300)
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_node(n3)
    graph.add_edge(MemoryEdge.create(n1.node_id, n2.node_id, "related"))
    graph.add_edge(MemoryEdge.create(n1.node_id, n3.node_id, "related"))
    neighbors = graph.neighbors(n1.node_id)
    neighbor_ids = {n.node_id for n in neighbors}
    assert n2.node_id in neighbor_ids
    assert n3.node_id in neighbor_ids


def test_memory_edge_create_generates_deterministic_id() -> None:
    from famulix.memory_graph import MemoryEdge

    e1 = MemoryEdge.create("from1", "to1", "related", weight=1.0)
    e2 = MemoryEdge.create("from1", "to1", "related", weight=1.0)
    assert e1.edge_id == e2.edge_id
    e3 = MemoryEdge.create("from1", "to1", "different", weight=1.0)
    assert e1.edge_id != e3.edge_id


def test_memory_node_metadata_preserved_through_operations() -> None:
    from famulix.memory_graph import MemoryGraph, MemoryNode

    graph = MemoryGraph()
    node = MemoryNode.create(
        "fact",
        "test",
        "content",
        created_at_s=100,
        metadata={"tier": "hot", "pinned": "true"},
    )
    graph.add_node(node)
    retrieved = graph.get_node(node.node_id)
    assert retrieved is not None
    assert retrieved.metadata["tier"] == "hot"
    assert retrieved.metadata["pinned"] == "true"


def test_memory_graph_has_node_checks_existence() -> None:
    from famulix.memory_graph import MemoryGraph, MemoryNode

    graph = MemoryGraph()
    node = MemoryNode.create("fact", "test", "content", created_at_s=100)
    assert not graph.has_node(node.node_id)
    graph.add_node(node)
    assert graph.has_node(node.node_id)
    assert not graph.has_node("nonexistent")


def test_memory_graph_active_nodes_returns_only_active() -> None:
    from dataclasses import replace

    from famulix.memory_graph import MemoryGraph, MemoryNode

    graph = MemoryGraph()
    n1 = MemoryNode.create("fact", "active", "content", created_at_s=100)
    n2 = MemoryNode.create("fact", "inactive", "content", created_at_s=200)
    graph.add_node(n1)
    graph.add_node(n2)
    graph._nodes[n2.node_id] = replace(n2, is_active=False)  # noqa: SLF001
    active = graph.active_nodes()
    assert len(active) == 1
    assert active[0].node_id == n1.node_id


def test_memory_graph_edge_count_tracks_all_edges() -> None:
    from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode

    graph = MemoryGraph()
    nodes = [MemoryNode.create("fact", f"n{i}", "content", created_at_s=i * 100) for i in range(5)]
    for node in nodes:
        graph.add_node(node)
    for i in range(4):
        graph.add_edge(MemoryEdge.create(nodes[i].node_id, nodes[i + 1].node_id, "next"))
    assert graph.edge_count() == 4
