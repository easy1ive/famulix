"""Edge case tests for retrieval module."""

from famulix.retrieval import BM25Index


def test_empty_query():
    """Empty query should return empty scores."""
    index = BM25Index()
    index.add("doc1", "test document")
    scores = index.score("")
    assert scores == {}


def test_whitespace_query():
    """Whitespace-only query should return empty scores."""
    index = BM25Index()
    index.add("doc1", "test document")
    scores = index.score("   ")
    assert scores == {}


def test_no_documents():
    """Scoring empty index should return empty results."""
    index = BM25Index()
    scores = index.score("test")
    assert scores == {}


def test_query_no_match():
    """Query with no matching terms should return empty scores."""
    index = BM25Index()
    index.add("doc1", "first document")
    scores = index.score("xyz")
    assert scores == {}


def test_single_document():
    """Single document should be scored correctly."""
    index = BM25Index()
    index.add("doc1", "test document")
    scores = index.score("test")
    assert "doc1" in scores
    assert scores["doc1"] > 0
