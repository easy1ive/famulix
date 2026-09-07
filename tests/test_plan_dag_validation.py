"""Tests for plan DAG validation: cycles, dangling refs, and topological order."""

from famulix.plan_dsl import Plan, PlanStep, topological_order, validate_plan


def _make_plan(steps: list[PlanStep]) -> Plan:
    return Plan(plan_id="test-plan", version=1, steps=steps)


def test_valid_linear_plan():
    plan = _make_plan(
        [
            PlanStep(id="s1", tool="echo", inputs={"text": "a"}),
            PlanStep(id="s2", tool="echo", inputs={"text": "b"}, depends_on=["s1"]),
            PlanStep(id="s3", tool="echo", inputs={"text": "c"}, depends_on=["s2"]),
        ]
    )
    result = validate_plan(plan)
    assert not result.errors


def test_valid_diamond_plan():
    plan = _make_plan(
        [
            PlanStep(id="s1", tool="echo", inputs={}),
            PlanStep(id="s2", tool="echo", inputs={}, depends_on=["s1"]),
            PlanStep(id="s3", tool="echo", inputs={}, depends_on=["s1"]),
            PlanStep(id="s4", tool="echo", inputs={}, depends_on=["s2", "s3"]),
        ]
    )
    result = validate_plan(plan)
    assert not result.errors


def test_cycle_detected():
    plan = _make_plan(
        [
            PlanStep(id="s1", tool="echo", inputs={}, depends_on=["s2"]),
            PlanStep(id="s2", tool="echo", inputs={}, depends_on=["s1"]),
        ]
    )
    result = validate_plan(plan)
    assert any("cycle" in e.lower() for e in result.errors)


def test_dangling_dependency_detected():
    plan = _make_plan(
        [
            PlanStep(id="s1", tool="echo", inputs={}, depends_on=["nonexistent"]),
        ]
    )
    result = validate_plan(plan)
    assert any(
        "dangling" in e.lower() or "reference" in e.lower() or "not found" in e.lower()
        for e in result.errors
    )


def test_duplicate_step_ids_detected():
    plan = _make_plan(
        [
            PlanStep(id="s1", tool="echo", inputs={}),
            PlanStep(id="s1", tool="echo", inputs={}),
        ]
    )
    result = validate_plan(plan)
    assert any("duplicate" in e.lower() for e in result.errors)


def test_topological_order_linear():
    plan = _make_plan(
        [
            PlanStep(id="s1", tool="echo", inputs={}),
            PlanStep(id="s2", tool="echo", inputs={}, depends_on=["s1"]),
        ]
    )
    order = topological_order(plan)
    assert order.index("s1") < order.index("s2")


def test_topological_order_independent_steps():
    plan = _make_plan(
        [
            PlanStep(id="a", tool="echo", inputs={}),
            PlanStep(id="b", tool="echo", inputs={}),
            PlanStep(id="c", tool="echo", inputs={}),
        ]
    )
    order = topological_order(plan)
    assert set(order) == {"a", "b", "c"}
