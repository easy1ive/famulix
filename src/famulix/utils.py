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


def validate_non_empty_string(value: str, field_name: str) -> list[str]:
    """Validate that a string is non-empty. Returns list of problems."""
    if not isinstance(value, str):
        return [f"{field_name} must be a string, got {type(value).__name__}"]
    if not value.strip():
        return [f"{field_name} must be non-empty"]
    return []


def validate_positive_int(value: int, field_name: str) -> list[str]:
    """Validate that an integer is positive. Returns list of problems."""
    if type(value) is not int:
        return [f"{field_name} must be an integer, got {type(value).__name__}"]
    if value <= 0:
        return [f"{field_name} must be positive, got {value}"]
    return []


def validate_finite_float(value: float, field_name: str) -> list[str]:
    """Validate that a float is finite. Returns list of problems."""
    import math

    if not isinstance(value, (int, float)):
        return [f"{field_name} must be numeric, got {type(value).__name__}"]
    if not math.isfinite(value):
        return [f"{field_name} must be finite, got {value}"]
    return []


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace sequences to single spaces and strip."""
    import re

    return re.sub(r"\s+", " ", text).strip()


def safe_int(value: object, default: int = 0) -> int:
    """Safely convert a value to int, returning default on failure."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except (ValueError, AttributeError):
            return default
    return default


def safe_float(value: object, default: float = 0.0) -> float:
    """Safely convert a value to float, returning default on failure."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (ValueError, AttributeError):
            return default
    return default
