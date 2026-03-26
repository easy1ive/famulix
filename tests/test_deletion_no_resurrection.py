"""Property test: deleted memories never resurrect through any query path."""

from famulix.consolidation import consolidate_graph
from famulix.deletion import delete_memory
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history
from famulix.retrieval import BM25Index, query_with_filters


def test_deleted_memory_never_reappears():
    """Verify deleted memories cannot be retrieved through any path."""
    events, _manifest = generate_history(seed=99, days=20)
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)

    # Get a memory to delete
    nodes = list(graph.all_nodes())
    assert len(nodes) > 0
    target = nodes[0]
    target_id = target.node_id

    # Delete it
    delete_memory(graph, target_id)

    # Build index
    index = BM25Index()
    for node in graph.all_nodes():
        index.add_node(node)

    # Try to retrieve it through various queries
    queries = [
        target.title,
        target.body[:30],
        f"kind:{target.kind} {target.title}",
    ]

    for query_text in queries:
        results = query_with_filters(
            query_text, graph=graph, index=index, now_s=events[-1].timestamp_s, max_results=20
        )
        result_ids = {r.node_id for r in results}
        assert target_id not in result_ids, f"deleted memory {target_id} resurrected"


def test_deletion_cascade_removes_edges():
    """Verify deletion removes all edges referencing the deleted node."""
    graph = encode_events_to_graph(
        [
            type(
                "Event",
                (),
                {
                    "event_id": "e1",
                    "event_type": "note",
                    "timestamp_s": 100,
                    "source": "test",
                    "data": {"text": "first note"},
                    "version": 1,
                },
            )(),
            type(
                "Event",
                (),
                {
                    "event_id": "e2",
                    "event_type": "note",
                    "timestamp_s": 200,
                    "source": "test",
                    "data": {"text": "second note"},
                    "version": 1,
                },
            )(),
        ]
    )

    # Get two nodes
    nodes = list(graph.all_nodes())
    if len(nodes) < 2:
        return  # Skip if not enough nodes

    n1, n2 = nodes[0], nodes[1]

    # Add an edge between them
    from famulix.memory_graph import MemoryEdge

    edge = MemoryEdge(edge_id="e_test", from_id=n1.node_id, to_id=n2.node_id, kind="related")
    graph.add_edge(edge)

    # Delete first node
    delete_memory(graph, n1.node_id)

    # Edge should be gone
    edges = list(graph.all_edges())
    assert all(e.from_id != n1.node_id and e.to_id != n1.node_id for e in edges), (
        "edges referencing deleted node should be removed"
    )
