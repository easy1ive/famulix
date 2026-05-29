# Tools and Execution

famulix provides a declarative tool system with JSON-schema arguments,
capability tags, side-effect classification, and a policy-gated executor.

## Tool Definitions

Tools are declared with schema, capabilities, and side-effect class:

```python
from famulix.tools import Tool, ToolRegistry

registry = ToolRegistry()
registry.register(Tool(
    name="recall",
    description="Search memory graph for relevant facts",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "k": {"type": "integer", "default": 10},
        },
        "required": ["query"],
    },
    capabilities={"read", "retrieval"},
    side_effects="none",  # none, local, external
))
```

### Side-Effect Classification

- **none**: Pure function, no state changes (e.g., recall, compute)
- **local**: Modifies local state (e.g., remember, forget)
- **external**: Interacts with external systems (e.g., send_email)

### Capability Tags

Tools declare capabilities for policy enforcement:
- `read`: Reads data
- `write`: Modifies data
- `export`: Exports data outside
- `retrieval`: Memory retrieval
- `communication`: Sends messages

## Tool Validation

`validate_tool_call()` checks arguments against the schema:

```python
from famulix.tools import validate_tool_call

problems = validate_tool_call(
    tool=registry.get("recall"),
    arguments={"query": "meeting with Riley"},
)
if problems:
    print(f"Invalid: {problems}")
```

Validation checks:
- Required parameters present
- Types match schema
- Values within constraints

## Execution

The `Executor` runs tools with policy gating and receipts:

```python
from famulix.executor import Executor, ExecutorConfig

executor = Executor(
    registry=registry,
    config=ExecutorConfig(
        timeout_s=5.0,
        max_retries=2,
        require_approval_for={"external"},
    ),
)

receipt = executor.execute(
    tool_name="recall",
    arguments={"query": "meeting with Riley", "k": 5},
    policy_engine=policy_engine,
)

print(f"Success: {receipt.success}")
print(f"Result: {receipt.result}")
print(f"Duration: {receipt.duration_s:.3f}s")
```

### Idempotency Keys

Side-effecting tools require idempotency keys:

```python
receipt = executor.execute(
    tool_name="send_email",
    arguments={"to": "user@example.com", "body": "Hello"},
    idempotency_key="unique-request-id-123",
    policy_engine=policy_engine,
)
```

Duplicate calls with the same key return the cached receipt.

### Timeouts and Retries

The executor enforces timeouts and retries with jitter:

```python
config = ExecutorConfig(
    timeout_s=10.0,
    max_retries=3,
    retry_jitter_s=0.5,
)
```

On timeout, the executor raises `ToolTimeoutError`. On retryable failure, it
retries up to `max_retries` times with exponential backoff + jitter.

### Policy Gating

Before execution, the executor checks the policy engine:

```python
decision, rule_id = policy_engine.evaluate(
    action="execute",
    resource=tool_name,
    tier=tier,
)
if decision == "deny":
    raise PolicyDeniedError(f"Policy {rule_id} denied execution")
```

## Execution History

Every execution is recorded in the `ExecutionLog`:

```python
from famulix.executor import ExecutionLog

log = ExecutionLog()
log.append(receipt)

# Query history
recent = log.recent(n=10)
failed = [r for r in log.entries if not r.success]
```

## Receipt Format

Execution receipts include:
- `tool_name`: Which tool was called
- `arguments`: What arguments were passed
- `success`: Whether execution succeeded
- `result`: Return value (if successful)
- `error`: Error message (if failed)
- `duration_s`: Execution time
- `retries`: Number of retries attempted
- `idempotency_key`: Key for side-effecting tools

## CLI Usage

```bash
# List available tools
famulix tools list

# Execute a tool
famulix tools exec recall --query "meeting" --k 5
```
