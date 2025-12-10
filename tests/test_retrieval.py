"""Tests for BM25 + hybrid retrieval + MMR."""

from __future__ import annotations

import pytest

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


def test_hybrid_score_candidate_kind_filter_excludes_other_indexed_kinds() -> None:
    graph = MemoryGraph()
    fact = MemoryNode.create("fact", "meeting", "project sync", created_at_s=100)
    episode = MemoryNode.create("episode", "meeting", "project sync", created_at_s=100)
    graph.add_node(fact)
    graph.add_node(episode)
    index = BM25Index()
    index.add_node(fact)
    index.add_node(episode)
    results = hybrid_score("meeting", graph=graph, index=index, now_s=100, candidate_kinds={"fact"})
    assert [result.node_id for result in results] == [fact.node_id]


def test_query_with_filters_kind_filter() -> None:
    from famulix.retrieval import query_with_filters

    graph = MemoryGraph()
    fact = MemoryNode.create("fact", "meeting", "project sync", created_at_s=100)
    episode = MemoryNode.create("episode", "meeting", "weekly standup", created_at_s=100)
    graph.add_node(fact)
    graph.add_node(episode)
    index = BM25Index()
    index.add_node(fact)
    index.add_node(episode)
    results = query_with_filters("kind:fact meeting", graph=graph, index=index, now_s=200)
    assert all(graph.get_node(r.node_id).kind == "fact" for r in results)
    assert len(results) >= 1


def test_query_with_filters_tag_filter() -> None:
    from famulix.retrieval import query_with_filters

    graph = MemoryGraph()
    a = MemoryNode.create(
        "fact", "note a", "important thing", created_at_s=100, metadata={"tag": "work"}
    )
    b = MemoryNode.create(
        "fact", "note b", "important personal thing", created_at_s=100, metadata={"tag": "personal"}
    )
    graph.add_node(a)
    graph.add_node(b)
    index = BM25Index()
    index.add_node(a)
    index.add_node(b)
    results = query_with_filters("tag:work important", graph=graph, index=index, now_s=200)
    assert all(graph.get_node(r.node_id).metadata.get("tag") == "work" for r in results)


def test_bm25_index_doc_and_term_counts() -> None:
    index = BM25Index()
    assert index.doc_count == 0
    assert index.term_count == 0
    index.add("d1", "apple banana cherry")
    assert index.doc_count == 1
    assert index.term_count == 3
    index.add("d2", "banana date")
    assert index.doc_count == 2
    assert index.term_count == 4  # apple, banana, cherry, date
    index.remove("d1")
    assert index.doc_count == 1
    # term_count is len(df dict); removed terms stay with zero count
    assert index.term_count >= 2


def test_bm25_top_terms_by_frequency() -> None:
    index = BM25Index()
    index.add("d1", "apple banana cherry")
    index.add("d2", "banana date")
    index.add("d3", "banana apple")
    top = index.top_terms(3)
    assert top[0][0] == "banana"  # appears in all 3 docs
    assert top[0][1] == 3
    assert top[1][0] == "apple"  # appears in 2 docs
    assert top[1][1] == 2


def test_query_with_filters_respects_max_results() -> None:
    from famulix.retrieval import query_with_filters

    graph = MemoryGraph()
    for i in range(10):
        node = MemoryNode.create("fact", f"doc{i}", f"content about retrieval {i}", created_at_s=i)
        graph.add_node(node)
        index = BM25Index()
    for node in graph.all_nodes():
        index.add_node(node)
    results = query_with_filters("retrieval", graph=graph, index=index, now_s=100, max_results=3)
    assert len(results) <= 3


def test_parse_query_returns_typed_lists_for_every_filter() -> None:
    from famulix.retrieval import parse_query

    parsed = parse_query("budget kind:fact kind:goal tag:work tag:home since:2026-01-01")
    assert parsed["terms"] == ["budget"]
    assert parsed["kinds"] == ["fact", "goal"]
    assert parsed["tags"] == ["work", "home"]
    assert parsed["since"] == "2026-01-01"
    assert parsed["until"] is None
    for value in parsed.values():
        assert value is None or isinstance(value, (str, list))


def test_parse_query_of_blank_input_yields_empty_filters() -> None:
    from famulix.retrieval import parse_query

    assert parse_query("") == {
        "terms": [],
        "phrases": [],
        "negated": [],
        "kinds": [],
        "tags": [],
        "since": None,
        "until": None,
    }
    assert parse_query("   ")["terms"] == []
    assert parse_query("until:2026-02-01")["until"] == "2026-02-01"


