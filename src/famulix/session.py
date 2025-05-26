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
        if not kind.strip():
            raise ValueError("session event kind must be non-empty")
        if type(timestamp_s) is not int or timestamp_s < 0:
            raise ValueError("session timestamp must be a non-negative integer")
        if not isinstance(payload, dict):
            raise ValueError("session payload must be an object")
        try:
            payload_snapshot = json.loads(json.dumps(payload, allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise ValueError("session payload must contain finite JSON values") from exc
        frame = {
            "session_id": self.session_id,
            "seq": len(self.entries),
            "kind": kind,
            "timestamp_s": timestamp_s,
            "payload": payload_snapshot,
            "seed": self.seed,
        }
        frame_json = json.dumps(frame, sort_keys=True, ensure_ascii=False, allow_nan=False)
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
        for index, entry in enumerate(self.entries):
            if not isinstance(entry, dict) or entry.get("seq") != index:
                return False
            if entry.get("session_id") != self.session_id or entry.get("seed") != self.seed:
                return False
            if not isinstance(entry.get("_hash"), str):
                return False
            frame_copy = {k: v for k, v in entry.items() if k != "_hash"}
            try:
                frame_json = json.dumps(
                    frame_copy, sort_keys=True, ensure_ascii=False, allow_nan=False
                )
            except (TypeError, ValueError):
                return False
            expected = hashlib.sha256((frame_json + "".join(hashes)).encode()).hexdigest()[:16]
            if expected != entry["_hash"]:
                return False
            hashes.append(entry["_hash"])
        return True

    def to_jsonl(self) -> str:
        return "\n".join(
            json.dumps(e, ensure_ascii=False, sort_keys=True, allow_nan=False) for e in self.entries
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_jsonl() + "\n")

    @classmethod
    def load(cls, path: str | Path) -> SessionRecorder:
        text = Path(path).read_text(encoding="utf-8")
        rec = cls(session_id="")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line:
                raise ValueError(f"empty session frame at line {line_number}")
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid session JSON at line {line_number}") from exc
            if not isinstance(entry, dict):
                raise ValueError(f"session frame at line {line_number} must be an object")
            required = {"session_id", "seq", "kind", "timestamp_s", "payload", "seed", "_hash"}
            if set(entry) != required:
                raise ValueError(
                    f"session frame at line {line_number} has unknown or missing fields"
                )
            if not required.issubset(entry):
                missing = ", ".join(sorted(required - entry.keys()))
                raise ValueError(f"session frame at line {line_number} is missing: {missing}")
            if (
                type(entry["seq"]) is not int
                or type(entry["timestamp_s"]) is not int
                or not isinstance(entry["kind"], str)
            ):
                raise ValueError(f"invalid session frame fields at line {line_number}")
            if entry["seq"] != len(rec.entries):
                raise ValueError(f"session sequence mismatch at line {line_number}")
            rec.entries.append(entry)
            rec._frame_hashes.append(entry["_hash"])
        if rec.entries:
            rec.session_id = rec.entries[0]["session_id"]
            rec.seed = rec.entries[0].get("seed", 0)
            if any(entry["session_id"] != rec.session_id for entry in rec.entries):
                raise ValueError("session frames contain multiple session ids")
            if any(entry["seed"] != rec.seed for entry in rec.entries):
                raise ValueError("session frames contain multiple seeds")
            if not rec.verify():
                raise ValueError("session frame checksum verification failed")
        return rec

    def checkpoint(self) -> dict[str, object]:
        """Return a resumable cursor over the verified trace."""
        if not self.verify():
            raise ValueError("cannot checkpoint an invalid session")
        return {
            "session_id": self.session_id,
            "seed": self.seed,
            "next_seq": len(self.entries),
            "digest": self.digest(),
        }

    @classmethod
    def resume_from(cls, checkpoint: dict[str, object], source: SessionRecorder) -> SessionRecorder:
        required = {"session_id", "seed", "next_seq", "digest"}
        if (
            set(checkpoint) != required
            or checkpoint.get("session_id") != source.session_id
            or checkpoint.get("seed") != source.seed
        ):
            raise ValueError("checkpoint does not match session")
        if (
            checkpoint.get("next_seq") != len(source.entries)
            or checkpoint.get("digest") != source.digest()
        ):
            raise ValueError("checkpoint cursor is stale")
        return source

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
        "first_difference": next(
            (
                index
                for index, (left, right) in enumerate(zip(a.entries, b.entries, strict=False))
                if left != right
            ),
            min(len(a.entries), len(b.entries)) if len(a.entries) != len(b.entries) else None,
        ),
    }
