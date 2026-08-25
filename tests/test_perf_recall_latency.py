"""Performance test: recall latency on a 90-day persona history.

These tests measure actual timing; bounds are generous since CI varies.
"""

import time

from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history_with_truth
from famulix.retrieval import BM25Index, query_with_filters


def _build_index():
    events, _manifest, _truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=90,
    )
    graph = encode_events_to_graph(events)
    index = BM25Index()
    for node in graph.active_nodes():
        index.add(node.node_id, f"{node.title} {node.body}")
    return index, graph


def test_recall_latency_90day():
    index, graph = _build_index()
    queries = ["home address", "meeting schedule", "project deadline", "contact info", "reminder"]

    # Warm up
    for q in queries:
        query_with_filters(q, graph=graph, index=index, now_s=2000000, max_results=10)

    # Measure
    start = time.monotonic()
    iterations = 50
    for _ in range(iterations):
        for q in queries:
            query_with_filters(q, graph=graph, index=index, now_s=2000000, max_results=10)
    elapsed = time.monotonic() - start
    avg_ms = (elapsed / (iterations * len(queries))) * 1000
    assert avg_ms < 5000, f"recall avg {avg_ms:.1f}ms exceeds 5s budget"


def test_index_build_time_90day():
    events, _manifest, _truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=90,
    )
    graph = encode_events_to_graph(events)

    start = time.monotonic()
    index = BM25Index()
    for node in graph.active_nodes():
        index.add(node.node_id, f"{node.title} {node.body}")
    elapsed_ms = (time.monotonic() - start) * 1000
    assert elapsed_ms < 30000, f"index build {elapsed_ms:.0f}ms exceeds 30s budget"
