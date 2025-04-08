# Usage

Install the project and its command-line entry point with `pip install -e '.[dev]'`. Run `famulix --help` to see commands, or `famulix demo --help` for a seeded offline run. The demo generates synthetic history, builds and consolidates a memory graph, retrieves context, and reports measured synthetic scorecard values.

Run examples from the repository root with `python examples/01_recall_benchmark.py` through `python examples/04_persona_day.py`. The final example writes `daily-briefing.html` and `scorecard.json` under `artifacts/persona-day/` by default; an optional argument selects a different output directory. No external dataset, service, key, or pretrained weight is required.

For development, create `.venv`, install `.[dev]`, then use `make build`, `make test`, `make test-all`, `make format-check`, `make lint`, and `make typecheck`.

`famulix ingest events.jsonl` validates checksummed event envelopes and reports
the resulting graph projection. `famulix export --format json` emits the full
versioned graph, including edges and provenance; `--format jsonl` writes a
graph header followed by node and edge records.
