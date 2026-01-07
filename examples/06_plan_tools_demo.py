#!/usr/bin/env python3
"""Example 06: Plan DSL and tools demonstration.

Demonstrates plan creation, validation, and execution with tools.
"""

from famulix.plan_dsl import validate_plan
from famulix.tools import ToolRegistry


def main() -> None:
    """Run plan and tools demonstration."""
    print("=== Plan DSL and Tools Demo ===\n")

    # Create a simple plan
    plan_data = {
        "version": 1,
        "name": "morning_routine",
        "steps": [
            {
                "name": "check_calendar",
                "tool": "calendar_lookup",
                "inputs": {"date": "today"},
                "outputs": {"events": "list"},
            },
            {
                "name": "summarize",
                "tool": "text_summary",
                "inputs": {"text": "$check_calendar.events"},
                "outputs": {"summary": "string"},
            },
        ],
    }

    print("Plan created:")
    print(f"  Name: {plan_data['name']}")
    print(f"  Steps: {len(plan_data['steps'])}")

    # Validate plan
    errors = validate_plan(plan_data)
    if errors:
        print(f"\nValidation errors: {errors}")
    else:
        print("\nPlan validation: PASSED")

    # Show tool registry
    registry = ToolRegistry()
    print(f"\nRegistered tools: {len(registry._tools)}")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
