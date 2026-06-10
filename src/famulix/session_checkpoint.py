"""Session checkpoint and resume support."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Checkpoint:
    event_offset: int
    state: dict[str, Any]
    checksum: str

    def save(self, path: Path) -> None:
        data = {
            "event_offset": self.event_offset,
            "state": self.state,
            "checksum": self.checksum,
        }
        path.write_text(json.dumps(data, indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: Path) -> Checkpoint:
        data = json.loads(path.read_text())
        return cls(
            event_offset=data["event_offset"],
            state=data["state"],
            checksum=data["checksum"],
        )


def can_resume_from(checkpoint: Checkpoint, total_events: int) -> bool:
    return checkpoint.event_offset < total_events
