"""End-to-end integration test: ingest -> consolidate -> recall -> brief."""

from famulix.briefing import build_briefing, render_briefing_html
from famulix.consolidation import consolidate_graph
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history_with_truth
from famulix.memory_graph import MemoryGraph
from famulix.retrieval import BM25Index, query_with_filters


def _build_graph(days: int = 14, seed: int = 42) -> MemoryGraph:
    events, _manifest, _truth = generate_history_with_truth(
        persona_id="alex",
        seed=seed,
        days=days,
    )
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    return graph


def test_full_pipeline_produces_briefing():
    graph = _build_graph(days=14)
    assert graph.node_count() > 0

    # Build retrieval index and query
    index = BM25Index()
    for node in graph.active_nodes():
        index.add(node.node_id, f"{node.title} {node.body}")
    results = query_with_filters(
        "address",
        graph=graph,
        index=index,
        now_s=2000000,
        max_results=5,
    )
    assert len(results) > 0

    # Build briefing
    briefing = build_briefing(
        graph,
        date_str="2026-03-15",
        now_s=1742000000,
        seed=42,
    )
    html = render_briefing_html(briefing)
    assert "<html" in html.lower() or "<!doctype" in html.lower()


def test_pipeline_citations_resolve_to_live_memories():
    graph = _build_graph(days=7)
    index = BM25Index()
    for node in graph.active_nodes():
        index.add(node.node_id, f"{node.title} {node.body}")

    results = query_with_filters(
        "meeting",
        graph=graph,
        index=index,
        now_s=2000000,
        max_results=10,
    )
    active_ids = {n.node_id for n in graph.active_nodes()}
    for r in results:
        assert r.node_id in active_ids, f"retrieval hit cites non-live memory {r.node_id}"


def test_pipeline_deterministic_across_runs():
    """Same seed produces identical briefing HTML."""
    htmls = []
    for _ in range(2):
        graph = _build_graph(days=7, seed=42)
        briefing = build_briefing(
            graph,
            date_str="2026-03-15",
            now_s=1742000000,
            seed=42,
        )
        htmls.append(render_briefing_html(briefing))
    assert htmls[0] == htmls[1], "briefing HTML must be byte-deterministic"
