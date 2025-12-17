# Example 01: Recall Benchmark

Demonstrates hybrid retrieval with measured recall@k on synthetic data.

## What This Does

1. Generates a 30-day synthetic persona history with planted facts
2. Builds a memory graph with encoding and consolidation
3. Runs retrieval queries against planted ground truth
4. Measures recall@k and precision@k
5. Reports per-slice and aggregate scorecards

## Running

```bash
python examples/01_recall_benchmark.py
```

## Expected Output

- Recall@5, Recall@10 metrics for planted facts
- Precision@k measurements
- Per-slice breakdown by fact type
- Aggregate scorecard

## Key Concepts

- **Hybrid scoring**: BM25 + recency + salience fusion
- **MMR diversification**: Maximal Marginal Relevance reranking
- **Planted ground truth**: Synthetic facts with known answers
- **Citation tracking**: Every result cites its source memory

## Offline Operation

No network calls, no external APIs, no pretrained models. Everything runs locally with deterministic seeds.
