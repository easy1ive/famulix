# Example 03: Preference Learning Loop

Demonstrates preference extraction, calibration, and personalized briefing variants.

## What This Does

1. Generates feedback stream (explicit ratings, implicit signals)
2. Extracts preferences from accept/decline/edit patterns
3. Builds versioned preference profile with confidence
4. Measures calibration (Brier score, reliability bins)
5. Generates personalized briefing variants (A/B comparison)

## Running

```bash
python examples/03_preference_loop.py
```

## Expected Output

- Preference profile with confidence scores
- Calibration report (Brier score, reliability diagram)
- Personalized briefing variants
- Counterfactual comparison metrics

## Key Concepts

- **Preference extraction**: From explicit ratings and implicit signals
- **Confidence with decay**: Newer signals weighted higher
- **Calibration**: Brier score measures prediction accuracy
- **Personalization**: Apply preferences to tone/format/ordering
- **Explainability**: "Why this choice" for each decision

## Planted Preferences

The synthetic persona has:
- Morning meeting preference (80% acceptance)
- Brief format preference (70% acceptance)
- Technical detail preference (varies by topic)

## Offline Operation

No network calls, no external APIs, no pretrained models. Everything runs locally with deterministic seeds.
