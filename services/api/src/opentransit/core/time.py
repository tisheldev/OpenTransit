"""Offset-aware instant helpers for schedule normalization.

Service dates are separate GTFS identities. These functions parse and compare
instants only; local time conversion is an explicit display operation.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

JERUSALEM = ZoneInfo("Asia/Jerusalem")


def parse_utc_instant(value: str) -> datetime:
    """Parse ISO-8601 with an explicit offset and normalize it to UTC."""
    if not isinstance(value, str) or not value:
        raise ValueError("Expected an ISO-8601 instant with an explicit UTC offset")
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("Invalid ISO-8601 instant") from exc
    return as_utc_instant(parsed)


def as_utc_instant(value: datetime) -> datetime:
    """Require an aware datetime and normalize it to UTC."""
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Datetime must include an explicit UTC offset")
    if value.utcoffset() is None:
        raise ValueError("Datetime must include an explicit UTC offset")
    return value.astimezone(UTC)


def engine_time(value: datetime) -> str:
    """Serialize an aware instant for a MOTIS query parameter, truncated to whole seconds.

    MOTIS v2.11.2 parses `%FT%T%Ez` into milliseconds (openapi-cpp/HowardHinnant date):
    fractional digits after the third are read as the UTC-offset hours and the real offset
    is ignored, so `datetime.isoformat()` with microseconds shifts the query by 0-99 hours.
    """
    offset = value.utcoffset() if isinstance(value, datetime) else None
    if offset is None:
        raise ValueError("Datetime must include an explicit UTC offset")
    if offset % timedelta(minutes=1):
        value = value.astimezone(UTC)
    return value.isoformat(timespec="seconds")


def is_before(left: datetime, right: datetime) -> bool:
    """Compare two aware datetimes as UTC instants, not local wall times."""
    return as_utc_instant(left) < as_utc_instant(right)


def checked_duration_seconds(start: datetime, end: datetime) -> float:
    """Return elapsed seconds, rejecting an end instant before its start."""
    start_utc, end_utc = as_utc_instant(start), as_utc_instant(end)
    if end_utc < start_utc:
        raise ValueError("End instant precedes start instant")
    return (end_utc - start_utc).total_seconds()


def to_local_display(value: datetime) -> datetime:
    """Convert an aware instant for Asia/Jerusalem display only."""
    return as_utc_instant(value).astimezone(JERUSALEM)
