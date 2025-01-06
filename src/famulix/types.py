"""Shared type aliases and constants."""

from __future__ import annotations

from typing import Literal

MemoryId = str
EventId = str
EntityId = str
FactKey = str
SessionId = str
TierName = Literal["hot", "warm", "cold", "archive"]
Confidence = float  # 0.0..1.0

SCHEMA_VERSION_CURRENT = 1
DEFAULT_TIMEZONE = "Asia/Shanghai"
