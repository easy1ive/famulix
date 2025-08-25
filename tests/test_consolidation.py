"""Tests for memory consolidation."""

from __future__ import annotations

import random
from collections import Counter

import pytest

from famulix import consolidation
from famulix.consolidation import (
    ConsolidationReport,
    _chars_can_reach,
    _lengths_can_reach,
    _normalized_text,
    _shared_char_count,
    _similarity,
    consolidate_graph,
    find_contradictions,
    find_near_duplicates,
    merge_duplicate,
    resolve_contradiction,
)
from famulix.memory_graph import MemoryEdge, MemoryGraph, MemoryNode


def _fact(title: str, body: str, ts: int = 100) -> MemoryNode:
    return MemoryNode.create("fact", title, body, created_at_s=ts)


def test_find_near_duplicates_identical() -> None:
    g = MemoryGraph()
    a = _fact("address", "123 Main St")
    b = _fact("address", "123 Main St")  # same text, same id
    # Since content-addressed, same body → same id → only one node
    g.add_node(a)
    g.add_node(b)
    assert g.node_count() == 1  # dedup by content id
    dups = find_near_duplicates(g, kind="fact")
    assert dups == []


def test_find_near_duplicates_similar() -> None:
    g = MemoryGraph()
    a = _fact("meeting", "weekly team meeting at 10am on Monday", ts=100)
    # Slightly different
    b = MemoryNode.create(
        "fact",
        "meeting note",
        "weekly team meeting at 10am on Mondays",
        created_at_s=200,
    )
    g.add_node(a)
    g.add_node(b)
    dups = find_near_duplicates(g, kind="fact", threshold=0.5)
    assert len(dups) >= 1


def test_find_near_duplicates_different() -> None:
    g = MemoryGraph()
    g.add_node(_fact("a", "completely different content here", ts=100))
    g.add_node(_fact("b", "nothing in common with the other one", ts=200))
    dups = find_near_duplicates(g, kind="fact", threshold=0.8)
    assert dups == []


def test_merge_duplicate_redirects_edges() -> None:
    g = MemoryGraph()
    survivor = _fact("survivor", "the winning fact", ts=200)
    obsolete = MemoryNode.create("fact", "obsolete", "very similar fact", created_at_s=100)
    ref = MemoryNode.create("episode", "ep", "episode referencing facts", created_at_s=50)
    g.add_node(survivor)
    g.add_node(obsolete)
    g.add_node(ref)
    g.add_edge(MemoryEdge.create(ref.node_id, obsolete.node_id, "derived_from"))
    g.add_edge(MemoryEdge.create(obsolete.node_id, ref.node_id, "part_of"))

    before_in = len(g.in_edges(obsolete.node_id))
    merge_duplicate(g, survivor, obsolete)
    # Obsolete is inactive
    assert not g.get_node(obsolete.node_id).is_active
    # Survivor gained edges
    assert len(g.in_edges(survivor.node_id)) >= before_in
    # Provenance edge exists
    assert any(e.kind == "supersedes" for e in g.out_edges(survivor.node_id))


def test_contradiction_detection() -> None:
    g = MemoryGraph()
    a = MemoryNode.create(
        "fact",
        "home address is",
        "home address is 123 Main St",
        created_at_s=100,
    )
    b = MemoryNode.create(
        "fact",
        "home address is",
        "home address is 456 Oak Ave",
        created_at_s=200,
    )
    g.add_node(a)
    g.add_node(b)
    contradictions = find_contradictions(g)
    assert len(contradictions) == 1
    assert contradictions[0][0].node_id in (a.node_id, b.node_id)
    assert contradictions[0][1].node_id in (a.node_id, b.node_id)


def test_resolve_contradiction_newer_wins() -> None:
    older = _fact("k", "old value", ts=100)
    newer = _fact("k", "new value", ts=200)
    winner = resolve_contradiction(newer, older)
    assert winner.node_id == newer.node_id


def test_resolve_contradiction_trusted_beats_untrusted() -> None:
    older = _fact("k", "old trusted", ts=100)
    newer = _fact("k", "new untrusted", ts=200)
    # older is trusted, newer is not → older wins despite being older
    winner = resolve_contradiction(newer, older, newer_trusted=False, older_trusted=True)
    assert winner.node_id == older.node_id


