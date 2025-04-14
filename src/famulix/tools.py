"""Declarative tool specs and deterministic in-process tool execution.

Tools have JSON-schema arguments, capability tags, side-effect class,
idempotency keys for side-effecting tools, timeouts, bounded retries with
jitter, and policy-gated receipts.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

SideEffectClass = Literal["none", "read", "write", "mutate"]


@dataclass(frozen=True)
class ToolSpec:
    """Declarative specification of a tool."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    side_effect_class: SideEffectClass = "read"
    capability_tags: frozenset[str] = frozenset()
    timeout_seconds: float = 5.0
    max_retries: int = 0
    idempotent: bool = False

    def validate_arguments(self, arguments: dict[str, Any]) -> list[str]:
        """Validate arguments against the parameter schema.

        Returns a list of error messages. Empty list means valid.
        This is a lightweight validator — not full JSON Schema, but covers
        required fields, types, and enums.
        """
        errors: list[str] = []
        props = self.parameters.get("properties", {})
        required = self.parameters.get("required", [])

        # Check required fields
        for req in required:
            if req not in arguments:
                errors.append(f"missing required field: {req}")

        # Check types and enums
        for name, value in arguments.items():
            if name not in props:
                errors.append(f"unknown field: {name}")
                continue
            prop = props[name]
            expected_type = prop.get("type")
            if expected_type:
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"{name}: expected string, got {type(value).__name__}")
                elif expected_type == "integer" and type(value) is not int:
                    errors.append(f"{name}: expected integer, got {type(value).__name__}")
                elif expected_type == "number" and type(value) not in (int, float):
                    errors.append(f"{name}: expected number, got {type(value).__name__}")
                elif expected_type == "number" and not math.isfinite(value):
                    errors.append(f"{name}: expected finite number, got {type(value).__name__}")
                elif expected_type == "boolean" and type(value) is not bool:
                    errors.append(f"{name}: expected boolean, got {type(value).__name__}")
                elif expected_type == "array" and not isinstance(value, list):
                    errors.append(f"{name}: expected array, got {type(value).__name__}")
                elif expected_type == "object" and not isinstance(value, dict):
                    errors.append(f"{name}: expected object, got {type(value).__name__}")

            if type(value) in (int, float) and type(value) is not bool:
                if "minimum" in prop and value < prop["minimum"]:
                    errors.append(f"{name}: value is below minimum {prop['minimum']}")
                if "maximum" in prop and value > prop["maximum"]:
                    errors.append(f"{name}: value is above maximum {prop['maximum']}")
            if isinstance(value, str):
                if "minLength" in prop and len(value) < prop["minLength"]:
                    errors.append(f"{name}: string is shorter than minLength {prop['minLength']}")
                if "maxLength" in prop and len(value) > prop["maxLength"]:
                    errors.append(f"{name}: string is longer than maxLength {prop['maxLength']}")

            # Check enum
            if "enum" in prop and value not in prop["enum"]:
                errors.append(f"{name}: value not in enum {prop['enum']}")

        return errors


@dataclass
class ToolResult:
    """Result of a tool invocation."""

    tool_name: str
    success: bool
    output: Any
    error: str | None = None
    duration_s: float = 0.0
    retries: int = 0
    receipt_id: str = ""


@dataclass
class ToolRegistry:
    """Registry of available tools with deterministic execution."""

    _tools: dict[str, tuple[ToolSpec, Callable[..., Any]]] = field(default_factory=dict)

    def register(
        self,
        spec: ToolSpec,
        handler: Callable[..., Any],
    ) -> None:
        self._tools[spec.name] = (spec, handler)

    def get_spec(self, name: str) -> ToolSpec | None:
        if name not in self._tools:
            return None
        return self._tools[name][0]

    def list_specs(self) -> list[ToolSpec]:
        return [spec for spec, _ in self._tools.values()]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        seed: int = 0,
    ) -> ToolResult:
        """Execute a tool with validation and bounded retries.

        The seed parameter is used for deterministic jitter in retries.
        """
        if name not in self._tools:
            return ToolResult(
                tool_name=name,
                success=False,
                output=None,
                error=f"tool not found: {name}",
            )

        spec, handler = self._tools[name]
        errors = spec.validate_arguments(arguments)
        if errors:
            return ToolResult(
                tool_name=name,
                success=False,
                output=None,
                error="; ".join(errors),
            )

        rng = random.Random(seed)
        start = time.monotonic()
        last_error: str | None = None
        retries = 0

        for attempt in range(spec.max_retries + 1):
            try:
                output = handler(**arguments)
                duration = time.monotonic() - start
                args_key = json.dumps(arguments, sort_keys=True)
                receipt_payload = f"{name}\0{args_key}\0{idempotency_key or ''}"
                receipt = f"{name}_{hashlib.sha256(receipt_payload.encode()).hexdigest()[:20]}"
                return ToolResult(
                    tool_name=name,
                    success=True,
                    output=output,
                    duration_s=round(duration, 6),
                    retries=retries,
                    receipt_id=receipt,
                )
            except Exception as e:  # noqa: BLE001
                last_error = str(e)
                retries = attempt + 1
                if attempt < spec.max_retries:
                    jitter = rng.uniform(0.1, 0.5) * (2**attempt)
                    time.sleep(min(jitter, 2.0))

        duration = time.monotonic() - start
        return ToolResult(
            tool_name=name,
            success=False,
            output=None,
            error=last_error,
            duration_s=round(duration, 6),
            retries=retries,
        )


# --- Built-in deterministic tools ------------------------------------------


def echo_tool(text: str) -> str:
    """A simple echo tool — always succeeds, no side effects."""
    return text


def add_tool(a: float, b: float) -> float:
    """Add two numbers."""
    return round(a + b, 6)


def build_default_registry() -> ToolRegistry:
    """Build a registry with the built-in deterministic tools."""
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="echo",
            description="Echo the input text back.",
            side_effect_class="none",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
        ),
        echo_tool,
    )
    registry.register(
        ToolSpec(
            name="add",
            description="Add two numbers.",
            side_effect_class="none",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        ),
        add_tool,
    )
    return registry
