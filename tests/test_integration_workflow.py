"""Integration test for full workflow."""

from famulix.briefing import briefing_stats, build_briefing
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history_with_truth


def test_full_workflow():
    """Test complete workflow from history to briefing."""
    from datetime import datetime

    # Generate history
    events, manifest, truth = generate_history_with_truth(persona_id="alex", seed=42, days=7)

    # Encode to graph
    graph = encode_events_to_graph(events)
    assert graph.node_count() > 0

    # Compute now_s from end_date
    end_dt = datetime.fromisoformat(manifest.end_date)
    now_s = int(end_dt.timestamp()) + 86400

    # Build briefing
    briefing = build_briefing(graph, date_str=manifest.end_date, now_s=now_s)
    assert briefing is not None

    # Get statistics
    stats = briefing_stats(briefing)
    assert stats["item_count"] >= 0
    assert stats["citation_count"] >= 0
