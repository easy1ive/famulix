"""Tests for decay protection: pinned memories never deleted by decay."""

from famulix.decay import DecayConfig, apply_decay
from famulix.memory_graph import MemoryGraph, MemoryNode


def test_pinned_memory_survives_decay():
    g = MemoryGraph()
    g.add_node(
        MemoryNode(
            node_id="pinned",
            kind="fact",
            title="important",
            body="keep me",
            metadata={"pinned": "true"},
        )
    )
    g.add_node(
        MemoryNode(
            node_id="unpinned",
            kind="fact",
            title="normal",
            body="decay me",
        )
    )
    config = DecayConfig()
    apply_decay(g, now_s=1000000, config=config)
    pinned = g.get_node("pinned")
    assert pinned is not None
    assert pinned.is_active


def test_decay_deterministic():
    g1 = MemoryGraph()
    g1.add_node(MemoryNode(node_id="a", kind="fact", title="a", body="content a", created_at_s=0))
    g2 = MemoryGraph()
    g2.add_node(MemoryNode(node_id="a", kind="fact", title="a", body="content a", created_at_s=0))
    config = DecayConfig()
    r1 = apply_decay(g1, now_s=86400 * 30, config=config)
    r2 = apply_decay(g2, now_s=86400 * 30, config=config)
    assert r1 == r2


def test_decay_config_has_tier_half_lives():
    config = DecayConfig()
    assert config.hot_half_life_s > 0
    assert config.warm_half_life_s > config.hot_half_life_s
    assert config.cold_half_life_s > config.warm_half_life_s
    assert config.archive_half_life_s > config.cold_half_life_s
