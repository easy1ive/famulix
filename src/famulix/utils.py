"""Utility helpers — checksums, serialization, deterministic hashing."""

from __future__ import annotations

import hashlib
import json


def content_checksum(data: bytes) -> str:
    """Return a deterministic SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def stable_json_dumps(obj: object) -> str:
    """JSON serialization with sorted keys for deterministic output."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_id(prefix: str, payload: str) -> str:
    """Build a content-addressed identifier: prefix_sha256hex[:24]."""
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"
