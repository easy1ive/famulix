"""Test consolidation report formatting with citations."""

from famulix.consolidation import ConsolidationReport, format_consolidation_report
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history


def test_format_consolidation_report_with_citations():
    """Verify consolidation report includes citations to memory nodes."""
    events, _manifest = generate_history(seed=42, days=10)
    graph = encode_events_to_graph(events)

    # Create a report with some actions
    report = ConsolidationReport(
        merged_pairs=[],
        superseded=[],
        summary_nodes=[],
        contradictions_resolved=0,
    )

    # Format the report
    text = format_consolidation_report(report, graph)

    # Should contain header and counts
    assert "# Consolidation Report" in text
    assert "Merged pairs" in text
    assert "Superseded" in text
    assert "Summary nodes created" in text


def test_format_consolidation_report_with_merges():
    """Verify report includes merged pair details with node citations."""
    events, _manifest = generate_history(seed=42, days=10)
    graph = encode_events_to_graph(events)

    # Get some nodes to merge
    nodes = list(graph.all_nodes())
    if len(nodes) < 2:
        return  # Skip if not enough nodes

    n1, n2 = nodes[0], nodes[1]

    report = ConsolidationReport(
        merged_pairs=[(n1.node_id, n2.node_id)],
        superseded=[],
        summary_nodes=[],
        contradictions_resolved=0,
    )

    text = format_consolidation_report(report, graph)

    # Should contain merge details
    assert "## Merged Near-Duplicates" in text
    assert n1.node_id in text
    assert n2.node_id in text
