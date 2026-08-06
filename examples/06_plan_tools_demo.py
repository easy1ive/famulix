#!/usr/bin/env python3
"""Example 06: Plan DSL and tools demonstration.

Demonstrates plan creation, validation, and topological ordering using
the Plan DSL, plus tool registration and capability inspection.
"""

from famulix.plan_dsl import Plan, PlanStep, topological_order, validate_plan
from famulix.tools import build_default_registry


def main() -> None:
    """Run plan and tools demonstration."""
    print("=== Plan DSL and Tools Demo ===\n")

    # Build a plan using the dataclass constructors
    plan = Plan(
        plan_id="morning_routine",
        version=1,
        steps=[
            PlanStep(
                id="check_calendar",
                tool="calendar_lookup",
                inputs={"date": "today"},
                output_types={"events": "list"},
            ),
            PlanStep(
                id="check_weather",
                tool="weather_lookup",
                inputs={"location": "home"},
                output_types={"forecast": "string"},
            ),
            PlanStep(
                id="summarize",
                tool="text_summary",
                inputs={"text": "$check_calendar.events"},
                depends_on=["check_calendar", "check_weather"],
                output_types={"summary": "string"},
            ),
        ],
        metadata={"persona": "alex", "trigger": "morning_briefing"},
    )

    print("Plan created:")
    print(f"  ID: {plan.plan_id}")
    print(f"  Steps: {plan.step_count()}")
    print(f"  Tools: {plan.tools_used()}")

    # Validate plan structure
    result = validate_plan(plan)
    if result.errors:
        print(f"\nValidation errors: {result.errors}")
    else:
        print("\nPlan validation: PASSED")
        if result.warnings:
            print(f"  Warnings: {result.warnings}")

    # Compute topological execution order
    order = topological_order(plan)
    print(f"\nExecution order: {order}")

    # Show tool registry with built-in deterministic tools
    registry = build_default_registry()
    print(f"\nRegistered tools: {registry.tool_count()}")
    for spec in registry.list_specs():
        print(f"  {spec.name}: {spec.description}")

    # Roundtrip: serialize and decode back
    payload = plan.to_dict()
    decoded = Plan.from_dict(payload)
    print(f"\nRoundtrip: plan_id={decoded.plan_id}, steps={decoded.step_count()}")
    print(f"  Digest match: {plan.to_dict() == decoded.to_dict()}")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
