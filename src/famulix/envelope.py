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


def validate_envelope(env: Envelope) -> list[str]:
    """Validate an envelope for structural correctness.

    Checks:
    - schema_version is valid
    - kind is non-empty
    - checksum is non-empty
    - payload is a dict

    Returns a list of validation problems found.
    """
    problems: list[str] = []

    if env.schema_version not in (1,):
        problems.append(f"unsupported schema_version: {env.schema_version}")

    if not env.kind or not env.kind.strip():
        problems.append("kind must be non-empty")

    if not env.checksum or not env.checksum.strip():
        problems.append("checksum must be non-empty")

    if not isinstance(env.payload, dict):
        problems.append(f"payload must be a dict, got {type(env.payload).__name__}")

    return problems


def batch_verify(envelopes: list[Envelope]) -> tuple[int, list[str]]:
    """Verify a batch of envelopes and return (valid_count, errors).

    Returns the number of valid envelopes and a list of error messages
    for any that fail verification.
    """
    valid_count = 0
    errors: list[str] = []

    for i, env in enumerate(envelopes):
        try:
            if env.verify():
                valid_count += 1
        except ValueError as exc:
            errors.append(f"envelope[{i}]: {exc}")

    return valid_count, errors


def envelope_statistics(envelopes: list[Envelope]) -> dict[str, object]:
    """Generate statistics for a batch of envelopes.

    Returns a dict with:
    - count: total number of envelopes
    - schema_versions: set of schema versions seen
    - kinds: set of envelope kinds seen
    - checksum_lengths: set of checksum lengths
    """
    if not envelopes:
        return {
            "count": 0,
            "schema_versions": set(),
            "kinds": set(),
            "checksum_lengths": set(),
        }

    return {
        "count": len(envelopes),
        "schema_versions": {e.schema_version for e in envelopes},
        "kinds": {e.kind for e in envelopes},
        "checksum_lengths": {len(e.checksum) for e in envelopes},
    }
