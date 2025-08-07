"""Tests for the synthetic personal history factory."""

from __future__ import annotations

import hashlib

import pytest

from famulix.events import Event
from famulix.factory import (
    DEFAULT_PERSONAS,
    HistoryFactory,
    HistoryManifest,
    generate_history,
    generate_history_with_truth,
    list_personas,
    persona_digest,
)


def test_list_personas_returns_sorted_ids():
    personas = list_personas()
    assert len(personas) >= 2
    assert personas == sorted(personas)
    assert "alex" in personas
    assert "bailey" in personas


def test_persona_digest_deterministic():
    d1 = persona_digest("alex", 42)
    d2 = persona_digest("alex", 42)
    assert d1 == d2


def test_persona_digest_different_inputs_differ():
    d1 = persona_digest("alex", 42)
    d2 = persona_digest("alex", 43)
    d3 = persona_digest("bailey", 42)
    assert d1 != d2
    assert d1 != d3


def test_factory_returns_events_and_manifest():
    events, manifest = generate_history("alex", seed=0, days=7)
    assert isinstance(events, list)
    assert len(events) > 0
    assert isinstance(manifest, HistoryManifest)
    assert manifest.persona_id == "alex"
    assert manifest.days == 7
    assert manifest.event_count == len(events)
    assert manifest.checksum


def test_factory_determinism_same_seed():
    events1, m1 = generate_history("alex", seed=42, days=30)
    events2, m2 = generate_history("alex", seed=42, days=30)
    assert [e.event_id for e in events1] == [e.event_id for e in events2]
    assert m1.checksum == m2.checksum
    assert m1.event_count == m2.event_count


def test_factory_different_seeds_produce_different_histories():
    events1, m1 = generate_history("alex", seed=1, days=30)
    events2, m2 = generate_history("alex", seed=2, days=30)
    # checksums should differ
    assert m1.checksum != m2.checksum
    # not necessarily same count, but both should have events
    assert m1.event_count > 0
    assert m2.event_count > 0


def test_factory_different_personas_produce_different_histories():
    events1, m1 = generate_history("alex", seed=42, days=30)
    events2, m2 = generate_history("bailey", seed=42, days=30)
    assert m1.checksum != m2.checksum


def test_events_have_valid_types():
    events, _ = generate_history("alex", seed=0, days=14)
    valid_types = {"note", "message", "calendar_item", "file_touch", "feedback_tap"}
    for evt in events:
        assert evt.event_type in valid_types
        assert isinstance(evt, Event)
        assert evt.event_id.startswith("evt_")
        assert evt.timestamp_s > 0


def test_events_sorted_by_timestamp():
    events, _ = generate_history("alex", seed=0, days=30)
    timestamps = [e.timestamp_s for e in events]
    assert timestamps == sorted(timestamps)


def test_manifest_by_type_counts_match():
    events, manifest = generate_history("alex", seed=0, days=30)
    actual_counts: dict[str, int] = {}
    for evt in events:
        actual_counts[evt.event_type] = actual_counts.get(evt.event_type, 0) + 1
    assert actual_counts == manifest.by_type


def test_manifest_planted_counts_reasonable():
    _, manifest = generate_history("alex", seed=0, days=90)
    assert manifest.planted_fact_count > 0
    assert manifest.planted_contradiction_count > 0
    assert manifest.planted_preference_count > 0
    assert manifest.planted_contradiction_count < manifest.planted_fact_count


def test_factory_short_history_one_day():
    events, manifest = generate_history("alex", seed=7, days=1)
    assert manifest.days == 1
    assert manifest.start_date == manifest.end_date
    assert len(events) == manifest.event_count


def test_factory_start_date_reflected_in_manifest():
    events, manifest = generate_history("alex", seed=0, days=5, start_date="2026-03-15")
    assert manifest.start_date == "2026-03-15"
    assert manifest.end_date == "2026-03-19"
    # first event should be on or after start date
    first_ts = events[0].timestamp_s
    from famulix.clock import day_start_epoch

    start_epoch = day_start_epoch("2026-03-15", DEFAULT_PERSONAS["alex"].timezone_offset)
    assert first_ts >= start_epoch


def test_generate_history_unknown_persona_raises():
    with pytest.raises(ValueError, match="Unknown persona"):
        generate_history("nonexistent", seed=0, days=1)


def test_default_personas_have_required_fields():
    for pid, persona in DEFAULT_PERSONAS.items():
        assert persona.persona_id == pid
        assert persona.name
        assert -12 <= persona.timezone_offset <= 14
        assert 0 <= persona.work_start_hour < 24
        assert 0 < persona.work_end_hour <= 24
        assert persona.work_start_hour < persona.work_end_hour
        assert len(persona.goals) > 0
        assert len(persona.device_mix) > 0


@pytest.mark.parametrize(
    "changes",
    [
        {"timezone_offset": 15},
        {"work_start_hour": 18, "work_end_hour": 9},
        {"note_frequency": 1.01},
        {"calendar_frequency": -0.1},
        {"device_mix": ()},
        {"name": " "},
    ],
)
def test_persona_profile_rejects_invalid_generation_settings(changes: dict[str, object]) -> None:
    from dataclasses import replace

    with pytest.raises(ValueError):
        replace(DEFAULT_PERSONAS["alex"], **changes)


