"""Memory graph invariant auditing."""

from __future__ import annotations

from famulix.memory_graph import MemoryGraph


def audit_graph_invariants(graph: MemoryGraph) -> list[str]:
    """Audit graph invariants and return list of issues."""
    issues = []

    node_ids = set(graph._nodes.keys())

    for edge in graph._edges.values():
        if edge.from_id not in node_ids:
            issues.append(f"Dangling edge source: {edge.from_id} not in graph")
        if edge.to_id not in node_ids:
            issues.append(f"Dangling edge target: {edge.to_id} not in graph")
        if edge.from_id == edge.to_id:
            issues.append(f"Self-loop: {edge.from_id} -> {edge.from_id}")

    return issues
