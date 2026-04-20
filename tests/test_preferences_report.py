"""Test preference profile report generation."""

from famulix.preferences import PreferenceProfile


def test_preference_report_empty():
    """Verify report for empty profile."""
    profile = PreferenceProfile()
    report = profile.generate_report(now_s=1000)

    assert "# Preference Profile Report" in report
    assert "**Version**: 1" in report
    assert "**Total entries**: 0" in report
    assert "No preferences with sufficient confidence" in report


def test_preference_report_with_entries():
    """Verify report includes current preferences."""
    profile = PreferenceProfile()
    profile.add_feedback("tone", "formal", "up", timestamp_s=100, confidence=0.8)
    profile.add_feedback("tone", "formal", "up", timestamp_s=200, confidence=0.9)
    profile.add_feedback("format", "brief", "accept", timestamp_s=150, confidence=0.7)

    report = profile.generate_report(now_s=300)

    assert "**Total entries**: 3" in report
    assert "**Unique keys**: 2" in report
    assert "## Current Preferences" in report
    assert "### tone" in report
    assert "### format" in report
    assert "**Preferred value**: formal" in report
    assert "**Preferred value**: brief" in report


def test_preference_report_with_decay():
    """Verify report reflects decay over time."""
    profile = PreferenceProfile()
    # Old preference
    profile.add_feedback("topic", "sports", "up", timestamp_s=100, confidence=0.9)
    # Recent preference
    profile.add_feedback("topic", "tech", "up", timestamp_s=10000, confidence=0.9)

    report = profile.generate_report(now_s=10100)

    assert "### topic" in report
    # Recent preference should dominate
    assert "**Preferred value**: tech" in report
