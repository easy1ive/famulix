# Offline examples

All examples use deterministic synthetic data and run without network access.

- `01_recall_benchmark.py`: 90-day synthetic history, memory graph, and planted-fact recall slice.
- `02_contradiction_week.py`: conflicting synthetic facts, supersession, and deletion audit.
- `03_preference_loop.py`: feedback signals, style selection, and a measured score on an explicitly constructed signal list.
- `04_persona_day.py`: a short seeded persona day that writes a self-contained HTML briefing and evaluation scorecard under `./artifacts/`.

- `05_privacy_demo.py`: PII detection, reversible and irreversible redaction, and a deletion cascade with tombstones.
- `06_plan_tools_demo.py`: plan DSL validation, topological ordering, and deterministic tool execution.
- `07_session_replay.py`: session record and replay with byte-equality verification.
- `08_memory_graph_demo.py`: memory graph node and edge operations with structural invariants.
- `09_reporting_demo.py`: evaluation and preference report generation as Markdown and HTML.

Run from the repository root with `python examples/<name>.py`. Synthetic scores are not evidence about real users or language-model quality.
