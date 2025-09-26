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
    from famulix.tools import ToolRegistry, ToolSpec

    def fail_handler() -> None:
        raise RuntimeError("scripted failure")

    registry = ToolRegistry()
    registry.register(
        ToolSpec(name="fail", description="fail", parameters={"type": "object"}), fail_handler
    )
    state = execute_plan(Plan(plan_id="test", steps=[PlanStep(id="bad", tool="fail")]), registry)
    assert state.history[0].success is False
    assert state.history[0].error == "scripted failure"
    assert execution_summary(state)["failures"] == 1


def test_executor_passes_only_explicit_capability_grants_to_tools() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="mail",
            description="read mail",
            parameters={"type": "object"},
            capability_tags=frozenset({"mail.read"}),
        ),
        lambda: "ok",
    )
    plan = Plan(plan_id="capability", steps=[PlanStep(id="read", tool="mail")])
    denied = execute_plan(plan, registry)
    allowed = execute_plan(plan, registry, granted_capabilities={"mail.read"})
    assert denied.steps_done == 0
    assert "missing capabilities" in (denied.termination_reason or "")
    assert allowed.history[0].success is True


def test_failed_tool_stops_plan_before_following_actions() -> None:
    from famulix.tools import ToolSpec

    def fail_handler() -> None:
        raise RuntimeError("scripted failure")

    registry = build_default_registry()
    registry.register(
        ToolSpec(name="fail", description="fail", parameters={"type": "object"}), fail_handler
    )
    plan = Plan(
        plan_id="stop-on-error",
        steps=[
            PlanStep(id="bad", tool="fail"),
            PlanStep(id="later", tool="echo", inputs={"text": "must not run"}, depends_on=["bad"]),
        ],
    )
    state = execute_plan(plan, registry)
    assert state.terminated
    assert state.termination_reason == "tool failed: bad"
    assert [item.step_id for item in state.history] == ["bad"]


def test_execution_preconditions_consume_prior_step_effects() -> None:
    plan = Plan(
        plan_id="facts",
        steps=[
            PlanStep(id="load", tool="echo", inputs={"text": "mail"}, effects=["mail_loaded"]),
            PlanStep(
                id="summarize",
                tool="echo",
                inputs={"text": "ready"},
                depends_on=["load"],
                preconditions=["mail_loaded"],
                effects=["summary_ready"],
            ),
        ],
    )
    state = execute_plan(plan, build_default_registry())
    assert not state.terminated
    assert state.facts == {"mail_loaded", "summary_ready"}
    assert state.outputs["summarize"] == "ready"


def test_unsatisfied_precondition_prevents_action() -> None:
    plan = Plan(
        plan_id="missing-fact",
        steps=[
            PlanStep(id="send", tool="echo", inputs={"text": "send"}, preconditions=["approved"])
        ],
    )
    state = execute_plan(plan, build_default_registry())
    assert state.terminated and state.steps_done == 1
    assert state.history[0].success is False
    assert "approved" in (state.termination_reason or "")


def test_plan_preflights_every_tool_before_running_the_first() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    calls: list[str] = []
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="record",
            description="record",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        ),
        lambda value: calls.append(value),
    )
    plan = Plan(
        plan_id="preflight",
        steps=[
            PlanStep(id="first", tool="record", inputs={"value": "no"}),
            PlanStep(id="second", tool="record", inputs={}, depends_on=["first"]),
        ],
    )
    state = execute_plan(plan, registry)
    assert state.terminated and state.steps_done == 0
    assert "preflight failed for second" in (state.termination_reason or "")
    assert calls == []


