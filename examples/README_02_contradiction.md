# Example 02: Contradiction Week

Demonstrates contradiction detection, supersede policy, and deletion cascade.

## What This Does

1. Generates history with planted contradictions (old vs new address)
2. Detects incompatible facts with same key
3. Applies deterministic supersede policy (newest-verified wins)
4. Creates audit trail of resolution decisions
5. Demonstrates deletion cascade across graph

## Running

```bash
python examples/02_contradiction_week.py
```

## Expected Output

- Contradiction detection report
- Supersede decisions with citations
- Audit trail of which fact won and why
- Deletion cascade visualization

## Key Concepts

- **Contradiction detection**: Same fact key, incompatible values
- **Supersede policy**: Deterministic winner selection (newest-verified, then source trust, then id)
- **Audit trail**: Every decision cites evidence
- **Deletion cascade**: Removing a node cascades to edges and projections

## Planted Contradictions

The synthetic history includes:
- Old address vs new address (moved during week)
- Changed meeting cadence (weekly → biweekly)
- Conflicting reminders times

## Offline Operation

No network calls, no external APIs, no pretrained models. Everything runs locally with deterministic seeds.
