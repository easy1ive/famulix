# Consolidation Pipeline

The consolidation pipeline maintains memory quality by merging near-duplicates,
resolving contradictions, and generating episode summaries.

## Overview

```python
from famulix.consolidation import consolidate_graph

report = consolidate_graph(graph)
print(f"Merged {len(report.merged_pairs)} pairs")
print(f"Resolved {report.contradictions_resolved} contradictions")
```

The pipeline has three stages:
1. **Dedup**: Merge near-duplicate fact nodes (similarity ≥ 0.85)
2. **Contradictions**: Detect and resolve conflicting facts
3. **Summaries**: Generate episode summaries (optional)

## Near-Duplicate Detection

`find_near_duplicates()` identifies fact nodes with similar content:

```python
from famulix.consolidation import find_near_duplicates

pairs = find_near_duplicates(graph, kind="fact", threshold=0.85)
for a, b, score in pairs:
    print(f"{a.title} ≈ {b.title} (score={score:.2f})")
```

Similarity is computed via Jaccard overlap of tokenized content. When two nodes
are merged, the newer one survives and the older is marked inactive.

## Contradiction Resolution

`find_contradictions()` detects fact nodes with the same key but different values:

```python
from famulix.consolidation import find_contradictions

pairs = find_contradictions(graph)
for a, b in pairs:
    print(f"{a.title}: '{a.body}' vs '{b.body}'")
```

The supersede policy resolves contradictions deterministically:

1. **Newest-verified wins**: The fact with the later timestamp survives
2. **Trust tie-breaking**: If timestamps are equal, higher trust wins
3. **ID tie-breaking**: If trust is also equal, lexicographic node_id wins

The loser is marked inactive and a `supersedes` edge is added:

```
winner --supersedes--> loser
winner --contradicts--> loser
```

## Idempotency

Consolidation is idempotent: running it twice produces no additional changes.

```python
report1 = consolidate_graph(graph)
report2 = consolidate_graph(graph)
assert report2.total_changes() == 0
```

This is achieved by looping until no more contradictions are found, and by
checking `is_active` before processing each pair.

## Consolidation Report

The `ConsolidationReport` tracks all changes:

```python
from famulix.consolidation import ConsolidationReport

report = ConsolidationReport(
    merged_pairs=[("winner_id", "loser_id")],
    superseded=["old_fact_id"],
    contradictions_resolved=1,
    summary_nodes=["summary_id"],
)

print(report.total_changes())  # 3
print(report.is_empty)  # False
```

### Serialization

Reports can be serialized to dict/JSON:

```python
data = report.to_dict()
import json
json_str = json.dumps(data)
```

### Markdown Rendering

Reports render to human-readable Markdown:

```python
md = report.to_markdown()
print(md)
```

## Episode Summaries

`summarize_episodes()` generates summary nodes for day-long episodes:

```python
from famulix.consolidation import summarize_episodes

episodes = [n for n in graph.all_nodes() if n.kind == "episode"]
summary = summarize_episodes(graph, episodes)
if summary:
    print(f"Summary: {summary.body}")
```

Summaries use a template with placeholders for count and topics.

## Structural Invariants

After consolidation:
- No dangling edges (all edge endpoints reference existing nodes)
- Acyclic provenance (supersedes chains form a DAG)
- Single active version per fact key
- Superseded nodes remain as inactive tombstones

## Performance

Consolidation is O(n²) in the number of fact nodes due to pairwise comparison.
For large graphs (>10k facts), consider:
- Filtering to recent facts only
- Using locality-sensitive hashing for approximate dedup
- Running consolidation incrementally on new events
