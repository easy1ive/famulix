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
from typing import Any, Literal

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
        return cls(
            edge_id=eid,
            from_id=from_id,
            to_id=to_id,
            kind=kind,
            weight=round(weight, 6),
        )


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
        if edge.kind == "derived_from" and self._has_provenance_path(edge.to_id, edge.from_id):
            raise ValueError("derived_from edges must keep provenance acyclic")
        self._edges[edge.edge_id] = edge
        self._out_edges[edge.from_id].append(edge.edge_id)
        self._in_edges[edge.to_id].append(edge.edge_id)

    def _has_provenance_path(self, start: MemoryId, target: MemoryId) -> bool:
        pending = [start]
        visited: set[MemoryId] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(
                edge.to_id for edge in self.out_edges(current) if edge.kind == "derived_from"
            )
        return False

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

    def active_nodes(self) -> list[MemoryNode]:
        return [n for n in self._nodes.values() if n.is_active]

    def active_node_count(self) -> int:
        return sum(1 for n in self._nodes.values() if n.is_active)

    def nodes_by_kind(self, kind: NodeKind) -> list[MemoryNode]:
        return [n for n in self._nodes.values() if n.kind == kind and n.is_active]

    def kind_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for node in self._nodes.values():
            if not node.is_active:
                continue
            counts[node.kind] = counts.get(node.kind, 0) + 1
        return counts

    def reachable_from(
        self,
        seed_ids: list[MemoryId],
        *,
        edge_kinds: set[EdgeKind] | None = None,
        max_depth: int = 10,
    ) -> set[MemoryId]:
        """Return all node ids reachable from seeds via edges of given kinds."""
        visited: set[MemoryId] = set()
        frontier: list[MemoryId] = [nid for nid in seed_ids if nid in self._nodes]
        depth = 0
        while frontier and depth < max_depth:
            next_frontier: list[MemoryId] = []
            for nid in frontier:
                if nid in visited:
                    continue
                visited.add(nid)
                for edge in self.out_edges(nid):
                    if (
                        edge_kinds is None or edge.kind in edge_kinds
                    ) and edge.to_id not in visited:
                        next_frontier.append(edge.to_id)
            frontier = next_frontier
            depth += 1
        return visited

    def to_dict(self) -> dict[str, Any]:
        """Return a versioned, deterministic representation of the graph."""
        nodes = [
            {
                "node_id": node.node_id,
                "kind": node.kind,
                "title": node.title,
                "body": node.body,
                "metadata": dict(sorted(node.metadata.items())),
                "created_at_s": node.created_at_s,
                "is_active": node.is_active,
                "version": node.version,
            }
            for node in sorted(self._nodes.values(), key=lambda item: item.node_id)
        ]
        edges = [
            {
                "edge_id": edge.edge_id,
                "from_id": edge.from_id,
                "to_id": edge.to_id,
                "kind": edge.kind,
                "weight": edge.weight,
            }
            for edge in sorted(self._edges.values(), key=lambda item: item.edge_id)
        ]
        return {"schema_version": 1, "nodes": nodes, "edges": edges}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> MemoryGraph:
        """Load a graph representation, rejecting unsupported or invalid data."""
        if data.get("schema_version") != 1:
            raise ValueError("unsupported memory graph schema version")
        nodes = data.get("nodes")
        edges = data.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise ValueError("memory graph nodes and edges must be lists")
        graph = cls()
        try:
            for raw_node in nodes:
                if not isinstance(raw_node, dict):
                    raise ValueError("memory graph node must be an object")
                if set(raw_node) != {
                    "node_id",
                    "kind",
                    "title",
                    "body",
                    "metadata",
                    "created_at_s",
                    "is_active",
                    "version",
                }:
                    raise ValueError("memory graph node has unknown or missing fields")
                if raw_node["node_id"] in graph._nodes:  # noqa: SLF001
                    raise ValueError("duplicate memory graph node id")
                if not isinstance(raw_node["metadata"], dict) or any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in raw_node["metadata"].items()
                ):
                    raise ValueError("memory graph node metadata must contain strings")
                if (
                    type(raw_node["created_at_s"]) is not int
                    or type(raw_node["version"]) is not int
                ):
                    raise ValueError("memory graph node timestamps and versions must be integers")
                if type(raw_node["is_active"]) is not bool:
                    raise ValueError("memory graph node active state must be boolean")
                graph.add_node(MemoryNode(**raw_node))
            for raw_edge in edges:
                if not isinstance(raw_edge, dict):
                    raise ValueError("memory graph edge must be an object")
                if set(raw_edge) != {"edge_id", "from_id", "to_id", "kind", "weight"}:
                    raise ValueError("memory graph edge has unknown or missing fields")
                if raw_edge["edge_id"] in graph._edges:  # noqa: SLF001
                    raise ValueError("duplicate memory graph edge id")
                if type(raw_edge["weight"]) not in (int, float):
                    raise ValueError("memory graph edge weight must be numeric")
                graph.add_edge(MemoryEdge(**raw_edge))
        except (TypeError, KeyError) as exc:
            raise ValueError("invalid memory graph record") from exc
        if graph.has_cycle_along("derived_from"):
            raise ValueError("memory graph provenance must be acyclic")
        return graph

    def remove_node(self, node_id: MemoryId) -> bool:
        """Remove a node and all edges referencing it. Returns True if removed."""
        if node_id not in self._nodes:
            return False
        # Cascade: remove all edges involving this node
        out_ids = list(self._out_edges.get(node_id, []))
        in_ids = list(self._in_edges.get(node_id, []))
        for eid in out_ids + in_ids:
            edge = self._edges.pop(eid, None)
            if edge is None:
                continue
            # Remove from neighbor adjacency lists
            self._out_edges.get(edge.from_id, []).remove(eid) if eid in self._out_edges.get(
                edge.from_id, []
            ) else None
            self._in_edges.get(edge.to_id, []).remove(eid) if eid in self._in_edges.get(
                edge.to_id, []
            ) else None
        del self._nodes[node_id]
        self._out_edges.pop(node_id, None)
        self._in_edges.pop(node_id, None)
        return True

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

    def extract_subgraph(
        self,
        seed_ids: list[MemoryId],
        *,
        max_depth: int = 2,
        edge_kinds: set[EdgeKind] | None = None,
    ) -> MemoryGraph:
        """Extract a k-hop subgraph around seed nodes.

        Returns a new MemoryGraph containing all nodes reachable within
        max_depth hops via edges of the specified kinds (or all kinds if
        None), plus all edges between included nodes. The seed nodes are
        always included even if isolated.
        """
        if max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        included_nodes: set[MemoryId] = set()
        frontier: list[MemoryId] = [nid for nid in seed_ids if nid in self._nodes]
        included_nodes.update(frontier)

        depth = 0
        while frontier and depth < max_depth:
            next_frontier: list[MemoryId] = []
            for nid in frontier:
                for edge in self.out_edges(nid):
                    if edge_kinds is not None and edge.kind not in edge_kinds:
                        continue
                    if edge.to_id not in included_nodes:
                        included_nodes.add(edge.to_id)
                        next_frontier.append(edge.to_id)
                for edge in self.in_edges(nid):
                    if edge_kinds is not None and edge.kind not in edge_kinds:
                        continue
                    if edge.from_id not in included_nodes:
                        included_nodes.add(edge.from_id)
                        next_frontier.append(edge.from_id)
            frontier = next_frontier
            depth += 1

        subgraph = MemoryGraph()
        for nid in sorted(included_nodes):
            node = self._nodes[nid]
            subgraph.add_node(node)
        for edge in self._edges.values():
            if (
                edge.from_id in included_nodes
                and edge.to_id in included_nodes
                and (edge_kinds is None or edge.kind in edge_kinds)
            ):
                subgraph.add_edge(edge)
        return subgraph

    def neighborhood(
        self, node_id: MemoryId, *, radius: int = 1
    ) -> tuple[list[MemoryNode], list[MemoryEdge]]:
        """Return nodes and edges within radius hops of a node.

        The center node is included in the node list. Returns empty lists
        if the node does not exist.
        """
        if radius < 0:
            raise ValueError("radius must be non-negative")
        if node_id not in self._nodes:
            return [], []
        visited: set[MemoryId] = {node_id}
        frontier = [node_id]
        edges: list[MemoryEdge] = []
        depth = 0
        while frontier and depth < radius:
            next_frontier: list[MemoryId] = []
            for nid in frontier:
                for edge in self.out_edges(nid) + self.in_edges(nid):
                    edges.append(edge)
                    neighbor = edge.to_id if edge.from_id == nid else edge.from_id
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.append(neighbor)
            frontier = next_frontier
            depth += 1
        nodes = [self._nodes[nid] for nid in sorted(visited) if nid in self._nodes]
        seen_edges: set[MemoryId] = set()
        unique_edges: list[MemoryEdge] = []
        for edge in edges:
            if edge.edge_id not in seen_edges:
                seen_edges.add(edge.edge_id)
                unique_edges.append(edge)
        return nodes, unique_edges
