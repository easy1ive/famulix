"""Tests for plan executor."""

from __future__ import annotations

from famulix.executor import (
    ExecutionBudget,
    execute_plan,
    execution_summary,
)
from famulix.plan_dsl import Plan, PlanStep
from famulix.tools import build_default_registry


def test_execute_valid_plan() -> None:
    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "hello"}),
            PlanStep(id="s2", tool="add", inputs={"a": 2, "b": 3}, depends_on=["s1"]),
        ],
    )
    reg = build_default_registry()
    state = execute_plan(plan, reg)
    assert not state.terminated
    assert state.steps_done == 2
    assert len(state.history) == 2
    assert state.history[0].success
    assert state.history[1].success


def test_execute_invalid_plan_terminates() -> None:
    plan = Plan(
        plan_id="bad",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={}, depends_on=["s99"]),
        ],
    )
    reg = build_default_registry()
    state = execute_plan(plan, reg)
    assert state.terminated
    assert "invalid" in (state.termination_reason or "")
    assert state.steps_done == 0


def test_step_budget_enforced() -> None:
    # Create a plan with more steps than budget allows
    steps = [PlanStep(id=f"s{i}", tool="echo", inputs={"text": str(i)}) for i in range(10)]
    plan = Plan(plan_id="many", steps=steps)
    reg = build_default_registry()
    budget = ExecutionBudget(max_steps=3, max_tokens=10000, max_money=100)
    state = execute_plan(plan, reg, budget=budget)
    assert state.terminated
    assert state.steps_done == 3
    assert state.termination_reason == "budget exceeded"


def test_execution_summary() -> None:
    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "hi"}),
            PlanStep(id="s2", tool="add", inputs={"a": 1, "b": 2}),
        ],
    )
    reg = build_default_registry()
    state = execute_plan(plan, reg)
    summary = execution_summary(state)
    assert summary["steps_done"] == 2
    assert summary["successes"] == 2
    assert summary["failures"] == 0
    assert summary["terminated"] is False
    assert summary["tokens_used"] >= 0
    assert summary["money_spent"] > 0


def test_execution_deterministic() -> None:
    plan = Plan(
        plan_id="test",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "abc"}),
            PlanStep(id="s2", tool="add", inputs={"a": 1.5, "b": 2.5}),
        ],
    )
    reg = build_default_registry()
    s1 = execute_plan(plan, reg, seed=42)
    s2 = execute_plan(plan, reg, seed=42)
    assert s1.steps_done == s2.steps_done
    assert s1.outputs == s2.outputs
    assert [h.success for h in s1.history] == [h.success for h in s2.history]


def test_execution_outputs_stored() -> None:
    plan = Plan(
        plan_id="test",
        steps=[PlanStep(id="s1", tool="echo", inputs={"text": "output_value"})],
    )
    reg = build_default_registry()
    state = execute_plan(plan, reg)
    assert "s1" in state.outputs
    assert state.outputs["s1"] == "output_value"


def test_failed_step_in_history() -> None:
    plan = Plan(
        plan_id="test",
        steps=[PlanStep(id="bad", tool="echo", inputs={})],  # missing required
    )
    reg = build_default_registry()
    state = execute_plan(plan, reg)
    assert state.history[0].success is False
    assert state.history[0].error is not None
    summary = execution_summary(state)
    assert summary["failures"] == 1
