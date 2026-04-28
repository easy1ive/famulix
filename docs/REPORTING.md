# Reporting Capabilities

famulix provides human-readable reporting for evaluation, preferences, execution, privacy, and consolidation. All reports include honest limitations sections that are automatically generated from the evaluation context.

## Evaluation Reports

Generate comprehensive evaluation reports with per-slice breakdowns:

```python
from famulix.evaluation import format_evaluation_report, run_full_evaluation

scorecard = run_full_evaluation(persona_id="alex", seed=42, days=90, budget=500)
report = format_evaluation_report(scorecard.to_dict(), include_details=True)

with open("evaluation_report.md", "w") as f:
    f.write(report)
```

Or via CLI:

```bash
famulix eval --persona alex --seed 42 --days 90
```

### Report contents

- Overall metrics (recall@k, precision@k, contradiction resolution, citation coverage)
- Per-slice breakdowns by fact type, time window, or other dimensions
- Budget adherence and privacy violation counters
- Automatically generated limitations section

## Preference Profile Reports

Generate preference profile reports with confidence levels and decay information:

```python
from famulix.preferences import PreferenceProfile

profile = PreferenceProfile()
# ... add feedback entries ...
report = profile.generate_report(now_s=1000)

print(report)
```

Or via CLI:

```bash
famulix prefs-report --persona alex --seed 42 --days 30
```

### Report contents

- Profile version and entry counts
- Current preferences with confidence levels
- Decay half-life information
- Per-key breakdowns with entry counts

## Execution Reports

Generate plan execution reports with step details and budget usage:

```python
from famulix.executor import ExecutionState, format_execution_report

state = ExecutionState()
# ... execute plan steps ...
report = format_execution_report(state)

print(report)
```

Or via CLI:

```bash
famulix exec-report
```

### Report contents

- Execution summary (steps completed, successes, failures)
- Token and money usage
- Per-step details with success/failure status
- Termination reasons (if applicable)

## Consolidation Reports

Generate consolidation reports with memory citations:

```python
from famulix.consolidation import format_consolidation_report

# After running consolidation
report = format_consolidation_report(consolidation_report, graph)

print(report)
```

### Report contents

- Merged near-duplicates with winner citations
- Superseded memories with reasons
- Summary nodes created
- Contradiction resolution counts

## Privacy Audit Reports

Generate privacy audit reports with PII detection statistics:

```python
from famulix.privacy import generate_privacy_audit_report

texts = ["Contact me at alice@example.com", "My phone is +86 138 1234 5678"]
report = generate_privacy_audit_report(texts, redaction_mode="reversible")

print(f"Texts with PII: {report['texts_with_pii']}")
print(f"PII types found: {report['pii_types_found']}")
```

### Report contents

- Total texts processed
- Texts containing PII
- PII types detected with counts
- Redacted text versions

## Tool Catalogs

Generate tool catalogs from registries:

```python
from famulix.tools import ToolRegistry

registry = ToolRegistry()
# ... register tools ...
catalog = registry.generate_catalog()

print(catalog)
```

### Catalog contents

- Tool names and descriptions
- Parameter specifications with types and requirements
- Side effect classifications
- Capability tags and timeout settings

## Connector Health Reports

Generate connector health reports:

```python
from famulix.connectors import ConnectorHub

hub = ConnectorHub([calendar_connector, notes_connector])
report = hub.health_report()

print(f"Healthy: {report['healthy_sources']}")
print(f"Failed: {report['failed_sources']}")
```

### Report contents

- Total, healthy, and failed source counts
- Per-source record counts
- Error messages for failed sources

## Common Features

All reports share these characteristics:

- **Human-readable**: Markdown format with clear structure
- **Deterministic**: Same inputs produce identical reports
- **Honest**: Include limitations and context about synthetic data
- **Citable**: Reference specific memory IDs, step IDs, or other identifiers
- **Reproducible**: Include version numbers and configuration details

## CLI Commands

| Command | Description |
|---------|-------------|
| `famulix eval` | Run evaluation and print scorecard |
| `famulix prefs-report` | Generate preference profile report |
| `famulix exec-report` | Generate plan execution report |
| `famulix validate-session` | Validate session recording integrity |

## Examples

See the [Reporting Demo](../examples/README_09_reporting.md) for a complete example demonstrating multiple report types.
