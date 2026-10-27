"""Tests for salience scoring with node features."""

from famulix.memory_graph import MemoryGraph, MemoryNode
from famulix.salience import compute_salience


def test_salience_deterministic():
    g = MemoryGraph()
    n = MemoryNode(node_id="m1", kind="fact", title="test", body="content", created_at_s=1000)
    g.add_node(n)
    s1 = compute_salience(n, graph=g, now_s=2000)
    s2 = compute_salience(n, graph=g, now_s=2000)
    assert round(s1, 6) == round(s2, 6)


def test_salience_recency_decays():
    """Recent nodes score higher than old nodes."""
    g = MemoryGraph()
    recent = MemoryNode(node_id="recent", kind="fact", title="r", body="r", created_at_s=900)
    old = MemoryNode(node_id="old", kind="fact", title="o", body="o", created_at_s=0)
    g.add_node(recent)
    g.add_node(old)
    s_recent = compute_salience(recent, graph=g, now_s=1000)
    s_old = compute_salience(old, graph=g, now_s=1000)
    assert s_recent >= s_old


def test_salience_frequency_boost():
    """Nodes with more in-edges score higher."""
    from famulix.memory_graph import MemoryEdge

    g = MemoryGraph()
    target = MemoryNode(node_id="target", kind="fact", title="t", body="t", created_at_s=500)
    g.add_node(target)
    for i in range(5):
        src = MemoryNode(
            node_id=f"src_{i}", kind="fact", title=f"s{i}", body=f"s{i}", created_at_s=500
        )
        g.add_node(src)
        g.add_edge(MemoryEdge(edge_id=f"e{i}", from_id=f"src_{i}", to_id="target", kind="mentions"))

    g2 = MemoryGraph()
    lone = MemoryNode(node_id="lone", kind="fact", title="l", body="l", created_at_s=500)
    g2.add_node(lone)

    s_target = compute_salience(target, graph=g, now_s=1000)
    s_lone = compute_salience(lone, graph=g2, now_s=1000)
    assert s_target >= s_lone


def test_salience_finite():
    g = MemoryGraph()
    n = MemoryNode(node_id="m1", kind="fact", title="test", body="content", created_at_s=0)
    g.add_node(n)
    score = compute_salience(n, graph=g, now_s=100000)
    import math

    assert math.isfinite(score)
