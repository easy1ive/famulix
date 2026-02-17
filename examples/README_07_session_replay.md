# Example 07: Session Record and Replay

Demonstrates session recording, checkpoint, and byte-identical replay.

## Running

```bash
python examples/07_session_replay.py
```

## Key Concepts

- Recording: Append-only JSONL with checksums
- Replay: Reconstruct byte-identical traces
- Determinism: Same seed + inputs → identical bytes
