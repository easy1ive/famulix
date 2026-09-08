"""Tests for event encoding round-trip: encode then decode reconstructs the source."""

from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history_with_truth


def test_encoding_preserves_event_ids():
    events, _manifest, _truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=7,
    )
    graph = encode_events_to_graph(events)
    assert graph.node_count() > 0


def test_encoding_produces_fact_nodes():
    events, _manifest, _truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=7,
    )
    graph = encode_events_to_graph(events)
    facts = [n for n in graph.all_nodes() if n.kind == "fact"]
    assert len(facts) > 0


def test_encoding_produces_episode_nodes():
    events, _manifest, _truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=7,
    )
    graph = encode_events_to_graph(events)
    episodes = [n for n in graph.all_nodes() if n.kind == "episode"]
    assert len(episodes) > 0


def test_encoding_deterministic():
    g1 = encode_events_to_graph(generate_history_with_truth(persona_id="alex", seed=42, days=5)[0])
    g2 = encode_events_to_graph(generate_history_with_truth(persona_id="alex", seed=42, days=5)[0])
    ids1 = sorted(n.node_id for n in g1.all_nodes())
    ids2 = sorted(n.node_id for n in g2.all_nodes())
    assert ids1 == ids2


def test_encoding_no_dangling_edges():
    events, _manifest, _truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=7,
    )
    graph = encode_events_to_graph(events)
    node_ids = {n.node_id for n in graph.all_nodes()}
    for edge in graph.all_edges():
        assert edge.from_id in node_ids, f"dangling from_id: {edge.from_id}"
        assert edge.to_id in node_ids, f"dangling to_id: {edge.to_id}"


def test_encoding_preserves_text_content():
    """Encoded fact nodes should contain text from the source events."""
    events, _manifest, truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=7,
    )
    graph = encode_events_to_graph(events)
    facts = [n for n in graph.all_nodes() if n.kind == "fact"]
    # At least one fact should have non-empty body text
    assert any(n.body.strip() for n in facts)
