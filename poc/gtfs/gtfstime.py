"""GTFS service-day time arithmetic.

The single most common transit-data bug (corpus check E02) is treating
`25:30:00` as invalid, or truncating it to `01:30:00` on the *wrong* calendar
day. In GTFS a time is an offset from noon-minus-12h of the **service day**,
so `25:30:00` is 01:30 on the calendar day after the service day started, and
it still belongs to the earlier service day.

Nothing in this module clamps, wraps or errors on hours >= 24.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

# GTFS allows H:MM:SS as well as HH:MM:SS, and hours are unbounded above.
_TIME_RE = re.compile(r"^(\d{1,3}):([0-5]\d):([0-5]\d)$")


class GtfsTimeError(ValueError):
    pass


def parse_gtfs_time(value: str | None) -> int | None:
    """'25:30:00' -> 91800 seconds from the start of the service day.

    Returns None for an empty value (GTFS permits blank arrival/departure on
    non-timepoint rows). Raises GtfsTimeError on anything else, deliberately:
    a silently dropped time is worse than a loud failure.
    """
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    m = _TIME_RE.match(v)
    if not m:
        raise GtfsTimeError(f"not a GTFS time: {value!r}")
    h, mi, s = (int(g) for g in m.groups())
    return h * 3600 + mi * 60 + s


def format_gtfs_time(seconds: int) -> str:
    """91800 -> '25:30:00'. Exact inverse of parse_gtfs_time for HH:MM:SS."""
    if seconds < 0:
        raise GtfsTimeError(f"negative service-day offset: {seconds}")
    h, rem = divmod(seconds, 3600)
    mi, s = divmod(rem, 60)
    return f"{h:02d}:{mi:02d}:{s:02d}"


def day_offset(seconds: int) -> int:
    """How many calendar days past the service-day date this time falls on."""
    return seconds // 86400


def wall_clock(service_day: date, seconds: int) -> datetime:
    """Absolute local wall clock for a service-day offset.

    (2026-09-06, 91800) -> 2026-09-07 01:30:00 — next calendar day, same
    service day. Naive datetime; the feed's agency_timezone is Asia/Jerusalem
    and the POC does not need tz-aware arithmetic to prove this property.
    """
    return datetime(service_day.year, service_day.month, service_day.day) + timedelta(
        seconds=seconds
    )


def clock_only(seconds: int) -> str:
    """'25:30:00' -> '01:30:00'. Use only for display; never for storage."""
    return format_gtfs_time(seconds % 86400)
