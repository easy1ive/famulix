# Session Recording and Replay

famulix records every event, decision, recall, and receipt to a checksummed
JSONL log for deterministic replay and debugging.

## SessionRecorder

The `SessionRecorder` appends frames with chained checksums:

```python
from famulix.session import SessionRecorder

recorder = SessionRecorder(session_id="session-001", seed=42)
recorder.record(
    kind="event",
    payload={"event_id": "evt_123", "type": "note"},
    timestamp_s=1000000,
)
recorder.record(
    kind="recall",
    payload={"query": "meeting", "results": 5},
    timestamp_s=1000001,
)
```

### Frame Structure

Each frame contains:
- `session_id`: Session identifier
- `seq`: Sequence number (0, 1, 2, ...)
- `kind`: Event type (event, recall, decision, receipt, ...)
- `timestamp_s`: Unix timestamp
- `payload`: Arbitrary JSON object
- `seed`: Random seed for determinism
- `_hash`: SHA-256 checksum chained from previous frames

### Checksum Chain

Each frame's hash includes all previous hashes:

```
hash_n = SHA256(frame_n_json + hash_0 + hash_1 + ... + hash_{n-1})
```

This ensures the entire session is tamper-evident.

## Verification

`verify()` checks the entire checksum chain:

```python
if recorder.verify():
    print("Session is valid")
else:
    print("Session is corrupted")
```

## Persistence

Save and load sessions:

```python
from pathlib import Path

# Save
recorder.save(Path("session.jsonl"))

# Load
loaded = SessionRecorder.load(Path("session.jsonl"))
assert loaded.verify()
assert loaded.entry_count() == recorder.entry_count()
```

The load function verifies checksums on read.

## Checkpoint and Resume

Sessions can be checkpointed and resumed:

```python
# Take a checkpoint
checkpoint = recorder.checkpoint()
# checkpoint = {"schema_version": 1, "session_id": "...", "seed": 42,
#               "next_seq": 100, "digest": "..."}

# Later, resume from checkpoint
resumed = SessionRecorder.resume_from(checkpoint, source_recorder)
resumed.record(kind="event", payload={...}, timestamp_s=2000000)
```

The checkpoint includes a digest to detect stale cursors.

## Replay

Replaying a session reconstructs the exact sequence of operations:

```python
# Given two runs with the same seed and inputs
recorder1 = run_session(seed=42)
recorder2 = run_session(seed=42)

# They should produce identical traces
assert recorder1.digest() == recorder2.digest()
assert recorder1.to_jsonl() == recorder2.to_jsonl()
```

### Byte-Equality Guarantee

Same seed + same inputs → identical bytes. This enables:
- Regression testing
- CI validation
- Debugging production issues by replaying logs

## Session Diff

`session_diff()` compares two sessions:

```python
from famulix.session import session_diff

diff = session_diff(recorder_a, recorder_b)
print(f"Added: {diff['added']}")
print(f"Removed: {diff['removed']}")
print(f"Changed: {diff['changed']}")
```

## Validation

`validate_session()` checks structural integrity:

```python
from famulix.session import validate_session

result = validate_session(recorder)
print(f"Valid: {result['valid']}")
print(f"Problems: {result['problems']}")
```

Checks:
- Checksum chain integrity
- Sequence continuity
- Required fields present
- Timestamp ordering

## CLI Usage

```bash
# Validate a session file
famulix validate-session session.jsonl

# Show session stats
famulix session stats session.jsonl

# Diff two sessions
famulix session diff session_a.jsonl session_b.jsonl
```

## Frame Kinds

Standard frame kinds:
- `event`: Raw input event
- `recall`: Retrieval query and results
- `decision`: Approval decision
- `receipt`: Tool execution receipt
- `checkpoint`: Checkpoint marker
- `error`: Error or exception

Custom kinds are allowed for application-specific events.

## Determinism

The session recorder is fully deterministic:
- Same operations → same frames
- Same frames → same checksums
- Same checksums → same digest

This is essential for reproducible debugging and testing.
