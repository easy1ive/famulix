"""Trigger cooldown tracking to prevent spam."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CooldownTracker:
    """Track trigger firings to enforce cooldowns."""

    cooldown_seconds: int = 3600
    last_fired: dict[str, int] = field(default_factory=dict)

    def can_fire(self, trigger_id: str, current_time_s: int) -> bool:
        """Check if a trigger can fire at the given time."""
        if trigger_id not in self.last_fired:
            return True

        elapsed = current_time_s - self.last_fired[trigger_id]
        return elapsed >= self.cooldown_seconds

    def record_fire(self, trigger_id: str, current_time_s: int) -> None:
        """Record that a trigger fired."""
        self.last_fired[trigger_id] = current_time_s

    def time_until_ready(self, trigger_id: str, current_time_s: int) -> int:
        """Return seconds until trigger can fire again."""
        if trigger_id not in self.last_fired:
            return 0

        elapsed = current_time_s - self.last_fired[trigger_id]
        remaining = self.cooldown_seconds - elapsed
        return max(0, remaining)
