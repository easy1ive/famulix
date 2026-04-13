"""Test evaluation report formatting."""

from famulix.evaluation import format_evaluation_report


def test_format_evaluation_report_basic():
    """Verify report includes all key metrics."""
    scorecard = {
        "recall_at_10": 0.85,
        "precision_at_10": 0.72,
        "contradiction_resolution": 0.95,
        "citation_coverage": 0.88,
        "budget_adherence": 1.0,
        "preference_brier": 0.1234,
        "deletion_resurrection_violations": 0,
        "privacy_violations": 0,
    }

    report = format_evaluation_report(scorecard)

    assert "# Evaluation Report" in report
    assert "## Overall Metrics" in report
    assert "**Recall@10**: 0.850" in report
    assert "**Precision@10**: 0.720" in report
    assert "**Contradiction resolution**: 0.950" in report
    assert "**Citation coverage**: 0.880" in report
    assert "**Preference calibration (Brier)**: 0.1234" in report
    assert "## Limitations" in report
    assert "synthetic data" in report


def test_format_evaluation_report_with_slices():
    """Verify report includes per-slice breakdown when requested."""
    scorecard = {
        "recall_at_10": 0.8,
        "precision_at_10": 0.7,
        "per_slice": {
            "facts": {"recall": 0.9, "precision": 0.8},
            "reminders": {"recall": 0.7, "precision": 0.6},
        },
    }

    report = format_evaluation_report(scorecard, include_details=True)

    assert "## Per-Slice Breakdown" in report
    assert "### facts" in report
    assert "### reminders" in report


def test_format_evaluation_report_without_details():
    """Verify report can skip per-slice breakdown."""
    scorecard = {
        "recall_at_10": 0.8,
        "per_slice": {"facts": {"recall": 0.9}},
    }

    report = format_evaluation_report(scorecard, include_details=False)

    assert "## Per-Slice Breakdown" not in report