def _tagged_graph() -> tuple[MemoryGraph, BM25Index]:
    graph = MemoryGraph()
    for suffix, tag in (("one", "work"), ("two", "home"), ("three", "work")):
        graph.add_node(
            MemoryNode.create(
                "fact",
                f"quarterly budget review {suffix}",
                f"planning notes about the budget for {suffix}",
                metadata={"tag": tag},
                created_at_s=100,
            )
        )
    index = BM25Index()
    for node in graph.all_nodes():
        index.add_node(node)
    return graph, index


def test_tag_filter_keeps_only_matching_metadata() -> None:
    from famulix.retrieval import query_with_filters

    graph, index = _tagged_graph()
    work = query_with_filters("budget tag:work", graph=graph, index=index, now_s=200)
    assert work, "expected the tag filter to keep the work notes"
    for result in work:
        node = graph.get_node(result.node_id)
        assert node is not None
        assert node.metadata["tag"] == "work"
    assert query_with_filters("budget tag:sport", graph=graph, index=index, now_s=200) == []


def test_tag_filter_accepts_several_tags_at_once() -> None:
    from famulix.retrieval import query_with_filters

    graph, index = _tagged_graph()
    both = query_with_filters("budget tag:work tag:home", graph=graph, index=index, now_s=200)
    assert len(both) == 3
    only_home = query_with_filters("budget tag:home", graph=graph, index=index, now_s=200)
    assert len(only_home) == 1


from dataclasses import replace  # noqa: E402

from famulix.retrieval import RetrievalResult, apply_reranker  # noqa: E402


def _rerank_graph() -> tuple[MemoryGraph, list[str]]:
    graph = MemoryGraph()
    ids: list[str] = []
    for i, text in enumerate(["alpha meeting", "beta deadline", "gamma idea"]):
        node = MemoryNode.create(kind="fact", title=text, body=text, created_at_s=1000 + i)
        graph.add_node(node)
        ids.append(node.node_id)
    return graph, ids


def _results(ids: list[str]) -> list[RetrievalResult]:
    return [
        RetrievalResult(node_id=nid, score=1.0 - i * 0.1, citation=f"cite-{i}")
        for i, nid in enumerate(ids)
    ]


def test_apply_reranker_reorders_and_preserves_set() -> None:
    graph, ids = _rerank_graph()
    results = _results(ids)
    reranked = apply_reranker(results, graph=graph, reranker=lambda hits, _: list(reversed(hits)))
    assert [r.node_id for r in reranked] == list(reversed(ids))
    assert {r.node_id for r in reranked} == set(ids)


def test_apply_reranker_may_drop_hits() -> None:
    graph, ids = _rerank_graph()
    reranked = apply_reranker(_results(ids), graph=graph, reranker=lambda hits, _: hits[:2])
    assert [r.node_id for r in reranked] == ids[:2]


def test_apply_reranker_rejects_invented_and_duplicate_ids() -> None:
    graph, ids = _rerank_graph()
    forged = _results(ids) + [RetrievalResult(node_id="evt_missing", score=9.0, citation="x")]
    with pytest.raises(ValueError, match="invented"):
        apply_reranker(_results(ids), graph=graph, reranker=lambda hits, _: forged)
    with pytest.raises(ValueError, match="duplicated"):
        apply_reranker(_results(ids), graph=graph, reranker=lambda hits, _: hits + hits[:1])


def test_apply_reranker_rejects_deactivated_memories() -> None:
    graph, ids = _rerank_graph()
    results = _results(ids)
    node = graph.get_node(ids[1])
    assert node is not None
    graph._nodes[ids[1]] = replace(node, is_active=False)  # noqa: SLF001
    with pytest.raises(ValueError, match="non-active"):
        apply_reranker(results, graph=graph, reranker=lambda hits, _: hits)


def test_apply_reranker_does_not_mutate_input() -> None:
    graph, ids = _rerank_graph()
    results = _results(ids)
    snapshot = list(results)
    apply_reranker(results, graph=graph, reranker=lambda hits, _: list(reversed(hits)))
    assert results == snapshot
    assert [r.node_id for r in results] == ids


def test_bm25_save_load_roundtrip(tmp_path: pytest.TempPathFactory) -> None:
    idx = BM25Index(k1=1.2, b=0.6)
    idx.add("d1", "hello world apple banana")
    idx.add("d2", "banana cherry date")
    path = tmp_path / "bm25.json"  # type: ignore[operator]
    idx.save(path)
    loaded = BM25Index.load(path)
    assert loaded.k1 == idx.k1
    assert loaded.b == idx.b
    assert loaded.docs == idx.docs
    assert loaded.df == idx.df
    assert loaded.avgdl == idx.avgdl
    assert loaded.score("banana") == idx.score("banana")


def test_bm25_load_rejects_bad_schema(tmp_path: pytest.TempPathFactory) -> None:
    import json

    path = tmp_path / "bad.json"  # type: ignore[operator]
    path.write_text(json.dumps({"schema_version": 99}))
    with pytest.raises(ValueError, match="schema version"):
        BM25Index.load(path)


