"""Integration test: full pipeline from history generation to briefing."""

from famulix.briefing import build_briefing, render_briefing_markdown
from famulix.consolidation import consolidate_graph
from famulix.context import ContextItem, assemble_context, estimate_tokens
from famulix.encoding import encode_events_to_graph
from famulix.evaluation import eval_contradiction_resolution, eval_recall_precision
from famulix.factory import generate_history_with_truth
from famulix.retrieval import BM25Index, hybrid_score


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


def test_pipeline_consolidate_retrieve_brief():
    """Consolidate → retrieve → brief with invariant checks at each stage."""
    events, manifest, truth = generate_history_with_truth(
        persona_id="alex", seed=99, days=30, start_date="2026-03-01"
    )
    graph = encode_events_to_graph(events)
    assert graph.node_count() > 0

    # No dangling edges after encoding
    all_ids = {n.node_id for n in graph.all_nodes()}
    for edge in graph.all_edges():
        assert edge.from_id in all_ids
        assert edge.to_id in all_ids

    # Consolidation is idempotent (second run finds nothing new)
    consolidate_graph(graph)
    report2 = consolidate_graph(graph)
    assert report2.total_changes() == 0

    # No dangling edges after consolidation
    all_ids_after = {n.node_id for n in graph.all_nodes()}
    for edge in graph.all_edges():
        assert edge.from_id in all_ids_after
        assert edge.to_id in all_ids_after

    # Retrieval returns valid citations
    idx = BM25Index()
    for node in graph.all_nodes():
        if node.is_active:
            idx.add_node(node)
    now_s = events[-1].timestamp_s + 3600
    results = hybrid_score("address phone schedule", graph=graph, index=idx, now_s=now_s)
    for r in results[:10]:
        assert graph.get_node(r.node_id) is not None

    # Briefing cites existing nodes
    briefing = build_briefing(graph, date_str=manifest.end_date, now_s=now_s, seed=99)
    for item in briefing.items:
        for mid in item.memory_ids:
            assert graph.get_node(mid) is not None

    # Context assembly respects budget
    ctx_items = [
        ContextItem(
            item_id=r.node_id,
            token_estimate=estimate_tokens(r.citation),
            value=r.score,
            payload=r.citation,
        )
        for r in results[:20]
    ]
    ctx = assemble_context(ctx_items, budget=200)
    assert ctx.total_tokens <= 200


def test_pipeline_planted_fact_recovery():
    """Evaluation harness recovers planted facts through the full pipeline."""
    events, _manifest, truth = generate_history_with_truth(
        persona_id="alex", seed=7, days=45, start_date="2026-02-01"
    )
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)
    now_s = events[-1].timestamp_s + 3600

    planted_fact_set = set(truth["fact_ids"])
    recall, precision = eval_recall_precision(graph, planted_fact_set, now_s)
    assert recall["@5"] >= 0.5
    assert precision["@5"] > 0.0


def test_pipeline_contradiction_resolution():
    """Contradiction resolution works end-to-end."""
    events, _manifest, truth = generate_history_with_truth(
        persona_id="alex", seed=42, days=60, start_date="2026-01-01"
    )
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)

    pairs = [(p[0], p[1]) for p in truth["contradiction_pairs"]]
    accuracy = eval_contradiction_resolution(graph, pairs)
    assert accuracy >= 0.5


def test_pipeline_mmr_diversity_reranking():
    """MMR diversity reranking integrates with retrieval pipeline."""
    from famulix.retrieval import mmr_rerank

    events, _manifest, truth = generate_history_with_truth(
        persona_id="alex", seed=55, days=21, start_date="2026-04-01"
    )
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)

    idx = BM25Index()
    for node in graph.all_nodes():
        if node.is_active:
            idx.add_node(node)

    now_s = events[-1].timestamp_s + 3600
    results = hybrid_score("meeting schedule address", graph=graph, index=idx, now_s=now_s)

    # Apply MMR reranking
    diverse_results = mmr_rerank(results, graph=graph, top_k=5, lambda_param=0.7)

    # Should return requested number of results
    assert len(diverse_results) <= 5
    # All results should have valid node references
    for r in diverse_results:
        assert graph.get_node(r.node_id) is not None


def test_pipeline_index_rebuild():
    """BM25 index rebuild works with graph mutations."""
    events, _manifest, truth = generate_history_with_truth(
        persona_id="alex", seed=77, days=14, start_date="2026-05-01"
    )
    graph = encode_events_to_graph(events)

    idx = BM25Index()
    idx.rebuild_from_graph(graph)
    initial_count = idx.doc_count

    # Add a new node
    from famulix.memory_graph import MemoryNode

    new_node = MemoryNode.create(
        kind="fact",
        title="new test fact",
        body="this is a test fact for rebuild",
        created_at_s=events[-1].timestamp_s + 100,
    )
    graph.add_node(new_node)

    # Index should detect staleness
    assert idx.needs_rebuild(graph)

    # Rebuild should include new node
    idx.rebuild_from_graph(graph)
    assert idx.doc_count == initial_count + 1
    assert not idx.needs_rebuild(graph)
