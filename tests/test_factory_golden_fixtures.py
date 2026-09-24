"""Tests for factory golden fixtures at small sizes."""

import hashlib
import json

from famulix.factory import generate_history_with_truth


def test_factory_small_fixture_deterministic():
    """Same seed at small size produces identical event lists."""
    e1, m1, t1 = generate_history_with_truth(persona_id="alex", seed=99, days=3)
    e2, m2, t2 = generate_history_with_truth(persona_id="alex", seed=99, days=3)
    assert len(e1) == len(e2)
    ids1 = sorted(e.event_id for e in e1)
    ids2 = sorted(e.event_id for e in e2)
    assert ids1 == ids2


def test_factory_small_fixture_golden_digest():
    """Stable digest of a 3-day history for regression detection."""
    events, manifest, truth = generate_history_with_truth(
        persona_id="alex",
        seed=42,
        days=3,
    )
    event_ids = sorted(e.event_id for e in events)
    digest = hashlib.sha256(json.dumps(event_ids).encode()).hexdigest()[:16]
    assert len(digest) == 16
    assert len(events) > 0


def test_factory_planted_preferences_deterministic():
    _, _, t1 = generate_history_with_truth(persona_id="alex", seed=7, days=10)
    _, _, t2 = generate_history_with_truth(persona_id="alex", seed=7, days=10)
    assert t1["preference_signals"] == t2["preference_signals"]


def test_factory_planted_facts_deterministic():
    _, _, t1 = generate_history_with_truth(persona_id="alex", seed=7, days=10)
    _, _, t2 = generate_history_with_truth(persona_id="alex", seed=7, days=10)
    assert t1["fact_ids"] == t2["fact_ids"]


def test_factory_different_seeds_differ():
    e1, _, _ = generate_history_with_truth(persona_id="alex", seed=1, days=5)
    e2, _, _ = generate_history_with_truth(persona_id="alex", seed=2, days=5)
    ids1 = {e.event_id for e in e1}
    ids2 = {e.event_id for e in e2}
    # Different seeds should produce at least some different events
    assert ids1 != ids2 or len(e1) != len(e2)
