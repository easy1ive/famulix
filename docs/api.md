# API reference

The supported public surface is currently organized by focused modules:

- `famulix.events`: versioned event records and typed event constructors.
- `famulix.eventlog`: SQLite append-only storage and verified replay.
- `famulix.memory_graph`: memory nodes, edges, and graph invariants.
- `famulix.encoding`, `consolidation`, and `decay`: event projection and memory lifecycle.
- `famulix.retrieval` and `context`: ranked retrieval and budgeted context selection.
- `famulix.preferences` and `personalization`: feedback aggregation and explained style selection.
- `famulix.privacy` and `deletion`: tier checks, redaction, policy, and tombstones.
- `famulix.plan_dsl`, `tools`, and `executor`: validated plans and policy-gated actions.
- `famulix.session`, `briefing`, and `evaluation`: replay, cited reports, and synthetic scorecards.

Public dataclasses and functions are type annotated. Serialized events use explicit schema versions and checksums; use their module codecs rather than relying on Python object representations.

The encoding module exposes `extract_fact_candidates` for text/confidence
pairs and `extract_fact_candidate_spans` for the same candidates with source
character offsets. `decode_fact_candidate(event, node)` reconstructs a span
only when the node's provenance names that event and its offsets are valid.

## Statistics and Summary Helpers

### `memory_graph.export_graph_summary(graph) -> str`

Export graph as human-readable summary with node/edge counts.

### `retrieval.retrieval_index_stats(index) -> dict`

Return index statistics (doc_count, term_count).

### `context.context_assembly_stats(result) -> dict`

Return assembly statistics (item_count, total_tokens, within_budget).

### `briefing.briefing_stats(briefing) -> dict`

Return briefing statistics (item_count, citation_count, section_count).

### `evaluation.evaluation_scorecard_summary(scorecard) -> dict`

Return scorecard summary (recall_at_5, precision_at_5, citation_coverage).

### `factory.factory_manifest_summary(manifest) -> dict`

Return manifest summary (persona_id, seed, days, event_count).

### `events.event_type_counts(events) -> dict`

Return counts of events by type.
