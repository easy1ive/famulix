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
