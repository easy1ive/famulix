"""Tests for plan DSL: validation, topological order, diff."""

from __future__ import annotations

from famulix.plan_dsl import (
    Plan,
    PlanStep,
    plan_diff,
    topological_order,
    validate_plan,
)


def test_empty_plan_valid() -> None:
    plan = Plan(plan_id="p1")
    result = validate_plan(plan)
    assert result.valid


def test_single_step_valid() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[PlanStep(id="s1", tool="echo", inputs={"text": "hi"})],
    )
    result = validate_plan(plan)
    assert result.valid
    assert result.errors == []


def test_dangling_dependency_invalid() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}, depends_on=["s99"]),
        ],
    )
    result = validate_plan(plan)
    assert not result.valid
    assert any("dangling" in e for e in result.errors)


def test_cycle_detected() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}, depends_on=["s2"]),
            PlanStep(id="s2", tool="echo", inputs={"text": "b"}, depends_on=["s1"]),
        ],
    )
    result = validate_plan(plan)
    assert not result.valid
    assert any("cycle" in e for e in result.errors)


def test_linear_chain_valid() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}),
            PlanStep(id="s2", tool="echo", inputs={"text": "b"}, depends_on=["s1"]),
            PlanStep(id="s3", tool="echo", inputs={"text": "c"}, depends_on=["s2"]),
        ],
    )
    result = validate_plan(plan)
    assert result.valid


def test_topological_order_linear() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s3", tool="echo", inputs={}, depends_on=["s2"]),
            PlanStep(id="s1", tool="echo", inputs={}),
            PlanStep(id="s2", tool="echo", inputs={}, depends_on=["s1"]),
        ],
    )
    order = topological_order(plan)
    assert order.index("s1") < order.index("s2") < order.index("s3")


def test_topological_order_deterministic() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="z", tool="echo", inputs={}),
            PlanStep(id="a", tool="echo", inputs={}),
            PlanStep(id="m", tool="echo", inputs={}),
        ],
    )
    order1 = topological_order(plan)
    order2 = topological_order(plan)
    assert order1 == order2
    # Entry points sorted alphabetically
    assert order1 == ["a", "m", "z"]


def test_topological_order_with_cycle_partial() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={}, depends_on=["s2"]),
            PlanStep(id="s2", tool="echo", inputs={}, depends_on=["s1"]),
            PlanStep(id="s3", tool="echo", inputs={}),
        ],
    )
    order = topological_order(plan)
    # s3 has no deps and should be in the order
    assert "s3" in order


def test_duplicate_step_ids_invalid() -> None:
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}),
            PlanStep(id="s1", tool="echo", inputs={"text": "b"}),
        ],
    )
    result = validate_plan(plan)
    assert not result.valid
    assert any("duplicate" in e for e in result.errors)


def test_plan_diff_added_removed_modified() -> None:
    a = Plan(
        plan_id="p",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}),
            PlanStep(id="s2", tool="echo", inputs={"text": "b"}),
        ],
    )
    b = Plan(
        plan_id="p",
        steps=[
            PlanStep(id="s1", tool="echo", inputs={"text": "a-modified"}),
            PlanStep(id="s3", tool="echo", inputs={"text": "c"}),
        ],
    )
    diff = plan_diff(a, b)
    assert "s3" in diff["added"]
    assert "s2" in diff["removed"]
    assert "s1" in diff["modified"]


def test_plan_diff_identical() -> None:
    a = Plan(
        plan_id="p",
        steps=[PlanStep(id="s1", tool="echo", inputs={"x": 1})],
    )
    b = Plan(
        plan_id="p",
        steps=[PlanStep(id="s1", tool="echo", inputs={"x": 1})],
    )
    diff = plan_diff(a, b)
    assert diff["added"] == []
    assert diff["removed"] == []
    assert diff["modified"] == []


def test_plan_to_dict() -> None:
    plan = Plan(plan_id="test", steps=[PlanStep(id="s1", tool="echo", inputs={"t": "x"})])
    d = plan.to_dict()
    assert d["plan_id"] == "test"
    assert len(d["steps"]) == 1
    assert d["steps"][0]["id"] == "s1"


def test_plan_get_step() -> None:
    plan = Plan(
        plan_id="p",
        steps=[PlanStep(id="s1", tool="echo"), PlanStep(id="s2", tool="add")],
    )
    assert plan.get_step("s1").tool == "echo"
    assert plan.get_step("missing") is None


def test_plan_json_roundtrip_has_versioned_golden_shape() -> None:
    plan = Plan(plan_id="daily", steps=[PlanStep(id="read", tool="echo", inputs={"text": "hi"})])
    payload = plan.to_json()
    expected = (
        '{"metadata":{},"plan_id":"daily","schema_version":1,'
        '"steps":[{"budget":0.0,"depends_on":[],"effects":[],"id":"read",'
        '"inputs":{"text":"hi"},"preconditions":[],"timeout_s":5.0,"tool":"echo"}],'
        '"version":1}'
    )
    assert payload == expected
    assert Plan.from_json(payload).to_json() == payload