def test_consolidation_orders_conflicts_by_time_not_insertion_or_id() -> None:
    graph = MemoryGraph()
    old = _fact("home", "old address", ts=100)
    new = _fact("home", "new address", ts=200)
    graph.add_node(new)
    graph.add_node(old)

    report = consolidate_graph(graph)

    assert graph.get_node(new.node_id) is not None
    assert graph.get_node(new.node_id).is_active
    assert graph.get_node(old.node_id) is not None
    assert not graph.get_node(old.node_id).is_active
    assert report.superseded == [old.node_id]


def test_consolidate_graph_full_pass() -> None:
    g = MemoryGraph()
    # Two similar facts (dedup)
    a = MemoryNode.create("fact", "meeting time", "weekly meeting at 10am Monday", created_at_s=100)
    b = MemoryNode.create(
        "fact", "meeting time", "weekly meeting at 10am on Mondays", created_at_s=200
    )
    # Two contradictory facts
    c = MemoryNode.create("fact", "address is", "address is 123 Main St", created_at_s=150)
    d = MemoryNode.create("fact", "address is", "address is 456 Oak Ave", created_at_s=250)
    g.add_node(a)
    g.add_node(b)
    g.add_node(c)
    g.add_node(d)

    report = consolidate_graph(g, dedup_threshold=0.5)
    assert isinstance(report, ConsolidationReport)
    assert report.total_changes() > 0
    # After consolidation, fewer active facts
    active_facts = [n for n in g.all_nodes() if n.kind == "fact" and n.is_active]
    assert len(active_facts) <= 3  # at least one merged or superseded


def test_consolidation_deterministic() -> None:
    def build() -> tuple[MemoryGraph, int]:
        g = MemoryGraph()
        g.add_node(MemoryNode.create("fact", "a", "fact a content", created_at_s=100))
        g.add_node(MemoryNode.create("fact", "b", "fact b content", created_at_s=200))
        g.add_node(MemoryNode.create("fact", "a", "fact a similar content", created_at_s=150))
        return g, g.node_count()

    g1, _ = build()
    g2, _ = build()
    r1 = consolidate_graph(g1)
    r2 = consolidate_graph(g2)
    assert r1.merged_pairs == r2.merged_pairs
    assert r1.superseded == r2.superseded
    active1 = {n.node_id for n in g1.all_nodes() if n.is_active}
    active2 = {n.node_id for n in g2.all_nodes() if n.is_active}
    assert active1 == active2


def test_consolidation_is_idempotent() -> None:
    """A second consolidation pass should produce no further changes."""
    g = MemoryGraph()
    g.add_node(MemoryNode.create("fact", "alpha", "the quick brown fox jumps", created_at_s=100))
    g.add_node(MemoryNode.create("fact", "alpha", "the quick brown fox hops", created_at_s=120))
    g.add_node(MemoryNode.create("fact", "beta", "entirely different content", created_at_s=150))
    first_report = consolidate_graph(g)
    assert first_report.total_changes() > 0
    second_report = consolidate_graph(g)
    assert second_report.is_empty
    assert second_report.total_changes() == 0


def test_consolidation_report_to_dict_keys() -> None:
    from famulix.consolidation import ConsolidationReport

    report = ConsolidationReport()
    d = report.to_dict()
    assert set(d.keys()) >= {
        "merged_pairs",
        "superseded",
        "contradictions_resolved",
        "total_changes",
    }
    assert d["total_changes"] == 0


def test_near_duplicate_pairs_are_independent_of_insertion_order() -> None:
    """Canonical pair ordering must survive any node insertion order."""
    nodes = [_fact("home address", "123 Main Street, Guangzhou", ts=100 + i) for i in range(4)]
    nodes.append(_fact("home address", "123 Main St, Guangzhou", ts=200))

    forward = MemoryGraph()
    for node in nodes:
        forward.add_node(node)
    backward = MemoryGraph()
    for node in reversed(nodes):
        backward.add_node(node)

    left = find_near_duplicates(forward, kind="fact", threshold=0.8)
    right = find_near_duplicates(backward, kind="fact", threshold=0.8)
    assert left, "fixture must actually contain near duplicates"
    assert [(a.node_id, b.node_id, s) for a, b, s in left] == [
        (a.node_id, b.node_id, s) for a, b, s in right
    ]
    for a, b, _score in left:
        assert a.node_id <= b.node_id


