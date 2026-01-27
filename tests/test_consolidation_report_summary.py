"""Test consolidation report summary."""

from famulix.consolidation import ConsolidationReport, consolidation_report_summary


def test_report_summary():
    """Should extract report fields."""
    report = ConsolidationReport(
        merged_pairs=[("a", "b"), ("c", "d")],
        superseded=["x", "y", "z"],
        contradictions_resolved=2,
    )
    result = consolidation_report_summary(report)
    assert result["merged_count"] == 2
    assert result["superseded_count"] == 3
    assert result["contradictions_resolved"] == 2
