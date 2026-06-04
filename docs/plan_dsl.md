# Plan DSL and Execution Loop

famulix provides a declarative plan DSL for multi-step workflows with
dependency tracking, budget enforcement, and approval escalation.

## Plan Structure

A plan consists of steps with typed inputs/outputs and dependencies:

```python
from famulix.plan_dsl import Plan, PlanStep

plan = Plan(
    plan_id="daily-briefing",
    version=1,
    steps=[
        PlanStep(
            id="gather",
            tool="recall",
            inputs={"query": "agenda commitments reminders"},
            depends_on=[],
            timeout_s=5.0,
        ),
        PlanStep(
            id="select",
            tool="context_assembly",
            inputs={"items": "{{gather.results}}"},
            depends_on=["gather"],
            timeout_s=2.0,
        ),
        PlanStep(
            id="compose",
            tool="briefing_compose",
            inputs={"items": "{{select.items}}"},
            depends_on=["select"],
            timeout_s=3.0,
        ),
    ],
    max_budget=0.10,  # $0.10 budget cap
)
```

## Step Fields

Each step has:
- `id`: Unique identifier
- `tool`: Which tool to execute
- `inputs`: Arguments (may reference previous outputs)
- `depends_on`: List of step IDs this step depends on
- `preconditions`: Conditions that must be true before execution
- `effects`: Conditions that become true after execution
- `timeout_s`: Maximum execution time
- `budget`: Cost budget for this step
- `output_types`: Type annotations for outputs
- `input_types`: Type annotations for inputs

## Validation

`validate_plan()` checks structural correctness:

```python
from famulix.plan_dsl import validate_plan

result = validate_plan(plan)
if not result.valid:
    for error in result.errors:
        print(f"Error: {error}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
```

### Checks Performed

- **No cycles**: Dependency graph must be a DAG
- **No dangling refs**: All `depends_on` must reference existing step IDs
- **Type compatibility**: Input types must match output types of dependencies
- **Budget consistency**: Step budgets must sum to ≤ plan budget
- **Timeout bounds**: Timeouts must be positive and finite

## Execution

The `Planner` executes plans topologically:

```python
from famulix.executor import Executor
from famulix.plan_dsl import Planner

planner = Planner(executor=executor)
result = planner.execute(plan, policy_engine=policy_engine)

print(f"Steps executed: {result.steps_completed}")
print(f"Total cost: ${result.total_cost:.4f}")
print(f"Success: {result.success}")
```

### Topological Ordering

Steps are executed in dependency order:
1. Steps with no dependencies execute first
2. Steps with dependencies wait for all dependencies to complete
3. Independent steps may execute in parallel (future work)

### Budget Enforcement

The planner tracks cumulative cost:

```python
for step_result in result.step_results:
    print(f"{step_result.step_id}: ${step_result.cost:.4f}")
    if result.cumulative_cost > plan.max_budget:
        print("Budget exceeded, stopping")
        break
```

### Approval Escalation

Steps requiring approval are queued:

```python
plan = Plan(
    plan_id="sensitive-action",
    steps=[
        PlanStep(
            id="delete",
            tool="delete_memory",
            inputs={"node_id": "mem_123"},
            requires_approval=True,
        ),
    ],
)
```

The planner submits approval requests and waits for decisions.

## Plan Diffing

`plan_diff()` compares two plan versions:

```python
from famulix.plan_dsl import plan_diff

diff = plan_diff(old_plan, new_plan)
print(f"Added steps: {diff['added']}")
print(f"Removed steps: {diff['removed']}")
print(f"Modified steps: {diff['modified']}")
```

## Serialization

Plans serialize to JSON:

```python
import json

data = plan.to_dict()
json_str = json.dumps(data, indent=2)

# Load
loaded_data = json.loads(json_str)
loaded_plan = Plan.from_dict(loaded_data)
```

## Perceive-Plan-Act-Observe Loop

The high-level agent loop:

```python
while not done:
    # Perceive: gather new events
    events = perceive(context)

    # Plan: generate a plan
    plan = generate_plan(events, goals)

    # Act: execute the plan
    result = planner.execute(plan)

    # Observe: check outcomes
    observations = observe(result)

    # Update state
    context.update(observations)
```

### Budget Types

The loop enforces multiple budgets:
- **Step budget**: Max steps per iteration
- **Token budget**: Max tokens per iteration
- **Money budget**: Max cost per iteration
- **Time budget**: Max wall-clock time

### Termination

The loop terminates when:
- Goals are achieved
- Budget is exhausted
- Max iterations reached
- Explicit stop signal

## CLI Usage

```bash
# Validate a plan
famulix plan validate plan.json

# Execute a plan
famulix plan execute plan.json

# Diff two plans
famulix plan diff old_plan.json new_plan.json
```

## Examples

See `examples/06_plan_tools_demo.py` for a complete plan execution example.
