# Architecture

famulix separates observations from derived memories. Versioned `Event` records form an append-only SQLite log; encoders project events into a provenance-linked `MemoryGraph`. Consolidation resolves duplicate and contradictory facts, while decay and deletion update active state without erasing audit tombstones.

Retrieval combines lexical matches with time and salience signals. Context assembly selects whole items under a token estimate budget. Preference feedback is maintained separately from factual memory and can explain the style applied to the daily briefing. Policy checks gate tool execution and plan steps. Session traces retain decisions and receipts for deterministic replay.

The daily briefing composes selected memories and includes source IDs on each item. Its HTML and SVG are rendered locally with escaped text. The synthetic history factory supplies reproducible fixtures and planted ground truth; its scores describe mechanics on those fixtures only.

Evaluation runs an explicit private-to-public export probe and counts whether the policy gate permits it. It also tombstones a live synthetic fact, rebuilds the active retrieval index, and counts any resurfacing result. These counters describe those executed checks, not a general privacy certification.

## Mechanism references

- Packer et al., [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560), for tiered memory as a system design idea.
- Park et al., [Generative Agents](https://arxiv.org/abs/2304.03442), for recency, importance, and relevance as memory signals.
- Robertson and Zaragoza, [The Probabilistic Relevance Framework: BM25 and Beyond](https://doi.org/10.1561/1500000019), for lexical retrieval.
- Carbonell and Goldstein, [The Use of MMR, Diversity-Based Reranking](https://doi.org/10.1145/290941.291025), for diversified selection.
- Brier, [Verification of Forecasts Expressed in Terms of Probability](https://doi.org/10.1175/1520-0493(1950)078%3C0001:VOFEIT%3E2.0.CO;2), for the squared probability score.
- Ebbinghaus, [Memory: A Contribution to Experimental Psychology](https://psychclassics.yorku.ca/Ebbinghaus/), for the historical forgetting-curve concept.

These works motivate mechanisms; famulix provides its own data model and implementation. No result here evaluates a real conversational model.


## Daily briefing visuals

The briefing charts aggregate active graph nodes by their stored creation time in the configured UTC+8 view. The day ribbon sums salience by local hour; the heatmap shows the latest seven represented local dates, with each cell summing the same node scores. Empty histories omit the heatmap. These visuals summarize the synthetic or user-provided graph supplied to the offline pipeline; they are not measurements of assistant quality.

## Plan execution snapshots

Plans carry a versioned JSON schema and a content fingerprint. Execution state
can be serialized as a strict version-one snapshot containing outputs, facts,
step receipts, counters, and the termination reason. The snapshot deliberately
contains no tool handlers; resuming therefore requires the caller to provide a
registry again. Declared step budgets are synthetic money costs, while the
run-level budget reserves the base receipt cost before each action.

## Privacy and replay artifacts

Privacy access logs are append-only JSONL with strict frame fields, and access
decisions have a small round-trippable shape for audit reports. Policy rules
are ordered by explicit priority and then rule id. Session checkpoints bind a
cursor to the session id, seed, length, and digest; a stale checkpoint cannot
resume a changed trace. Session diffs report the first divergent frame.

## Data flow

The typical data flow proceeds through five stages:

1. **Ingestion**: Raw events (notes, messages, calendar items, file touches) are validated, assigned content-addressed IDs, and appended to the SQLite event log with checksummed envelopes.

2. **Encoding**: The encoding pipeline segments events into day/session episodes, extracts entity mentions via rule-based alias tables, identifies fact candidates with confidence scores, and deduplicates repeated mentions. Each derived memory node carries provenance edges back to its source events.

3. **Consolidation**: Near-duplicate facts are merged with stable winner selection (newest verified wins). Contradictions (same fact key, incompatible values) are resolved deterministically. Episode summaries cite their source nodes via `derived_from` edges.

4. **Retrieval**: Queries parse structured filters (kind, tag, time window). BM25 scores are fused with recency and salience signals. MMR diversification reduces redundancy. Every result carries a citation pointing to an active memory node.

5. **Assembly**: Context items are selected via 0/1 knapsack DP to maximize value under a token budget. The briefing pipeline composes sections (agenda, commitments, reminders, recent memories) with per-item citations and renders self-contained HTML with embedded SVG visuals.

## Module dependencies

Core modules form a layered dependency graph:

- **Foundation**: `events`, `envelope`, `clock`, `utils` (no internal dependencies)
- **Storage**: `eventlog` depends on `events`, `envelope`
- **Memory**: `memory_graph` depends on foundation; `encoding` depends on `memory_graph`, `events`
- **Scoring**: `salience`, `decay`, `consolidation` depend on `memory_graph`
- **Retrieval**: `retrieval` depends on `memory_graph`, `salience`
- **Assembly**: `context`, `briefing`, `reports` depend on `retrieval`, `memory_graph`
- **Policy**: `privacy`, `tools`, `executor` depend on `memory_graph`
- **Planning**: `plan_dsl`, `approval`, `triggers` depend on `memory_graph`, `salience`
- **Session**: `session` depends on foundation only
- **Evaluation**: `evaluation`, `factory` depend on most modules for end-to-end scenarios

Optional `salience_torch` provides trainable rank-fusion models and is imported only when the `torch` extra is installed.
