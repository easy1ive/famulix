# Example 04: Full Persona Day

End-to-end demonstration producing HTML briefing and evaluation scorecard.

## What This Does

1. Generates 14-day synthetic persona history
2. Ingests events into memory graph
3. Runs consolidation (dedup, contradiction resolution)
4. Retrieves relevant memories for briefing
5. Assembles context within token budget
6. Composes self-contained HTML briefing
7. Runs evaluation harness with scorecard

## Running

```bash
python examples/04_persona_day.py
```

Optional: `python examples/04_persona_day.py /path/to/output/dir`

## Expected Output

Under `artifacts/persona-day/` (or specified directory):

- `daily-briefing.html`: Self-contained HTML briefing
- `scorecard.json`: Measured evaluation metrics

## HTML Briefing Contents

- **Agenda section**: Today's meetings and events
- **Commitments section**: Open promises and deadlines
- **Reminders section**: Proactive triggers and follow-ups
- **Recent memories**: Relevant past events
- **SVG visuals**: Day ribbon, commitment timeline, retention heatmap
- **Citations**: Every item cites memory IDs used
- **Metadata**: Versions, seeds, config hash
- **Limitations**: Honest coverage facts

## Evaluation Scorecard

- Recall@k and precision@k for planted facts
- Contradiction-resolution accuracy
- Citation coverage (must be 100%)
- Preference calibration (Brier score)
- Budget adherence (token count ≤ limit)
- Privacy violations (must be 0)
- Deletion resurrection (must be 0)

## Determinism

Same seed produces identical HTML bytes and scorecard values. Verified by tests.

## Offline Operation

No network calls, no external APIs, no pretrained models. Everything runs locally with deterministic seeds.
