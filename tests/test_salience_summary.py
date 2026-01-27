"""Test salience score summary."""

from famulix.salience import salience_score_summary


def test_empty_scores():
    """Empty list should have zero statistics."""
    result = salience_score_summary([])
    assert result["count"] == 0
    assert result["mean"] == 0.0


def test_score_summary():
    """Should compute correct statistics."""
    scores = [0.5, 0.8, 0.3, 0.9]
    result = salience_score_summary(scores)
    assert result["count"] == 4
    assert result["min"] == 0.3
    assert result["max"] == 0.9
    assert abs(result["mean"] - 0.625) < 0.001
