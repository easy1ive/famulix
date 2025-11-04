"""Plan DSL: versioned JSON plan schema and deterministic topological planner.

Plans have steps with typed inputs/outputs, preconditions/effects, and
budgets. The validator checks for cycles, dangling references, and type
mismatches. The planner produces a topological execution order.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanStep:
    """A single step in a plan."""

    id: str
    tool: str
    inputs: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    timeout_s: float = 5.0
    budget: float = 0.0
    output_types: dict[str, str] = field(default_factory=dict)
    input_types: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "inputs": self.inputs,
            "depends_on": self.depends_on,
            "preconditions": self.preconditions,
            "effects": self.effects,
            "timeout_s": self.timeout_s,
            "budget": self.budget,
            "output_types": self.output_types,
            "input_types": self.input_types,
        }


@dataclass
class Plan:
    """A complete plan with metadata and steps."""

    plan_id: str
    version: int = 1
    steps: list[PlanStep] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    max_budget: float = 0.0  # 0 means no plan-level budget cap

    def total_step_budget(self) -> float:
        """Sum of all step budgets."""
        return sum(step.budget for step in self.steps)

    def step_ids(self) -> set[str]:
        return {s.id for s in self.steps}

    def step_count(self) -> int:
        return len(self.steps)

    def tools_used(self) -> set[str]:
        return {step.tool for step in self.steps}

    def get_step(self, step_id: str) -> PlanStep | None:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "plan_id": self.plan_id,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
            "max_budget": self.max_budget,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        """Decode a versioned plan payload with strict record shapes."""
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("unsupported plan schema version")
        if set(data) != {
            "schema_version",
            "plan_id",
            "version",
            "steps",
            "metadata",
            "max_budget",
        }:
            raise ValueError("plan payload has unknown or missing fields")
        if not isinstance(data["plan_id"], str) or type(data["version"]) is not int:
            raise ValueError("plan identity and version have invalid types")
        if not isinstance(data["steps"], list) or not isinstance(data["metadata"], dict):
            raise ValueError("plan steps and metadata have invalid types")
        if any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in data["metadata"].items()
        ):
            raise ValueError("plan metadata values must be strings")
        fields = {
            "id",
            "tool",
            "inputs",
            "depends_on",
            "preconditions",
            "effects",
            "timeout_s",
            "budget",
            "output_types",
            "input_types",
        }
        steps: list[PlanStep] = []
        for raw in data["steps"]:
            if not isinstance(raw, dict) or set(raw) != fields:
                raise ValueError("plan step has unknown or missing fields")
            if not isinstance(raw["id"], str) or not isinstance(raw["tool"], str):
                raise ValueError("plan step identity fields must be strings")
            if not isinstance(raw["inputs"], dict):
                raise ValueError("plan step inputs must be an object")
            for name in ("depends_on", "preconditions", "effects"):
                if not isinstance(raw[name], list) or any(
                    not isinstance(item, str) for item in raw[name]
                ):
                    raise ValueError(f"plan step {name} must be a list of strings")
            if type(raw["timeout_s"]) not in (int, float) or type(raw["budget"]) not in (
                int,
                float,
            ):
                raise ValueError("plan step numeric limits must be numbers")
            for type_field in ("output_types", "input_types"):
                if not isinstance(raw[type_field], dict):
                    raise ValueError(f"plan step {type_field} must be an object")
                if any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in raw[type_field].items()
                ):
                    raise ValueError(f"plan step {type_field} values must be strings")
            steps.append(PlanStep(**raw))
        max_budget = data.get("max_budget", 0.0)
        if not isinstance(max_budget, (int, float)):
            raise ValueError("plan max_budget must be numeric")
        return cls(
            plan_id=data["plan_id"],
            version=data["version"],
            steps=steps,
            metadata=dict(data["metadata"]),
            max_budget=float(max_budget),
        )

    def fingerprint(self) -> str:
        """Return a stable content digest for this versioned plan."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        """Serialize the plan as compact, deterministic JSON."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_json(cls, payload: str) -> Plan:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid plan JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("plan JSON must contain an object")
        return cls.from_dict(data)


