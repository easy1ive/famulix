"""Integration test: deletion cascade followed by retrieval and context checks."""

from famulix.consolidation import consolidate_graph
from famulix.context import ContextItem, assemble_context
from famulix.deletion import delete_memory, is_deleted
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history_with_truth
from famulix.retrieval import BM25Index, query_with_filters


def test_deletion_removes_from_index_and_context():
    """After deletion, the memory is absent from both retrieval and context."""
    events, _, truth = generate_history_with_truth(persona_id="alex", seed=42, days=7)
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)

    # Pick the first active fact to delete
    active_facts = [n for n in graph.active_nodes() if n.kind == "fact"]
    assert len(active_facts) > 0
    target = active_facts[0]
    target_id = target.node_id

    # Delete the memory
    delete_memory(graph, target_id, cascade=True)
    assert is_deleted(graph, target_id)

    # Build retrieval index from remaining active nodes
    index = BM25Index()
    for node in graph.active_nodes():
        index.add(node.node_id, f"{node.title} {node.body}")

    # Query and verify deleted memory is absent
    results = query_with_filters(
        target.title,
        graph=graph,
        index=index,
        now_s=2000000,
        max_results=20,
    )
    result_ids = {r.node_id for r in results}
    assert target_id not in result_ids

    # Context assembly also excludes the deleted memory
    ctx_items = [
        ContextItem(
            item_id=n.node_id,
            payload=f"{n.title} {n.body}",
            token_estimate=10,
            value=0.5,
        )
        for n in graph.active_nodes()
    ]
    ctx = assemble_context(ctx_items, budget=500)
    ctx_ids = {item.item_id for item in ctx.items}
    assert target_id not in ctx_ids


def test_consolidation_then_deletion_stable():
    """Consolidating after deletion does not resurrect deleted memories."""
    events, _, _ = generate_history_with_truth(persona_id="alex", seed=42, days=7)
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)

    active_facts = [n for n in graph.active_nodes() if n.kind == "fact"]
    if not active_facts:
        return
    target_id = active_facts[0].node_id
    delete_memory(graph, target_id, cascade=True)

    # Consolidate again — should not bring back the deleted node
    consolidate_graph(graph)
    assert is_deleted(graph, target_id)
    active_ids = {n.node_id for n in graph.active_nodes()}
    assert target_id not in active_ids
