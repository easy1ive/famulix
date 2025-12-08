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

from famulix.plan_dsl import Plan, PlanStep, topological_order, validate_plan
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

    def step_count(self) -> int:
        return len(self.history)

    def success_count(self) -> int:
        return sum(1 for item in self.history if item.success)

    def failure_count(self) -> int:
        return sum(1 for item in self.history if not item.success)

    def status_summary(self) -> dict[str, int]:
        return {
            "total": self.step_count(),
            "success": self.success_count(),
            "failed": self.failure_count(),
        }

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

    for candidate in plan.steps:
        errors = registry.preflight(
            candidate.tool,
            candidate.inputs,
            idempotency_key=candidate.id,
            granted_capabilities=granted_capabilities,
        )
        if errors:
            state.terminated = True
            state.termination_reason = (
                f"tool preflight failed for {candidate.id}: {'; '.join(errors)}"
            )
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

        step: PlanStep | None = step_map.get(step_id)
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


def execution_diagnostics(state: ExecutionState) -> dict[str, Any]:
    """Generate detailed diagnostics for an execution run.

    Returns a dict with:
    - summary: basic execution summary
    - step_details: per-step success/failure/timing
    - budget_usage: budget consumption breakdown
    - failure_details: detailed failure information
    """
    summary = execution_summary(state)

    step_details: list[dict[str, Any]] = []
    for step_result in state.history:
        step_details.append(
            {
                "step_id": step_result.step_id,
                "success": step_result.success,
                "error": step_result.error,
            }
        )

    budget_usage = {
        "steps_executed": state.steps_done,
        "tokens_used": state.tokens_used,
        "money_spent": round(state.money_spent, 6),
    }

    failure_details: list[dict[str, Any]] = []
    for step_result in state.history:
        if not step_result.success:
            failure_details.append(
                {
                    "step_id": step_result.step_id,
                    "error": step_result.error,
                }
            )

    return {
        "summary": summary,
        "step_details": step_details,
        "budget_usage": budget_usage,
        "failure_details": failure_details,
    }


def budget_monitoring_report(
    state: ExecutionState,
    budget: ExecutionBudget,
) -> dict[str, Any]:
    """Generate a budget monitoring report comparing usage to limits.

    Returns a dict with:
    - step_usage: steps used vs limit
    - token_usage: tokens used vs limit
    - money_usage: money spent vs limit
    - within_all_budgets: whether all budgets are satisfied
    - warnings: list of budget warnings
    """
    warnings: list[str] = []

    step_pct = (state.steps_done / budget.max_steps * 100) if budget.max_steps > 0 else 0
    token_pct = (state.tokens_used / budget.max_tokens * 100) if budget.max_tokens > 0 else 0
    money_pct = (state.money_spent / budget.max_money * 100) if budget.max_money > 0 else 0

    if step_pct >= 90:
        warnings.append(f"Step budget {step_pct:.1f}% consumed")
    if token_pct >= 90:
        warnings.append(f"Token budget {token_pct:.1f}% consumed")
    if money_pct >= 90:
        warnings.append(f"Money budget {money_pct:.1f}% consumed")

    return {
        "step_usage": {
            "used": state.steps_done,
            "limit": budget.max_steps,
            "percent": round(step_pct, 2),
        },
        "token_usage": {
            "used": state.tokens_used,
            "limit": budget.max_tokens,
            "percent": round(token_pct, 2),
        },
        "money_usage": {
            "used": round(state.money_spent, 6),
            "limit": budget.max_money,
            "percent": round(money_pct, 2),
        },
        "within_all_budgets": state.within_budget(budget),
        "warnings": warnings,
    }
