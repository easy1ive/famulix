# CLI Reference

famulix provides a comprehensive CLI for all framework operations.

## Global Options

```bash
famulix --help          # Show help
famulix --version       # Show version
```

## Core Commands

### demo

Run a full seeded persona day offline:

```bash
famulix demo
famulix demo --persona alex --seed 42 --days 14
```

Generates synthetic history, builds memory graph, consolidates, retrieves,
assembles context, and produces a briefing with evaluation scores.

### eval

Run evaluation on a synthetic persona:

```bash
famulix eval --persona alex --seed 42 --days 30
famulix eval --persona blair --seed 99 --days 90 --json
```

Returns recall@k, precision@k, contradiction accuracy, citation coverage,
preference Brier score, privacy violations, deletion resurrection count,
and replay determinism.

### recall

Search memory graph for a query:

```bash
famulix recall "meeting with Riley"
famulix recall "project deadline" --persona alex --seed 42 --k 20
famulix recall "favorite color" --json
```

### brief

Generate a daily briefing:

```bash
famulix brief --date 2026-03-15
famulix brief --persona alex --seed 42 --output briefing.html
famulix brief --format markdown
```

### context

Assemble budgeted context for a query:

```bash
famulix context "meeting agenda" --budget 500
famulix context "commitments" --json
```

### prefs

View learned preferences:

```bash
famulix prefs
famulix prefs --persona alex --seed 42 --json
```

## Memory Operations

### remember

Add a fact to memory:

```bash
famulix remember "Favorite color is blue"
famulix remember "Meeting with Riley at 3pm" --tier internal
```

### forget

Remove a memory by id:

```bash
famulix forget mem_abc123
famulix forget mem_def456 --reason "User requested deletion"
```

### ingest

Ingest events from JSONL:

```bash
famulix ingest events.jsonl
famulix ingest events.jsonl --persona alex
```

### export

Export memory graph:

```bash
famulix export --format json > graph.json
famulix export --format jsonl > events.jsonl
```

## Reports

### prefs-report

Generate preference profile report:

```bash
famulix prefs-report
famulix prefs-report --persona alex --seed 42 --output prefs.md
```

### exec-report

Generate plan execution report:

```bash
famulix exec-report
famulix exec-report --output exec.md
```

## Session Management

### replay

Replay a session from log:

```bash
famulix replay session.jsonl
famulix replay session.jsonl --verbose
```

### validate-session

Validate session file integrity:

```bash
famulix validate-session session.jsonl
```

### diff

Diff two sessions:

```bash
famulix diff session_a.jsonl session_b.jsonl
```

## Triggers and Privacy

### triggers

List proactive triggers:

```bash
famulix triggers
famulix triggers --persona alex --seed 42
```

### privacy

Run privacy audit:

```bash
famulix privacy
famulix privacy --tier sensitive --json
```

## Exit Codes

- `0`: Success
- `1`: General error
- `2`: Invalid arguments
- `3`: Policy denied
- `4`: Timeout
- `5`: Budget exceeded

## Examples

See the `examples/` directory for complete runnable examples:
- `01_recall_benchmark.py`: Recall benchmark
- `02_contradiction_week.py`: Contradiction resolution
- `03_preference_loop.py`: Preference learning
- `04_persona_day.py`: Full persona day
- `06_plan_tools_demo.py`: Plan execution
- `07_session_replay.py`: Session replay
- `08_memory_graph_demo.py`: Memory graph operations
- `09_reporting_demo.py`: Report generation
