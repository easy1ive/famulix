"""Golden fixture test for small synthetic history."""

from famulix.factory import generate_history


def test_factory_golden_small():
    """Verify small history generation is deterministic."""
    events1, manifest1 = generate_history(persona_id="alex", seed=42, days=7)
    events2, manifest2 = generate_history(persona_id="alex", seed=42, days=7)

    assert len(events1) == len(events2)
    assert manifest1.persona_id == manifest2.persona_id

    for e1, e2 in zip(events1, events2, strict=True):
        assert e1.event_id == e2.event_id
        assert e1.timestamp_s == e2.timestamp_s


def test_factory_golden_plants_facts():
    """Verify facts are planted."""
    events, manifest = generate_history(persona_id="alex", seed=42, days=30)

    assert manifest.planted_fact_count > 0


def test_factory_golden_plants_preferences():
    """Verify preferences are planted."""
    events, manifest = generate_history(persona_id="alex", seed=42, days=30)

    assert manifest.planted_preference_count > 0
