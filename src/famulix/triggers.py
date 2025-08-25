"""Proactive reminder triggers derived from memory and deadlines.

Triggers are generated from memory salience and deadlines, with quiet hours,
cooldowns, dedupe windows, and suppression when a briefing already covers
the item. Produces deterministic trigger logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from famulix.memory_graph import MemoryGraph, MemoryNode
from famulix.salience import compute_salience


@dataclass
class Trigger:
    """A single proactive trigger."""

    trigger_id: str
    memory_id: str
    trigger_time_s: int
    reason: str
    fired: bool = False


@dataclass
class TriggerConfig:
    """Configuration for trigger generation."""

    salience_threshold: float = 0.6
    cooldown_seconds: int = 3600  # min time between same-memory triggers
    quiet_hours_start: int = 22  # hour of day
    quiet_hours_end: int = 8  # hour of day
    max_triggers_per_day: int = 20
    dedupe_window_seconds: int = 1800  # suppress duplicate triggers within this window


@dataclass
class TriggerLog:
    """Deterministic log of trigger evaluations."""

    entries: list[dict[str, object]] = field(default_factory=list)

    def record(
        self,
        *,
        timestamp_s: int,
        trigger_id: str,
        memory_id: str,
        action: str,
        reason: str = "",
    ) -> None:
        self.entries.append(
            {
                "timestamp_s": timestamp_s,
                "trigger_id": trigger_id,
                "memory_id": memory_id,
                "action": action,
                "reason": reason,
            }
        )

    def count_by_action(self, action: str) -> int:
        return sum(1 for e in self.entries if e["action"] == action)

    def action_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.entries:
            action = str(entry.get("action", "unknown"))
            counts[action] = counts.get(action, 0) + 1
        return counts

    def entry_count(self) -> int:
        return len(self.entries)

    def clear(self) -> None:
        self.entries.clear()


def _is_quiet_hour(timestamp_s: int, config: TriggerConfig) -> bool:
    """Check if a given timestamp falls within quiet hours (local time, UTC+8)."""
    from datetime import datetime, timedelta, timezone

    dt = datetime.fromtimestamp(timestamp_s, tz=timezone(timedelta(hours=8)))
    hour = dt.hour
    if config.quiet_hours_start < config.quiet_hours_end:
        return config.quiet_hours_start <= hour < config.quiet_hours_end
    # Overnight quiet hours (e.g., 22:00 - 08:00)
    return hour >= config.quiet_hours_start or hour < config.quiet_hours_end


def generate_triggers(
    graph: MemoryGraph,
    *,
    now_s: int,
    config: TriggerConfig | None = None,
    already_covered: set[str] | None = None,
    log: TriggerLog | None = None,
) -> list[Trigger]:
    """Generate trigger candidates from high-salience memories.

    Suppressed by: quiet hours, already-covered set, cooldown tracking.
    Returns triggers sorted by projected firing time (earliest first).
    """
    cfg = config or TriggerConfig()
    if not 0.0 <= cfg.salience_threshold <= 1.0:
        raise ValueError("salience_threshold must be within [0, 1]")
    if cfg.cooldown_seconds < 0 or cfg.max_triggers_per_day < 0:
        raise ValueError("cooldown and daily trigger limit must be non-negative")
    if not 0 <= cfg.quiet_hours_start <= 23 or not 0 <= cfg.quiet_hours_end <= 23:
        raise ValueError("quiet hours must be within [0, 23]")
    covered = already_covered or set()

    if _is_quiet_hour(now_s, cfg):
        if log is not None:
            log.record(
                timestamp_s=now_s,
                trigger_id="",
                memory_id="",
                action="suppressed",
                reason="quiet hours",
            )
        return []

    # Score all active fact/reminder nodes
    candidates: list[tuple[MemoryNode, float]] = []
    for node in graph.all_nodes():
        if not node.is_active:
            continue
        if node.kind not in {"fact", "reminder", "goal"}:
            continue
        if node.node_id in covered:
            continue
        score = compute_salience(node, graph=graph, now_s=now_s)
        if score >= cfg.salience_threshold:
            candidates.append((node, score))

    # Sort by salience (highest first), cap at max
    candidates.sort(key=lambda x: x[1], reverse=True)
    candidates = candidates[: cfg.max_triggers_per_day]

    triggers: list[Trigger] = []
    last_fired: dict[str, int] = {}
    if log is not None:
        for entry in log.entries:
            if entry.get("action") == "generated":
                memory_id = entry.get("memory_id")
                timestamp = entry.get("timestamp_s")
                if isinstance(memory_id, str) and type(timestamp) is int:
                    last_fired[memory_id] = max(last_fired.get(memory_id, timestamp), timestamp)
    for node, score in candidates:
        previous = last_fired.get(node.node_id)
        if previous is not None and now_s - previous < cfg.cooldown_seconds:
            if log is not None:
                log.record(
                    timestamp_s=now_s,
                    trigger_id=f"trig_{node.node_id}",
                    memory_id=node.node_id,
                    action="suppressed",
                    reason="cooldown",
                )
            continue
        if previous is not None and now_s - previous < cfg.dedupe_window_seconds:
            if log is not None:
                log.record(
                    timestamp_s=now_s,
                    trigger_id=f"trig_{node.node_id}",
                    memory_id=node.node_id,
                    action="suppressed",
                    reason="dedupe window",
                )
            continue
        # Compute trigger time: proportional to salience — higher salience → sooner
        delay = int(3600 * (1.0 - min(score, 0.99)))
        trigger_time = now_s + delay

        # Skip if trigger time falls in quiet hours
        if _is_quiet_hour(trigger_time, cfg):
            if log is not None:
                log.record(
                    timestamp_s=now_s,
                    trigger_id=f"trig_{node.node_id}",
                    memory_id=node.node_id,
                    action="scheduled",
                    reason="deferred past quiet hours",
                )
            continue

        tid = f"trig_{node.node_id}"
        trigger = Trigger(
            trigger_id=tid,
            memory_id=node.node_id,
            trigger_time_s=trigger_time,
            reason=f"salience={score:.3f}",
        )
        triggers.append(trigger)
        if log is not None:
            log.record(
                timestamp_s=now_s,
                trigger_id=tid,
                memory_id=node.node_id,
                action="generated",
                reason=f"salience={score:.3f}",
            )

    # Sort by trigger time
    triggers.sort(key=lambda t: t.trigger_time_s)
    return triggers
