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
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("envelope kind must be non-empty")
        if type(schema_version) is not int or schema_version != SCHEMA_VERSION_CURRENT:
            raise ValueError(f"unsupported envelope schema version: {schema_version}")
        if not isinstance(payload, dict):
            raise ValueError("envelope payload must be an object")
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
        required = {"schemaVersion", "kind", "payload", "checksum"}
        if set(data) != required:
            raise ValueError("envelope has unknown or missing fields")
        schema_version = data["schemaVersion"]
        if type(schema_version) is not int or schema_version != SCHEMA_VERSION_CURRENT:
            raise ValueError(f"unsupported envelope schema version: {schema_version}")
        if not isinstance(data["kind"], str) or not data["kind"]:
            raise ValueError("envelope kind must be a non-empty string")
        if not isinstance(data["payload"], dict):
            raise ValueError("envelope payload must be an object")
        if not isinstance(data["checksum"], str):
            raise ValueError("envelope checksum must be a string")
        env = cls(
            schema_version=schema_version,
            kind=data["kind"],
            payload=data["payload"],
            checksum=data["checksum"],
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
        return stable_json_dumps(self.to_dict())

    @classmethod
    def from_jsonl_line(cls, line: str) -> Envelope:
        try:
            data = json.loads(line, parse_constant=_reject_json_constant)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid envelope JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("envelope JSON must contain an object")
        return cls.from_dict(data)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")
