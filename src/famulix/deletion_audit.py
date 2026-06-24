"""Deletion audit trail for right-to-forget compliance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeletionAuditEntry:
    """A single deletion audit entry."""

    timestamp_s: int
    node_id: str
    node_kind: str
    reason: str
    cascaded_to: list[str] = field(default_factory=list)
    tombstone_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_s": self.timestamp_s,
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "reason": self.reason,
            "cascaded_to": self.cascaded_to,
            "tombstone_id": self.tombstone_id,
        }


@dataclass
class DeletionAuditLog:
    """Immutable audit log of all deletions."""

    entries: list[DeletionAuditEntry] = field(default_factory=list)

    def record(self, entry: DeletionAuditEntry) -> None:
        """Record a deletion."""
        self.entries.append(entry)

    def count(self) -> int:
        """Return total deletion count."""
        return len(self.entries)

    def by_kind(self) -> dict[str, int]:
        """Return deletion counts by node kind."""
        counts: dict[str, int] = {}
        for entry in self.entries:
            counts[entry.node_kind] = counts.get(entry.node_kind, 0) + 1
        return counts
