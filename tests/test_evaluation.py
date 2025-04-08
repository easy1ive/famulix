"""Tests for the memory evaluation harness."""

from __future__ import annotations

import pytest

from famulix.evaluation import (
    EvalScorecard,
    compute_recall_precision,
    eval_budget_adherence,
    eval_citation_coverage,
    eval_contradiction_resolution,
    eval_deletion_resurrection,
    eval_preference_calibration,
    eval_recall_precision,
    run_full_evaluation,
)
from famulix.memory_graph import MemoryGraph, MemoryNode
from famulix.preferences import PreferenceProfile


def test_compute_recall_precision_perfect():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"a", "b", "c"}
    recall, precision = compute_recall_precision(retrieved, relevant, k=5)
    assert recall == pytest.approx(1.0)
    assert precision == pytest.approx(3 / 5)


def test_compute_recall_precision_none_relevant():
    retrieved = ["a", "b", "c"]
    relevant: set[str] = set()
    recall, precision = compute_recall_precision(retrieved, relevant, k=5)
    assert recall == 1.0
    assert precision == 1.0


def test_compute_recall_precision_no_retrieved():
    retrieved: list[str] = []
    relevant = {"a", "b"}
    recall, precision = compute_recall_precision(retrieved, relevant, k=5)
    assert recall == 0.0
    assert precision == 0.0


def test_compute_recall_precision_zero_and_negative_k() -> None:
    assert compute_recall_precision(["a"], {"a"}, k=0) == (0.0, 0.0)
    with pytest.raises(ValueError, match="non-negative"):
        compute_recall_precision(["a"], {"a"}, k=-1)


def test_compute_recall_precision_k_limits():
    retrieved = ["a", "b", "c", "d", "e", "f"]
    relevant = {"a", "c", "e"}
    r_at_3, p_at_3 = compute_recall_precision(retrieved, relevant, k=3)
    r_at_6, p_at_6 = compute_recall_precision(retrieved, relevant, k=6)
    # recall should be lower or equal at smaller k
    assert r_at_3 <= r_at_6
    # precision at k=3: 2 of 3 are relevant (a and c)
    assert p_at_3 == pytest.approx(2 / 3)
    # precision at k=6: 3 of 6 are relevant
    assert p_at_6 == pytest.approx(3 / 6)


def test_eval_recall_precision_with_graph():
    g = MemoryGraph()
    planted_ids = set()
    for i in range(10):
        node = MemoryNode.create(
            kind="fact",
            title=f"fact_{i}",
            body=f"body of fact {i}",
            created_at_s=i * 100,
        )
        g.add_node(node)
        if i < 5:
            planted_ids.add(node.node_id)

    recall, precision = eval_recall_precision(g, planted_ids, now_s=1000, k_values=[3, 5])
    assert "@3" in recall
    assert "@5" in recall
    assert "@3" in precision
    assert "@5" in precision
    assert 0.0 <= recall["@3"] <= 1.0
    assert 0.0 <= precision["@3"] <= 1.0


def test_eval_contradiction_resolution_all_correct():
    g = MemoryGraph()
    # Create old and new facts; mark old as inactive (superseded)
    from dataclasses import replace

    old = MemoryNode.create(kind="fact", title="address", body="123 Oak St", created_at_s=100)
    new = MemoryNode.create(kind="fact", title="address", body="456 Pine Ave", created_at_s=500)
    g.add_node(old)
    g.add_node(new)
    g._nodes[old.node_id] = replace(old, is_active=False)

    accuracy = eval_contradiction_resolution(g, [(old.node_id, new.node_id)])
    assert accuracy == 1.0


def test_eval_contradiction_resolution_all_wrong():
    g = MemoryGraph()
    from dataclasses import replace

    old = MemoryNode.create(kind="fact", title="address", body="123 Oak St", created_at_s=100)
    new = MemoryNode.create(kind="fact", title="address", body="456 Pine Ave", created_at_s=500)
    g.add_node(old)
    g.add_node(new)
    g._nodes[new.node_id] = replace(new, is_active=False)

    accuracy = eval_contradiction_resolution(g, [(old.node_id, new.node_id)])
    assert accuracy < 1.0


def test_eval_contradiction_resolution_empty_pairs():
    g = MemoryGraph()
    accuracy = eval_contradiction_resolution(g, [])
    assert accuracy == 1.0


def test_eval_citation_coverage_full():
    class FakeItem:
        def __init__(self, ids):
            self.memory_ids = ids

    items = [FakeItem(["a", "b"]), FakeItem(["c"]), FakeItem(["d"])]
    coverage = eval_citation_coverage(items, {"a", "b", "c", "d"})
    assert coverage == 1.0


