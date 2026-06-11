"""Test plan DAG validation."""

from famulix.plan_dsl import Plan, PlanStep
from famulix.plan_validate import validate_plan_dag


def test_validate_plan_dag_accepts_valid():
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="fetch", depends_on=[]),
            PlanStep(id="s2", tool="process", depends_on=["s1"]),
            PlanStep(id="s3", tool="save", depends_on=["s2"]),
        ],
    )

    errors = validate_plan_dag(plan)
    assert len(errors) == 0


def test_validate_plan_dag_detects_cycle():
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="fetch", depends_on=["s2"]),
            PlanStep(id="s2", tool="process", depends_on=["s1"]),
        ],
    )

    errors = validate_plan_dag(plan)
    assert len(errors) > 0
    assert any("cycle" in e.lower() for e in errors)


def test_validate_plan_dag_detects_missing_dep():
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="fetch", depends_on=["s_missing"]),
        ],
    )

    errors = validate_plan_dag(plan)
    assert len(errors) > 0
    assert any("unknown" in e.lower() for e in errors)


def test_validate_plan_dag_detects_self_dep():
    plan = Plan(
        plan_id="p1",
        steps=[
            PlanStep(id="s1", tool="fetch", depends_on=["s1"]),
        ],
    )

    errors = validate_plan_dag(plan)
    assert len(errors) > 0
    assert any("itself" in e.lower() for e in errors)
