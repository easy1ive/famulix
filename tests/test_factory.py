"""Tests for the synthetic personal history factory."""

from __future__ import annotations

import pytest

from famulix.events import Event
from famulix.factory import (
    DEFAULT_PERSONAS,
    HistoryFactory,
    HistoryManifest,
    generate_history,
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


def test_factory_direct_construction():
    persona = DEFAULT_PERSONAS["alex"]
    factory = HistoryFactory(persona, seed=123, days=10)
    events, manifest = factory.generate()
    assert manifest.days == 10
    assert manifest.persona_id == "alex"
    assert len(events) > 0
