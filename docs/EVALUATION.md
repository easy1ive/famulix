# Evaluation Harness

famulix includes a memory-focused evaluation harness that scores end-to-end persona scenarios against planted ground truth. All metrics come from synthetic data with deterministic seeds — no real LLM, real user data, or external benchmarks are involved.

## Metrics

The evaluation harness computes:

- **Recall@k and Precision@k**: For planted facts in the synthetic history
- **Contradiction resolution accuracy**: Whether newer facts correctly supersede older ones
- **Citation coverage**: Fraction of briefing items that cite their source memories
- **Budget adherence**: Whether context assembly respects token budgets
- **Preference calibration (Brier score)**: How well preference predictions match outcomes
- **Privacy violations**: Count of PII leaks across privacy tiers (must be zero)
- **Deletion resurrection violations**: Count of deleted memories reappearing (must be zero)
- **Replay determinism**: Whether double-run produces byte-identical traces

## Usage

### Running a Full Evaluation

```python
from famulix.evaluation import run_full_evaluation

scorecard = run_full_evaluation(
    persona_id="alex",
    seed=42,
    days=90,
    budget=500,
)

print(scorecard.summary())
```

### Per-Metric Evaluation

```python
from famulix.evaluation import (
    eval_recall_precision,
    eval_contradiction_resolution,
    eval_citation_coverage,
    eval_budget_adherence,
)

# Recall and precision at multiple k values
recall, precision = eval_recall_precision(
    graph,
    planted_fact_ids={"fact_1", "fact_2"},
    now_s=1000,
    k_values=[1, 5, 10, 20],
)

print(f"Recall@10: {recall['@10']:.3f}")
print(f"Precision@10: {precision['@10']:.3f}")
```

### Generating a Report

```python
from famulix.evaluation import format_evaluation_report

scorecard_dict = scorecard.to_dict()
report = format_evaluation_report(scorecard_dict, include_details=True)

# Save to file
with open("evaluation_report.md", "w") as f:
    f.write(report)
```

## Scorecard Structure

The `EvalScorecard` dataclass holds:

- `persona_id`, `seed`, `days`: Evaluation parameters
- `recall_at_k`, `precision_at_k`: Dicts mapping k values to scores
- `contradiction_accuracy`: Fraction of contradictions correctly resolved
- `citation_coverage`: Fraction of briefing items with citations
- `budget_adherence`: Boolean indicating budget compliance
- `privacy_violations`: Count of PII leaks
- `deletion_resurrection_count`: Count of deleted memories reappearing
- `replay_deterministic`: Boolean indicating replay equality
- `preference_brier_score`: Calibration error for preferences
- `slices`: Per-slice breakdowns (e.g., by fact type, time window)

## Invariants

- **Honesty**: All metrics computed on synthetic data with planted ground truth
- **No real LLM**: Results reflect framework mechanics, not conversational ability
- **Determinism**: Same seed + config → identical scores
- **Privacy**: Violation counters must be zero for any passing evaluation
- **Deletion**: Resurrection violations must be zero

## CLI

Run evaluation via CLI:

```bash
famulix eval --persona alex --seed 42 --days 90 --budget 500
famulix eval --persona alex --seed 42 --days 90 --json
```

The `demo` subcommand runs a full seeded persona day with evaluation:

```bash
famulix demo --persona alex --seed 42 --days 14
```

## Limitations

The evaluation harness measures **framework mechanics** — encoding, consolidation, retrieval, context assembly, preference calibration, privacy enforcement, and deletion semantics — not the conversational ability of any real LLM. All scores come from synthetic data with planted ground truth and deterministic seeds.
