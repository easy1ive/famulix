"""Tests for memory decay and forgetting."""

from __future__ import annotations

from famulix.decay import (
    DecayConfig,
    apply_decay,
    count_tombstoned,
    get_tier,
    protected_nodes_survive,
    retention_score,
    tier_distribution,
    tier_for_retention,
)
from famulix.memory_graph import MemoryGraph, MemoryNode


def test_retention_decreases_with_age() -> None:
    node = MemoryNode.create("fact", "t", "b", created_at_s=0)
    near = retention_score(node, now_s=1000)
    far = retention_score(node, now_s=10_000_000)
    assert near > far


def test_retention_is_in_unit_interval() -> None:
    node = MemoryNode.create("fact", "t", "b", created_at_s=100)
    for now in [0, 100, 1000, 86400, 10_000_000]:
        r = retention_score(node, now_s=now)
        assert 0.0 <= r <= 1.0


def test_grace_period_protects_new_memories() -> None:
    cfg = DecayConfig(grace_period_s=3600)
    node = MemoryNode.create("fact", "t", "b", created_at_s=1000)
    # Within grace period
    assert retention_score(node, now_s=2000, config=cfg) == 1.0
    # After grace period: should have started decaying
    after = retention_score(node, now_s=100_000, config=cfg)
    assert after < 1.0


def test_pinned_memory_never_decays() -> None:
    node = MemoryNode.create("fact", "t", "b", created_at_s=0, metadata={"pinned": "true"})
    assert retention_score(node, now_s=10_000_000) == 1.0


def test_protected_memory_never_decays() -> None:
    node = MemoryNode.create("fact", "t", "b", created_at_s=0, metadata={"protected": "true"})
    assert retention_score(node, now_s=10_000_000) == 1.0


def test_tier_affects_decay_rate() -> None:
    hot = MemoryNode.create("fact", "t", "b", created_at_s=0, metadata={"tier": "hot"})
    cold = MemoryNode.create("fact", "t", "b", created_at_s=0, metadata={"tier": "cold"})
    # After 1 day, hot should have decayed more than cold (hot has shorter half-life)
    now = 86400
    r_hot = retention_score(hot, now_s=now)
    r_cold = retention_score(cold, now_s=now)
    assert r_hot < r_cold


def test_get_tier_default() -> None:
    node = MemoryNode.create("fact", "t", "b")
    assert get_tier(node) == "warm"


def test_get_tier_explicit() -> None:
    node = MemoryNode.create("fact", "t", "b", metadata={"tier": "archive"})
    assert get_tier(node) == "archive"


def test_tier_for_retention_buckets() -> None:
    assert tier_for_retention(0.9) == "hot"
    assert tier_for_retention(0.5) == "warm"
    assert tier_for_retention(0.2) == "cold"
    assert tier_for_retention(0.05) == "archive"


def test_apply_decay_covers_all_active_nodes() -> None:
    g = MemoryGraph()
    g.add_node(MemoryNode.create("fact", "a", "a", created_at_s=0))
    g.add_node(MemoryNode.create("fact", "b", "b", created_at_s=1000))
    g.add_node(MemoryNode.create("episode", "ep", "ep", created_at_s=500))
    scores = apply_decay(g, now_s=10_000)
    assert len(scores) == 3


def test_count_tombstoned_increases_over_time() -> None:
    g = MemoryGraph()
    for i in range(20):
        g.add_node(MemoryNode.create("fact", f"f{i}", f"body {i}", created_at_s=i * 100))
    early = count_tombstoned(g, now_s=1000)
    late = count_tombstoned(g, now_s=10_000_000)
    assert late >= early


def test_tier_distribution_sums_to_count() -> None:
    g = MemoryGraph()
    for i in range(10):
        g.add_node(MemoryNode.create("fact", f"f{i}", f"b{i}", created_at_s=i * 1000))
    dist = tier_distribution(g, now_s=5000)
    assert sum(dist.values()) == 10


def test_protected_nodes_survive_property() -> None:
    g = MemoryGraph()
    g.add_node(MemoryNode.create("fact", "a", "a", created_at_s=0, metadata={"pinned": "true"}))
    g.add_node(MemoryNode.create("fact", "b", "b", created_at_s=0, metadata={"protected": "true"}))
    g.add_node(MemoryNode.create("fact", "c", "c", created_at_s=0))
    assert protected_nodes_survive(g, now_s=10_000_000) is True


def test_half_life_actually_fifty_percent() -> None:
    cfg = DecayConfig(warm_half_life_s=1000, grace_period_s=0)
    node = MemoryNode.create("fact", "t", "b", created_at_s=0, metadata={"tier": "warm"})
    r = retention_score(node, now_s=1000, config=cfg)
    assert 0.49 < r < 0.51
