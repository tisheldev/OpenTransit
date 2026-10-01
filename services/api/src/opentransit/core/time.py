"""Offset-aware instant helpers for schedule normalization.

Service dates are separate GTFS identities. These functions parse and compare
instants only; local time conversion is an explicit display operation.
"""

from datetime import UTC, datetime
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
