"""Comprehensive edge case tests."""

from famulix.context import ContextItem, assemble_context
from famulix.memory_graph import MemoryGraph
from famulix.retrieval import BM25Index


def test_empty_graph_operations():
    """Empty graph should handle all operations gracefully."""
    graph = MemoryGraph()
    assert graph.summary()["node_count"] == 0
    assert len(graph.all_nodes()) == 0
    assert len(graph.all_edges()) == 0


def test_empty_index_operations():
    """Empty index should handle all operations gracefully."""
    index = BM25Index()
    assert index.doc_count == 0
    assert index.term_count == 0
    assert index.score("test") == {}


def test_context_budget_edge_cases():
    """Context assembly should handle budget edge cases."""
    items = [ContextItem(item_id="1", payload="text", value=1.0, token_estimate=100)]

    # Zero budget
    result = assemble_context(items, budget=0)
    assert result.items == []

    # Exact budget
    result = assemble_context(items, budget=100)
    assert len(result.items) == 1

    # Over budget
    result = assemble_context(items, budget=50)
    assert result.items == []
