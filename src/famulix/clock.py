"""Synthetic deterministic clock and timezone-safe day bucketing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class SyntheticClock:
    """A deterministic clock for tests and synthetic history generation."""

    start_timestamp_s: int
    offset_seconds: int = 0
    tz_offset_hours: int = 8

    def now(self) -> datetime:
        tz = timezone(timedelta(hours=self.tz_offset_hours))
        return datetime.fromtimestamp(self.start_timestamp_s + self.offset_seconds, tz=tz)

    def advance(self, seconds: int) -> SyntheticClock:
        return SyntheticClock(
            start_timestamp_s=self.start_timestamp_s,
            offset_seconds=self.offset_seconds + seconds,
            tz_offset_hours=self.tz_offset_hours,
        )

    def day_bucket(self, dt: datetime | None = None) -> str:
        if dt is None:
            dt = self.now()
        local = dt.astimezone(timezone(timedelta(hours=self.tz_offset_hours)))
        return local.date().isoformat()


def day_start_epoch(date_str: str, tz_offset_hours: int = 8) -> int:
    """Return epoch seconds for 00:00 on the given local date."""
    d = datetime.fromisoformat(date_str)
    tz = timezone(timedelta(hours=tz_offset_hours))
    dt = d.replace(tzinfo=tz)
    return int(dt.timestamp())


def day_bounds_epoch(date_str: str, tz_offset_hours: int = 8) -> tuple[int, int]:
    """Return (start, end) epoch seconds for the given local date.

    End is exclusive (start of the next day).
    """
    start = day_start_epoch(date_str, tz_offset_hours)
    d = datetime.fromisoformat(date_str)
    tz = timezone(timedelta(hours=tz_offset_hours))
    next_day = d.replace(tzinfo=tz) + timedelta(days=1)
    return start, int(next_day.timestamp())


def week_bounds_epoch(date_str: str, tz_offset_hours: int = 8) -> tuple[int, int]:
    """Return (start, end) epoch seconds for the Monday-starting week.

    End is exclusive (start of the next Monday).
    """
    d = datetime.fromisoformat(date_str)
    tz = timezone(timedelta(hours=tz_offset_hours))
    # Monday = 0 in weekday()
    monday = d.replace(tzinfo=tz) - timedelta(days=d.weekday())
    next_monday = monday + timedelta(days=7)
    return int(monday.timestamp()), int(next_monday.timestamp())


def validate_timezone_offset(tz_offset_hours: int) -> list[str]:
    """Validate a timezone offset in hours. Returns list of problems."""
    problems: list[str] = []
    if type(tz_offset_hours) is not int:
        problems.append(f"tz_offset_hours must be an integer, got {type(tz_offset_hours).__name__}")
    elif not -12 <= tz_offset_hours <= 14:
        problems.append(f"tz_offset_hours must be in [-12, 14], got {tz_offset_hours}")
    return problems


def timestamp_to_local(timestamp_s: int, tz_offset_hours: int = 8) -> str:
    """Convert epoch seconds to ISO format local date-time string."""
    tz = timezone(timedelta(hours=tz_offset_hours))
    dt = datetime.fromtimestamp(timestamp_s, tz=tz)
    return dt.isoformat()


def is_within_time_range(
    timestamp_s: int,
    start_s: int,
    end_s: int,
) -> bool:
    """Check if a timestamp falls within [start_s, end_s)."""
    return start_s <= timestamp_s < end_s


def count_days_between(start_date: str, end_date: str) -> int:
    """Count the number of days between two ISO date strings (inclusive)."""
    d1 = datetime.fromisoformat(start_date).date()
    d2 = datetime.fromisoformat(end_date).date()
    delta = (d2 - d1).days
    return delta + 1 if delta >= 0 else 0


def generate_date_range(start_date: str, end_date: str) -> list[str]:
    """Generate a list of ISO date strings from start to end (inclusive)."""
    d1 = datetime.fromisoformat(start_date).date()
    d2 = datetime.fromisoformat(end_date).date()
    dates: list[str] = []
    current = d1
    while current <= d2:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates
