"""Tests for memory graph neighborhood and subgraph extraction."""

from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode


def _build_chain_graph() -> MemoryGraph:
    """Build a linear chain: A -> B -> C -> D with a mentions edge."""
    g = MemoryGraph()
    for node_id in ["A", "B", "C", "D"]:
        g.add_node(
            MemoryNode(
                node_id=node_id,
                kind="fact",
                title=node_id,
                body=f"content {node_id}",
            )
        )
    for i, (src, dst) in enumerate([("A", "B"), ("B", "C"), ("C", "D")]):
        g.add_edge(
            MemoryEdge(
                edge_id=f"e{i}",
                from_id=src,
                to_id=dst,
                kind="mentions",
            )
        )
    return g


def test_neighbors_follows_edges():
    g = _build_chain_graph()
    neighbors = g.neighbors("B")
    neighbor_ids = {n.node_id for n in neighbors}
    assert "A" in neighbor_ids or "C" in neighbor_ids


def test_neighbors_with_kind_filter():
    g = _build_chain_graph()
    neighbors = g.neighbors("B", kind="mentions")
    assert len(neighbors) >= 1


def test_extract_subgraph_includes_nodes_and_edges():
    g = _build_chain_graph()
    sub = g.extract_subgraph(seed_ids=["A", "B"], max_depth=0)
    assert sub.node_count() == 2
    active_ids = {n.node_id for n in sub.active_nodes()}
    assert "A" in active_ids
    assert "B" in active_ids


def test_extract_subgraph_excludes_distant_nodes():
    g = _build_chain_graph()
    sub = g.extract_subgraph(seed_ids=["A"], max_depth=0)
    active_ids = {n.node_id for n in sub.active_nodes()}
    assert "A" in active_ids
    assert "D" not in active_ids


def test_neighborhood_with_radius():
    g = _build_chain_graph()
    nodes, edges = g.neighborhood("B", radius=1)
    node_ids = {n.node_id for n in nodes}
    assert "B" in node_ids
    assert len(node_ids) >= 2


def test_neighborhood_empty_for_unknown_node():
    g = _build_chain_graph()
    nodes, edges = g.neighborhood("Z", radius=2)
    assert nodes == []
    assert edges == []


def test_extract_subgraph_deterministic():
    g = _build_chain_graph()
    s1 = g.extract_subgraph(seed_ids=["A", "B", "C"], max_depth=0)
    s2 = g.extract_subgraph(seed_ids=["A", "B", "C"], max_depth=0)
    ids1 = sorted(n.node_id for n in s1.active_nodes())
    ids2 = sorted(n.node_id for n in s2.active_nodes())
    assert ids1 == ids2
