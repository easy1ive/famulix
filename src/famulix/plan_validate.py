"""Plan DAG validation: cycle detection and dependency checks."""

from __future__ import annotations

from famulix.plan_dsl import Plan


def validate_plan_dag(plan: Plan) -> list[str]:
    """Validate plan step dependencies form a DAG.

    Checks:
    - No cycles in depends_on
    - All depends_on references exist
    - No self-dependencies

    Returns list of validation errors.
    """
    errors = []

    step_ids = plan.step_ids()

    for step in plan.steps:
        if step.id in step.depends_on:
            errors.append(f"Step {step.id} depends on itself")

        for dep in step.depends_on:
            if dep not in step_ids:
                errors.append(f"Step {step.id} depends on unknown step {dep}")

    visited: set[str] = set()
    in_stack: set[str] = set()

    def has_cycle(step_id: str) -> bool:
        if step_id in in_stack:
            return True
        if step_id in visited:
            return False

        visited.add(step_id)
        in_stack.add(step_id)

        step = plan.get_step(step_id)
        if step:
            for dep in step.depends_on:
                if has_cycle(dep):
                    return True

        in_stack.remove(step_id)
        return False

    for step in plan.steps:
        if has_cycle(step.id):
            errors.append(f"Cycle detected involving step {step.id}")
            break

    return errors
