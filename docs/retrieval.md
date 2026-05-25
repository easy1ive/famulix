# Retrieval and Context Assembly

famulix provides hybrid retrieval combining BM25 text matching with recency and
salience scoring, followed by diversity-aware reranking and budgeted context
assembly.

## BM25 Index

The `BM25Index` implements the Okapi BM25 ranking function:

```python
from famulix.retrieval import BM25Index

idx = BM25Index(k1=1.5, b=0.75)
idx.add("node1", "meeting with Riley about project Horizon")
idx.add("node2", "coffee at 3pm with Alex")

scores = idx.score("meeting project")
# {"node1": 1.234}
```

### Persistence

Save and reload indexes:

```python
idx.save("index.json")
loaded = BM25Index.load("index.json")
```

### Stale Detection

Detect when the index is out of sync with the graph:

```python
live_ids = {n.node_id for n in graph.all_nodes() if n.is_active}
stale = idx.stale_ids(live_ids)
if stale:
    idx.prune_stale(live_ids)
```

## Hybrid Scoring

`hybrid_score()` combines three signals:

1. **BM25**: Text relevance via term frequency
2. **Recency**: Exponential decay from now
3. **Salience**: Node importance (degree + content length)

```python
from famulix.retrieval import hybrid_score, FusionConfig

config = FusionConfig(
    bm25_weight=0.5,
    recency_weight=0.3,
    salience_weight=0.2,
)

results = hybrid_score(
    "meeting with Riley",
    graph=graph,
    index=idx,
    now_s=1000000,
    config=config,
)
```

Each result includes:
- `node_id`: The matched memory
- `score`: Fused score
- `citation`: Human-readable reference
- `metadata`: Component scores (bm25, recency, salience)

## MMR Diversification

Maximal Marginal Relevance (MMR) reduces redundancy in results:

```python
from famulix.retrieval import mmr_rerank

diverse = mmr_rerank(results, lambda_param=0.7, top_k=10)
```

Higher `lambda_param` favors relevance; lower favors diversity.

## Context Assembly

`assemble_context()` selects the highest-value items within a token budget using
exact dynamic programming (0/1 knapsack):

```python
from famulix.context import ContextItem, assemble_context, estimate_tokens

items = [
    ContextItem(
        item_id=r.node_id,
        token_estimate=estimate_tokens(r.citation),
        value=r.score,
        payload=r.citation,
    )
    for r in results[:50]
]

ctx = assemble_context(items, budget=500, use_dp=True)
print(f"Selected {len(ctx.items)} items, {ctx.total_tokens} tokens")
assert ctx.total_tokens <= 500
```

### DP vs Greedy

- `use_dp=True`: Exact optimal solution via dynamic programming
- `use_dp=False`: Greedy approximation (faster, may miss optimum)

For small item sets (<1000), DP is fast enough and guarantees optimality.

## Token Estimation

`estimate_tokens()` provides a rough token count:

```python
from famulix.context import estimate_tokens

text = "Meeting with Riley at 3pm to discuss project Horizon"
tokens = estimate_tokens(text)  # ~12 tokens
```

This is a heuristic (≈4 chars per token) suitable for budget enforcement, not
exact billing.

## Citation Integrity

Every retrieval result includes a citation that resolves to an existing, active
memory node. The evaluation harness verifies this invariant:

```python
for result in results:
    node = graph.get_node(result.node_id)
    assert node is not None
    assert node.is_active
```

Deleted or superseded nodes never appear in retrieval results.
