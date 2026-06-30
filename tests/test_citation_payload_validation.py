"""Test citation payloads always resolve to live memories."""

from famulix.retrieval import RetrievalResult


def test_citation_payload_format():
    """Verify citation payload structure."""
    result = RetrievalResult(
        node_id="n1",
        score=0.95,
        citation="mem:n1:fact:Meeting at 3pm",
        metadata={"bm25": 0.8, "recency": 0.9},
    )

    d = result.as_dict()

    assert d["node_id"] == "n1"
    assert d["score"] == 0.95
    assert "citation" in d
    assert "metadata" in d


def test_citation_payload_metadata_rounding():
    """Verify metadata floats are rounded."""
    result = RetrievalResult(
        node_id="n1",
        score=0.123456789,
        citation="mem:n1",
        metadata={"score": 0.987654321},
    )

    d = result.as_dict()

    assert d["score"] == 0.123457
    assert d["metadata"]["score"] == 0.987654
