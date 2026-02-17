"""Test evaluation scorecard summary."""

from famulix.evaluation import evaluation_scorecard_summary


def test_empty_scorecard():
    """Empty scorecard should have zero values."""
    result = evaluation_scorecard_summary({})
    assert result["recall_at_5"] == 0.0


def test_scorecard_summary():
    """Should extract scorecard fields."""
    scorecard = {"recall_at_5": 0.85, "citation_coverage": 1.0}
    result = evaluation_scorecard_summary(scorecard)
    assert result["recall_at_5"] == 0.85
    assert result["citation_coverage"] == 1.0