def test_bm25_stale_ids_detects_removed_nodes() -> None:
    idx = BM25Index()
    idx.add("a", "text one")
    idx.add("b", "text two")
    idx.add("c", "text three")
    assert idx.stale_ids({"a", "b"}) == {"c"}
    assert idx.stale_ids({"a", "b", "c"}) == set()
    assert idx.stale_ids(set()) == {"a", "b", "c"}


def test_bm25_rebuild_from_graph_reindexes_active_only() -> None:
    graph = MemoryGraph()
    active = MemoryNode.create("fact", "active", "active content", created_at_s=100)
    inactive = MemoryNode.create("fact", "inactive", "inactive content", created_at_s=100)
    graph.add_node(active)
    graph.add_node(inactive)
    from dataclasses import replace

    graph._nodes[inactive.node_id] = replace(inactive, is_active=False)  # noqa: SLF001
    idx = BM25Index()
    idx.add("stale_node", "old text that should be gone")
    count = idx.rebuild_from_graph(graph)
    assert count == 1
    assert active.node_id in idx.docs
    assert inactive.node_id not in idx.docs
    assert "stale_node" not in idx.docs


def test_bm25_prune_stale_removes_dead_entries() -> None:
    idx = BM25Index()
    idx.add("live", "still here")
    idx.add("dead1", "should be removed")
    idx.add("dead2", "also removed")
    pruned = idx.prune_stale({"live"})
    assert pruned == 2
    assert idx.doc_count == 1
    assert "live" in idx.docs


def test_parse_query_handles_quoted_phrases() -> None:
    from famulix.retrieval import parse_query

    parsed = parse_query('find "important meeting" notes')
    assert parsed["terms"] == ["find", "notes"]
    assert parsed["phrases"] == ["important meeting"]


def test_parse_query_handles_negated_terms() -> None:
    from famulix.retrieval import parse_query

    parsed = parse_query("search -spam -junk relevant")
    assert parsed["terms"] == ["search", "relevant"]
    assert parsed["negated"] == ["spam", "junk"]


def test_parse_query_handles_multi_word_quotes() -> None:
    from famulix.retrieval import parse_query

    parsed = parse_query('"project deadline" "team meeting"')
    assert parsed["phrases"] == ["project deadline", "team meeting"]
    assert parsed["terms"] == []


def test_parse_query_handles_unclosed_quotes() -> None:
    from famulix.retrieval import parse_query

    parsed = parse_query('"unclosed phrase with words')
    assert parsed["phrases"] == ["unclosed phrase with words"]


def test_query_with_filters_applies_phrase_filter() -> None:
    from famulix.retrieval import (
        BM25Index,
        MemoryGraph,
        MemoryNode,
        query_with_filters,
    )

    graph = MemoryGraph()
    n1 = MemoryNode.create("fact", "important meeting", "schedule review", created_at_s=1000)
    n2 = MemoryNode.create("fact", "casual chat", "informal discussion", created_at_s=2000)
    graph.add_node(n1)
    graph.add_node(n2)
    index = BM25Index()
    index.add_node(n1)
    index.add_node(n2)
    results = query_with_filters(
        '"important meeting"',
        graph=graph,
        index=index,
        now_s=3000,
    )
    assert len(results) == 1
    assert results[0].node_id == n1.node_id


def test_query_with_filters_applies_negation() -> None:
    from famulix.retrieval import BM25Index, MemoryGraph, MemoryNode, query_with_filters

    graph = MemoryGraph()
    n1 = MemoryNode.create("fact", "project update", "progress report", created_at_s=1000)
    n2 = MemoryNode.create("fact", "spam message", "junk content", created_at_s=2000)
    graph.add_node(n1)
    graph.add_node(n2)
    index = BM25Index()
    index.add_node(n1)
    index.add_node(n2)
    results = query_with_filters(
        "-spam update",
        graph=graph,
        index=index,
        now_s=3000,
    )
    assert all(r.node_id != n2.node_id for r in results)


def test_bm25_digest_deterministic() -> None:
    from famulix.retrieval import BM25Index

    idx1 = BM25Index()
    idx1.add("n1", "hello world")
    idx1.add("n2", "foo bar")

    idx2 = BM25Index()
    idx2.add("n2", "foo bar")
    idx2.add("n1", "hello world")

    assert idx1.digest() == idx2.digest()


def test_bm25_digest_changes_with_content() -> None:
    from famulix.retrieval import BM25Index

    idx1 = BM25Index()
    idx1.add("n1", "hello world")
    d1 = idx1.digest()

    idx1.add("n2", "new document")
    d2 = idx1.digest()

    assert d1 != d2


