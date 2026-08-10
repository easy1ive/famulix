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
    Tiers must be ordered so hot decays fastest and archive slowest.
    """

    hot_half_life_s: float = 86400 * 1  # 1 day
    warm_half_life_s: float = 86400 * 7  # 1 week
    cold_half_life_s: float = 86400 * 30  # 1 month
    archive_half_life_s: float = 86400 * 365  # 1 year
    grace_period_s: float = 3600  # memories younger than this never decay
    tombstone_threshold: float = 0.01  # retention below this → tombstone

    def __post_init__(self) -> None:
        half_lives = [
            self.hot_half_life_s,
            self.warm_half_life_s,
            self.cold_half_life_s,
            self.archive_half_life_s,
        ]
        if any(hl <= 0 for hl in half_lives):
            raise ValueError("all half-lives must be positive")
        if not (
            self.hot_half_life_s
            <= self.warm_half_life_s
            <= self.cold_half_life_s
            <= self.archive_half_life_s
        ):
            raise ValueError("half-lives must be ordered: hot <= warm <= cold <= archive")
        if self.grace_period_s < 0:
            raise ValueError("grace period must be non-negative")
        if not 0 < self.tombstone_threshold < 1:
            raise ValueError("tombstone threshold must be in (0, 1)")


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


TIER_RANK: dict[TierName, int] = {"archive": 0, "cold": 1, "warm": 2, "hot": 3}


def _tier_rank(tier: TierName) -> int:
    return TIER_RANK.get(tier, 1)


def promote_tier(node: MemoryNode) -> TierName:
    """Promote a node one tier hotter; capped at hot."""
    tier = get_tier(node)
    if tier == "hot":
        return "hot"
    if tier == "warm":
        return "hot"
    if tier == "cold":
        return "warm"
    return "cold"


def demote_tier(node: MemoryNode) -> TierName:
    """Demote a node one tier colder; capped at archive."""
    tier = get_tier(node)
    if tier == "archive":
        return "archive"
    if tier == "cold":
        return "archive"
    if tier == "warm":
        return "cold"
    return "warm"


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


def validate_decay_config(config: DecayConfig) -> list[str]:
    """Validate a decay configuration and return any additional problems.

    The DecayConfig.__post_init__ already validates most constraints.
    This function provides a non-raising validation interface for
    additional checks beyond the constructor validation.

    Returns an empty list if the config is valid.
    """
    # DecayConfig.__post_init__ already validates:
    # - all half-lives are positive
    # - half-lives are ordered: hot <= warm <= cold <= archive
    # - grace_period_s is non-negative
    # - tombstone_threshold is in (0, 1)
    # Any config that exists has passed those checks.
    return []


def retention_diagnostics(
    graph: MemoryGraph,
    *,
    now_s: int,
    config: DecayConfig | None = None,
) -> dict[str, object]:
    """Generate diagnostics for retention scores across the graph.

    Returns a dict with:
    - min_retention: minimum retention score
    - max_retention: maximum retention score
    - mean_retention: average retention score
    - tier_counts: number of nodes in each tier
    - protected_count: number of protected nodes
    """
    scores = apply_decay(graph, now_s=now_s, config=config)
    if not scores:
        return {
            "min_retention": 0.0,
            "max_retention": 0.0,
            "mean_retention": 0.0,
            "tier_counts": {"hot": 0, "warm": 0, "cold": 0, "archive": 0},
            "protected_count": 0,
        }

    values = list(scores.values())
    tier_counts = {"hot": 0, "warm": 0, "cold": 0, "archive": 0}
    protected_count = 0

    for node in graph.all_nodes():
        if not node.is_active:
            continue
        score = scores.get(node.node_id, 0.0)
        tier = tier_for_retention(score)
        tier_counts[tier] += 1
        is_protected = (
            node.metadata.get("pinned") == "true" or node.metadata.get("protected") == "true"
        )
        if is_protected:
            protected_count += 1

    return {
        "min_retention": round(min(values), 6),
        "max_retention": round(max(values), 6),
        "mean_retention": round(sum(values) / len(values), 6),
        "tier_counts": tier_counts,
        "protected_count": protected_count,
    }


def simulate_steady_state(
    tier_thresholds: dict[str, float] | None = None,
    total_memories: int = 1000,
    seed: int = 42,
) -> dict[str, int]:
    """Simulate steady-state memory distribution across retention tiers.

    Generates memories with random salience and assigns them to tiers based
    on thresholds. Runs until distribution stabilizes (change < 1% per cycle).
    Returns the count of memories in each tier at steady state.
    """
    import random

    rng = random.Random(seed)
    if tier_thresholds is None:
        tier_thresholds = {"hot": 0.8, "warm": 0.5, "cold": 0.2, "archive": 0.0}

    tiers = sorted(tier_thresholds.keys(), key=lambda t: -tier_thresholds[t])
    counts: dict[str, int] = {t: 0 for t in tiers}
    saliences = [rng.random() for _ in range(total_memories)]

    for _ in range(100):
        old_counts = dict(counts)
        counts = {t: 0 for t in tiers}
        for s in saliences:
            for t in tiers:
                if s >= tier_thresholds[t]:
                    counts[t] += 1
                    break
        total_change = sum(abs(counts[t] - old_counts[t]) for t in tiers)
        if total_change < total_memories * 0.01:
            break

    return counts
