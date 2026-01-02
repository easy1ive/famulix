# Evaluation Guide

Famulix includes a comprehensive evaluation harness for measuring memory mechanics on synthetic data.

## Running Evaluations

```bash
# Basic evaluation
famulix eval --persona alex --days 90

# With custom seed
famulix eval --persona alex --seed 42 --days 30

# JSON output
famulix eval --persona alex --json
```

## Metrics

### Recall and Precision

- **Recall@k**: Fraction of planted facts retrieved in top-k results
- **Precision@k**: Fraction of top-k results that are planted facts

### Contradiction Resolution

- **Accuracy**: Fraction of contradictions resolved correctly
- **Supersede policy**: Newest-verified wins, ties broken by source trust then ID

### Citation Coverage

- **Coverage**: Fraction of briefing items with valid citations (must be 100%)
- **Resolution**: Every citation must point to a live, non-deleted memory

### Preference Calibration

- **Brier score**: Mean squared error of preference predictions
- **Reliability bins**: Calibration across confidence levels

### Budget Adherence

- **Token count**: Must not exceed specified budget
- **Assembly**: Knapsack DP returns optimum within budget

### Privacy and Deletion

- **Violations**: Count of privacy tier leaks (must be 0)
- **Resurrection**: Count of deleted memories reappearing (must be 0)

## Synthetic Ground Truth

All evaluations use planted ground truth:

- **Planted facts**: Known facts with specific content
- **Planted contradictions**: Conflicting facts with known resolution
- **Planted preferences**: Preference signals with known calibration
- **Planted PII**: Personal information for privacy testing

## Determinism

Same seed produces identical evaluation results. Verified by double-run tests.

## Offline Operation

No network calls, no external APIs, no pretrained models. Everything runs locally.
