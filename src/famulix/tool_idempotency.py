"""Tool idempotency key generation for side-effecting tools."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def generate_idempotency_key(tool_name: str, args: dict[str, Any], seed: int = 0) -> str:
    """Generate a deterministic idempotency key."""
    payload = json.dumps(
        {"tool": tool_name, "args": args, "seed": seed},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def is_idempotent_tool(tool_name: str) -> bool:
    """Check if a tool is inherently idempotent."""
    non_idempotent = {"send_email", "create_file", "delete_file", "execute_command"}
    return tool_name not in non_idempotent
