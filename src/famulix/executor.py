"""Plan executor: perceive→plan→act→observe loop with budgets.

Executes a validated plan step-by-step, tracking tokens, steps, and a
synthetic 'money' budget. Supports approval escalation and terminating
scenarios for property testing.
"""

from __future__ import annotations

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

    def within_budget(self, budget: ExecutionBudget) -> bool:
        return (
            self.steps_done < budget.max_steps
            and self.tokens_used < budget.max_tokens
            and self.money_spent < budget.max_money
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

        # Money cost: 0.01 per step by default
        state.money_spent += 0.01
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