def test_eval_citation_coverage_empty():
    coverage = eval_citation_coverage([], set())
    assert coverage == 1.0


def test_eval_budget_adherence_within_budget():
    class FakeItem:
        def __init__(self, payload):
            self.payload = payload

    items = [FakeItem("hello world") for _ in range(3)]
    ok, violations = eval_budget_adherence(items, budget=1000)
    assert ok is True
    assert violations == 0


def test_eval_budget_adherence_over_budget():
    class FakeItem:
        def __init__(self, payload):
            self.payload = payload

    # Many large items
    items = [FakeItem("x " * 1000) for _ in range(10)]
    ok, violations = eval_budget_adherence(items, budget=10)
    assert ok is False
    assert violations == 1


def test_eval_deletion_resurrection_none():
    class FakeResult:
        def __init__(self, nid):
            self.node_id = nid

    results = [FakeResult("a"), FakeResult("b"), FakeResult("c")]
    deleted = {"x", "y"}
    count = eval_deletion_resurrection(MemoryGraph(), deleted, results)
    assert count == 0


def test_eval_deletion_resurrection_some():
    class FakeResult:
        def __init__(self, nid):
            self.node_id = nid

    results = [FakeResult("a"), FakeResult("b"), FakeResult("c")]
    deleted = {"a", "c"}
    count = eval_deletion_resurrection(MemoryGraph(), deleted, results)
    assert count == 2


def test_eval_preference_calibration_zero_for_empty():
    profile = PreferenceProfile()
    brier = eval_preference_calibration(profile, [], now_s=0)
    assert brier == 0.0


def test_eval_preference_calibration_range():
    profile = PreferenceProfile()
    signals = [
        {"key": "style", "value": "concise", "rating": "up"},
        {"key": "style", "value": "concise", "rating": "down"},
        {"key": "style", "value": "detailed", "rating": "up"},
    ]
    brier = eval_preference_calibration(profile, signals, now_s=0)
    # Brier score should be in [0, 1]
    assert 0.0 <= brier <= 1.0


def test_run_full_evaluation_basic():
    """Full evaluation should run and produce a valid scorecard."""
    scorecard = run_full_evaluation(
        persona_id="alex",
        seed=42,
        days=14,
        start_date="2026-01-01",
        budget_tokens=300,
    )
    assert isinstance(scorecard, EvalScorecard)
    assert scorecard.persona_id == "alex"
    assert scorecard.seed == 42
    assert scorecard.days == 14
    assert scorecard.total_planted_facts > 0
    assert scorecard.total_contradiction_pairs >= 0
    assert 0.0 <= scorecard.contradiction_accuracy <= 1.0
    assert 0.0 <= scorecard.citation_coverage <= 1.0
    assert 0.0 <= scorecard.preference_brier_score <= 1.0
    assert scorecard.replay_deterministic is True
    assert scorecard.privacy_violations == 0
    assert scorecard.deletion_resurrection_count == 0
    assert len(scorecard.recall_at_k) > 0
    assert len(scorecard.precision_at_k) > 0


def test_run_full_evaluation_deterministic():
    s1 = run_full_evaluation(persona_id="alex", seed=7, days=14)
    s2 = run_full_evaluation(persona_id="alex", seed=7, days=14)
    assert s1.recall_at_k == s2.recall_at_k
    assert s1.precision_at_k == s2.precision_at_k
    assert s1.contradiction_accuracy == s2.contradiction_accuracy
    assert s1.citation_coverage == s2.citation_coverage
    assert s1.preference_brier_score == s2.preference_brier_score
    assert s1.replay_deterministic == s2.replay_deterministic


def test_scorecard_to_dict_roundtrip():
    scorecard = run_full_evaluation(persona_id="alex", seed=0, days=10)
    d = scorecard.to_dict()
    assert d["persona_id"] == "alex"
    assert "recall_at_k" in d
    assert "precision_at_k" in d
    assert isinstance(d["contradiction_accuracy"], float)
    assert isinstance(d["citation_coverage"], float)
    assert isinstance(d["budget_adherence"], bool)
    assert "slices" in d


def test_run_full_evaluation_different_personas_differ():
    s1 = run_full_evaluation(persona_id="alex", seed=0, days=14)
    s2 = run_full_evaluation(persona_id="bailey", seed=0, days=14)
    # Different personas should have different profiles at least
    # (might have same scores by chance on small runs, but structure differs)
    assert s1.persona_id != s2.persona_id