def test_bm25_needs_rebuild_detects_missing_nodes() -> None:
    from famulix.memory_graph import MemoryGraph, MemoryNode
    from famulix.retrieval import BM25Index

    graph = MemoryGraph()
    n1 = MemoryNode.create("fact", "test", "body", created_at_s=100)
    n2 = MemoryNode.create("fact", "test2", "body2", created_at_s=200)
    graph.add_node(n1)
    graph.add_node(n2)

    index = BM25Index()
    index.add_node(n1)

    assert index.needs_rebuild(graph) is True


def test_bm25_needs_rebuild_false_when_synced() -> None:
    from famulix.memory_graph import MemoryGraph, MemoryNode
    from famulix.retrieval import BM25Index

    graph = MemoryGraph()
    n1 = MemoryNode.create("fact", "test", "body", created_at_s=100)
    n2 = MemoryNode.create("fact", "test2", "body2", created_at_s=200)
    graph.add_node(n1)
    graph.add_node(n2)

    index = BM25Index()
    index.add_node(n1)
    index.add_node(n2)

    assert index.needs_rebuild(graph) is False


def test_bm25_needs_rebuild_detects_stale_nodes() -> None:
    from famulix.memory_graph import MemoryGraph, MemoryNode
    from famulix.retrieval import BM25Index

    graph = MemoryGraph()
    n1 = MemoryNode.create("fact", "test", "body", created_at_s=100)
    graph.add_node(n1)

    index = BM25Index()
    index.add_node(n1)
    index.add("deleted-node", "old content")

    assert index.needs_rebuild(graph) is True


def test_linear_reranker_reorders_by_weights() -> None:
    """Linear reranker recombines component scores with custom weights."""
    from famulix.retrieval import RetrievalResult, apply_reranker, make_linear_reranker

    graph = MemoryGraph()
    n1 = MemoryNode.create("fact", "alpha", "body one", created_at_s=100)
    n2 = MemoryNode.create("fact", "beta", "body two", created_at_s=200)
    graph.add_node(n1)
    graph.add_node(n2)

    results = [
        RetrievalResult(
            node_id=n1.node_id,
            score=0.5,
            citation="e1",
            metadata={"bm25": 0.9, "recency": 0.1, "salience": 0.5},
        ),
        RetrievalResult(
            node_id=n2.node_id,
            score=0.6,
            citation="e2",
            metadata={"bm25": 0.1, "recency": 0.9, "salience": 0.5},
        ),
    ]

    bm25_heavy = make_linear_reranker(bm25_weight=1.0, recency_weight=0.0, salience_weight=0.0)
    bm25_ranked = apply_reranker(results, graph=graph, reranker=bm25_heavy)
    assert [r.node_id for r in bm25_ranked] == [n1.node_id, n2.node_id]

    recency_heavy = make_linear_reranker(bm25_weight=0.0, recency_weight=1.0, salience_weight=0.0)
    recency_ranked = apply_reranker(results, graph=graph, reranker=recency_heavy)
    assert [r.node_id for r in recency_ranked] == [n2.node_id, n1.node_id]


def test_linear_reranker_is_deterministic_with_tiebreak() -> None:
    from famulix.retrieval import RetrievalResult, make_linear_reranker

    results = [
        RetrievalResult(
            node_id="n1",
            score=0.5,
            citation="e1",
            metadata={"bm25": 0.3, "recency": 0.7, "salience": 0.4},
        ),
        RetrievalResult(
            node_id="n2",
            score=0.5,
            citation="e2",
            metadata={"bm25": 0.3, "recency": 0.7, "salience": 0.4},
        ),
    ]
    graph = MemoryGraph()
    r1 = make_linear_reranker()(list(results), graph)
    r2 = make_linear_reranker()(list(results), graph)
    assert [r.node_id for r in r1] == [r.node_id for r in r2]
    assert r1[0].node_id == "n1"


def test_apply_reranker_rejects_invented_node_ids() -> None:
    import pytest

    from famulix.retrieval import RetrievalResult, apply_reranker

    graph = MemoryGraph()
    n = MemoryNode.create("fact", "x", "y", created_at_s=100)
    graph.add_node(n)

    results = [RetrievalResult(node_id=n.node_id, score=1.0, citation="e1")]

    def bad_reranker(rs: list[RetrievalResult], g: MemoryGraph) -> list[RetrievalResult]:
        return [RetrievalResult(node_id="invented", score=1.0, citation="fake")]

    with pytest.raises(ValueError, match="invented unknown result"):
        apply_reranker(results, graph=graph, reranker=bad_reranker)


@pytest.mark.model
def test_torch_reranker_presence_matches_torch_availability() -> None:
    from famulix.retrieval import make_torch_reranker
    from famulix.salience_torch import is_torch_available

    reranker = make_torch_reranker(seed=42)
    if is_torch_available():
        assert reranker is not None
    else:
        assert reranker is None
