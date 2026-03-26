"""Test plan DAG type checking and validation."""

from famulix.plan_dsl import (
    Plan,
    PlanStep,
    check_budget_escalation,
    validate_step_type_compatibility,
)


def test_plan_type_mismatch_detected():
    """Verify type mismatches between step outputs and inputs are caught."""
    step1 = PlanStep(
        id="s1",
        tool="tool_a",
        output_types={"data": "string"},
    )
    step2 = PlanStep(
        id="s2",
        tool="tool_b",
        depends_on=["s1"],
        inputs={"data": {"from": "s1.data"}},
        input_types={"data": "integer"},  # expects integer, gets string
    )

    plan = Plan(plan_id="p1", steps=[step1, step2])
    errors = validate_step_type_compatibility(plan)

    # Should detect type mismatch
    assert len(errors) > 0, f"expected type mismatch error, got: {errors}"


def test_plan_budget_escalation_check():
    """Verify budget escalation is detected."""
    step1 = PlanStep(id="s1", tool="t1", budget=5.0)
    step2 = PlanStep(id="s2", tool="t2", budget=5.0)
    step3 = PlanStep(id="s3", tool="t3", budget=50.0)  # 5x the average
    plan = Plan(plan_id="p1", steps=[step1, step2, step3], max_budget=100.0)

    problems = check_budget_escalation(plan, max_budget_multiplier=2.0)
    # Should flag the escalation
    assert len(problems) > 0, "should detect budget escalation"


def test_plan_dangling_reference():
    """Verify dangling step references are caught."""
    step1 = PlanStep(id="s1", tool="tool_a", depends_on=["nonexistent"])
    plan = Plan(plan_id="p1", steps=[step1])

    from famulix.plan_dsl import validate_plan

    result = validate_plan(plan)
    # Should have validation errors
    assert not result.valid, f"expected validation to fail, got: {result}"
