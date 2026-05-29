"""Integration test: encoding pipeline and decay mechanics.

Verifies that encoding produces correct graph structure, hostile text is
sanitized, and decay respects protected/pinned memories.
"""

from famulix.decay import DecayConfig, retention_score
from famulix.encoding import encode_events_to_graph, sanitize_hostile_text
from famulix.factory import generate_history
from famulix.memory_graph import MemoryNode


def test_encoding_produces_valid_graph_structure():
    """Verify encoding produces a graph with no dangling edges."""
    events, _ = generate_history(persona_id="alex", seed=42, days=10)
    graph = encode_events_to_graph(events)

    # All edges should reference existing nodes
    all_ids = {n.node_id for n in graph.all_nodes()}
    for edge in graph.all_edges():
        assert edge.from_id in all_ids, f"Dangling source: {edge.from_id}"
        assert edge.to_id in all_ids, f"Dangling target: {edge.to_id}"

    # Should have episodes, entities, and facts
    kinds = {n.kind for n in graph.all_nodes()}
    assert "episode" in kinds
    assert "entity" in kinds or "fact" in kinds


def test_encoding_fact_provenance():
    """Verify fact nodes track their source event."""
    events, _ = generate_history(persona_id="alex", seed=99, days=5)
    graph = encode_events_to_graph(events)

    fact_nodes = [n for n in graph.all_nodes() if n.kind == "fact"]
    for fact in fact_nodes:
        source_event = fact.metadata.get("source_event")
        assert source_event, "Fact should have source_event metadata"
        # Source event should be one of the input events
        event_ids = {e.event_id for e in events}
        assert source_event in event_ids, f"Unknown source: {source_event}"


def test_sanitize_hostile_text():
    """Verify hostile text is sanitized correctly."""
    # Zero-width characters
    text_with_zw = "hello​world"
    sanitized = sanitize_hostile_text(text_with_zw)
    assert "​" not in sanitized
    assert "helloworld" in sanitized

    # Control characters
    text_with_ctrl = "hello\x00world"
    sanitized = sanitize_hostile_text(text_with_ctrl)
    assert "\x00" not in sanitized

    # Excessive whitespace
    text_with_spaces = "hello    world"
    sanitized = sanitize_hostile_text(text_with_spaces)
    assert "hello world" in sanitized


def test_decay_reduces_salience_over_time():
    """Verify decay reduces salience as memories age."""
    # Create a fact node
    node = MemoryNode.create(
        kind="fact",
        title="test fact",
        body="This is a test fact",
        created_at_s=1000000,
    )

    # Apply decay with default config
    config = DecayConfig()
    salience_now = retention_score(node, now_s=1000000, config=config)
    salience_later = retention_score(node, now_s=1000000 + 86400 * 30, config=config)

    # Salience should decrease over time
    assert salience_later < salience_now, "Salience should decay over time"
    assert 0.0 <= salience_later <= 1.0, "Salience should be in [0, 1]"


def test_decay_respects_pinned_memories():
    """Verify pinned memories are protected from decay."""
    # Create a pinned fact node
    node = MemoryNode.create(
        kind="fact",
        title="pinned fact",
        body="This is important",
        created_at_s=1000000,
        metadata={"pinned": "true"},
    )

    config = DecayConfig()
    salience_now = retention_score(node, now_s=1000000, config=config)
    salience_later = retention_score(node, now_s=1000000 + 86400 * 365, config=config)

    # Pinned memories should not decay (or decay much less)
    assert salience_later >= salience_now * 0.9, "Pinned memories should be protected"


def test_decay_tier_based_retention():
    """Verify different tiers have different retention curves.

    Note: "hot" tier has short half-life (1 day) so it decays quickly.
    "cold" tier has long half-life (30 days) so it decays slowly.
    This is intentional - hot memories are very recent, cold are archival.
    """
    # Create nodes in different tiers
    hot_node = MemoryNode.create(
        kind="fact",
        title="hot fact",
        body="Recent important fact",
        created_at_s=1000000,
        metadata={"tier": "hot"},
    )
    cold_node = MemoryNode.create(
        kind="fact",
        title="cold fact",
        body="Older less important fact",
        created_at_s=1000000,
        metadata={"tier": "cold"},
    )

    config = DecayConfig()
    time_later = 1000000 + 86400 * 60  # 60 days later

    hot_salience = retention_score(hot_node, now_s=time_later, config=config)
    cold_salience = retention_score(cold_node, now_s=time_later, config=config)

    # Cold tier retains more than hot tier (cold has longer half-life)
    assert cold_salience >= hot_salience, "Cold tier should retain more than hot"
    assert 0.0 <= hot_salience <= 1.0
    assert 0.0 <= cold_salience <= 1.0
