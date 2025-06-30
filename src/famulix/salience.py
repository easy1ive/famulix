"""Salience scoring for memory nodes.

Implements a transparent NumPy-based scorer combining frequency, recency,
commitment language, goal linkage, and explicit pinning. References:
recency/importance/relevance decomposition from Park et al. (2023)
Generative Agents memory-stream scoring.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from famulix.memory_graph import MemoryGraph, MemoryNode


@dataclass(frozen=True)
class SalienceConfig:
    """Weights for the salience scorer."""

    recency_weight: float = 0.3
    frequency_weight: float = 0.2
    importance_weight: float = 0.3
    goal_linkage_weight: float = 0.15
    pinning_weight: float = 0.05
    recency_half_life_s: float = 86400 * 3  # 3-day half-life
    max_score: float = 1.0


def _recency_score(created_at_s: int, now_s: int, half_life: float) -> float:
    """Exponential decay based on age relative to half-life."""
    age_s = max(now_s - created_at_s, 0)
    return float(np.exp(-age_s * np.log(2) / half_life))


def _importance_from_text(body: str, title: str) -> float:
    """Estimate importance from content features.

    Uses length, presence of commitment markers, and number of distinct
    named entities as a transparent proxy.
    """
    text = f"{title} {body}".lower()
    score = 0.3
    # Length signal (capped)
    score += min(len(text) / 500, 0.3)
    # Commitment markers
    markers = [
        "must",
        "will",
        "always",
        "never",
        "critical",
        "important",
        "deadline",
        "决定",
        "重要",
        "必须",
    ]
    marker_hits = sum(1 for m in markers if m in text)
    score += min(marker_hits * 0.08, 0.25)
    return round(min(score, 1.0), 6)


def compute_salience(
    node: MemoryNode,
    *,
    graph: MemoryGraph | None = None,
    now_s: int,
    config: SalienceConfig | None = None,
) -> float:
    """Compute a salience score in [0, config.max_score] for a memory node."""
    cfg = config or SalienceConfig()
    # Frequency: number of in-edges (how many things reference this node)
    freq_raw = len(graph.in_edges(node.node_id)) if graph is not None else 0
    freq_score = min(freq_raw / 5.0, 1.0)

    # Recency
    rec_score = _recency_score(node.created_at_s, now_s, cfg.recency_half_life_s)

    # Importance (content-based)
    imp_score = _importance_from_text(node.body, node.title)

    # Goal linkage: edges to/from goal nodes
    goal_score = 0.0
    if graph is not None:
        goal_neighbors = [n for n in graph.neighbors(node.node_id) if n.kind == "goal"]
        # Also check incoming: if a goal references this
        for e in graph.in_edges(node.node_id):
            src = graph.get_node(e.from_id)
            if src is not None and src.kind == "goal":
                goal_neighbors.append(src)
        goal_score = min(len(goal_neighbors) / 2.0, 1.0)

    # Pinning: from metadata "pinned" = "true"
    pin_score = 1.0 if node.metadata.get("pinned") == "true" else 0.0

    raw = (
        cfg.recency_weight * rec_score
        + cfg.frequency_weight * freq_score
        + cfg.importance_weight * imp_score
        + cfg.goal_linkage_weight * goal_score
        + cfg.pinning_weight * pin_score
    )
    return round(min(raw * cfg.max_score / 1.0, cfg.max_score), 6)


def score_all_nodes(
    graph: MemoryGraph,
    *,
    now_s: int,
    config: SalienceConfig | None = None,
) -> dict[str, float]:
    """Score all nodes in a graph. Returns {node_id: score}."""
    return {
        n.node_id: compute_salience(n, graph=graph, now_s=now_s, config=config)
        for n in graph.all_nodes()
    }


def recency_weights(timestamps: list[int], *, now_s: int, half_life: float) -> list[float]:
    """Vectorized recency scores for a list of creation timestamps."""
    if not timestamps:
        return []
    ages = np.maximum(now_s - np.array(timestamps, dtype=np.float64), 0.0)
    weights = np.exp(-ages * np.log(2) / max(half_life, 1e-9))
    return [round(float(w), 6) for w in weights]


def top_k(scores: dict[str, float], k: int) -> list[tuple[str, float]]:
    """Return the top-k node ids by score, deterministic on ties (by id)."""
    items = [(nid, score) for nid, score in scores.items()]
    items.sort(key=lambda pair: (-pair[1], pair[0]))
    return items[: max(k, 0)]


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Min-max normalize scores to [0, 1]; returns zeros if all equal."""
    if not scores:
        return {}
    vals = list(scores.values())
    lo = min(vals)
    hi = max(vals)
    if hi - lo < 1e-9:
        return {nid: 0.0 for nid in scores}
    return {nid: round((s - lo) / (hi - lo), 6) for nid, s in scores.items()}


def slice_diagnostics(scores: dict[str, float]) -> dict[str, float]:
    """Summary statistics for a set of salience scores."""
    vals = np.array(list(scores.values()), dtype=np.float64)
    if len(vals) == 0:
        return {"count": 0.0, "mean": 0.0, "median": 0.0, "p90": 0.0, "max": 0.0}
    return {
        "count": float(len(vals)),
        "mean": round(float(np.mean(vals)), 6),
        "median": round(float(np.median(vals)), 6),
        "p90": round(float(np.percentile(vals, 90)), 6),
        "max": round(float(np.max(vals)), 6),
    }