def test_near_duplicate_pairs_are_totally_ordered() -> None:
    """Equal scores must still produce a single stable ordering."""
    g = MemoryGraph()
    for offset in range(3):
        g.add_node(_fact("standup cadence", "daily standup at nine", ts=300 + offset))
        g.add_node(_fact("standup cadence", "daily standup at nine!", ts=400 + offset))
    pairs = find_near_duplicates(g, kind="fact", threshold=0.5)
    scores = [score for _, _, score in pairs]
    assert scores == sorted(scores, reverse=True)
    keys = [(-score, a.node_id, b.node_id) for (a, b, score) in pairs]
    assert keys == sorted(keys)


def test_consolidation_report_matches_across_insertion_orders() -> None:
    """The whole consolidation pass must be insertion-order independent."""
    nodes = [
        _fact("home address", "123 Main Street, Guangzhou", ts=100),
        _fact("home address", "123 Main St, Guangzhou", ts=200),
        _fact("meeting cadence", "weekly sync on Monday", ts=150),
        _fact("meeting cadence", "weekly sync on Tuesday", ts=250),
    ]
    reports = []
    for order in (nodes, list(reversed(nodes))):
        graph = MemoryGraph()
        for node in order:
            graph.add_node(node)
        reports.append(consolidate_graph(graph).to_dict())
    assert reports[0] == reports[1]
    assert reports[0]["total_changes"] > 0


def _random_corpus(rng: random.Random, size: int) -> list[str]:
    words = ["standup", "monday", "address", "guangzhou", "call", "dentist", "budget", "report"]
    texts = []
    for _ in range(size):
        length = rng.randint(1, 6)
        texts.append(" ".join(rng.choice(words) for _ in range(length)))
    return texts


def test_length_prefilter_never_rejects_a_qualifying_pair() -> None:
    """The bound is exact: anything it rejects truly cannot reach threshold."""
    rng = random.Random(11)
    for threshold in (0.5, 0.7, 0.85, 0.95):
        for text in _random_corpus(rng, 60):
            for other in _random_corpus(rng, 60):
                reachable = _lengths_can_reach(len(text), len(other), threshold)
                if not reachable:
                    assert _similarity(text, other) < threshold


def test_find_near_duplicates_matches_unfiltered_brute_force() -> None:
    """Prefiltering must not change which pairs are reported."""
    rng = random.Random(7)
    graph = MemoryGraph()
    for index, text in enumerate(_random_corpus(rng, 40)):
        graph.add_node(_fact(f"note {index}", text, ts=1000 + index))
    for threshold in (0.4, 0.6, 0.85):
        expected: dict[tuple[str, str], float] = {}
        nodes = [n for n in graph.all_nodes() if n.kind == "fact" and n.is_active]
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = sorted((nodes[i], nodes[j]), key=lambda n: n.node_id)
                score = _similarity(_normalized_text(a), _normalized_text(b))
                if score >= threshold:
                    expected[(a.node_id, b.node_id)] = score
        actual = {
            (a.node_id, b.node_id): score
            for a, b, score in find_near_duplicates(graph, kind="fact", threshold=threshold)
        }
        assert actual == expected


