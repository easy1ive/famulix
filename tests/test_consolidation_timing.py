"""Tests for consolidation elapsed timing."""

from famulix.consolidation import consolidate_graph
from famulix.memory_graph import MemoryGraph


def test_consolidation_records_elapsed_time():
    """Consolidation report includes elapsed_seconds."""
    graph = MemoryGraph()
    report = consolidate_graph(graph)
    assert report.elapsed_seconds >= 0.0
    assert "elapsed_seconds" in report.to_dict()


def test_consolidation_elapsed_in_dict():
    """elapsed_seconds appears in dict with rounding."""
    graph = MemoryGraph()
    report = consolidate_graph(graph)
    d = report.to_dict()
    assert isinstance(d["elapsed_seconds"], float)


def test_consolidation_elapsed_in_markdown():
    """Markdown report includes elapsed time when non-zero."""
    graph = MemoryGraph()
    report = consolidate_graph(graph)
    # Force a non-zero elapsed for testing
    report.elapsed_seconds = 0.123
    md = report.to_markdown()
    assert "Elapsed:" in md
    assert "0.123s" in md


def test_consolidation_elapsed_omitted_when_zero():
    """Markdown omits elapsed when zero (empty consolidation)."""
    graph = MemoryGraph()
    report = consolidate_graph(graph)
    report.elapsed_seconds = 0.0
    md = report.to_markdown()
    assert "Elapsed:" not in md
