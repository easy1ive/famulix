# Events and Envelopes

Events are the atomic units of personal history in famulix. Each event is
wrapped in a versioned envelope with content checksums for integrity.

## Event Structure

```python
from famulix.events import Event

event = Event(
    event_id="evt_abc123",
    timestamp_s=1000000,
    event_type="note",
    source="laptop",
    data={
        "text": "Meeting with Riley at 3pm",
        "tags": ["meeting", "riley"],
    },
)
```

### Event Types

Standard event types:
- `note`: Personal notes and memos
- `message`: Incoming/outgoing messages
- `calendar`: Calendar events and appointments
- `file`: File access and modifications
- `feedback`: User feedback signals
- `timer`: Reminder fires
- `utterance`: User speech acts

### Deterministic IDs

Event IDs are content-addressed and deterministic:

```python
from famulix.events import compute_event_id

event_id = compute_event_id(
    timestamp_s=1000000,
    event_type="note",
    source="laptop",
    data={"text": "Hello"},
)
# "evt_sha256_prefix"
```

Same inputs → same event_id. This enables deduplication and replay.

## Envelopes

Events are wrapped in versioned envelopes:

```python
from famulix.envelope import Envelope

envelope = Envelope(
    schema_version=1,
    event=event,
    checksum="sha256:abc123...",
)
```

### Schema Versioning

Envelopes include a schema version for forward/backward compatibility:

```python
if envelope.schema_version == 1:
    # Parse v1 format
    ...
elif envelope.schema_version == 2:
    # Parse v2 format
    ...
else:
    raise ValueError(f"Unsupported schema: {envelope.schema_version}")
```

### Content Checksums

Each envelope includes a checksum over the event content:

```python
from famulix.envelope import compute_checksum

checksum = compute_checksum(event)
assert envelope.checksum == checksum
```

Checksums detect corruption and tampering.

## Serialization

Events serialize to JSON for persistence:

```python
import json

# Serialize
data = event.to_dict()
json_str = json.dumps(data)

# Deserialize
loaded_data = json.loads(json_str)
loaded_event = Event.from_dict(loaded_data)

assert loaded_event.event_id == event.event_id
assert loaded_event.data == event.data
```

### JSONL Format

Events are stored as JSONL (one JSON object per line):

```python
from pathlib import Path

# Write
with Path("events.jsonl").open("w") as f:
    for event in events:
        f.write(json.dumps(event.to_dict()) + "\n")

# Read
events = []
with Path("events.jsonl").open() as f:
    for line in f:
        events.append(Event.from_dict(json.loads(line)))
```

## Roundtrip Tests

Golden tests verify serialization roundtrips:

```python
def test_event_roundtrip():
    original = Event(...)
    data = original.to_dict()
    loaded = Event.from_dict(data)
    assert loaded == original
```

This ensures no data loss during serialization.

## Clock and Timezone

The `clock` module provides deterministic time utilities:

```python
from famulix.clock import day_start_epoch, day_bucket

# Get start of day in epoch seconds
day_start = day_start_epoch("2026-03-15", tz_offset_hours=8)

# Bucket events by day
buckets = day_bucket(events, tz_offset_hours=8)
for day, day_events in buckets.items():
    print(f"{day}: {len(day_events)} events")
```

### DST Handling

Timezone-aware bucketing handles DST boundaries:

```python
# Events across DST transition
events = [
    Event(timestamp_s=dst_boundary - 3600, ...),  # Before DST
    Event(timestamp_s=dst_boundary + 3600, ...),  # After DST
]

buckets = day_bucket(events, tz_offset_hours=8)
# Both events bucketed correctly despite DST shift
```

## Content Addressing

Content-addressed IDs enable:
- Deduplication of identical events
- Integrity verification via checksum
- Deterministic replay from logs
- Cross-system event correlation

## CLI Usage

```bash
# Ingest events from JSONL
famulix ingest events.jsonl

# Export events to JSONL
famulix export --format jsonl > events.jsonl

# Show event stats
famulix events stats events.jsonl
```
