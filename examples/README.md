# Offline examples

All examples use deterministic synthetic data and run without network access.

- `01_recall_benchmark.py`: 90-day synthetic history, memory graph, and planted-fact recall slice.
- `02_contradiction_week.py`: conflicting synthetic facts, supersession, and deletion audit.
- `03_preference_loop.py`: feedback signals, style selection, and a measured score on an explicitly constructed signal list.
- `04_persona_day.py`: a short seeded persona day that writes a self-contained HTML briefing and evaluation scorecard under `./artifacts/`.

Run from the repository root with `python examples/<name>.py`. Synthetic scores are not evidence about real users or language-model quality.
