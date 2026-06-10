"""Test evaluation per-slice scorecards."""

from famulix.evaluation import compute_per_slice_scorecard


def test_per_slice_scorecard_breaks_down_metrics():
    results = [
        {"slice": "facts", "recall": 0.9, "precision": 0.8},
        {"slice": "facts", "recall": 0.85, "precision": 0.75},
        {"slice": "preferences", "recall": 0.7, "precision": 0.9},
    ]

    scorecard = compute_per_slice_scorecard(results)

    assert "facts" in scorecard
    assert "preferences" in scorecard

    assert abs(scorecard["facts"]["avg_recall"] - 0.875) < 0.01
    assert abs(scorecard["facts"]["avg_precision"] - 0.775) < 0.01


def test_per_slice_scorecard_empty():
    scorecard = compute_per_slice_scorecard([])
    assert scorecard == {}