def test_execution_budgets_reject_invalid_limits() -> None:
    import pytest

    with pytest.raises(ValueError, match="max_steps"):
        ExecutionBudget(max_steps=-1)
    with pytest.raises(ValueError, match="max_tokens"):
        ExecutionBudget(max_tokens=1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_money"):
        ExecutionBudget(max_money=float("nan"))


def test_money_budget_is_reserved_before_running_a_tool() -> None:
    plan = Plan(plan_id="money", steps=[PlanStep(id="one", tool="echo", inputs={"text": "x"})])
    state = execute_plan(plan, build_default_registry(), budget=ExecutionBudget(max_money=0.005))
    assert state.terminated and state.steps_done == 0
    assert state.termination_reason == "budget exceeded"
    assert state.money_spent == 0.0


def test_execution_state_snapshot_is_canonical() -> None:
    plan = Plan(plan_id="snapshot", steps=[PlanStep(id="s", tool="echo", inputs={"text": "ok"})])
    state = execute_plan(plan, build_default_registry())
    assert state.to_json() == state.to_json()
    assert state.to_dict()["schema_version"] == 1


def test_execution_state_roundtrip_restores_receipts_and_facts() -> None:
    plan = Plan(
        plan_id="restore",
        steps=[PlanStep(id="s", tool="echo", inputs={"text": "ok"}, effects=["ready"])],
    )
    state = execute_plan(plan, build_default_registry())
    restored = type(state).from_json(state.to_json())
    assert restored.to_json() == state.to_json()
    assert restored.facts == {"ready"}


def test_execution_state_decoder_rejects_unknown_fields() -> None:
    import pytest

    from famulix.executor import ExecutionState

    with pytest.raises(ValueError, match="malformed"):
        ExecutionState.from_dict({"schema_version": 1, "extra": True})


def test_declared_step_cost_is_reflected_in_money_usage() -> None:
    plan = Plan(
        plan_id="cost", steps=[PlanStep(id="s", tool="echo", inputs={"text": "ok"}, budget=2.5)]
    )
    state = execute_plan(plan, build_default_registry(), budget=ExecutionBudget(max_money=3))
    assert not state.terminated
    assert state.money_spent == 2.5


def test_dependency_failure_is_recorded_before_dependent_action() -> None:
    from famulix.tools import ToolRegistry, ToolSpec

    calls: list[str] = []
    registry = ToolRegistry()

    def fail() -> None:
        raise RuntimeError("no")

    registry.register(
        ToolSpec(name="fail", description="fail", parameters={"type": "object"}), fail
    )
    registry.register(
        ToolSpec(name="record", description="record", parameters={"type": "object"}),
        lambda: calls.append("ran"),
    )
    plan = Plan(
        plan_id="deps",
        steps=[
            PlanStep(id="bad", tool="fail"),
            PlanStep(id="later", tool="record", depends_on=["bad"]),
        ],
    )
    state = execute_plan(plan, registry)
    assert [item.step_id for item in state.history] == ["bad"]
    assert calls == []


def test_execution_state_status_summary() -> None:
    from famulix.executor import ExecutionState, StepExecution

    state = ExecutionState()
    state.history.append(StepExecution(step_id="a", success=True))
    state.history.append(StepExecution(step_id="b", success=False, error="failed"))
    state.history.append(StepExecution(step_id="c", success=True))
    assert state.step_count() == 3
    assert state.success_count() == 2
    assert state.failure_count() == 1
    summary = state.status_summary()
    assert summary["total"] == 3
    assert summary["success"] == 2
    assert summary["failed"] == 1


def test_execution_state_json_rejects_non_object_payload() -> None:
    import pytest

    from famulix.executor import ExecutionState

    with pytest.raises(ValueError, match="object"):
        ExecutionState.from_json("[]")


def test_steps_run_in_dependency_order_not_declaration_order() -> None:
    """Topological order must win over the order steps were declared in."""
    plan = Plan(
        plan_id="reordered",
        steps=[
            PlanStep(id="second", tool="echo", inputs={"text": "b"}, depends_on=["first"]),
            PlanStep(id="first", tool="echo", inputs={"text": "a"}),
        ],
    )
    state = execute_plan(plan, build_default_registry())
    assert not state.terminated
    assert [item.step_id for item in state.history] == ["first", "second"]


def test_execution_state_initializes_with_defaults() -> None:
    from famulix.executor import ExecutionState

    state = ExecutionState()
    assert state.steps_done == 0
    assert state.tokens_used == 0
    assert state.money_spent == 0.0
    assert not state.terminated


def test_execution_budget_tracks_consumption() -> None:
    from famulix.executor import ExecutionBudget

    budget = ExecutionBudget()
    assert budget.max_steps > 0
    assert budget.max_tokens > 0
    assert budget.max_money > 0.0


def test_step_execution_records_result() -> None:
    from famulix.executor import StepExecution

    step = StepExecution(step_id="s1", success=True)
    assert step.step_id == "s1"
    assert step.success is True


def test_execution_summary_formats_state() -> None:
    from famulix.executor import ExecutionState, execution_summary

    state = ExecutionState()
    state.steps_done = 3
    state.money_spent = 5.5
    summary = execution_summary(state)
    assert isinstance(summary, dict)
    assert "steps_done" in summary or "step_count" in summary
