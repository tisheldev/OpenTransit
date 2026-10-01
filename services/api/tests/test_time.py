from datetime import UTC, datetime

import pytest

from opentransit.core.time import (
    as_utc_instant,
    checked_duration_seconds,
    is_before,
    parse_utc_instant,
    to_local_display,
)


def test_dst_fallback_duration_uses_utc_instants():
    before = parse_utc_instant("2026-10-25T01:50:00+03:00")
    after = parse_utc_instant("2026-10-25T01:10:00+02:00")

    assert checked_duration_seconds(before, after) == 1200
    assert is_before(before, after)
    assert to_local_display(before).isoformat() == "2026-10-25T01:50:00+03:00"
    assert to_local_display(after).isoformat() == "2026-10-25T01:10:00+02:00"


def test_reverse_utc_order_is_rejected():
    start = parse_utc_instant("2026-10-25T01:10:00+02:00")
    end = parse_utc_instant("2026-10-25T01:50:00+03:00")

    assert is_before(start, end) is False
    with pytest.raises(ValueError, match="precedes"):
        checked_duration_seconds(start, end)


def test_equivalent_offsets_represent_the_same_instant():
    first = parse_utc_instant("2026-10-25T01:50:00+03:00")
    same = parse_utc_instant("2026-10-25T00:50:00+02:00")

    assert first == same == datetime(2026, 10, 24, 22, 50, tzinfo=UTC)
    assert checked_duration_seconds(first, same) == 0


@pytest.mark.parametrize("value", ["2026-10-25T01:50:00", "2026-10-25", ""])
def test_naive_or_incomplete_iso_values_are_rejected(value):
    with pytest.raises(ValueError):
        parse_utc_instant(value)


def test_datetime_helpers_reject_naive_datetimes():
    with pytest.raises(ValueError, match="explicit UTC offset"):
        as_utc_instant(datetime(2026, 10, 25, 1, 50))
