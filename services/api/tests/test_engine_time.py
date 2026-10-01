"""MOTIS time parameters must survive the pinned engine timestamp parser exactly.

The readiness failure recorded on 2026-09-30/10-01 came from sub-second request
times: MOTIS logged `[VERIFY FAIL] query time ... is outside of loaded timetable
window` for every `/readyz` 503 and for no 200. `motis_parse_time` emulates the
parser so the failure is deterministic here without an engine.
"""

import re
from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest
from test_reference_api import reference_client
from test_timetable_api import FROM, attach_snapshot, engine_response

from opentransit.core.time import engine_time

_LOCAL = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})T(\d{1,2}):(\d{1,2})")
_SECONDS = re.compile(r":(\d{2})(?:\.(\d{0,3}))?")
_OFFSET = re.compile(r"([+-]?)(\d{1,2})(?::(\d{2}))?")


def motis_parse_time(value: str) -> datetime:
    """Emulate openapi-cpp `parse(date_time_t)` used by MOTIS v2.11.2.

    Source: triptix-tech/openapi-cpp@22492d0 src/date_time.cc parses into
    `date::sys_time<milliseconds>` trying `%FT%TZ`, `%FT%T%Ez`, `%FT%H:%MZ`,
    `%FT%H:%M%Ez`. HowardHinnant/date reads `%T` seconds with at most three
    fractional digits, `%Ez` as an optional sign plus one or two hour digits and an
    optional `:MM`, and ignores trailing input. Microsecond digits 4-5 therefore
    become the "offset" hours and the real offset is never read.
    """
    local = _LOCAL.match(value)
    if local is None:
        raise ValueError(f"failed to parse timestamp {value!r}")
    year, month, day, hour, minute = (int(part) for part in local.groups())
    wall = datetime(year, month, day, hour, minute, tzinfo=UTC)
    for with_seconds in (True, False):
        rest = value[local.end() :]
        moment = wall
        if with_seconds:
            seconds = _SECONDS.match(rest)
            if seconds is None:
                continue
            fraction = (seconds.group(2) or "").ljust(3, "0")
            moment += timedelta(seconds=int(seconds.group(1)), milliseconds=int(fraction))
            rest = rest[seconds.end() :]
        if rest.startswith("Z"):
            return moment
        offset = _OFFSET.match(rest)
        if offset is not None:
            sign = -1 if offset.group(1) == "-" else 1
            delta = timedelta(hours=int(offset.group(2)), minutes=int(offset.group(3) or 0))
            return moment - sign * delta
    raise ValueError(f"failed to parse timestamp {value!r}")


def test_emulated_parser_reproduces_the_recorded_whole_hour_shift():
    # Python's default isoformat() keeps microseconds; "162" after the parsed
    # milliseconds is read as a +16:00 offset and "+00:00" is ignored.
    sent = datetime(2026, 9, 30, 22, 47, 47, 673162, tzinfo=UTC).isoformat()
    assert sent == "2026-09-30T22:47:47.673162+00:00"
    assert motis_parse_time(sent) == datetime(2026, 9, 30, 6, 47, 47, 673000, tzinfo=UTC)
    # A non-UTC fractional time silently loses its real offset as well.
    israel = timezone(timedelta(hours=3))
    local = datetime(2026, 10, 1, 8, 0, 0, 500000, tzinfo=israel).isoformat()
    assert motis_parse_time(local) == datetime(2026, 10, 1, 8, 0, 0, 500000, tzinfo=UTC)
    # Whole-second strings are the only previously exercised form and are exact.
    assert motis_parse_time("2026-10-01T08:00:00+03:00") == datetime(2026, 10, 1, 5, tzinfo=UTC)
    assert motis_parse_time("2026-10-01T05:00:00Z") == datetime(2026, 10, 1, 5, tzinfo=UTC)


@pytest.mark.parametrize("microsecond", [0, 1, 123456, 673162, 999999])
@pytest.mark.parametrize("hours", [0, 2, 3, -5])
def test_engine_time_round_trips_through_the_motis_parser(microsecond, hours):
    value = datetime(2026, 9, 30, 23, 10, 8, microsecond, tzinfo=timezone(timedelta(hours=hours)))
    sent = engine_time(value)
    assert "." not in sent
    assert motis_parse_time(sent) == value.replace(microsecond=0).astimezone(UTC)