@dataclass
class ValidationResult:
    """Result of plan validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_plan(plan: Plan) -> ValidationResult:
    """Validate a plan for structural correctness.

    Checks:
    - No duplicate step ids
    - All dependencies reference existing steps
    - No cycles in dependency graph
    - At least one step has no dependencies (entry point)
    """
    errors: list[str] = []
    warnings: list[str] = []
    ids = plan.step_ids()

    if not plan.plan_id.strip():
        errors.append("plan id must not be empty")
    if type(plan.version) is not int or plan.version < 1:
        errors.append("plan version must be a positive integer")
    if len(ids) != len(plan.steps):
        errors.append("duplicate step ids found")

    # Dangling references
    for step in plan.steps:
        if not step.id.strip() or not step.tool.strip():
            errors.append("step id and tool name must not be empty")
        if len(step.depends_on) != len(set(step.depends_on)):
            errors.append(f"step {step.id}: duplicate dependencies found")
        if (
            type(step.timeout_s) not in (int, float)
            or not math.isfinite(step.timeout_s)
            or step.timeout_s <= 0
        ):
            errors.append(f"step {step.id}: timeout must be positive")
        if (
            type(step.budget) not in (int, float)
            or not math.isfinite(step.budget)
            or step.budget < 0
        ):
            errors.append(f"step {step.id}: budget must be non-negative")
        for dep in step.depends_on:
            if dep not in ids:
                errors.append(f"step {step.id}: dangling dependency '{dep}'")

    # Plan-level budget validation
    if (
        type(plan.max_budget) not in (int, float)
        or not math.isfinite(plan.max_budget)
        or plan.max_budget < 0
    ):
        errors.append("plan max_budget must be a non-negative finite number")
    elif plan.max_budget > 0 and plan.total_step_budget() > plan.max_budget:
        errors.append(
            f"plan step budgets ({plan.total_step_budget():.2f}) "
            f"exceed max_budget ({plan.max_budget:.2f})"
        )

    # Cycle detection via Kahn's algorithm
    in_degree: dict[str, int] = {s.id: 0 for s in plan.steps}
    adjacency: dict[str, list[str]] = {s.id: [] for s in plan.steps}
    for step in plan.steps:
        for dep in step.depends_on:
            if dep in adjacency:
                adjacency[dep].append(step.id)
                in_degree[step.id] += 1

    queue = [sid for sid, d in in_degree.items() if d == 0]
    visited = 0
    while queue:
        node = queue.pop(0)
        visited += 1
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(plan.steps):
        errors.append("dependency graph contains a cycle")

    if not any(not s.depends_on for s in plan.steps):
        warnings.append("no entry point (all steps have dependencies)")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def check_step_types(plan: Plan) -> list[str]:
    """Validate that step input types match dependency output types.

    Returns a list of type mismatch errors. Empty list means all types match.
    """
    errors: list[str] = []
    step_map = {step.id: step for step in plan.steps}

    for step in plan.steps:
        if not step.input_types:
            continue
        for input_name, expected_type in step.input_types.items():
            provider_type: str | None = None
            for dep_id in step.depends_on:
                dep_step = step_map.get(dep_id)
                if dep_step and input_name in dep_step.output_types:
                    provider_type = dep_step.output_types[input_name]
                    break
            if provider_type is None:
                errors.append(
                    f"step {step.id}: input '{input_name}' has no provider in dependencies"
                )
            elif provider_type != expected_type:
                errors.append(
                    f"step {step.id}: input '{input_name}' expects {expected_type}, "
                    f"but dependency provides {provider_type}"
                )
    return errors


def topological_order(plan: Plan) -> list[str]:
    """Return steps in a valid topological execution order.

    Uses Kahn's algorithm; within a level, steps are sorted by id for
    determinism.
    """
    in_degree: dict[str, int] = {s.id: len(s.depends_on) for s in plan.steps}
    adjacency: dict[str, list[str]] = {s.id: [] for s in plan.steps}
    for step in plan.steps:
        for dep in step.depends_on:
            if dep in adjacency:
                adjacency[dep].append(step.id)

    # Use sorted queue for determinism
    queue = sorted([sid for sid, d in in_degree.items() if d == 0])
    order: list[str] = []
    while queue:
        queue.sort()
        node = queue.pop(0)
        order.append(node)
        new_ready: list[str] = []
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                new_ready.append(neighbor)
        queue.extend(new_ready)

    # If cycle, return what we can
    return order


def plan_diff(a: Plan, b: Plan) -> dict[str, list[str]]:
    """Compute the difference between two plans.

    Returns {'added': [...], 'removed': [...], 'modified': [...]}.
    """
    a_ids = a.step_ids()
    b_ids = b.step_ids()
    added = sorted(b_ids - a_ids)
    removed = sorted(a_ids - b_ids)
    modified: list[str] = []
    for sid in a_ids & b_ids:
        sa = a.get_step(sid)
        sb = b.get_step(sid)
        if sa is not None and sb is not None and sa.to_dict() != sb.to_dict():
            modified.append(sid)
    return {"added": sorted(added), "removed": sorted(removed), "modified": sorted(modified)}
