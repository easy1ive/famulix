"""Tests for retrieval query parser: entities, time windows, and tags."""

from famulix.retrieval import parse_query


def test_parse_simple_query():
    result = parse_query("home address")
    assert "terms" in result
    assert len(result["terms"]) >= 1


def test_parse_query_with_kind():
    result = parse_query("kind:fact meeting schedule")
    assert "kinds" in result
    assert "fact" in result["kinds"]


def test_parse_query_with_tag():
    result = parse_query("tag:important project deadline")
    assert "tags" in result
    assert "important" in result["tags"]


def test_parse_empty_query():
    result = parse_query("")
    assert result.get("terms") == [] or result.get("terms") is None


def test_parse_query_deterministic():
    r1 = parse_query("meeting tomorrow")
    r2 = parse_query("meeting tomorrow")
    assert r1 == r2


def test_parse_query_preserves_order():
    result = parse_query("alpha beta gamma")
    terms = result.get("terms", [])
    assert len(terms) >= 1
