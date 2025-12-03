"""Tests for memory decay and forgetting."""

from __future__ import annotations

import pytest

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
    cfg = DecayConfig(
        hot_half_life_s=100,
        warm_half_life_s=1000,
        cold_half_life_s=5000,
        archive_half_life_s=10000,
        grace_period_s=0,
    )
    node = MemoryNode.create("fact", "t", "b", created_at_s=0, metadata={"tier": "warm"})
    r = retention_score(node, now_s=1000, config=cfg)
    assert 0.49 < r < 0.51


def test_promote_tier_moves_up_one_level() -> None:
    from famulix.decay import promote_tier

    cold = MemoryNode.create("fact", "c", "b", metadata={"tier": "cold"})
    assert promote_tier(cold) == "warm"
    warm = MemoryNode.create("fact", "w", "b", metadata={"tier": "warm"})
    assert promote_tier(warm) == "hot"
    hot = MemoryNode.create("fact", "h", "b", metadata={"tier": "hot"})
    assert promote_tier(hot) == "hot"  # capped


def test_demote_tier_moves_down_one_level() -> None:
    from famulix.decay import demote_tier

    hot = MemoryNode.create("fact", "h", "b", metadata={"tier": "hot"})
    assert demote_tier(hot) == "warm"
    warm = MemoryNode.create("fact", "w", "b", metadata={"tier": "warm"})
    assert demote_tier(warm) == "cold"
    archive = MemoryNode.create("fact", "a", "b", metadata={"tier": "archive"})
    assert demote_tier(archive) == "archive"  # capped


def test_promote_then_demote_roundtrip_at_mid_tiers() -> None:
    from famulix.decay import demote_tier, promote_tier

    warm = MemoryNode.create("fact", "w", "b", metadata={"tier": "warm"})
    promoted = promote_tier(warm)
    # Make a node with the promoted tier
    promoted_node = MemoryNode.create("fact", "p", "b", metadata={"tier": promoted})
    assert demote_tier(promoted_node) == "warm"


def test_decay_config_rejects_non_positive_half_lives() -> None:
    from famulix.decay import DecayConfig

    with pytest.raises(ValueError, match="positive"):
        DecayConfig(hot_half_life_s=0)
    with pytest.raises(ValueError, match="positive"):
        DecayConfig(warm_half_life_s=-100)


def test_decay_config_rejects_wrong_ordering() -> None:
    from famulix.decay import DecayConfig

    with pytest.raises(ValueError, match="ordered"):
        DecayConfig(hot_half_life_s=86400 * 10, warm_half_life_s=86400 * 7)
    with pytest.raises(ValueError, match="ordered"):
        DecayConfig(cold_half_life_s=86400 * 5, archive_half_life_s=86400 * 4)


def test_decay_config_rejects_invalid_grace_period() -> None:
    from famulix.decay import DecayConfig

    with pytest.raises(ValueError, match="non-negative"):
        DecayConfig(grace_period_s=-1)


def test_decay_config_rejects_invalid_tombstone_threshold() -> None:
    from famulix.decay import DecayConfig

    with pytest.raises(ValueError, match="threshold"):
        DecayConfig(tombstone_threshold=0)
    with pytest.raises(ValueError, match="threshold"):
        DecayConfig(tombstone_threshold=1.0)
    with pytest.raises(ValueError, match="threshold"):
        DecayConfig(tombstone_threshold=1.5)


def test_decay_config_default_is_valid() -> None:
    from famulix.decay import DecayConfig

    config = DecayConfig()
    assert config.hot_half_life_s < config.warm_half_life_s
    assert config.warm_half_life_s < config.cold_half_life_s
    assert config.cold_half_life_s < config.archive_half_life_s


def test_validate_decay_config_valid() -> None:
    from famulix.decay import DecayConfig, validate_decay_config

    config = DecayConfig()
    problems = validate_decay_config(config)
    assert problems == []


def test_retention_diagnostics_empty_graph() -> None:
    from famulix.decay import retention_diagnostics
    from famulix.memory_graph import MemoryGraph

    graph = MemoryGraph()
    diag = retention_diagnostics(graph, now_s=1000)
    assert diag["min_retention"] == 0.0
    assert diag["max_retention"] == 0.0
    assert diag["mean_retention"] == 0.0
    assert diag["protected_count"] == 0


def test_retention_diagnostics_with_nodes() -> None:
    from famulix.decay import retention_diagnostics
    from famulix.memory_graph import MemoryGraph, MemoryNode

    graph = MemoryGraph()
    n1 = MemoryNode.create("fact", "recent", "body", created_at_s=900, metadata={"tier": "hot"})
    n2 = MemoryNode.create(
        "fact",
        "old",
        "body",
        created_at_s=100,
        metadata={"tier": "cold", "pinned": "true"},
    )
    graph.add_node(n1)
    graph.add_node(n2)

    diag = retention_diagnostics(graph, now_s=1000)
    assert diag["min_retention"] >= 0.0
    assert diag["max_retention"] <= 1.0
    assert diag["protected_count"] == 1
    assert sum(diag["tier_counts"].values()) == 2
