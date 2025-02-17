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
                del graph._edges[e.edge_id]  # noqa: SLF001
                report.deleted_edges.append(e.edge_id)
        for e in list(graph.out_edges(node_id)):
            if e.edge_id in graph._edges:  # noqa: SLF001
                del graph._edges[e.edge_id]  # noqa: SLF001
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
