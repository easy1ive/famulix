# Session Recording and Replay

famulix provides deterministic session recording and replay with checksummed JSONL traces. Every event, decision, recall, and receipt is appended to a session log with per-frame checksums, enabling byte-identical replay.

## Features

- **Checksummed frames**: Each session entry includes a SHA-256 hash chained to previous frames
- **Deterministic replay**: Same seed + inputs → identical bytes
- **Checkpoint/resume**: Resume sessions across simulated crashes
- **Session diff**: Compare two sessions and identify divergences

## Usage

### Recording a Session

```python
from famulix.session import SessionRecorder

rec = SessionRecorder(session_id="user_123", seed=42)
rec.record("event", {"type": "note", "content": "Meeting at 3pm"}, timestamp_s=1000)
rec.record("recall", {"query": "meeting time", "results": ["note_1"]}, timestamp_s=1100)

# Save to disk
rec.save("session.jsonl")
```

### Validating a Session

```python
from famulix.session import SessionRecorder, validate_session

rec = SessionRecorder.load("session.jsonl")
report = validate_session(rec)

print(f"Valid: {report['valid']}")
print(f"Entries: {report['entry_count']}")
print(f"Checksum valid: {report['checksum_valid']}")
```

Or via CLI:

```bash
famulix validate-session session.jsonl
famulix validate-session session.jsonl --json
```

### Checkpoint and Resume

```python
# Create checkpoint
checkpoint = rec.checkpoint()

# Later, resume from checkpoint
rec2 = SessionRecorder.resume_from(checkpoint, rec)
rec2.record("event", {"type": "action"}, timestamp_s=1200)
```

### Comparing Sessions

```python
from famulix.session import session_diff

diff = session_diff(rec_a, rec_b)
print(f"Identical: {diff['identical']}")
print(f"First difference at frame: {diff['first_difference']}")
```

## Invariants

- **Byte-determinism**: Same seed + config → identical traces
- **Checksum integrity**: Every frame's hash is chained to all previous frames
- **Timestamp monotonicity**: Timestamps are non-decreasing within a session
- **Replay equality**: Replayer reconstructs byte-identical traces from the same inputs

## Schema

Each session frame is a JSON object with:

- `session_id`: String identifier for the session
- `seq`: Integer sequence number (0-indexed)
- `kind`: String event kind (e.g., "event", "recall", "decision")
- `timestamp_s`: Integer Unix timestamp
- `payload`: Object with event-specific data
- `seed`: Integer random seed
- `_hash`: 16-character hex checksum (SHA-256 prefix)

Frames are stored as newline-delimited JSON (JSONL) with sorted keys for determinism.
