"""Test trigger quiet hours enforcement."""

from famulix.triggers import is_quiet_hours


def test_quiet_hours_blocks_night():
    assert is_quiet_hours(hour=2, quiet_start=22, quiet_end=8)
    assert is_quiet_hours(hour=23, quiet_start=22, quiet_end=8)


def test_quiet_hours_allows_day():
    assert not is_quiet_hours(hour=10, quiet_start=22, quiet_end=8)
    assert not is_quiet_hours(hour=20, quiet_start=22, quiet_end=8)


def test_quiet_hours_boundary():
    assert is_quiet_hours(hour=22, quiet_start=22, quiet_end=8)
    assert not is_quiet_hours(hour=8, quiet_start=22, quiet_end=8)
