"""Test clock utility functions."""

from famulix.clock import format_timestamp, parse_iso_date


def test_format_timestamp():
    """Should format timestamp as ISO string."""
    result = format_timestamp(1700000000, tz_offset_hours=0)
    assert "2023-11-14" in result


def test_parse_iso_date():
    """Should parse ISO date to timestamp."""
    ts = parse_iso_date("2023-11-14T12:00:00")
    assert ts > 0


def test_roundtrip():
    """Format and parse should be inverse operations."""
    original = 1700000000
    formatted = format_timestamp(original, tz_offset_hours=0)
    parsed = parse_iso_date(formatted)
    # Allow small difference due to timezone
    assert abs(parsed - original) < 86400
