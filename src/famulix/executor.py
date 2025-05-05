"""Plan executor: perceive→plan→act→observe loop with budgets.

Executes a validated plan step-by-step, tracking tokens, steps, and a
synthetic 'money' budget. Supports approval escalation and terminating
scenarios for property testing.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

from famulix.plan_dsl import Plan, topological_order, validate_plan
from famulix.tools import ToolRegistry, ToolResult


@dataclass
class ExecutionBudget:
    """Budget constraints for an execution run."""

    max_steps: int = 100
    max_tokens: int = 4096
    max_money: float = 100.0

    def __post_init__(self) -> None:
        if type(self.max_steps) is not int or self.max_steps < 0:
            raise ValueError("max_steps must be a non-negative integer")
        if type(self.max_tokens) is not int or self.max_tokens < 0:
            raise ValueError("max_tokens must be a non-negative integer")
        if not math.isfinite(self.max_money) or self.max_money < 0:
            raise ValueError("max_money must be finite and non-negative")


@dataclass
class StepExecution:
    """Record of a single step execution."""

    step_id: str
    success: bool
    result: ToolResult | None = None
    error: str | None = None


@dataclass
class ExecutionState:
    """Mutable state during plan execution."""

    steps_done: int = 0
    tokens_used: int = 0
    money_spent: float = 0.0
    outputs: dict[str, Any] = field(default_factory=dict)
    history: list[StepExecution] = field(default_factory=list)
    facts: set[str] = field(default_factory=set)
    terminated: bool = False
    termination_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize an execution state without callable registry data."""
        return {
            "schema_version": 1,
            "steps_done": self.steps_done,
            "tokens_used": self.tokens_used,
            "money_spent": round(self.money_spent, 6),
            "outputs": self.outputs,
            "history": [
                {
                    "step_id": item.step_id,
                    "success": item.success,
                    "result": item.result.to_dict() if item.result else None,
                    "error": item.error,
                }
                for item in self.history
            ],
            "facts": sorted(self.facts),
            "terminated": self.terminated,
            "termination_reason": self.termination_reason,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionState:
        """Decode a strict execution snapshot."""
        required = {
            "schema_version",
            "steps_done",
            "tokens_used",
            "money_spent",
            "outputs",
            "history",
            "facts",
            "terminated",
            "termination_reason",
        }
        if set(data) != required or data.get("schema_version") != 1:
            raise ValueError("unsupported or malformed execution state")
        if type(data["steps_done"]) is not int or type(data["tokens_used"]) is not int:
            raise ValueError("execution counters must be integers")
        if (
            type(data["terminated"]) is not bool
            or not isinstance(data["outputs"], dict)
            or not isinstance(data["facts"], list)
        ):
            raise ValueError("invalid execution state fields")
        history: list[StepExecution] = []
        for raw in data["history"]:
            if not isinstance(raw, dict) or set(raw) != {"step_id", "success", "result", "error"}:
                raise ValueError("malformed execution history")
            result = ToolResult.from_dict(raw["result"]) if raw["result"] is not None else None
            history.append(StepExecution(raw["step_id"], raw["success"], result, raw["error"]))
        return cls(
            steps_done=data["steps_done"],
            tokens_used=data["tokens_used"],
            money_spent=float(data["money_spent"]),
            outputs=dict(data["outputs"]),
            history=history,
            facts=set(data["facts"]),
            terminated=data["terminated"],
            termination_reason=data["termination_reason"],
        )

    @classmethod
    def from_json(cls, payload: str) -> ExecutionState:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid execution state JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("execution state JSON must contain an object")
        return cls.from_dict(data)

    def within_budget(self, budget: ExecutionBudget) -> bool:
        return (
            self.steps_done < budget.max_steps
            and self.tokens_used < budget.max_tokens
            and self.money_spent + 0.01 <= budget.max_money
        )


def execute_plan(
    plan: Plan,
    registry: ToolRegistry,
    *,
    budget: ExecutionBudget | None = None,
    seed: int = 0,
    granted_capabilities: set[str] | None = None,
    initial_facts: set[str] | None = None,
) -> ExecutionState:
    """Execute a validated plan step by step.

    Returns the final execution state. If the plan is invalid, returns
    immediately with a termination reason.
    """
    state = ExecutionState(facts=set(initial_facts or set()))
    budget = budget or ExecutionBudget()

    # Validate first
    validation = validate_plan(plan)
    if not validation.valid:
        state.terminated = True
        state.termination_reason = f"invalid plan: {'; '.join(validation.errors)}"
        return state

    for step in plan.steps:
        errors = registry.preflight(
            step.tool,
            step.inputs,
            idempotency_key=step.id,
            granted_capabilities=granted_capabilities,
        )
        if errors:
            state.terminated = True
            state.termination_reason = f"tool preflight failed for {step.id}: {'; '.join(errors)}"
            return state

    # Get execution order
    order = topological_order(plan)
    step_map = {s.id: s for s in plan.steps}

    for step_id in order:
        if state.terminated:
            break
        if not state.within_budget(budget):
            state.terminated = True
            state.termination_reason = "budget exceeded"
            break

        step = step_map.get(step_id)
        if step is None:
            continue

        missing_dependencies = [
            dependency
            for dependency in step.depends_on
            if not any(item.step_id == dependency and item.success for item in state.history)
        ]
        if missing_dependencies:
            message = "failed dependencies: " + ", ".join(sorted(missing_dependencies))
            state.history.append(StepExecution(step_id=step.id, success=False, error=message))
            state.steps_done += 1
            state.terminated = True
            state.termination_reason = message
            break

        missing_facts = sorted(set(step.preconditions) - state.facts)
        if missing_facts:
            message = "unsatisfied preconditions: " + ", ".join(missing_facts)
            state.history.append(StepExecution(step_id=step.id, success=False, error=message))
            state.steps_done += 1
            state.terminated = True
            state.termination_reason = message
            break

        # Execute the step
        result = registry.execute(
            step.tool,
            step.inputs,
            idempotency_key=step.id,
            seed=seed,
            granted_capabilities=granted_capabilities,
        )

        step_exec = StepExecution(
            step_id=step.id,
            success=result.success,
            result=result,
            error=result.error,
        )
        state.history.append(step_exec)
        state.steps_done += 1

        # Rough token cost: length of output string / 4
        if result.success:
            state.facts.update(step.effects)
            if result.output is not None:
                state.tokens_used += len(str(result.output)) // 4
                state.outputs[step.id] = result.output

        # Declared step budgets are synthetic money costs.
        state.money_spent = round(state.money_spent + max(step.budget, 0.01), 6)
        if not result.success:
            state.terminated = True
            state.termination_reason = f"tool failed: {step.id}"
            break

    if not state.terminated:
        # Normal completion — mark as done (not terminated early)
        pass

    return state


def execution_summary(state: ExecutionState) -> dict[str, Any]:
    """Generate a summary dict of an execution run."""
    successes = sum(1 for s in state.history if s.success)
    failures = sum(1 for s in state.history if not s.success)
    return {
        "steps_done": state.steps_done,
        "successes": successes,
        "failures": failures,
        "tokens_used": state.tokens_used,
        "money_spent": round(state.money_spent, 6),
        "terminated": state.terminated,
        "termination_reason": state.termination_reason,
    }
