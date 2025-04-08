"""Tests for BM25 + hybrid retrieval + MMR."""

from __future__ import annotations

from famulix.memory_graph import MemoryGraph, MemoryNode
from famulix.retrieval import (
    BM25Index,
    FusionConfig,
    hybrid_score,
    mmr_rerank,
    parse_query,
    tokenize,
)


def test_tokenize_lowercase_and_split() -> None:
    tokens = tokenize("Hello, World! This is a test.")
    assert "hello" in tokens
    assert "world" in tokens
    assert len(tokens) == 6


def test_tokenize_chinese() -> None:
    tokens = tokenize("你好世界")
    assert len(tokens) >= 1


def test_bm25_basic_ranking() -> None:
    idx = BM25Index()
    idx.add("d1", "the quick brown fox jumps over the lazy dog")
    idx.add("d2", "a fast brown hare runs through the forest")
    idx.add("d3", "completely unrelated content about cooking")
    scores = idx.score("brown fox")
    assert "d1" in scores
    assert scores["d1"] > scores.get("d2", 0)


def test_bm25_no_match() -> None:
    idx = BM25Index()
    idx.add("d1", "hello world")
    scores = idx.score("xyz")
    assert scores == {}


def test_bm25_add_remove() -> None:
    idx = BM25Index()
    idx.add("d1", "hello world")
    idx.add("d2", "goodbye world")
    assert len(idx.docs) == 2
    idx.remove("d1")
    assert len(idx.docs) == 1
    scores = idx.score("hello")
    assert "d1" not in scores


def test_hybrid_score_returns_citations() -> None:
    g = MemoryGraph()
    n = MemoryNode.create("fact", "test memory", "this is a test memory body", created_at_s=1000)
    g.add_node(n)
    idx = BM25Index()
    idx.add_node(n)
    results = hybrid_score("test memory", graph=g, index=idx, now_s=2000)
    assert len(results) >= 1
    r = results[0]
    assert r.node_id == n.node_id
    assert r.citation  # non-empty
    # Verify citation resolves to live memory
    assert g.get_node(r.node_id) is not None
    assert g.get_node(r.node_id).is_active


def test_hybrid_score_weights() -> None:
    g = MemoryGraph()
    n1 = MemoryNode.create("fact", "a", "apple banana cherry", created_at_s=100)
    n2 = MemoryNode.create("fact", "b", "apple banana date", created_at_s=5000)
    g.add_node(n1)
    g.add_node(n2)
    idx = BM25Index()
    idx.add_node(n1)
    idx.add_node(n2)
    # Recency-heavy config should prefer newer (n2)
    recency_cfg = FusionConfig(bm25_weight=0.0, recency_weight=1.0, salience_weight=0.0)
    results = hybrid_score("apple banana", graph=g, index=idx, now_s=6000, config=recency_cfg)
    assert results[0].node_id == n2.node_id


def test_mmr_diversifies() -> None:
    g = MemoryGraph()
    # Three docs: two very similar, one different
    n1 = MemoryNode.create("fact", "a1", "apple banana cherry date elderberry", created_at_s=100)
    n2 = MemoryNode.create("fact", "a2", "apple banana cherry date fig", created_at_s=200)
    n3 = MemoryNode.create("fact", "b1", "xyz abc def ghi jkl", created_at_s=300)
    g.add_node(n1)
    g.add_node(n2)
    g.add_node(n3)
    idx = BM25Index()
    idx.add_node(n1)
    idx.add_node(n2)
    idx.add_node(n3)

    from famulix.retrieval import RetrievalResult

    # Three results with similar scores
    results = [
        RetrievalResult(node_id=n1.node_id, score=0.9, citation="a1"),
        RetrievalResult(node_id=n2.node_id, score=0.85, citation="a2"),
        RetrievalResult(node_id=n3.node_id, score=0.8, citation="b1"),
    ]
    reranked = mmr_rerank(results, graph=g, lambda_param=0.5, top_k=2)
    assert len(reranked) == 2
    # With low lambda, diversity matters: should pick one from {n1,n2} plus n3
    selected_ids = {r.node_id for r in reranked}
    assert n3.node_id in selected_ids
    assert (n1.node_id in selected_ids) != (n2.node_id in selected_ids)


def test_mmr_respects_top_k() -> None:
    g = MemoryGraph()
    from famulix.retrieval import RetrievalResult

    results = [
        RetrievalResult(node_id=f"n{i}", score=1.0 - i * 0.1, citation=f"doc {i}")
        for i in range(10)
    ]
    for i in range(10):
        g.add_node(MemoryNode.create("fact", f"n{i}", f"unique content {i}", created_at_s=i * 100))
    reranked = mmr_rerank(results, graph=g, top_k=3)
    assert len(reranked) == 3


def test_parse_query_filters() -> None:
    q = parse_query("meeting kind:fact tag:work since:2024-01-01")
    assert "meeting" in q["terms"]
    assert "fact" in q["kinds"]
    assert "work" in q["tags"]
    assert q["since"] == "2024-01-01"
    assert q["until"] is None


def test_parse_query_plain_terms() -> None:
    q = parse_query("hello world")
    assert q["terms"] == ["hello", "world"]
    assert q["kinds"] == []
    assert q["tags"] == []


def test_retrieval_deterministic() -> None:
    g = MemoryGraph()
    n1 = MemoryNode.create("fact", "apple", "red fruit", created_at_s=100)
    n2 = MemoryNode.create("fact", "banana", "yellow fruit", created_at_s=200)
    g.add_node(n1)
    g.add_node(n2)
    idx = BM25Index()
    idx.add_node(n1)
    idx.add_node(n2)
    r1 = hybrid_score("fruit", graph=g, index=idx, now_s=500)
    r2 = hybrid_score("fruit", graph=g, index=idx, now_s=500)
    assert [x.node_id for x in r1] == [x.node_id for x in r2]
    assert [round(x.score, 6) for x in r1] == [round(x.score, 6) for x in r2]


def test_hybrid_score_breaks_equal_scores_by_memory_id() -> None:
    graph = MemoryGraph()
    nodes = [
        MemoryNode.create("fact", "same", "same text", metadata={"case": str(i)}) for i in range(2)
    ]
    for node in nodes:
        graph.add_node(node)
    index = BM25Index()
    for node in nodes:
        index.add_node(node)
    results = hybrid_score("absent", graph=graph, index=index, now_s=1000000000)
    assert [item.node_id for item in results] == sorted(node.node_id for node in nodes)


def test_fusion_config_rejects_invalid_weight_sets() -> None:
    import pytest

    with pytest.raises(ValueError, match="finite and non-negative"):
        FusionConfig(bm25_weight=float("nan"))
    with pytest.raises(ValueError, match="finite and non-negative"):
        FusionConfig(recency_weight=-0.1)
    with pytest.raises(ValueError, match="at least one"):
        FusionConfig(0.0, 0.0, 0.0)
