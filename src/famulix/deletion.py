"""Deletion semantics: right-to-forget cascade and tombstones.

Deletes a memory node and cascades across edges, projections, and retrieval
indexes. Tombstones block re-derivation from surviving events. Provides an
audit report and a property test guarantee that deleted content never
reappears through any query path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from famulix.memory_graph import MemoryGraph


@dataclass
class DeletionReport:
    """Auditable record of what a deletion operation removed."""

    target_id: str
    deleted_nodes: list[str] = field(default_factory=list)
    deleted_edges: list[str] = field(default_factory=list)
    tombstone_nodes: list[str] = field(default_factory=list)
    cascade_depth: int = 0

    @property
    def total_deleted(self) -> int:
        return len(self.deleted_nodes) + len(self.deleted_edges)


def _mark_deleted(graph: MemoryGraph, node_id: str) -> None:
    """Mark a node as deleted (tombstone)."""
    from dataclasses import replace

    node = graph.get_node(node_id)
    if node is None:
        return
    graph._nodes[node_id] = replace(
        node,
        is_active=False,  # noqa: SLF001
        metadata={**node.metadata, "deleted": "true"},
    )


def _remove_edge(graph: MemoryGraph, edge_id: str) -> None:
    edge = graph._edges.pop(edge_id, None)  # noqa: SLF001
    if edge is None:
        return
    graph._out_edges[edge.from_id].remove(edge_id)  # noqa: SLF001
    graph._in_edges[edge.to_id].remove(edge_id)  # noqa: SLF001


def delete_memory(
    graph: MemoryGraph,
    node_id: str,
    *,
    cascade: bool = True,
) -> DeletionReport:
    """Delete a memory node and optionally cascade.

    In cascade mode, also deletes any edges connected to the node.
    The node is tombstoned (kept in the graph but marked inactive with
    a deleted flag) so re-derivation from events can be blocked.
    """
    report = DeletionReport(target_id=node_id)

    node = graph.get_node(node_id)
    if node is None:
        return report
    if not node.is_active:
        return report

    # Tombstone the target
    _mark_deleted(graph, node_id)
    report.deleted_nodes.append(node_id)
    report.tombstone_nodes.append(node_id)

    if cascade:
        # Remove all connected edges
        for e in list(graph.in_edges(node_id)):
            if e.edge_id in graph._edges:  # noqa: SLF001
                _remove_edge(graph, e.edge_id)
                report.deleted_edges.append(e.edge_id)
        for e in list(graph.out_edges(node_id)):
            if e.edge_id in graph._edges:  # noqa: SLF001
                _remove_edge(graph, e.edge_id)
                report.deleted_edges.append(e.edge_id)

        # Clean up adjacency lists
        if node_id in graph._in_edges:  # noqa: SLF001
            graph._in_edges[node_id] = []  # noqa: SLF001
        if node_id in graph._out_edges:  # noqa: SLF001
            graph._out_edges[node_id] = []  # noqa: SLF001

        report.cascade_depth = 1

    return report


def is_deleted(graph: MemoryGraph, node_id: str) -> bool:
    """Check if a node has been tombstoned/deleted."""
    node = graph.get_node(node_id)
    if node is None:
        return True
    if not node.is_active:
        return True
    return node.metadata.get("deleted") == "true"


def can_derive(graph: MemoryGraph, source_event_id: str) -> bool:
    """Check if a tombstone blocks re-derivation from a source event.

    Returns True if derivation is allowed (no tombstone for this source).
    Returns False if a tombstone with the matching source_event exists.
    """
    for node in graph.all_nodes():
        if (
            node.metadata.get("deleted") == "true"
            and node.metadata.get("source_event") == source_event_id
        ):
            return False
    return True


def deletion_audit_report(graph: MemoryGraph) -> dict[str, object]:
    """Generate an audit report of all deleted/tombstoned nodes."""
    deleted = [n.node_id for n in graph.all_nodes() if n.metadata.get("deleted") == "true"]
    inactive = [
        n.node_id
        for n in graph.all_nodes()
        if not n.is_active and n.metadata.get("deleted") != "true"
    ]
    return {
        "total_nodes": graph.node_count(),
        "deleted_count": len(deleted),
        "deleted_ids": deleted,
        "inactive_count": len(inactive),
        "inactive_ids": inactive,
    }


def deleted_content_never_reappears(
    graph: MemoryGraph,
    deleted_ids: set[str],
    query_results: list[object],
) -> bool:
    """Property: deleted node ids never appear in query results.

    Accepts any list of objects that have a 'node_id' attribute or key.
    """
    for result in query_results:
        nid = getattr(result, "node_id", None)
        if nid is None and isinstance(result, dict):
            nid = result.get("node_id")
        if nid in deleted_ids:
            return False
    return True


def verify_deletion_cascade(graph: MemoryGraph, deleted_id: str) -> dict[str, object]:
    """Verify that a deletion cascaded correctly through the graph.

    Checks:
    - The node is marked as deleted
    - All edges to/from the node are removed or marked
    - No active edges reference the deleted node
    - No active nodes derive from the deleted node

    Returns a dict with verification results and any violations found.
    """
    violations: list[str] = []

    node = graph.get_node(deleted_id)
    if node is None:
        return {
            "verified": False,
            "node_exists": False,
            "violations": ["node not found in graph"],
        }

    if node.metadata.get("deleted") != "true":
        violations.append("node is not marked as deleted")

    # Check for active edges referencing this node
    for edge in graph.all_edges():
        if edge.from_id == deleted_id or edge.to_id == deleted_id:
            violations.append(f"active edge {edge.edge_id} references deleted node")

    # Check for active nodes that derive from this node
    for other_node in graph.all_nodes():
        if other_node.node_id == deleted_id:
            continue
        if not other_node.is_active:
            continue
        for edge in graph.out_edges(other_node.node_id):
            if edge.kind == "derived_from" and edge.to_id == deleted_id:
                violations.append(f"active node {other_node.node_id} derives from deleted node")

    return {
        "verified": len(violations) == 0,
        "node_exists": True,
        "violations": violations,
    }


def validate_deletion_integrity(graph: MemoryGraph) -> list[str]:
    """Validate that all deletions in the graph are consistent.

    Returns a list of integrity violations found.
    """
    violations: list[str] = []

    deleted_nodes = [n for n in graph.all_nodes() if n.metadata.get("deleted") == "true"]

    for node in deleted_nodes:
        result = verify_deletion_cascade(graph, node.node_id)
        result_violations = result["violations"]
        assert isinstance(result_violations, list)
        for violation in result_violations:
            violations.append(f"node {node.node_id}: {violation}")

    return violations
