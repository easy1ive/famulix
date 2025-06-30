"""Tests for salience scoring."""

from __future__ import annotations

from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode
from famulix.salience import (
    SalienceConfig,
    compute_salience,
    normalize_scores,
    score_all_nodes,
    slice_diagnostics,
    top_k,
)


def test_salience_in_range() -> None:
    node = MemoryNode.create("fact", "title", "body text here", created_at_s=1000)
    score = compute_salience(node, now_s=2000)
    assert 0.0 <= score <= 1.0


def test_recency_decays() -> None:
    node = MemoryNode.create("fact", "t", "b", created_at_s=0)
    near = compute_salience(node, now_s=1000)
    far = compute_salience(node, now_s=10_000_000)
    assert near > far


def test_recency_at_creation_is_max() -> None:
    node = MemoryNode.create("fact", "t", "b", created_at_s=500)
    score = compute_salience(node, now_s=500)
    # At t=0 age, recency component is 1.0
    assert score > 0.25


def test_pinned_scores_higher() -> None:
    normal = MemoryNode.create("fact", "t", "b", created_at_s=100)
    pinned = MemoryNode.create("fact", "t", "b", created_at_s=100, metadata={"pinned": "true"})
    s_normal = compute_salience(normal, now_s=200)
    s_pinned = compute_salience(pinned, now_s=200)
    assert s_pinned > s_normal


def test_frequency_boosts_score() -> None:
    g = MemoryGraph()
    target = MemoryNode.create("entity", "alice", "person", created_at_s=0)
    g.add_node(target)
    # Before linking
    s_before = compute_salience(target, graph=g, now_s=100)
    # Add many episodes that mention the target
    for i in range(10):
        ep = MemoryNode.create("episode", f"ep{i}", f"day {i}", created_at_s=i * 10)
        g.add_node(ep)
        g.add_edge(MemoryEdge.create(ep.node_id, target.node_id, "mentions"))
    s_after = compute_salience(target, graph=g, now_s=100)
    assert s_after > s_before


def test_custom_weights_affect_score() -> None:
    node = MemoryNode.create("fact", "important deadline", "critical must do now", created_at_s=500)
    default = compute_salience(node, now_s=500)
    heavy_recency = SalienceConfig(
        recency_weight=0.9, importance_weight=0.05, frequency_weight=0.05, goal_linkage_weight=0.0
    )
    high_recency = compute_salience(node, now_s=500, config=heavy_recency)
    # Both should be valid numbers; recency-heavy at t=0 should be high
    assert high_recency > 0.5
    assert default > 0.2


def test_score_all_nodes_maps_ids() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "aaa", created_at_s=10)
    b = MemoryNode.create("fact", "b", "bbb", created_at_s=20)
    g.add_node(a)
    g.add_node(b)
    scores = score_all_nodes(g, now_s=100)
    assert a.node_id in scores
    assert b.node_id in scores
    assert len(scores) == 2


def test_slice_diagnostics_empty() -> None:
    diag = slice_diagnostics({})
    assert diag["count"] == 0.0
    assert diag["mean"] == 0.0


def test_slice_diagnostics_statistics() -> None:
    scores = {f"n{i}": float(i) / 10.0 for i in range(11)}  # 0.0..1.0
    diag = slice_diagnostics(scores)
    assert diag["count"] == 11.0
    assert diag["max"] == 1.0
    assert 0.45 < diag["mean"] < 0.55
    assert diag["median"] == 0.5
    assert diag["p90"] >= 0.8


def test_top_k_returns_sorted_descending() -> None:
    scores = {"a": 0.8, "b": 0.3, "c": 0.9, "d": 0.5}
    top3 = top_k(scores, 3)
    assert len(top3) == 3
    assert top3[0][0] == "c"  # highest
    assert top3[1][0] == "a"
    assert top3[2][0] == "d"
    # Sorted by score descending, then id ascending for ties
    assert top3 == sorted(top3, key=lambda pair: (-pair[1], pair[0]))


def test_top_k_deterministic_on_ties() -> None:
    scores = {"z": 0.5, "a": 0.5, "m": 0.5}
    result = top_k(scores, 3)
    assert [nid for nid, _ in result] == ["a", "m", "z"]  # alphabetical on tie


def test_normalize_scores_spreads_to_zero_one() -> None:
    scores = {"a": 10.0, "b": 20.0, "c": 30.0}
    norm = normalize_scores(scores)
    assert norm["a"] == 0.0
    assert norm["c"] == 1.0
    assert 0.0 < norm["b"] < 1.0
    assert 0.0 <= min(norm.values()) <= max(norm.values()) <= 1.0


def test_normalize_scores_equal_values_returns_zeros() -> None:
    scores = {"a": 5.0, "b": 5.0}
    norm = normalize_scores(scores)
    assert norm["a"] == 0.0
    assert norm["b"] == 0.0


def test_normalize_scores_empty_input() -> None:
    assert normalize_scores({}) == {}


def test_salience_deterministic() -> None:
    g = MemoryGraph()
    a = MemoryNode.create("fact", "a", "some content", created_at_s=100)
    b = MemoryNode.create("episode", "ep", "episode body", created_at_s=100)
    g.add_node(a)
    g.add_node(b)
    g.add_edge(MemoryEdge.create(b.node_id, a.node_id, "derived_from"))
    s1 = compute_salience(a, graph=g, now_s=500)
    s2 = compute_salience(a, graph=g, now_s=500)
    assert s1 == s2
