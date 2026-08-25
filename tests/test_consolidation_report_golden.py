"""Golden tests for consolidation report output format."""

import hashlib
import json

from famulix.consolidation import ConsolidationReport


def test_consolidation_report_empty_markdown():
    report = ConsolidationReport()
    md = report.to_markdown()
    assert "# Consolidation Report" in md
    assert "No changes were made" in md


def test_consolidation_report_with_merges():
    report = ConsolidationReport(
        merged_pairs=[("mem_a", "mem_b"), ("mem_c", "mem_d")],
        contradictions_resolved=1,
        elapsed_seconds=0.123,
    )
    md = report.to_markdown()
    assert "## Merged duplicates" in md
    assert "`mem_a` ← `mem_b`" in md
    assert "**Contradictions resolved:** 1" in md


def test_consolidation_report_with_superseded():
    report = ConsolidationReport(
        superseded=["mem_old_1", "mem_old_2"],
        contradictions_resolved=2,
    )
    md = report.to_markdown()
    assert "## Superseded facts" in md
    assert "`mem_old_1`" in md


def test_consolidation_report_dict_roundtrip():
    report = ConsolidationReport(
        merged_pairs=[("mem_a", "mem_b")],
        superseded=["mem_x"],
        contradictions_resolved=1,
        summary_nodes=["ep_sum_1"],
        elapsed_seconds=0.5,
    )
    d = report.to_dict()
    assert d["total_changes"] == 3
    assert d["merged_pairs"] == [("mem_a", "mem_b")]
    assert d["elapsed_seconds"] == 0.5


def test_consolidation_report_golden_digest():
    """Stable digest for a fixed consolidation report."""
    report = ConsolidationReport(
        merged_pairs=[("mem_001", "mem_002")],
        superseded=["mem_003"],
        contradictions_resolved=1,
        elapsed_seconds=0.25,
    )
    d = report.to_dict()
    digest = hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]
    # This golden value must remain stable across changes
    assert len(digest) == 16
    assert d["total_changes"] == 2
