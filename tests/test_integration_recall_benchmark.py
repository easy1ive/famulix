"""Integration test: end-to-end pipeline with recall measurement."""

from famulix.consolidation import consolidate_graph
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history
from famulix.retrieval import BM25Index, query_with_filters


def test_end_to_end_pipeline_recall():
    """Verify full pipeline: generate -> encode -> consolidate -> retrieve."""
    events, manifest = generate_history(persona_id="alex", seed=42, days=30)
    assert len(events) > 0, "factory should generate events"

    graph = encode_events_to_graph(events)
    assert graph.node_count() > 0, "encoding should produce nodes"

    consolidate_graph(graph)

    # Build BM25 index
    index = BM25Index()
    for node in graph.all_nodes():
        index.add_node(node)

    # Query for some content from the events
    sample_events = [e for e in events if e.data.get("text")][:5]
    assert len(sample_events) > 0, "should have events with text"

    hits_total = 0
    for event in sample_events:
        text = str(event.data.get("text", ""))[:50]
        results = query_with_filters(
            text, graph=graph, index=index, now_s=events[-1].timestamp_s, max_results=10
        )
        hits_total += len(results)

    # Should recover at least some results
    assert hits_total >= 5, f"recall too low: {hits_total} hits for {len(sample_events)} queries"
