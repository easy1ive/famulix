"""Performance tests for large graphs."""

import time

from famulix.memory_graph import MemoryGraph, MemoryNode


def test_large_graph_creation():
    """Creating a large graph should be reasonably fast."""
    graph = MemoryGraph()

    start = time.perf_counter()
    for i in range(1000):
        graph.add_node(MemoryNode.create(kind="fact", title=f"Fact {i}", body=f"Body {i}"))
    elapsed = time.perf_counter() - start

    # Should complete in under 1 second
    assert elapsed < 1.0
    assert graph.node_count() == 1000


def test_large_graph_summary():
    """Computing summary of large graph should be fast."""
    graph = MemoryGraph()
    for i in range(1000):
        graph.add_node(MemoryNode.create(kind="fact", title=f"Fact {i}", body=f"Body {i}"))

    start = time.perf_counter()
    summary = graph.summary()
    elapsed = time.perf_counter() - start

    # Should complete in under 0.1 seconds
    assert elapsed < 0.1
    assert summary["node_count"] == 1000
