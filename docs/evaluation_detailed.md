# Evaluation Harness

The evaluation harness measures the mechanical correctness of famulix's memory
and personalization pipelines against synthetic ground truth.

## Design Philosophy

The harness evaluates **mechanics**, not conversational ability. Every metric
comes from synthetic data with planted ground truth:

- **recall@k**: Fraction of planted facts found in top-k retrieval results
- **precision@k**: Fraction of top-k results that are planted facts
- **contradiction accuracy**: Fraction of contradictions correctly resolved
- **citation coverage**: Fraction of briefing items with valid memory citations
- **preference Brier score**: Calibration of learned preferences vs planted signals
- **privacy violations**: Count of PII leaks (must be zero)
- **deletion resurrection**: Count of deleted memories that reappear (must be zero)
- **replay determinism**: Byte-equality of two runs with same seed

## Running the Evaluation

### CLI

```bash
famulix eval --persona alex --seed 42 --days 30
```

### Python API

```python
from famulix.evaluation import run_full_evaluation

scorecard = run_full_evaluation(
    persona_id="alex",
    seed=42,
    days=30,
    start_date="2026-01-01",
    budget_tokens=500,
)

print(f"Recall@5: {scorecard.recall_at_k['@5']:.3f}")
print(f"Contradiction accuracy: {scorecard.contradiction_accuracy:.3f}")
print(f"Citation coverage: {scorecard.citation_coverage:.3f}")
```

## Synthetic Factory

The `generate_history_with_truth()` function creates a seeded persona history
with known ground truth:

```python
from famulix.factory import generate_history_with_truth

events, manifest, truth = generate_history_with_truth(
    persona_id="alex",
    seed=42,
    days=90,
    start_date="2026-01-01",
)

# truth contains:
# - fact_ids: list of event_ids for planted facts
# - contradiction_pairs: list of (old_id, new_id) tuples
# - preference_signals: list of feedback events
```

### Planted Facts

The factory plants facts at known positions in the history:

- "Lives at 123 Oak Street, Apt 4B"
- "Phone ends with 5678"
- "Favorite color is navy blue"
- "Always orders oat milk latte"
- etc.

These facts are encoded into the memory graph and should be retrievable.

### Planted Contradictions

The factory generates pairs of conflicting facts:

- Old: "Lives at 123 Oak Street"
- New: "Lives at 456 Pine Avenue"

The consolidation pipeline should resolve these by keeping the newer fact and
marking the older one as superseded.

### Planted Preferences

The factory generates feedback signals:

- Explicit ratings (up/down)
- Implicit signals (accept/decline/edit)

The preference learning pipeline should calibrate to these signals.

## Evaluation Metrics

### Recall and Precision

For each planted fact, the harness queries using the fact's title and checks if
it appears in the top-k results:

```python
recall, precision = eval_recall_precision(
    graph=graph,
    planted_fact_ids=truth["fact_ids"],
    now_s=events[-1].timestamp_s + 3600,
)
```

- **recall@k**: For each planted fact, is it in the top-k? Average over all facts.
- **precision@k**: For each planted fact query, what fraction of top-k are correct?

### Contradiction Resolution

For each contradiction pair (old_id, new_id), the newer fact should be active
and the older should be superseded:

```python
accuracy = eval_contradiction_resolution(
    graph=graph,
    contradiction_pairs=truth["contradiction_pairs"],
)
```

### Citation Coverage

Every briefing item should cite at least one memory node:

```python
coverage = eval_citation_coverage(
    briefing_items=briefing.items,
    planted_fact_ids=truth["fact_ids"],
)
```

### Preference Calibration

The Brier score measures how well learned preferences match planted signals:

```python
brier = eval_preference_calibration(
    profile=profile,
    preference_signals=truth["preference_signals"],
    now_s=events[-1].timestamp_s + 3600,
)
```

Lower Brier score = better calibration (0.0 = perfect, 1.0 = worst).

## Interpreting Results

### Good Scores

- **recall@5 ≥ 0.8**: Most planted facts are retrievable
- **contradiction accuracy ≥ 0.9**: Most contradictions resolved correctly
- **citation coverage = 1.0**: All briefing items have citations
- **privacy violations = 0**: No PII leaks
- **deletion resurrection = 0**: Deleted memories stay deleted
- **replay deterministic = True**: Same seed produces identical output

### What Scores Mean

These scores describe **mechanical correctness** on synthetic data. They do NOT
measure:
- Conversational quality
- Real-world accuracy
- User satisfaction
- LLM capability

A perfect score means the pipelines work as designed on the synthetic factory's
output. It says nothing about performance on real personal data or with real
language models.

## Determinism

The evaluation is fully deterministic:

- Same seed → identical events
- Same events → identical graph
- Same graph → identical scores

This enables regression testing and CI validation.
