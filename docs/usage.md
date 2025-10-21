# Usage

Install the project and its command-line entry point with `pip install -e '.[dev]'`. Run `famulix --help` to see commands, or `famulix demo --help` for a seeded offline run. The demo generates synthetic history, builds and consolidates a memory graph, retrieves context, and reports measured synthetic scorecard values.

Run examples from the repository root with `python examples/01_recall_benchmark.py` through `python examples/04_persona_day.py`. The final example writes `daily-briefing.html` and `scorecard.json` under `artifacts/persona-day/` by default; an optional argument selects a different output directory. No external dataset, service, key, or pretrained weight is required.

For development, create `.venv`, install `.[dev]`, then use `make build`, `make test`, `make test-all`, `make format-check`, `make lint`, and `make typecheck`.

`famulix ingest events.jsonl` validates checksummed event envelopes and reports
the resulting graph projection. `famulix export --format json` emits the full
versioned graph, including edges and provenance; `--format jsonl` writes a
graph header followed by node and edge records.

## Optional PyTorch extra

`pip install -e '.[dev,torch]' --extra-index-url https://download.pytorch.org/whl/cpu` installs
the CPU-only torch extra. It powers two optional learners in `famulix.salience_torch`:

- `SalienceMLP` with `train_demo_synthetic` — a small MLP trained on synthetic salience targets,
  reporting per-epoch losses that measurably decrease.
- `RankFusionMLP` with `train_rank_fusion_demo` — a pairwise margin-ranking model over
  `(bm25, recency, salience)` features, trained on synthetic pairs with a planted nonlinear rule
  and compared in tests against the default linear fusion baseline.

Both learners train only on generated data with fixed seeds; the project ships no pretrained
weights and makes no claims about real model quality. Model tests carry the `model` and `slow`
markers: run them with `make test-all` (or `pytest -m model`); they skip cleanly when the extra
is absent.

## Common workflows

### Building a memory graph from synthetic history

```bash
famulix demo --seed 42 --days 30
```

This generates a 30-day synthetic persona history, ingests it into a memory graph, runs consolidation (deduplication and contradiction resolution), and produces a daily briefing with measured scorecard values.

### Querying memories

```bash
famulix recall "meeting with alice"
```

Retrieves memories matching the query using hybrid scoring (BM25 + recency + salience) with MMR diversification. Each result includes a citation pointing to the source memory node.

### Generating a daily briefing

```bash
famulix brief --date 2026-11-12 --output briefing.html
```

Produces a self-contained HTML briefing with sections for agenda, commitments, reminders, and recent memories. Each item cites the memory IDs it used. The HTML includes embedded SVG visuals (day ribbon, retention heatmap) and a limitations section.

### Exporting the memory graph

```bash
famulix export --format json > graph.json
famulix export --format jsonl > graph.jsonl
```

Exports the full versioned memory graph with all nodes, edges, and provenance information. JSON format produces a single document; JSONL format writes one record per line for streaming processing.

### Evaluating memory mechanics

```bash
famulix eval --seed 42 --days 7
```

Runs the evaluation harness against a synthetic persona with planted ground truth. Reports recall@k, precision@k, contradiction-resolution accuracy, citation coverage, preference calibration, budget adherence, privacy violation count (must be zero), and deletion resurrection checks (must be zero).

### Managing privacy and deletion

```bash
famulix forget <memory_id>
famulix privacy --check <memory_id>
```

The `forget` command cascades deletion across nodes, edges, projections, and retrieval indexes, leaving a tombstone to prevent re-derivation. The `privacy` command checks tier rules and reports access decisions.

## Configuration

Most commands accept `--seed` for deterministic reproducibility and `--config` to load a JSON configuration file. Configuration keys include:

- `retrieval.bm25_weight`, `retrieval.recency_weight`, `retrieval.salience_weight` — hybrid scoring weights (must sum to 1.0)
- `context.max_tokens` — token budget for context assembly
- `consolidation.dedup_threshold` — similarity threshold for near-duplicate merging (0.0–1.0)
- `decay.hot_half_life_s`, `decay.warm_half_life_s`, etc. — retention curve parameters per tier
- `privacy.default_tier` — default privacy tier for new memories (`public`, `shared`, `personal`, `private`)

All configuration values are embedded in report metadata and briefing HTML for reproducibility tracking.
