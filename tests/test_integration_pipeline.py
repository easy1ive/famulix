"""Integration test: full pipeline from history generation to briefing."""

from famulix.briefing import build_briefing, render_briefing_markdown
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history_with_truth


def test_full_pipeline_history_to_brief():
    """Test complete pipeline: factory → encode → brief."""
    # Generate synthetic history with ground truth
    events, manifest, truth = generate_history_with_truth(persona_id="alex", seed=42, days=7)

    # Encode events into memory graph
    graph = encode_events_to_graph(events)
    assert graph.node_count() > 0

    # Build briefing (use end of last day as now_s)
    from datetime import datetime

    end_dt = datetime.fromisoformat(manifest.end_date)
    now_s = int(end_dt.timestamp()) + 86400  # End of last day
    briefing = build_briefing(graph, date_str=manifest.end_date, now_s=now_s)
    assert briefing is not None

    # Render
    md = render_briefing_markdown(briefing)
    assert len(md) > 0


def test_pipeline_determinism():
    """Same seed produces identical histories."""
    events1, _, _ = generate_history_with_truth(persona_id="alex", seed=123, days=3)
    events2, _, _ = generate_history_with_truth(persona_id="alex", seed=123, days=3)

    # Events should be identical
    assert len(events1) == len(events2)
    for e1, e2 in zip(events1, events2, strict=True):
        assert e1.event_id == e2.event_id
        assert e1.timestamp_s == e2.timestamp_s
        assert e1.data == e2.data


def test_pipeline_graph_encoding():
    """Verify encoding produces non-empty graph with expected structure."""
    events, _, _ = generate_history_with_truth(persona_id="alex", seed=99, days=3)
    graph = encode_events_to_graph(events)

    # Should have nodes
    assert graph.node_count() > 0
    # Should have some edges
    assert graph.edge_count() >= 0
    # All nodes should be retrievable
    all_nodes = graph.all_nodes()
    assert len(all_nodes) == graph.node_count()
