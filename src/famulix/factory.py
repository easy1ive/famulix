"""Synthetic personal history factory.

Generates seeded, reproducible personal event histories for offline
testing and evaluation. Personas have deterministic traits and the
factory produces a mix of note/message/calendar/file/feedback events
spanning multiple days with planted facts, preferences, and contradictions.

All outputs are deterministic for a given (persona_id, seed, days) tuple.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Literal

from famulix.clock import day_start_epoch
from famulix.events import (
    Event,
    calendar_event,
    feedback_event,
    message_event,
    note_event,
)


@dataclass(frozen=True)
class PersonaProfile:
    """Configuration for a synthetic persona."""

    persona_id: str
    name: str
    timezone_offset: int = 8
    work_start_hour: int = 9
    work_end_hour: int = 18
    relationship_names: tuple[str, ...] = ()
    goals: tuple[str, ...] = ()
    device_mix: tuple[str, ...] = ("phone", "laptop")
    note_frequency: float = 0.3
    message_frequency: float = 0.5
    calendar_frequency: float = 0.4
    file_frequency: float = 0.2

    def __post_init__(self) -> None:
        if not self.persona_id.strip() or not self.name.strip():
            raise ValueError("persona id and name must be non-empty")
        if not -14 <= self.timezone_offset <= 14:
            raise ValueError("persona timezone offset must be within UTC-14..UTC+14")
        if not 0 <= self.work_start_hour < self.work_end_hour <= 24:
            raise ValueError("persona work hours must satisfy 0 <= start < end <= 24")
        if not self.device_mix or any(not device.strip() for device in self.device_mix):
            raise ValueError("persona device mix must contain non-empty device names")
        frequencies = (
            self.note_frequency,
            self.message_frequency,
            self.calendar_frequency,
            self.file_frequency,
        )
        if any(not 0 <= frequency <= 1 for frequency in frequencies):
            raise ValueError("persona event frequencies must be within [0, 1]")


DEFAULT_PERSONAS: dict[str, PersonaProfile] = {
    "alex": PersonaProfile(
        persona_id="alex",
        name="Alex Chen",
        timezone_offset=8,
        work_start_hour=9,
        work_end_hour=18,
        relationship_names=("Jamie", "Sam", "Mom"),
        goals=(
            "finish quarterly report by end of month",
            "go to gym three times per week",
            "read one book per month",
        ),
        device_mix=("phone", "laptop", "tablet"),
        note_frequency=0.4,
        message_frequency=0.6,
        calendar_frequency=0.5,
        file_frequency=0.3,
    ),
    "bailey": PersonaProfile(
        persona_id="bailey",
        name="Bailey Liu",
        timezone_offset=-5,
        work_start_hour=10,
        work_end_hour=19,
        relationship_names=("Riley", "Dad", "Team"),
        goals=(
            "launch side project in Q4",
            "learn Rust basics",
            "weekly hiking trip",
        ),
        device_mix=("laptop", "phone"),
        note_frequency=0.3,
        message_frequency=0.4,
        calendar_frequency=0.6,
        file_frequency=0.4,
    ),
}


def persona_digest(persona_id: str, seed: int) -> int:
    """Derive a deterministic seed for a persona+seed combo."""
    h = hashlib.sha256(f"{persona_id}:{seed}".encode()).digest()
    return int.from_bytes(h[:8], "big")


@dataclass
class HistoryManifest:
    """Summary of a generated synthetic history."""

    persona_id: str
    seed: int
    days: int
    start_date: str
    end_date: str
    event_count: int
    by_type: dict[str, int] = field(default_factory=dict)
    planted_fact_count: int = 0
    planted_contradiction_count: int = 0
    planted_preference_count: int = 0
    checksum: str = ""

    def planted_total(self) -> int:
        return (
            self.planted_fact_count
            + self.planted_contradiction_count
            + self.planted_preference_count
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "persona_id": self.persona_id,
            "seed": self.seed,
            "days": self.days,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "event_count": self.event_count,
            "by_type": dict(self.by_type),
            "planted_fact_count": self.planted_fact_count,
            "planted_contradiction_count": self.planted_contradiction_count,
            "planted_preference_count": self.planted_preference_count,
            "checksum": self.checksum,
        }


def _file_event(timestamp_s: int, source: str, path: str, action: str) -> Event:
    return Event.create("file_touch", timestamp_s, source, {"path": path, "action": action})


class HistoryFactory:
    """Deterministic synthetic personal history generator."""

    def __init__(self, persona: PersonaProfile, seed: int = 0, days: int = 90) -> None:
        if type(days) is not int or days < 1:
            raise ValueError("history days must be a positive integer")
        self.persona = persona
        self.seed = seed
        self.days = days
        self._seed_val = persona_digest(persona.persona_id, seed)
        self._rng = random.Random(self._seed_val)

    def _rand(self) -> float:
        return self._rng.random()

    def _randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def _choice(self, seq: tuple[str, ...]) -> str:
        return self._rng.choice(seq)

    def generate(
        self,
        start_date: str = "2026-01-01",
    ) -> tuple[list[Event], HistoryManifest]:
        """Generate a full event history spanning the configured days."""
        events: list[Event] = []
        day_epoch = day_start_epoch(start_date, self.persona.timezone_offset)
        day_seconds = 86400

        by_type: dict[str, int] = {}

        for day_idx in range(self.days):
            day_start = day_epoch + day_idx * day_seconds
            day_events = self._generate_day_events(day_start, day_idx)
            for evt in day_events:
                by_type[evt.event_type] = by_type.get(evt.event_type, 0) + 1
            events.extend(day_events)

        # Add planted facts as notes at specific days
        planted_facts = self._generate_planted_facts(day_epoch, day_seconds)
        for evt in planted_facts:
            by_type[evt.event_type] = by_type.get(evt.event_type, 0) + 1
        events.extend(planted_facts)

        # Add planted contradictions (conflicting facts at different times)
        planted_contradictions = self._generate_planted_contradictions(day_epoch, day_seconds)
        for evt in planted_contradictions:
            by_type[evt.event_type] = by_type.get(evt.event_type, 0) + 1
        events.extend(planted_contradictions)

        # Add planted preference signals (feedback taps)
        planted_prefs = self._generate_planted_preferences(day_epoch, day_seconds)
        for evt in planted_prefs:
            by_type[evt.event_type] = by_type.get(evt.event_type, 0) + 1
        events.extend(planted_prefs)

        events.sort(key=lambda e: (e.timestamp_s, e.event_id))

        total_count = len(events)
        checksum = self._checksum(events)
        end_date_epoch = day_epoch + (self.days - 1) * day_seconds
        from datetime import datetime, timedelta, timezone

        end_dt = datetime.fromtimestamp(
            end_date_epoch, tz=timezone(timedelta(hours=self.persona.timezone_offset))
        )
        end_date_str = end_dt.date().isoformat()

        planted_fact_count = len(planted_facts)
        planted_contradiction_count = len(planted_contradictions) // 2
        planted_preference_count = len(planted_prefs)

        manifest = HistoryManifest(
            persona_id=self.persona.persona_id,
            seed=self.seed,
            days=self.days,
            start_date=start_date,
            end_date=end_date_str,
            event_count=total_count,
            by_type=by_type,
            planted_fact_count=planted_fact_count,
            planted_contradiction_count=planted_contradiction_count,
            planted_preference_count=planted_preference_count,
            checksum=checksum,
        )
        return events, manifest

    def _generate_day_events(self, day_start: int, day_idx: int) -> list[Event]:
        events: list[Event] = []
        is_weekend = (day_idx % 7) >= 5

        # Notes
        note_count = self._pick_count(self.persona.note_frequency, max_val=5)
        for _ in range(note_count):
            ts = self._daytime_timestamp(day_start, is_weekend)
            src = self._choice(self.persona.device_mix)
            text = self._random_note_text(day_idx)
            events.append(note_event(ts, src, text))

        # Messages
        msg_count = self._pick_count(self.persona.message_frequency, max_val=8)
        for _ in range(msg_count):
            ts = self._daytime_timestamp(day_start, is_weekend)
            src = self._choice(self.persona.device_mix)
            direction: Literal["in", "out"] = "in" if self._rand() > 0.5 else "out"
            counterpart = self._choice(self.persona.relationship_names)
            text = self._random_message_text(counterpart, day_idx)
            events.append(message_event(ts, src, direction, counterpart, text))

        # Calendar items
        if not is_weekend:
            cal_count = self._pick_count(self.persona.calendar_frequency, max_val=4)
            for _ in range(cal_count):
                start_h = self._randint(
                    self.persona.work_start_hour, self.persona.work_end_hour - 1
                )
                start_ts = day_start + start_h * 3600 + self._randint(0, 30) * 60
                duration_h = self._randint(1, 2)
                end_ts = start_ts + duration_h * 3600
                src = self._choice(self.persona.device_mix)
                title = self._random_calendar_title(day_idx)
                events.append(calendar_event(start_ts, src, title, start_ts, end_ts))

        # File touches
        file_count = self._pick_count(self.persona.file_frequency, max_val=6)
        for _ in range(file_count):
            ts = self._daytime_timestamp(day_start, is_weekend)
            src = (
                "laptop"
                if "laptop" in self.persona.device_mix
                else self._choice(self.persona.device_mix)
            )
            path = self._random_file_path(day_idx)
            action = self._choice(("open", "modify", "create"))
            events.append(_file_event(ts, src, path, action))

        # Feedback taps (sparse)
        if self._rand() < 0.15:
            ts = self._daytime_timestamp(day_start, is_weekend)
            src = self._choice(self.persona.device_mix)
            target = f"mem_{day_idx}_{self._randint(0, 100)}"
            rating = self._choice(("up", "down", "skip"))
            events.append(feedback_event(ts, src, target, rating))  # type: ignore[arg-type]

        return events

    def _pick_count(self, frequency: float, *, max_val: int) -> int:
        if self._rand() > frequency:
            return 0
        return self._randint(1, max_val)

    def _daytime_timestamp(self, day_start: int, is_weekend: bool) -> int:
        if is_weekend:
            hour = self._randint(10, 21)
        else:
            hour = self._randint(self.persona.work_start_hour - 1, self.persona.work_end_hour + 2)
        minute = self._randint(0, 59)
        second = self._randint(0, 59)
        return day_start + hour * 3600 + minute * 60 + second

    def _random_note_text(self, day_idx: int) -> str:
        templates = [
            "Reminder to follow up on {topic} with {person}",
            "Idea: {topic} could be improved by adding {detail}",
            "Read about {topic} today, key takeaway was {detail}",
            "Todo: {topic} before end of week",
            "Meeting notes from {person} about {topic}: {detail}",
            "Bookmark: article on {topic} with {detail}",
            "Reflection on {topic}: {detail}",
        ]
        topics = [
            "project planning",
            "machine learning",
            "product design",
            "team sync",
            "budget review",
            "documentation",
            "user feedback",
            "performance review",
        ]
        details = [
            "action items to track",
            "three main points to remember",
            "a deadline next friday",
            "follow-up next week",
            "some open questions",
            "great references to read",
            "surprising insights",
        ]
        t = templates[self._randint(0, len(templates) - 1)]
        topic = topics[self._randint(0, len(topics) - 1)]
        detail = details[self._randint(0, len(details) - 1)]
        person = self._choice(self.persona.relationship_names)
        return t.format(topic=topic, detail=detail, person=person)

    def _random_message_text(self, counterpart: str, day_idx: int) -> str:
        templates = [
            "Hey, can we talk about {topic} later?",
            "Did you see the update on {topic}?",
            "Thanks for the help with {topic}",
            "Let me know when you're free to discuss {topic}",
            "Just got back from {topic}, it was great",
            "{topic} deadline moved to next week",
        ]
        topics = [
            "the project",
            "the meeting",
            "the report",
            "dinner plans",
            "the weekend trip",
            "the presentation",
            "the review",
        ]
        t = templates[self._randint(0, len(templates) - 1)]
        topic = topics[self._randint(0, len(topics) - 1)]
        return t.format(topic=topic)

    def _random_calendar_title(self, day_idx: int) -> str:
        templates = [
            "{topic} meeting",
            "{topic} review",
            "{topic} sync",
            "1:1 with {person}",
            "{topic} planning session",
            "{topic} demo",
        ]
        topics = [
            "Product",
            "Engineering",
            "Design",
            "Q3 roadmap",
            "Sprint",
            "Client",
            "Team",
        ]
        t = templates[self._randint(0, len(templates) - 1)]
        topic = topics[self._randint(0, len(topics) - 1)]
        person = self._choice(self.persona.relationship_names)
        return t.format(topic=topic, person=person)

    def _random_file_path(self, day_idx: int) -> str:
        folders = [
            "~/documents/work/",
            "~/documents/personal/",
            "~/projects/famulix/",
            "~/notes/",
            "~/downloads/",
            "~/photos/",
        ]
        names = [
            "report.docx",
            "notes.md",
            "budget.xlsx",
            "design.png",
            "meeting-notes.txt",
            "code.py",
            "presentation.pptx",
            "photo.jpg",
        ]
        folder = folders[self._randint(0, len(folders) - 1)]
        name = names[self._randint(0, len(names) - 1)]
        return folder + name

    def _checksum(self, events: list[Event]) -> str:
        h = hashlib.sha256()
        for evt in events:
            h.update(evt.event_id.encode())
        return h.hexdigest()[:16]

    def _generate_planted_facts(self, day_epoch: int, day_seconds: int) -> list[Event]:
        """Generate deliberately planted fact notes at known positions."""
        facts: list[Event] = []
        fact_templates = [
            ("home address", "Lives at 123 Oak Street, Apt 4B"),
            ("phone number", "Phone ends with 5678"),
            ("favorite color", "Favorite color is navy blue"),
            ("coffee order", "Always orders oat milk latte"),
            ("gym schedule", "Gym is at 6am on Mon/Wed/Fri"),
            ("project name", "Main project is codenamed Horizon"),
            ("sister name", "Sister is named Riley"),
            ("birthday month", "Birthday is in July"),
            ("pet name", "Has a cat named Mochi"),
            ("commute time", "Commute is 45 minutes by train"),
        ]
        count = max(2, self.days // 15)
        rng = random.Random(self._seed_val + 1000)
        for i in range(count):
            template_idx = i % len(fact_templates)
            title, body = fact_templates[template_idx]
            day_offset = rng.randint(0, max(0, self.days - 1))
            hour = rng.randint(9, 20)
            minute = rng.randint(0, 59)
            ts = day_epoch + day_offset * day_seconds + hour * 3600 + minute * 60
            text = f"{title}: {body}"
            facts.append(note_event(ts, "laptop", text))
        return facts

    def _generate_planted_contradictions(self, day_epoch: int, day_seconds: int) -> list[Event]:
        """Generate pairs of conflicting facts at different times.

        The newer fact should supersede the older one in consolidation.
        """
        events: list[Event] = []
        contradiction_pairs = [
            (
                "home address",
                "Lives at 123 Oak Street, Apt 4B",
                "home address",
                "Lives at 456 Pine Avenue, Suite 12",
            ),
            (
                "meeting cadence",
                "Team meets every Monday at 10am",
                "meeting cadence",
                "Team meets every Tuesday at 2pm",
            ),
            (
                "reminder time",
                "Doctor appointment is March 15 at 9am",
                "reminder time",
                "Doctor appointment rescheduled to March 20 at 2pm",
            ),
        ]
        pair_count = max(1, min(len(contradiction_pairs), self.days // 30))
        rng = random.Random(self._seed_val + 2000)
        for i in range(pair_count):
            old_title, old_body, new_title, new_body = contradiction_pairs[i]
            # old fact in first third of period
            old_day = rng.randint(0, max(0, self.days // 3))
            # new fact in last third of period
            new_day = rng.randint(2 * self.days // 3, max(0, self.days - 1))
            old_ts = day_epoch + old_day * day_seconds + 10 * 3600
            new_ts = day_epoch + new_day * day_seconds + 14 * 3600
            events.append(note_event(old_ts, "phone", f"{old_title}: {old_body}"))
            events.append(note_event(new_ts, "laptop", f"{new_title}: {new_body}"))
        return events

    def _generate_planted_preferences(self, day_epoch: int, day_seconds: int) -> list[Event]:
        """Generate planted preference feedback signals."""
        events: list[Event] = []
        pref_targets = [
            ("brief_style", "concise"),
            ("brief_style", "detailed"),
            ("morning_preference", "early"),
            ("topic_priority", "work"),
            ("topic_priority", "personal"),
        ]
        count = max(5, self.days // 10)
        rng = random.Random(self._seed_val + 3000)
        for i in range(count):
            target_key, target_val = pref_targets[i % len(pref_targets)]
            day_offset = rng.randint(0, max(0, self.days - 1))
            hour = rng.randint(8, 22)
            minute = rng.randint(0, 59)
            ts = day_epoch + day_offset * day_seconds + hour * 3600 + minute * 60
            # Create a feedback event referencing a memory-like target id
            target_id = f"pref_{target_key}_{target_val}"
            rating = "up" if rng.random() > 0.3 else "down"
            events.append(
                Event.create(
                    "feedback_tap",
                    ts,
                    self._choice(self.persona.device_mix),
                    {
                        "target_id": target_id,
                        "rating": rating,
                        "preference_key": target_key,
                        "preference_value": target_val,
                    },
                )
            )
        return events

    def planted_ground_truth(self, start_date: str = "2026-01-01") -> dict[str, Any]:
        """Return ground truth about planted items for evaluation.

        This is the reference the evaluation harness compares against.
        """
        day_epoch = day_start_epoch(start_date, self.persona.timezone_offset)
        day_seconds = 86400
        facts = self._generate_planted_facts(day_epoch, day_seconds)
        contradictions = self._generate_planted_contradictions(day_epoch, day_seconds)
        prefs = self._generate_planted_preferences(day_epoch, day_seconds)
        return {
            "fact_ids": [e.event_id for e in facts],
            "contradiction_pairs": [
                (contradictions[i].event_id, contradictions[i + 1].event_id)
                for i in range(0, len(contradictions), 2)
            ],
            "preference_signals": [
                {
                    "event_id": e.event_id,
                    "key": e.data.get("preference_key", ""),
                    "value": e.data.get("preference_value", ""),
                    "rating": e.data.get("rating", ""),
                }
                for e in prefs
            ],
        }


def generate_history_with_truth(
    persona_id: str = "alex",
    seed: int = 0,
    days: int = 90,
    start_date: str = "2026-01-01",
) -> tuple[list[Event], HistoryManifest, dict[str, Any]]:
    """Generate history plus ground truth for evaluation."""
    persona = DEFAULT_PERSONAS.get(persona_id)
    if persona is None:
        raise ValueError(f"Unknown persona: {persona_id}")
    factory = HistoryFactory(persona, seed=seed, days=days)
    events, manifest = factory.generate(start_date=start_date)
    truth = factory.planted_ground_truth(start_date=start_date)
    return events, manifest, truth


def generate_history(
    persona_id: str = "alex",
    seed: int = 0,
    days: int = 90,
    start_date: str = "2026-01-01",
) -> tuple[list[Event], HistoryManifest]:
    """Convenience function to generate a synthetic history."""
    persona = DEFAULT_PERSONAS.get(persona_id)
    if persona is None:
        raise ValueError(f"Unknown persona: {persona_id}")
    factory = HistoryFactory(persona, seed=seed, days=days)
    return factory.generate(start_date=start_date)


GOLDEN_FIXTURES: dict[tuple[str, int, int, str], dict[str, object]] = {
    ("alex", 42, 1, "2025-01-06"): {
        "persona_id": "alex",
        "seed": 42,
        "days": 1,
        "start_date": "2025-01-06",
        "end_date": "2025-01-06",
        "event_count": 11,
        "by_type": {"feedback_tap": 5, "note": 6},
        "planted_fact_count": 2,
        "planted_contradiction_count": 1,
        "planted_preference_count": 5,
        "checksum": "5421cd094e11b6d5",
    },
}


def golden_fixture_keys() -> list[tuple[str, int, int, str]]:
    """Return the list of registered golden fixture keys."""
    return sorted(GOLDEN_FIXTURES.keys())


def list_personas() -> list[str]:
    """Return available persona ids."""
    return sorted(DEFAULT_PERSONAS.keys())


def factory_manifest_summary(manifest: HistoryManifest) -> dict[str, object]:
    """Return summary of factory manifest."""
    return {
        "persona_id": manifest.persona_id,
        "seed": manifest.seed,
        "days": manifest.days,
        "event_count": manifest.event_count,
    }
