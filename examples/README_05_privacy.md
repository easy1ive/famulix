# Example 05: Privacy and Right-to-Forget

Demonstrates PII detection, redaction, tier rules, and deletion cascade.

## What This Does

1. Generates synthetic history
2. Detects PII (email, phone, card patterns)
3. Redacts sensitive information
4. Builds memory graph
5. Demonstrates deletion cascade with tombstones

## Running

```bash
python examples/05_privacy_demo.py
```

## Expected Output

- PII detection report with positions
- Redacted text with masked values
- Memory graph statistics
- Deletion cascade report (nodes, edges, tombstones)

## Key Concepts

- **PII detection**: Pattern matching for email, phone, card numbers
- **Redaction**: Reversible vs irreversible modes
- **Tier rules**: public, shared, personal, private
- **Deletion cascade**: Removes nodes, edges, projections, indexes
- **Tombstones**: Prevent re-derivation of deleted content

## Offline Operation

No network calls, no external APIs, no pretrained models.
