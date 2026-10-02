"""Tests for personalization cold-start defaults and preference application."""

from famulix.personalization import PersonalizationConfig, apply_preferences
from famulix.preferences import PreferenceProfile


def test_cold_start_returns_defaults():
    """Empty profile should yield cold-start defaults."""
    profile = PreferenceProfile()
    style = apply_preferences(profile, now_s=1000)
    assert style.tone is not None
    assert style.format is not None


def test_learned_preference_applied():
    """A confident preference should override the default."""
    profile = PreferenceProfile()
    profile.add_feedback(
        pref_key="tone",
        value="concise",
        signal="up",
        timestamp_s=0,
        confidence=0.9,
        source="user",
    )
    style = apply_preferences(profile, now_s=100)
    assert style.tone == "concise"


def test_config_overrides():
    """PersonalizationConfig can supply custom defaults."""
    config = PersonalizationConfig()
    profile = PreferenceProfile()
    style = apply_preferences(profile, now_s=1000, config=config)
    assert style is not None


def test_apply_preferences_deterministic():
    """Same inputs produce identical output."""
    p1 = PreferenceProfile()
    p1.add_feedback(
        pref_key="tone", value="concise", signal="up", timestamp_s=0, confidence=0.8, source="user"
    )
    s1 = apply_preferences(p1, now_s=100)

    p2 = PreferenceProfile()
    p2.add_feedback(
        pref_key="tone", value="concise", signal="up", timestamp_s=0, confidence=0.8, source="user"
    )
    s2 = apply_preferences(p2, now_s=100)

    assert s1.tone == s2.tone
    assert s1.format == s2.format