def test_duplicate_scan_skips_diffing_impossible_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only length-compatible pairs should reach the expensive differ."""
    graph = MemoryGraph()
    graph.add_node(_fact("short", "call mum", ts=10))
    for index in range(12):
        graph.add_node(
            _fact(
                f"long {index}",
                "a much longer body of text that cannot match the short note " * 3,
                ts=20 + index,
            )
        )
    calls: list[tuple[str, str]] = []
    original = consolidation._similarity

    def counting(a: str, b: str) -> float:
        calls.append((a, b))
        return original(a, b)

    monkeypatch.setattr(consolidation, "_similarity", counting)
    find_near_duplicates(graph, kind="fact", threshold=0.85)
    total_pairs = 13 * 12 // 2
    assert len(calls) < total_pairs
    short_text = "short call mum"
    assert all(short_text not in pair for pair in calls)


def test_character_bound_never_rejects_a_qualifying_pair() -> None:
    """The multiset bound is exact: rejected pairs truly fall short."""
    rng = random.Random(23)
    corpus = _random_corpus(rng, 50)
    for threshold in (0.45, 0.6, 0.85, 0.99):
        for text in corpus:
            counts_a = Counter(text)
            for other in corpus:
                counts_b = Counter(other)
                total = len(text) + len(other)
                if not _chars_can_reach(counts_a, counts_b, total, threshold):
                    assert _similarity(text, other) < threshold


def test_shared_char_count_is_symmetric_and_bounded() -> None:
    counts_a = Counter("aabbc")
    counts_b = Counter("abddd")
    assert _shared_char_count(counts_a, counts_b) == _shared_char_count(counts_b, counts_a)
    assert _shared_char_count(counts_a, counts_b) == 2
    assert _shared_char_count(counts_a, Counter("")) == 0
    assert _shared_char_count(counts_a, counts_a) == sum(counts_a.values())


def test_empty_texts_never_pass_the_character_bound() -> None:
    assert not _chars_can_reach(Counter(""), Counter(""), 0, 0.5)
    assert not _chars_can_reach(Counter(""), Counter("abc"), 3, 0.5)


def test_summarize_episodes_creates_derived_from_edges() -> None:
    from famulix.consolidation import summarize_episodes

    graph = MemoryGraph()
    eps = [
        MemoryNode.create("episode", "morning run", "ran 5km", created_at_s=100),
        MemoryNode.create("episode", "lunch meeting", "discussed project", created_at_s=200),
        MemoryNode.create("episode", "evening reading", "read chapter 3", created_at_s=300),
    ]
    for ep in eps:
        graph.add_node(ep)
    summary = summarize_episodes(graph, eps)
    assert summary is not None
    assert summary.kind == "episode"
    assert "3 events" in summary.body
    assert graph.has_node(summary.node_id)
    out_edges = graph.out_edges(summary.node_id)
    derived = [e for e in out_edges if e.kind == "derived_from"]
    assert len(derived) == 3
    derived_targets = {e.to_id for e in derived}
    assert derived_targets == {ep.node_id for ep in eps}


def test_summarize_episodes_returns_none_for_empty_input() -> None:
    from famulix.consolidation import summarize_episodes

    graph = MemoryGraph()
    assert summarize_episodes(graph, []) is None


def test_summarize_episodes_skips_inactive() -> None:
    from dataclasses import replace

    from famulix.consolidation import summarize_episodes

    graph = MemoryGraph()
    active = MemoryNode.create("episode", "active event", "content", created_at_s=100)
    inactive = MemoryNode.create("episode", "inactive event", "old content", created_at_s=50)
    graph.add_node(active)
    graph.add_node(inactive)
    graph._nodes[inactive.node_id] = replace(inactive, is_active=False)  # noqa: SLF001
    inactive_updated = graph.get_node(inactive.node_id)
    assert inactive_updated is not None
    summary = summarize_episodes(graph, [active, inactive_updated])
    assert summary is not None
    out_edges = graph.out_edges(summary.node_id)
    derived_targets = {e.to_id for e in out_edges if e.kind == "derived_from"}
    assert derived_targets == {active.node_id}


def test_consolidate_with_summaries_records_summary_nodes() -> None:
    from famulix.consolidation import consolidate_with_summaries

    graph = MemoryGraph()
    eps = [
        MemoryNode.create("episode", "event a", "detail a", created_at_s=100),
        MemoryNode.create("episode", "event b", "detail b", created_at_s=200),
    ]
    for ep in eps:
        graph.add_node(ep)
    report = consolidate_with_summaries(graph, episode_groups={"day1": eps})
    assert len(report.summary_nodes) == 1
    assert graph.has_node(report.summary_nodes[0])
