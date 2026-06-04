# Salience Scoring

Salience scoring determines memory importance based on multiple features,
with both a transparent NumPy baseline and an optional PyTorch MLP demo.

## Importance Features

The salience scorer combines multiple signals:

```python
from famulix.salience import compute_salience

score = compute_salience(node, graph=graph, now_s=1000000)
```

### Feature Components

1. **Frequency**: How often the fact is mentioned
2. **Recency**: How recently the fact was created/accessed
3. **Commitment**: Language indicating promises or obligations
4. **Goal linkage**: Connection to stated goals
5. **Explicit pinning**: User-marked importance

### NumPy Scorer

The baseline scorer uses transparent NumPy operations:

```python
from famulix.salience import SalienceScorer

scorer = SalienceScorer(
    frequency_weight=0.2,
    recency_weight=0.3,
    commitment_weight=0.2,
    goal_weight=0.2,
    pin_weight=0.1,
)

score = scorer.score(node, graph=graph, now_s=1000000)
```

All weights are configurable and sum to 1.0.

## Slice Diagnostics

`salience_diagnostics()` breaks down scores by feature:

```python
from famulix.salience import salience_diagnostics

diag = salience_diagnostics(node, graph=graph, now_s=1000000)
print(f"Frequency: {diag['frequency']:.3f}")
print(f"Recency: {diag['recency']:.3f}")
print(f"Commitment: {diag['commitment']:.3f}")
print(f"Goal: {diag['goal']:.3f}")
print(f"Pin: {diag['pin']:.3f}")
print(f"Total: {diag['total']:.3f}")
```

## PyTorch MLP Demo

An optional MLP demonstrates trainable salience scoring:

```python
from famulix.salience_torch import RankFusionMLP, TorchRankFusionConfig

config = TorchRankFusionConfig(
    input_dim=3,
    hidden_dim=16,
    seed=42,
)
model = RankFusionMLP(config)

# Train on synthetic preference pairs
losses = model.train_on_pairs(winners, losers)
print(f"Final loss: {losses[-1]:.4f}")

# Score feature rows
scores = model.score_rows(feature_rows)
```

### Honest Comparison

The MLP is compared against the NumPy baseline:

```python
numpy_scores = [scorer.score(n, graph, now_s) for n in nodes]
torch_scores = model.score_rows(feature_rows)

# Compare rankings
correlation = rank_correlation(numpy_scores, torch_scores)
print(f"Rank correlation: {correlation:.3f}")
```

### Training Requirements

The MLP demo:
- Uses only synthetic data (no pretrained weights)
- Shows real loss decrease with deterministic seeds
- Is marked `@pytest.mark.model` and `@pytest.mark.slow`
- Skips cleanly when PyTorch is not installed

### Loss Curve

Training uses pairwise margin-ranking loss:

```
loss = max(0, margin - (winner_score - loser_score))
```

The model learns to rank preferred items higher.

## Salience in Retrieval

Salience is one component of hybrid retrieval:

```python
from famulix.retrieval import hybrid_score, FusionConfig

config = FusionConfig(
    bm25_weight=0.5,
    recency_weight=0.3,
    salience_weight=0.2,  # Salience component
)

results = hybrid_score(query, graph=graph, index=idx, now_s=now_s, config=config)
```

Higher salience → higher retrieval rank (all else equal).

## Decay Interaction

Salience interacts with decay:

```python
# Initial salience
score_t0 = compute_salience(node, graph, now_s=t0)

# After decay
score_t1 = compute_salience(node, graph, now_s=t1)
# score_t1 < score_t0 (unless pinned)
```

Pinned memories maintain high salience regardless of age.

## CLI Usage

```bash
# View salience scores for all facts
famulix salience --persona alex --seed 42

# View diagnostics for a specific node
famulix salience diagnostics mem_abc123
```
