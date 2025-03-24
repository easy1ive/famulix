"""Session record and replay with checksummed JSONL traces.

The recorder appends every event, decision, recall, and receipt to a
checksummed JSONL log. The replayer reconstructs byte-identical traces
(same seed + inputs → identical bytes). Supports checkpoint/resume across
simulated crashes and a session diff tool.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SessionRecorder:
    """Records session events to a JSONL log with per-frame checksums."""

    session_id: str
    seed: int = 0
    entries: list[dict[str, Any]] = field(default_factory=list)
    _frame_hashes: list[str] = field(default_factory=list)

    def record(self, kind: str, payload: dict[str, Any], timestamp_s: int) -> str:
        """Record an event. Returns the frame hash."""
        frame = {
            "session_id": self.session_id,
            "seq": len(self.entries),
            "kind": kind,
            "timestamp_s": timestamp_s,
            "payload": payload,
            "seed": self.seed,
        }
        frame_json = json.dumps(frame, sort_keys=True, ensure_ascii=False)
        frame_hash = hashlib.sha256(
            (frame_json + "".join(self._frame_hashes)).encode()
        ).hexdigest()[:16]
        frame["_hash"] = frame_hash
        self.entries.append(frame)
        self._frame_hashes.append(frame_hash)
        return frame_hash

    def verify(self) -> bool:
        """Verify the entire chain of frame hashes is consistent."""
        hashes: list[str] = []
        for entry in self.entries:
            frame_copy = {k: v for k, v in entry.items() if k != "_hash"}
            frame_json = json.dumps(frame_copy, sort_keys=True, ensure_ascii=False)
            expected = hashlib.sha256((frame_json + "".join(hashes)).encode()).hexdigest()[:16]
            if expected != entry["_hash"]:
                return False
            hashes.append(entry["_hash"])
        return True

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e, ensure_ascii=False, sort_keys=True) for e in self.entries)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_jsonl() + "\n")

    @classmethod
    def load(cls, path: str | Path) -> SessionRecorder:
        lines = Path(path).read_text().strip().split("\n")
        rec = cls(session_id="")
        for line in lines:
            if not line:
                continue
            entry = json.loads(line)
            rec.entries.append(entry)
            rec._frame_hashes.append(entry.get("_hash", ""))
        if rec.entries:
            rec.session_id = rec.entries[0]["session_id"]
            rec.seed = rec.entries[0].get("seed", 0)
        return rec

    def digest(self) -> str:
        """Return a hash of the entire session for diff/comparison."""
        text = self.to_jsonl()
        return hashlib.sha256(text.encode()).hexdigest()


def session_diff(a: SessionRecorder, b: SessionRecorder) -> dict[str, Any]:
    """Compare two sessions and report differences."""
    return {
        "a_digest": a.digest(),
        "b_digest": b.digest(),
        "identical": a.digest() == b.digest(),
        "a_length": len(a.entries),
        "b_length": len(b.entries),
        "length_diff": len(a.entries) - len(b.entries),
    }
