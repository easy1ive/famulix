"""Memory decay and forgetting with tiered retention curves.

Implements Ebbinghaus-style exponential decay per tier (hot/warm/cold/archive),
with protected/pinned memories, grace periods, and tombstone semantics.

Reference: Ebbinghaus forgetting curve.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from famulix.memory_graph import MemoryGraph, MemoryNode
from famulix.types import TierName


@dataclass(frozen=True)
class DecayConfig:
    """Retention curve parameters per tier.

    Half-life is the time in seconds after which retention drops to 50%.
    """

    hot_half_life_s: float = 86400 * 1  # 1 day
    warm_half_life_s: float = 86400 * 7  # 1 week
    cold_half_life_s: float = 86400 * 30  # 1 month
    archive_half_life_s: float = 86400 * 365  # 1 year
    grace_period_s: float = 3600  # memories younger than this never decay
    tombstone_threshold: float = 0.01  # retention below this → tombstone


TIER_HALF_LIVES: dict[TierName, str] = {
    "hot": "hot_half_life_s",
    "warm": "warm_half_life_s",
    "cold": "cold_half_life_s",
    "archive": "archive_half_life_s",
}


def get_tier(node: MemoryNode, default: TierName = "warm") -> TierName:
    tier = node.metadata.get("tier", default)
    if tier in {"hot", "warm", "cold", "archive"}:
        return tier  # type: ignore[return-value]
    return default


def retention_score(
    node: MemoryNode,
    *,
    now_s: int,
    config: DecayConfig | None = None,
) -> float:
    """Compute retention score in [0, 1] for a node.

    Pinned or protected nodes always return 1.0. Nodes within the grace
    period return 1.0. Otherwise exponential decay by tier.
    """
    cfg = config or DecayConfig()

    # Protected: pinned or explicitly protected
    if node.metadata.get("pinned") == "true":
        return 1.0
    if node.metadata.get("protected") == "true":
        return 1.0

    age = max(now_s - node.created_at_s, 0)
    # Grace period
    if age <= cfg.grace_period_s:
        return 1.0

    tier = get_tier(node)
    attr = TIER_HALF_LIVES[tier]
    half_life = getattr(cfg, attr)
    score = float(np.exp(-age * np.log(2) / half_life))
    return round(score, 6)


def tier_for_retention(retention: float) -> TierName:
    """Suggest a tier based on retention score.

    >=0.7 → hot, >=0.4 → warm, >=0.1 → cold, else archive.
    """
    if retention >= 0.7:
        return "hot"
    if retention >= 0.4:
        return "warm"
    if retention >= 0.1:
        return "cold"
    return "archive"


def apply_decay(
    graph: MemoryGraph,
    *,
    now_s: int,
    config: DecayConfig | None = None,
) -> dict[str, float]:
    """Compute retention for all active nodes. Returns {node_id: retention}."""
    cfg = config or DecayConfig()
    result: dict[str, float] = {}
    for node in graph.all_nodes():
        if not node.is_active:
            continue
        result[node.node_id] = retention_score(node, now_s=now_s, config=cfg)
    return result


def count_tombstoned(
    graph: MemoryGraph,
    *,
    now_s: int,
    config: DecayConfig | None = None,
) -> int:
    """Count nodes whose retention has fallen below the tombstone threshold."""
    cfg = config or DecayConfig()
    scores = apply_decay(graph, now_s=now_s, config=cfg)
    return sum(1 for s in scores.values() if s < cfg.tombstone_threshold)


def tier_distribution(
    graph: MemoryGraph,
    *,
    now_s: int,
    config: DecayConfig | None = None,
) -> dict[TierName, int]:
    """Count how many nodes fall into each retention tier."""
    scores = apply_decay(graph, now_s=now_s, config=config)
    dist: dict[TierName, int] = {"hot": 0, "warm": 0, "cold": 0, "archive": 0}
    for score in scores.values():
        tier = tier_for_retention(score)
        dist[tier] += 1
    return dist


def protected_nodes_survive(
    graph: MemoryGraph,
    *,
    now_s: int,
    config: DecayConfig | None = None,
) -> bool:
    """Property: every protected/pinned node has retention == 1.0."""
    scores = apply_decay(graph, now_s=now_s, config=config)
    for node in graph.all_nodes():
        if not node.is_active:
            continue
        is_protected = (
            node.metadata.get("pinned") == "true" or node.metadata.get("protected") == "true"
        )
        if is_protected and scores.get(node.node_id, 0.0) != 1.0:
            return False
    return True
