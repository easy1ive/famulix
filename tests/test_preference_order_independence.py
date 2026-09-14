"""Tests for preference learning order-independence where specified."""

from famulix.preferences import PreferenceProfile


def test_feedback_order_entry_count():
    """Adding feedback A then B should yield the same entry count as B then A."""
    p1 = PreferenceProfile()
    p1.add_feedback(
        pref_key="tone",
        value="concise",
        signal="up",
        timestamp_s=100,
        confidence=0.8,
        source="user",
    )
    p1.add_feedback(
        pref_key="tone",
        value="detailed",
        signal="down",
        timestamp_s=200,
        confidence=0.6,
        source="user",
    )

    p2 = PreferenceProfile()
    p2.add_feedback(
        pref_key="tone",
        value="detailed",
        signal="down",
        timestamp_s=200,
        confidence=0.6,
        source="user",
    )
    p2.add_feedback(
        pref_key="tone",
        value="concise",
        signal="up",
        timestamp_s=100,
        confidence=0.8,
        source="user",
    )

    assert len(p1.entries) == len(p2.entries)


def test_multiple_keys_independent():
    """Feedback for different keys should not interfere."""
    p = PreferenceProfile()
    p.add_feedback(
        pref_key="tone",
        value="concise",
        signal="up",
        timestamp_s=100,
        confidence=0.8,
        source="user",
    )
    p.add_feedback(
        pref_key="format",
        value="markdown",
        signal="accept",
        timestamp_s=200,
        confidence=0.9,
        source="user",
    )

    profile = p.current_preferences(now_s=300)
    assert "tone" in profile
    assert "format" in profile


def test_confidence_decay_over_time():
    """Confidence should decrease as time passes since last feedback."""
    p = PreferenceProfile()
    p.add_feedback(
        pref_key="tone", value="concise", signal="up", timestamp_s=0, confidence=0.9, source="user"
    )

    early = p.current_preferences(now_s=100)
    late = p.current_preferences(now_s=100000)

    early_conf = early["tone"][1]  # (value, confidence) tuple
    late_conf = late["tone"][1]
    assert late_conf <= early_conf


def test_profile_deterministic():
    """Same inputs produce identical profile."""
    p1 = PreferenceProfile()
    p1.add_feedback(
        pref_key="tone",
        value="concise",
        signal="up",
        timestamp_s=100,
        confidence=0.8,
        source="user",
    )
    prof1 = p1.current_preferences(now_s=200)

    p2 = PreferenceProfile()
    p2.add_feedback(
        pref_key="tone",
        value="concise",
        signal="up",
        timestamp_s=100,
        confidence=0.8,
        source="user",
    )
    prof2 = p2.current_preferences(now_s=200)

    assert prof1 == prof2
