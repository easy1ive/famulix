"""Integration test: factory plants contradictions, eval recovers them."""

from famulix.evaluation import run_full_evaluation
from famulix.factory import generate_history_with_truth


def test_factory_plants_at_least_one_contradiction():
    _events, _manifest, truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=30,
    )
    pairs = truth.get("contradiction_pairs", [])
    assert len(pairs) >= 1, "factory should plant at least one contradiction pair"


def test_factory_contradiction_pairs_are_tuples():
    _events, _manifest, truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=30,
    )
    for pair in truth["contradiction_pairs"]:
        assert len(pair) == 2
        assert pair[0] != pair[1]


def test_factory_has_planted_facts():
    _events, _manifest, truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=30,
    )
    assert len(truth["fact_ids"]) >= 1


def test_eval_reports_contradiction_accuracy():
    scorecard = run_full_evaluation(persona_id="alex", seed=42, days=14)
    d = scorecard.to_dict()
    assert "contradiction_accuracy" in d
    assert "total_contradiction_pairs" in d
    assert d["total_contradiction_pairs"] >= 1


def test_eval_contradiction_accuracy_bounded():
    scorecard = run_full_evaluation(persona_id="alex", seed=42, days=14)
    d = scorecard.to_dict()
    assert 0.0 <= d["contradiction_accuracy"] <= 1.0


def test_factory_deterministic_contradictions():
    """Same seed plants identical contradictions."""
    _, _, t1 = generate_history_with_truth(persona_id="alex", seed=7, days=20)
    _, _, t2 = generate_history_with_truth(persona_id="alex", seed=7, days=20)
    assert t1["contradiction_pairs"] == t2["contradiction_pairs"]
