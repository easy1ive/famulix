"""Personal memory graph: typed nodes and edges with provenance.

Node kinds: entity, episode, fact, preference, goal, reminder.
Edge kinds: mentions, part_of, derived_from, supersedes, contradicts.

Invariants:
- No dangling edges (both endpoints must exist).
- Acyclic provenance (derived_from chain never loops).
- Single active version per fact key (the newest non-superseded node).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from famulix.types import MemoryId
from famulix.utils import content_id, stable_json_dumps

NodeKind = Literal["entity", "episode", "fact", "preference", "goal", "reminder"]
EdgeKind = Literal["mentions", "part_of", "derived_from", "supersedes", "contradicts"]


@dataclass(frozen=True)
class MemoryNode:
    """A node in the personal memory graph."""

    node_id: MemoryId
    kind: NodeKind
    title: str
    body: str
    metadata: dict[str, str] = field(default_factory=dict)
    created_at_s: int = 0
    is_active: bool = True
    version: int = 1

    @classmethod
    def create(
        cls,
        kind: NodeKind,
        title: str,
        body: str,
        *,
        metadata: dict[str, str] | None = None,
        created_at_s: int = 0,
    ) -> MemoryNode:
        payload = stable_json_dumps(
            {
                "kind": kind,
                "title": title,
                "body": body,
                "metadata": metadata or {},
                "created_at_s": created_at_s,
            }
        )
        nid = content_id("mem", payload)
        return cls(
            node_id=nid,
            kind=kind,
            title=title,
            body=body,
            metadata=metadata or {},
            created_at_s=created_at_s,
        )


@dataclass(frozen=True)
class MemoryEdge:
    """A directed, typed edge between two memory nodes."""

    edge_id: MemoryId
    from_id: MemoryId
    to_id: MemoryId
    kind: EdgeKind
    weight: float = 1.0

    @classmethod
    def create(
        cls,
        from_id: MemoryId,
        to_id: MemoryId,
        kind: EdgeKind,
        weight: float = 1.0,
    ) -> MemoryEdge:
        payload = stable_json_dumps(
            {"from": from_id, "to": to_id, "kind": kind, "weight": round(weight, 6)}
        )
        eid = content_id("edg", payload)
        return cls(edge_id=eid, from_id=from_id, to_id=to_id, kind=kind, weight=weight)


class MemoryGraph:
    """An in-memory memory graph with structural invariants."""

    def __init__(self) -> None:
        self._nodes: dict[MemoryId, MemoryNode] = {}
        self._edges: dict[MemoryId, MemoryEdge] = {}
        self._out_edges: dict[MemoryId, list[MemoryId]] = {}
        self._in_edges: dict[MemoryId, list[MemoryId]] = {}

    def add_node(self, node: MemoryNode) -> None:
        if node.node_id in self._nodes:
            return
        self._nodes[node.node_id] = node
        self._out_edges.setdefault(node.node_id, [])
        self._in_edges.setdefault(node.node_id, [])

    def add_edge(self, edge: MemoryEdge) -> None:
        if edge.edge_id in self._edges:
            return
        if edge.from_id not in self._nodes:
            raise ValueError(f"dangling edge from {edge.from_id}")
        if edge.to_id not in self._nodes:
            raise ValueError(f"dangling edge to {edge.to_id}")
        self._edges[edge.edge_id] = edge
        self._out_edges[edge.from_id].append(edge.edge_id)
        self._in_edges[edge.to_id].append(edge.edge_id)

    def get_node(self, node_id: MemoryId) -> MemoryNode | None:
        return self._nodes.get(node_id)

    def has_node(self, node_id: MemoryId) -> bool:
        return node_id in self._nodes

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)

    def out_edges(self, node_id: MemoryId) -> list[MemoryEdge]:
        return [self._edges[eid] for eid in self._out_edges.get(node_id, [])]

    def in_edges(self, node_id: MemoryId) -> list[MemoryEdge]:
        return [self._edges[eid] for eid in self._in_edges.get(node_id, [])]

    def neighbors(self, node_id: MemoryId, *, kind: EdgeKind | None = None) -> list[MemoryNode]:
        result: list[MemoryNode] = []
        for e in self.out_edges(node_id):
            if kind is None or e.kind == kind:
                n = self._nodes.get(e.to_id)
                if n is not None:
                    result.append(n)
        return result

    def all_nodes(self) -> list[MemoryNode]:
        return list(self._nodes.values())

    def all_edges(self) -> list[MemoryEdge]:
        return list(self._edges.values())

    def has_cycle_along(self, kind: EdgeKind) -> bool:
        """Return True if there is a cycle along edges of the given kind."""
        white, gray, black = 0, 1, 2
        color: dict[MemoryId, int] = {nid: white for nid in self._nodes}

        def dfs(nid: MemoryId) -> bool:
            color[nid] = gray
            for e in self.out_edges(nid):
                if e.kind != kind:
                    continue
                if color[e.to_id] == gray:
                    return True
                if color[e.to_id] == white and dfs(e.to_id):
                    return True
            color[nid] = black
            return False

        return any(color[nid] == white and dfs(nid) for nid in self._nodes)
