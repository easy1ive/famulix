"""Test retrieval index statistics."""

from famulix.retrieval import BM25Index, retrieval_index_stats


def test_empty_index():
    """Empty index should have zero counts."""
    index = BM25Index()
    stats = retrieval_index_stats(index)
    assert stats["doc_count"] == 0
    assert stats["term_count"] == 0


def test_index_stats():
    """Should count documents and terms."""
    index = BM25Index()
    index.add("doc1", "hello world")
    index.add("doc2", "hello there")

    stats = retrieval_index_stats(index)
    assert stats["doc_count"] == 2
    assert stats["term_count"] > 0
