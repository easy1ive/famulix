"""Schema-versioned JSON envelopes for durable artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from famulix.types import SCHEMA_VERSION_CURRENT
from famulix.utils import content_checksum, stable_json_dumps


@dataclass(frozen=True)
class Envelope:
    """Schema-versioned wrapper with content checksum.

    Every persisted artifact (event, memory, plan, session record) is wrapped
    so consumers can detect version skew and verify integrity.
    """

    schema_version: int
    kind: str
    payload: dict[str, Any]
    checksum: str

    @classmethod
    def wrap(
        cls,
        kind: str,
        payload: dict[str, Any],
        schema_version: int = SCHEMA_VERSION_CURRENT,
    ) -> Envelope:
        inner = stable_json_dumps(payload).encode("utf-8")
        return cls(
            schema_version=schema_version,
            kind=kind,
            payload=payload,
            checksum=content_checksum(inner),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "kind": self.kind,
            "payload": self.payload,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Envelope:
        env = cls(
            schema_version=int(data["schemaVersion"]),
            kind=str(data["kind"]),
            payload=dict(data["payload"]),
            checksum=str(data["checksum"]),
        )
        env.verify()
        return env

    def verify(self) -> bool:
        expected = content_checksum(stable_json_dumps(self.payload).encode("utf-8"))
        if expected != self.checksum:
            raise ValueError(
                f"Envelope checksum mismatch: expected {expected}, got {self.checksum}"
            )
        return True

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_jsonl_line(cls, line: str) -> Envelope:
        return cls.from_dict(json.loads(line))
