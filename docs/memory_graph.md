# Memory Graph Architecture

The memory graph is the core data structure in famulix, representing personal
knowledge as a typed directed graph with provenance tracking.

## Node Types

Memory nodes represent different kinds of personal information:

- **episode**: A time-bounded session or day segment containing events
- **entity**: A person, place, or thing mentioned in events
- **fact**: A discrete piece of knowledge extracted from events
- **preference**: A learned user preference or style choice
- **goal**: A stated objective or intention
- **reminder**: A time-sensitive action item

Each node has:
- `node_id`: Content-addressed deterministic identifier
- `kind`: One of the node types above
- `title`: Short human-readable label
- `body`: Full content text
- `metadata`: Arbitrary key-value pairs (confidence, source_event, etc.)
- `created_at_s`: Unix timestamp of creation
- `is_active`: Whether the node is current (vs superseded/deleted)

## Edge Types

Edges represent relationships between nodes:

- **mentions**: Episode mentions an entity
- **part_of**: Fact/reminder belongs to an episode
- **derived_from**: Node was extracted from an event
- **supersedes**: Newer fact replaces an older contradictory fact
- **contradicts**: Two facts have incompatible values

## Structural Invariants

The graph maintains these invariants:

1. **No dangling edges**: Every edge's source and target must reference existing nodes
2. **Acyclic provenance**: The `derived_from` and `supersedes` chains form a DAG
3. **Single active version**: For each fact key, at most one node is active
4. **Deterministic IDs**: Same input produces the same node_id

## Graph Operations

### Encoding Pipeline

The `encode_events_to_graph()` function converts raw events into graph nodes:

```python
from famulix.encoding import encode_events_to_graph
from famulix.factory import generate_history

events, _ = generate_history(persona_id="alex", seed=42, days=30)
graph = encode_events_to_graph(events)
```

This produces:
- One episode node per day
- Entity nodes for detected mentions
- Fact nodes for extracted knowledge candidates

### Consolidation

The `consolidate_graph()` function merges duplicates and resolves contradictions:

```python
from famulix.consolidation import consolidate_graph

report = consolidate_graph(graph)
print(f"Merged {len(report.merged_pairs)} near-duplicates")
print(f"Resolved {report.contradictions_resolved} contradictions")
```

Consolidation is idempotent - running it twice produces no additional changes.

### Retrieval

The retrieval layer builds a BM25 index over active nodes and combines it with
recency and salience scores:

```python
from famulix.retrieval import BM25Index, hybrid_score

idx = BM25Index()
for node in graph.all_nodes():
    if node.is_active:
        idx.add_node(node)

results = hybrid_score("meeting with Riley", graph=graph, index=idx, now_s=1000000)
for r in results[:5]:
    print(f"{r.score:.3f} {r.citation}")
```

## Serialization

Graphs can be serialized to JSON for persistence:

```python
data = graph.to_dict()
import json
json_str = json.dumps(data)

# Reload
loaded_data = json.loads(json_str)
loaded_graph = MemoryGraph.from_dict(loaded_data)
```

## Provenance and Audit

Every fact node tracks its source event via `metadata["source_event"]`. This
enables:
- Tracing knowledge back to raw evidence
- Deleting derived facts when source events are removed
- Auditing what the system knows and why

## Deletion Semantics

The `delete_memory()` function cascades deletion across the graph:

```python
from famulix.deletion import delete_memory

delete_memory(graph, target_node_id)
```

This:
1. Marks the target node as inactive
2. Removes all edges to/from the node
3. Prevents re-derivation from surviving events (tombstone)

Deleted nodes remain in the graph as inactive tombstones to maintain the audit
trail and prevent resurrection through re-encoding.