@pytest.mark.parametrize("days", [0, -1, 1.5])
def test_history_factory_requires_positive_whole_days(days: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        HistoryFactory(DEFAULT_PERSONAS["alex"], days=days)


def test_factory_direct_construction():
    persona = DEFAULT_PERSONAS["alex"]
    factory = HistoryFactory(persona, seed=123, days=10)
    events, manifest = factory.generate()
    assert manifest.days == 10
    assert manifest.persona_id == "alex"
    assert len(events) > 0


def test_planted_facts_present_in_events():
    events, manifest = generate_history("alex", seed=0, days=60)
    assert manifest.planted_fact_count > 0
    assert manifest.planted_contradiction_count > 0
    assert manifest.planted_preference_count > 0
    # feedback taps include preference signals
    assert manifest.by_type.get("feedback_tap", 0) >= manifest.planted_preference_count


def test_generate_history_with_truth_returns_ground_truth():
    events, manifest, truth = generate_history_with_truth("alex", seed=7, days=90)
    assert "fact_ids" in truth
    assert "contradiction_pairs" in truth
    assert "preference_signals" in truth
    assert len(truth["fact_ids"]) == manifest.planted_fact_count
    assert len(truth["contradiction_pairs"]) == manifest.planted_contradiction_count
    assert len(truth["preference_signals"]) == manifest.planted_preference_count


def test_planted_fact_ids_exist_in_event_stream():
    events, _, truth = generate_history_with_truth("alex", seed=42, days=30)
    event_ids = {e.event_id for e in events}
    for fid in truth["fact_ids"]:
        assert fid in event_ids
    for old_id, new_id in truth["contradiction_pairs"]:
        assert old_id in event_ids
        assert new_id in event_ids


def test_contradiction_pairs_have_newer_second_event():
    events, _, truth = generate_history_with_truth("alex", seed=42, days=60)
    event_by_id = {e.event_id: e for e in events}
    for old_id, new_id in truth["contradiction_pairs"]:
        old_evt = event_by_id[old_id]
        new_evt = event_by_id[new_id]
        assert new_evt.timestamp_s > old_evt.timestamp_s


def test_ground_truth_deterministic():
    _, _, t1 = generate_history_with_truth("alex", seed=5, days=30)
    _, _, t2 = generate_history_with_truth("alex", seed=5, days=30)
    assert t1["fact_ids"] == t2["fact_ids"]
    assert t1["contradiction_pairs"] == t2["contradiction_pairs"]
    assert t1["preference_signals"] == t2["preference_signals"]


def test_planted_preferences_have_key_value_rating():
    _, _, truth = generate_history_with_truth("alex", seed=0, days=30)
    for sig in truth["preference_signals"]:
        assert "event_id" in sig
        assert "key" in sig
        assert "value" in sig
        assert sig["rating"] in {"up", "down", "skip"}


def test_short_history_still_has_planted_items():
    events, manifest = generate_history("alex", seed=0, days=7)
    # Even a 1-week history should have some planted content
    assert manifest.planted_fact_count >= 1
    assert manifest.planted_contradiction_count >= 1
    assert manifest.planted_preference_count >= 1


def test_manifest_planted_total_matches_components():
    _, manifest = generate_history("alex", seed=0, days=14)
    total = manifest.planted_total()
    assert total == (
        manifest.planted_fact_count
        + manifest.planted_contradiction_count
        + manifest.planted_preference_count
    )
    assert total > 0


def test_manifest_to_dict_round_trip_values():
    _, manifest = generate_history("alex", seed=42, days=10)
    d = manifest.to_dict()
    assert d["persona_id"] == manifest.persona_id
    assert d["seed"] == manifest.seed
    assert d["event_count"] == manifest.event_count
    assert d["checksum"] == manifest.checksum
    assert set(d.keys()) >= {
        "persona_id",
        "seed",
        "days",
        "start_date",
        "end_date",
        "event_count",
        "by_type",
        "planted_fact_count",
        "planted_contradiction_count",
        "planted_preference_count",
        "checksum",
    }


from famulix.envelope import Envelope  # noqa: E402

GOLDEN_JSONL_DIGEST = "07b2cd52aaf65f7fe26e3243bf9d0d7bcdc54e138e3f1dac2fa45f3803ec289e"


def _golden_history():
    return generate_history("alex", seed=7, days=3, start_date="2026-03-02")


def test_small_history_golden_fixture() -> None:
    """Golden digests for a tiny seeded history (synthetic data).

    Constants were recorded from an actual run of the factory; update them
    only when a factory change is deliberate.
    """
    events, manifest = _golden_history()
    lines = [event.to_envelope().to_jsonl_line() for event in events]
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    assert digest == GOLDEN_JSONL_DIGEST
    assert manifest.checksum == "adf3f2ca7f67e3c5"
    assert manifest.event_count == len(events) == 27
    assert manifest.by_type == {
        "calendar_item": 7,
        "feedback_tap": 6,
        "note": 6,
        "message": 2,
        "file_touch": 6,
    }
    assert manifest.planted_fact_count == 2
    assert manifest.planted_contradiction_count == 1
    assert manifest.planted_preference_count == 5
    assert events[0].event_id == "evt_68d252dc1dc6b23df288bab4"
    assert events[-1].event_id == "evt_8aeaad77275feb6416e5ea09"


def test_small_history_golden_survives_envelope_roundtrip() -> None:
    """Decoding and re-encoding every envelope reproduces the golden digest."""
    events, _manifest = _golden_history()
    restored = [
        Event.from_envelope(Envelope.from_jsonl_line(event.to_envelope().to_jsonl_line()))
        for event in events
    ]
    lines = [event.to_envelope().to_jsonl_line() for event in restored]
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    assert digest == GOLDEN_JSONL_DIGEST
