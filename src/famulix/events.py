"""Typed personal events with versioned dataclasses and JSONL serialization.

Event types: note, message, calendar_item, file_touch, feedback_tap,
timer_fire, user_utterance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from famulix.envelope import Envelope
from famulix.types import EventId
from famulix.utils import content_id, stable_json_dumps

EventType = Literal[
    "note",
    "message",
    "calendar_item",
    "file_touch",
    "feedback_tap",
    "timer_fire",
    "user_utterance",
]


@dataclass(frozen=True)
class Event:
    """A single personal event with a content-addressed id."""

    event_id: EventId
    event_type: EventType
    timestamp_s: int
    source: str
    data: dict[str, Any]
    version: int = 1

    @classmethod
    def create(
        cls,
        event_type: EventType,
        timestamp_s: int,
        source: str,
        data: dict[str, Any],
    ) -> Event:
        payload = stable_json_dumps(
            {
                "event_type": event_type,
                "timestamp_s": timestamp_s,
                "source": source,
                "data": data,
            }
        )
        eid = content_id("evt", payload)
        return cls(
            event_id=eid,
            event_type=event_type,
            timestamp_s=timestamp_s,
            source=source,
            data=data,
        )

    def to_envelope(self) -> Envelope:
        return Envelope.wrap("event", asdict(self))

    @classmethod
    def from_envelope(cls, env: Envelope) -> Event:
        if env.kind != "event":
            raise ValueError(f"Expected event envelope, got {env.kind}")
        p = env.payload
        return cls(
            event_id=p["event_id"],
            event_type=p["event_type"],
            timestamp_s=int(p["timestamp_s"]),
            source=p["source"],
            data=p["data"],
            version=int(p.get("version", 1)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def note_event(timestamp_s: int, source: str, text: str) -> Event:
    """Build a note event."""
    return Event.create("note", timestamp_s, source, {"text": text})


def message_event(
    timestamp_s: int,
    source: str,
    direction: Literal["in", "out"],
    counterpart: str,
    text: str,
) -> Event:
    return Event.create(
        "message",
        timestamp_s,
        source,
        {"direction": direction, "counterpart": counterpart, "text": text},
    )


def calendar_event(
    timestamp_s: int,
    source: str,
    title: str,
    start_s: int,
    end_s: int,
    attendees: list[str] | None = None,
) -> Event:
    return Event.create(
        "calendar_item",
        timestamp_s,
        source,
        {
            "title": title,
            "start_s": start_s,
            "end_s": end_s,
            "attendees": attendees or [],
        },
    )


def feedback_event(
    timestamp_s: int,
    source: str,
    target_id: str,
    rating: Literal["up", "down", "skip"],
) -> Event:
    return Event.create(
        "feedback_tap",
        timestamp_s,
        source,
        {"target_id": target_id, "rating": rating},
    )


def validate_event(event: Event) -> list[str]:
    """Validate an event for structural correctness.

    Checks:
    - event_id is non-empty
    - event_type is non-empty
    - timestamp_s is non-negative
    - source is non-empty
    - data is a dict

    Returns a list of validation problems found.
    """
    problems: list[str] = []

    if not event.event_id or not event.event_id.strip():
        problems.append("event_id must be non-empty")

    if not event.event_type or not event.event_type.strip():
        problems.append("event_type must be non-empty")

    if event.timestamp_s < 0:
        problems.append(f"timestamp_s must be non-negative, got {event.timestamp_s}")

    if not event.source or not event.source.strip():
        problems.append("source must be non-empty")

    if not isinstance(event.data, dict):
        problems.append(f"data must be a dict, got {type(event.data).__name__}")

    return problems


def batch_validate_events(events: list[Event]) -> tuple[int, list[str]]:
    """Validate a batch of events and return (valid_count, errors).

    Returns the number of valid events and a list of error messages
    for any that fail validation.
    """
    valid_count = 0
    errors: list[str] = []

    for i, event in enumerate(events):
        problems = validate_event(event)
        if problems:
            for problem in problems:
                errors.append(f"event[{i}]: {problem}")
        else:
            valid_count += 1

    return valid_count, errors


def event_statistics(events: list[Event]) -> dict[str, object]:
    """Generate statistics for a batch of events.

    Returns a dict with:
    - count: total number of events
    - event_types: set of event types seen
    - sources: set of sources seen
    - timestamp_range: (min, max) timestamps
    """
    if not events:
        return {
            "count": 0,
            "event_types": set(),
            "sources": set(),
            "timestamp_range": (0, 0),
        }

    timestamps = [e.timestamp_s for e in events]
    return {
        "count": len(events),
        "event_types": {e.event_type for e in events},
        "sources": {e.source for e in events},
        "timestamp_range": (min(timestamps), max(timestamps)),
    }


def event_type_counts(events: list) -> dict[str, int]:
    """Return counts of events by type."""
    counts: dict[str, int] = {}
    for event in events:
        etype = event.event_type
        counts[etype] = counts.get(etype, 0) + 1
    return counts
