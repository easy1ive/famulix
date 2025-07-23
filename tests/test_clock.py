"""Tests for synthetic clock and day bucketing."""

from __future__ import annotations

from datetime import UTC, timedelta, timezone

from famulix.clock import SyntheticClock, day_start_epoch


def test_clock_now_returns_aware_datetime() -> None:
    clock = SyntheticClock(start_timestamp_s=1_700_000_000, tz_offset_hours=8)
    now = clock.now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(hours=8)


def test_clock_advance() -> None:
    clock = SyntheticClock(start_timestamp_s=1_700_000_000)
    later = clock.advance(3600)
    diff = later.now() - clock.now()
    assert diff == timedelta(hours=1)


def test_clock_deterministic() -> None:
    a = SyntheticClock(start_timestamp_s=1_700_000_000, offset_seconds=100)
    b = SyntheticClock(start_timestamp_s=1_700_000_000, offset_seconds=100)
    assert a.now() == b.now()


def test_day_bucket_returns_iso_date() -> None:
    clock = SyntheticClock(start_timestamp_s=1_700_000_000, tz_offset_hours=8)
    bucket = clock.day_bucket()
    assert len(bucket) == 10
    assert bucket[4] == "-" and bucket[7] == "-"


def test_advance_one_day_changes_bucket() -> None:
    clock = SyntheticClock(start_timestamp_s=1_700_000_000, tz_offset_hours=0)
    day1 = clock.day_bucket()
    later = clock.advance(86400)
    day2 = later.day_bucket()
    assert day1 != day2


def test_day_start_epoch_matches_date() -> None:
    ts = day_start_epoch("2024-01-15", tz_offset_hours=8)
    from datetime import datetime

    dt = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8)))
    assert dt.hour == 0
    assert dt.minute == 0
    assert dt.date().isoformat() == "2024-01-15"


def test_day_bucket_from_explicit_dt() -> None:
    clock = SyntheticClock(start_timestamp_s=0, tz_offset_hours=8)
    from datetime import datetime

    dt = datetime.fromtimestamp(0, tz=UTC)
    bucket = clock.day_bucket(dt)
    assert bucket == "1970-01-01"


def test_day_bounds_epoch_is_24h() -> None:
    from famulix.clock import day_bounds_epoch

    start, end = day_bounds_epoch("2026-01-15")
    assert end - start == 86400
    # start matches day_start_epoch
    from famulix.clock import day_start_epoch

    assert start == day_start_epoch("2026-01-15")


def test_week_bounds_epoch_is_7days_from_monday() -> None:
    from famulix.clock import week_bounds_epoch

    # 2026-01-15 is a Thursday
    start, end = week_bounds_epoch("2026-01-15")
    assert end - start == 86400 * 7
    # Monday is 2026-01-12
    from datetime import datetime, timedelta, timezone

    tz = timezone(timedelta(hours=8))
    monday = datetime(2026, 1, 12, 0, 0, tzinfo=tz)
    assert start == int(monday.timestamp())


def test_week_bounds_on_monday_starts_same_day() -> None:
    from famulix.clock import week_bounds_epoch

    # 2026-01-12 is a Monday
    start, end = week_bounds_epoch("2026-01-12")
    assert end - start == 86400 * 7
    from datetime import datetime, timedelta, timezone

    tz = timezone(timedelta(hours=8))
    expected_start = datetime(2026, 1, 12, 0, 0, tzinfo=tz)
    assert start == int(expected_start.timestamp())