def test_engine_time_keeps_whole_second_strings_and_rejects_naive_times():
    israel = timezone(timedelta(hours=3))
    assert engine_time(datetime(2026, 10, 1, 8, tzinfo=israel)) == "2026-10-01T08:00:00+03:00"
    odd = timezone(timedelta(hours=2, minutes=20, seconds=54))
    assert engine_time(datetime(2026, 10, 1, 8, tzinfo=odd)) == "2026-10-01T05:39:06+00:00"
    with pytest.raises(ValueError):
        engine_time(datetime(2026, 10, 1, 8))


def motis_like_engine(seen, window_start, window_end, engine_route):
    """Answer like MOTIS: an out-of-window parsed query time is a server error."""

    def engine(request):
        seen.append(request.url.params.get("time"))
        when = motis_parse_time(request.url.params["time"])
        if not window_start <= when < window_end:
            return httpx.Response(500, json={"error": "query time outside timetable window"})
        if request.url.params.get("fromPlace") == "32.0836,34.7981":
            return httpx.Response(200, json={"itineraries": [], "direct": []})
        return httpx.Response(200, json=engine_route)

    return engine


# 2026-09-30T09:00:00.123456Z: "456" would be read as a 45-hour offset, which
# lands before the synthetic coverage start (2026-09-28T21:00Z).
SUB_SECOND_NOW = datetime(2026, 9, 30, 9, 0, 0, 123456, tzinfo=UTC)
WINDOW = (datetime(2026, 9, 28, 21, tzinfo=UTC), datetime(2026, 10, 29, 22, tzinfo=UTC))


def test_readiness_with_a_sub_second_clock_is_deterministically_ready(manifest, engine_route):
    seen = []
    engine = motis_like_engine(seen, *WINDOW, engine_route)
    with reference_client(manifest, engine_route, now=SUB_SECOND_NOW, engine=engine) as client:
        response = client.get("/readyz")
        status = client.get("/v1/status").json()["data"]
    assert response.status_code == 200, response.json()
    assert status["ready"] and status["routing"] == "available"
    assert seen[0] == "2026-09-30T09:00:00+00:00"


def test_engine_failure_reason_is_reported_without_engine_details(manifest, engine_route):
    def engine(request):
        return httpx.Response(500, json={"error": "sentinel-private-detail"})

    with reference_client(manifest, engine_route, engine=engine) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "NOT_READY"
    assert body["errors"] == [
        {"condition": "engine", "reason": "ENGINE_HTTP_STATUS", "httpStatus": "500"}
    ]
    assert "sentinel-private-detail" not in response.text


def test_unreachable_engine_reason_is_machine_readable(manifest, engine_route):
    with reference_client(manifest, engine_route, engine_down=True) as client:
        response = client.get("/readyz")
    assert response.json()["errors"] == [{"condition": "engine", "reason": "ENGINE_UNREACHABLE"}]
    assert "sentinel-private-host" not in response.text


def test_expired_coverage_reason_is_machine_readable(manifest, engine_route):
    late = datetime(2026, 11, 1, tzinfo=UTC)
    with reference_client(manifest, engine_route, now=late) as client:
        body = client.get("/readyz").json()
    assert {"condition": "coverage", "reason": "OUTSIDE_COVERAGE"} in body["errors"]


def test_sub_second_journey_and_departure_times_reach_the_engine_exactly(
    client_factory, query, engine_route
):
    seen = []
    engine = motis_like_engine(seen, *WINDOW, engine_route)
    query = {**query, "departAt": "2026-09-30T08:00:00.123456+03:00"}
    with client_factory(engine) as client:
        response = client.post("/v1/journeys", json=query)
    assert response.status_code == 200, response.json()
    assert motis_parse_time(seen[-1]) == datetime(2026, 9, 30, 5, tzinfo=UTC)

    stoptimes = []

    def timetable_engine(request):
        if request.url.path.endswith("/stoptimes"):
            stoptimes.append(request.url.params["time"])
        return engine_response(request)

    with client_factory(timetable_engine) as client:
        attach_snapshot(client)
        response = client.get(
            "/v1/stops/mot:stop:board/departures",
            params={"from": FROM.replace(":00+", ":00.987654+"), "horizonMinutes": 120},
        )
    assert response.status_code == 200, response.json()
    assert motis_parse_time(stoptimes[0]) == datetime(2026, 10, 1, 5, tzinfo=UTC)
