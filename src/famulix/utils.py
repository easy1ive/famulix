"""Utility helpers — checksums, serialization, deterministic hashing."""

from __future__ import annotations

import hashlib
import json


def content_checksum(data: bytes) -> str:
    """Return a deterministic SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def stable_json_dumps(obj: object) -> str:
    """JSON serialization with sorted keys for deterministic output."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def content_id(prefix: str, payload: str) -> str:
    """Build a content-addressed identifier: prefix_sha256hex[:24]."""
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def stable_hash(text: str, *, length: int = 16) -> str:
    """Return a stable hex hash of a string."""
    if length < 1:
        raise ValueError("hash length must be positive")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def truncate_string(text: str, max_len: int, suffix: str = "...") -> str:
    """Truncate text to max_len characters, appending suffix if needed."""
    if max_len < 0:
        raise ValueError("max_len must be non-negative")
    if len(text) <= max_len:
        return text
    if max_len <= len(suffix):
        return suffix[:max_len]
    return text[: max_len - len(suffix)] + suffix
