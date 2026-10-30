# Synthetic Personal-History Factory

The factory generates seeded synthetic personal histories for offline testing
and evaluation. Every output is deterministic and reproducible.

## Overview

```python
from famulix.factory import generate_history, generate_history_with_truth

# Simple history
events, manifest = generate_history(
    persona_id="alex",
    seed=42,
    days=90,
    start_date="2026-01-01",
)

# History with ground truth for evaluation
events, manifest, truth = generate_history_with_truth(
    persona_id="alex",
    seed=42,
    days=90,
    start_date="2026-01-01",
)
```

## Personas

Built-in personas with distinct characteristics:

```python
from famulix.factory import list_personas, DEFAULT_PERSONAS

print(list_personas())  # ["alex", "blair", "casey"]

alex = DEFAULT_PERSONAS["alex"]
print(alex.timezone_offset)  # 8 (UTC+8)
print(alex.work_hours)  # (9, 18)
print(alex.relationships)  # ["Riley", "Jordan", ...]
```

Each persona has:
- **timezone_offset**: Hours from UTC
- **work_hours**: Typical work schedule
- **relationships**: Known contacts
- **goals**: Stated objectives
- **device_mix**: Probability of laptop vs phone

## Event Types

The factory generates diverse event types:

- **notes**: Personal notes and memos
- **messages**: Incoming/outgoing messages
- **calendar**: Meetings and appointments
- **files**: File access events
- **feedback**: Preference signals (accept/decline/edit)
- **timer**: Reminder fires
- **utterance**: User speech acts

Each event has:
- `event_id`: Content-addressed deterministic ID
- `timestamp_s`: Unix timestamp
- `event_type`: One of the types above
- `source`: Device or channel
- `data`: Type-specific payload

## Planted Ground Truth

`generate_history_with_truth()` returns ground truth for evaluation:

```python
truth = {
    "fact_ids": ["evt_abc", "evt_def", ...],
    "contradiction_pairs": [("evt_old", "evt_new"), ...],
    "preference_signals": [
        {"event_id": "evt_xyz", "key": "tone", "value": "concise", "rating": 0.9},
        ...,
    ],
}
```

### Planted Facts

Deliberately planted facts at known positions:
- "Lives at 123 Oak Street, Apt 4B"
- "Phone ends with 5678"
- "Favorite color is navy blue"
- "Always orders oat milk latte"
- etc.

These facts should be retrievable by the evaluation harness.

### Planted Contradictions

Pairs of conflicting facts at different times:
- Old: "Lives at 123 Oak Street"
- New: "Lives at 456 Pine Avenue"

The consolidation pipeline should resolve these correctly.

### Planted Preferences

Feedback signals for preference learning:
- Explicit ratings (up/down)
- Implicit signals (accept/decline/edit)

The preference pipeline should calibrate to these.

## Determinism

The factory is fully deterministic:
- Same seed → identical events
- Same events → identical event_ids
- Same event_ids → identical checksums

```python
events1, _ = generate_history(persona_id="alex", seed=42, days=30)
events2, _ = generate_history(persona_id="alex", seed=42, days=30)

assert len(events1) == len(events2)
for e1, e2 in zip(events1, events2):
    assert e1.event_id == e2.event_id
    assert e1.timestamp_s == e2.timestamp_s
    assert e1.data == e2.data
```

## Manifest

The `HistoryManifest` summarizes the generated history:

```python
manifest = HistoryManifest(
    persona_id="alex",
    seed=42,
    days=90,
    start_date="2026-01-01",
    end_date="2026-03-31",
    event_count=1234,
    planted_fact_count=6,
    planted_contradiction_count=2,
    planted_preference_count=15,
)

print(f"Generated {manifest.event_count} events over {manifest.days} days")
print(f"Planted {manifest.planted_fact_count} facts")
```

## Noise and Realism

The factory adds realistic noise:
- **Timestamp jitter**: ±5 minutes on event times
- **Device switching**: Probabilistic device selection
- **Typo injection**: Occasional spelling variations
- **Duplicate mentions**: Same fact mentioned multiple times

This tests robustness without breaking determinism (all noise is seeded).

## Golden Fixtures

Small factory outputs (days=1-3) serve as golden fixtures for regression tests:

```python
events, manifest = generate_history(persona_id="alex", seed=0, days=1)
# Save as golden fixture
import json

with open("golden_alex_1day.json", "w") as f:
    json.dump([e.to_dict() for e in events], f)
```

## Checksums

Every event has a content checksum:

```python
for event in events:
    assert event.checksum == event.compute_checksum()
```

The manifest includes an aggregate checksum over all events.

## Usage in Tests

```python
def test_recall_finds_planted_facts():
    events, _, truth = generate_history_with_truth(seed=42, days=30)
    graph = encode_events_to_graph(events)
    consolidate_graph(graph)

    planted_ids = set(truth["fact_ids"])
    recall, _ = eval_recall_precision(graph, planted_ids, now_s=1000000)
    assert recall["@5"] >= 0.8
```
