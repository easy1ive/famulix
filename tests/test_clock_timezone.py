"""Tests for deterministic clock and timezone-safe day boundaries."""

from famulix.clock import day_start_epoch


def test_day_start_epoch_utc():
    """Day start at midnight UTC for offset 0."""
    result = day_start_epoch("2026-03-15", tz_offset_hours=0)
    assert result == 1773532800  # 2026-03-15T00:00:00Z


def test_day_start_epoch_positive_offset():
    """Positive offset shifts day start earlier in UTC."""
    utc = day_start_epoch("2026-03-15", tz_offset_hours=0)
    plus8 = day_start_epoch("2026-03-15", tz_offset_hours=8)
    assert plus8 == utc - 8 * 3600


def test_day_start_epoch_negative_offset():
    """Negative offset shifts day start later in UTC."""
    utc = day_start_epoch("2026-03-15", tz_offset_hours=0)
    minus5 = day_start_epoch("2026-03-15", tz_offset_hours=-5)
    assert minus5 == utc + 5 * 3600


def test_day_start_deterministic():
    """Same inputs produce identical output."""
    r1 = day_start_epoch("2026-06-01", tz_offset_hours=5)
    r2 = day_start_epoch("2026-06-01", tz_offset_hours=5)
    assert r1 == r2


def test_day_start_different_dates():
    """Different dates produce different epoch values."""
    d1 = day_start_epoch("2026-03-15", tz_offset_hours=0)
    d2 = day_start_epoch("2026-03-16", tz_offset_hours=0)
    assert d2 - d1 == 86400


def test_day_start_leap_year():
    """Feb 29 on a leap year works correctly."""
    result = day_start_epoch("2028-02-29", tz_offset_hours=0)
    assert result > 0


def test_day_start_year_boundary():
    """Dec 31 to Jan 1 crosses correctly."""
    dec31 = day_start_epoch("2026-12-31", tz_offset_hours=0)
    jan1 = day_start_epoch("2027-01-01", tz_offset_hours=0)
    assert jan1 - dec31 == 86400
