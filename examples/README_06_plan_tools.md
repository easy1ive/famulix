# Example 06: Plan DSL and Tools

Demonstrates plan creation, validation, and execution with tools.

## What This Does

1. Creates a multi-step plan
2. Validates plan structure and dependencies
3. Shows tool registry
4. Demonstrates plan execution semantics

## Running

```bash
python examples/06_plan_tools_demo.py
```

## Expected Output

- Plan summary (name, step count)
- Validation result (passed/failed with errors)
- Tool registry count

## Key Concepts

- **Plan DSL**: Versioned JSON schema for steps
- **Validation**: DAG checks, type validation, budget enforcement
- **Tools**: Declarative specs with JSON-schema arguments
- **Execution**: Policy-gated with approval escalation

## Offline Operation

No network calls, no external APIs, no pretrained models.
