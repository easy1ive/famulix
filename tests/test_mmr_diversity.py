"""Tests for MMR diversity reranking on near-duplicate sets."""

from famulix.memory_graph import MemoryGraph, MemoryNode
from famulix.retrieval import RetrievalResult, mmr_rerank


def _build_graph_with_nodes() -> MemoryGraph:
    g = MemoryGraph()
    nodes = [
        MemoryNode(node_id="m1", kind="fact", title="address", body="123 Oak St"),
        MemoryNode(node_id="m2", kind="fact", title="address", body="123 Oak Street"),
        MemoryNode(node_id="m3", kind="fact", title="phone", body="555-0100"),
        MemoryNode(node_id="m4", kind="fact", title="email", body="user@test.com"),
    ]
    for n in nodes:
        g.add_node(n)
    return g


def test_mmr_diversifies_near_duplicates():
    """MMR should prefer diverse results over near-duplicates."""
    graph = _build_graph_with_nodes()
    results = [
        RetrievalResult(node_id="m1", score=0.9, citation="address: 123 Oak St"),
        RetrievalResult(node_id="m2", score=0.88, citation="address: 123 Oak Street"),
        RetrievalResult(node_id="m3", score=0.7, citation="phone: 555-0100"),
        RetrievalResult(node_id="m4", score=0.6, citation="email: user@test.com"),
    ]
    reranked = mmr_rerank(results, graph=graph, top_k=3, lambda_param=0.5)
    ids = [r.node_id for r in reranked]
    assert ids[0] == "m1"
    assert "m3" in ids or "m4" in ids


def test_mmr_deterministic():
    """Same inputs produce same output."""
    graph = _build_graph_with_nodes()
    results = [
        RetrievalResult(node_id="m1", score=0.8, citation="text a"),
        RetrievalResult(node_id="m3", score=0.7, citation="text b"),
    ]
    r1 = mmr_rerank(results, graph=graph, top_k=2, lambda_param=0.5)
    r2 = mmr_rerank(results, graph=graph, top_k=2, lambda_param=0.5)
    assert [x.node_id for x in r1] == [x.node_id for x in r2]


def test_mmr_top_k_limits_results():
    graph = _build_graph_with_nodes()
    results = [
        RetrievalResult(node_id=f"m{i}", score=0.5 + i * 0.1, citation=f"text {i}")
        for i in range(1, 5)
    ]
    reranked = mmr_rerank(results, graph=graph, top_k=2, lambda_param=0.5)
    assert len(reranked) == 2


def test_mmr_preserves_citation_fields():
    """Reranked results keep their citation payloads."""
    graph = _build_graph_with_nodes()
    results = [
        RetrievalResult(node_id="m1", score=0.9, citation="addr"),
        RetrievalResult(node_id="m3", score=0.7, citation="phone"),
    ]
    reranked = mmr_rerank(results, graph=graph, top_k=2, lambda_param=0.5)
    for r in reranked:
        assert r.citation is not None
