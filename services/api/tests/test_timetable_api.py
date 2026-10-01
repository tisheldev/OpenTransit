import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from itertools import count
from threading import Event
from types import SimpleNamespace

import httpx
from test_motis_timetable import body_for, profile

TRIP_IDS = {
    "loop_trip": "20261001_08:00_mot60day_loop_trip",
    "other_trip": "20261001_08:00_mot60day_other_trip",
}
SOURCES = {
    "loop_trip": profile("loop_trip", loop=True, pickup=2),
    "other_trip": profile("other_trip", pickup=3),
}
SERVICE_DATE = date(2026, 10, 1)
FROM = "2026-10-01T08:00:00+03:00"
_generation_sequence = count()


class Reference:
    def stop(self, _stop_ref):
        return {
            "source_id": "board",
            "platform_code": "Bay 1",
            "children": [],
        }

    def source_profile(self, source_trip_id):
        return SOURCES.get(source_trip_id)

    def service_active(self, _service_id, _service_date):
        return True


def stop_times():
    rows = []
    for trip_id in (TRIP_IDS["loop_trip"], TRIP_IDS["loop_trip"], TRIP_IDS["other_trip"]):
        rows.append(
            {
                "tripId": trip_id,
                "mode": "BUS",
                "realTime": False,
                "cancelled": False,
                "tripCancelled": False,
                "pickupDropoffType": "NORMAL",
                "headsign": "Destination",
                "place": {
                    "stopId": "mot60day_board",
                    "scheduledDeparture": "2026-10-01T05:10:00Z",
                    "stopCode": "not-a-platform-code",
                },
            }
        )
    return {"stopTimes": rows}


def engine_response(request, *, trip_status=200, malformed=False):
    if request.url.path.endswith("/stoptimes"):
        return httpx.Response(200, json=stop_times())
    if request.url.path.endswith("/trip"):
        engine_id = request.url.params["tripId"]
        source_id = next(key for key, value in TRIP_IDS.items() if value == engine_id)
        body = body_for(SOURCES[source_id], engine_id, SERVICE_DATE)
        if malformed:
            body["legs"][0]["tripId"] = "wrong-dated-identity"
        return httpx.Response(
            trip_status, json=body if trip_status == 200 else {"error": "missing"}
        )
    return httpx.Response(404)


def attach_snapshot(client, *, reference=True, generation=None):
    current = client.app.state.snapshot
    client.app.state.snapshot_manager = None
    client.app.state.snapshot = SimpleNamespace(
        generation=generation
        or replace(current.generation, id=f"timetable-api-{next(_generation_sequence)}"),
        motis=current.motis,
        reference=Reference() if reference else None,
        routing_verified=True,
    )
    return client.app.state.snapshot


def test_api_trip_and_departure_pages_preserve_source_identity_and_restrictions(client_factory):
    with client_factory(engine_response) as client:
        attach_snapshot(client)
        trip = client.get(f"/v1/trips/{TRIP_IDS['loop_trip']}")
        assert trip.status_code == 200
        assert trip.json()["data"]["tripRef"] == TRIP_IDS["loop_trip"]
        assert trip.json()["data"]["sourceTripId"] == "loop_trip"
        assert [call["callSequence"] for call in trip.json()["data"]["calls"]] == [5, 9, 13, 17, 21]
        assert [call["pickupType"] for call in trip.json()["data"]["calls"]] == [2] * 5

        first = client.get(
            "/v1/stops/mot:stop:board/departures",
            params={"from": FROM, "horizonMinutes": 120, "limit": 1},
        )
        assert first.status_code == 200
        assert first.json()["data"][0]["platformCode"] == "Bay 1"
        assert first.json()["data"][0]["platformCode"] != "not-a-platform-code"
        events = first.json()["data"]
        cursor = first.json()["page"]["nextCursor"]
        while cursor:
            page = client.get(
                "/v1/stops/mot:stop:board/departures",
                params={"from": FROM, "horizonMinutes": 120, "limit": 1, "cursor": cursor},
            )
            assert page.status_code == 200
            events.extend(page.json()["data"])
            cursor = page.json()["page"]["nextCursor"]
        keys = [(event["tripRef"], event["callSequence"]) for event in events]
        assert keys == [
            (TRIP_IDS["loop_trip"], 9),
            (TRIP_IDS["loop_trip"], 17),
            (TRIP_IDS["other_trip"], 2),
        ]
        assert [event["pickupType"] for event in events] == [2, 2, 3]


def test_api_missing_reference_and_expired_generation_are_unavailable(client_factory):
    with client_factory(engine_response) as client:
        attach_snapshot(client, reference=False)
        missing = client.get(f"/v1/trips/{TRIP_IDS['loop_trip']}")
        assert missing.status_code == 503

    with client_factory(engine_response) as client:
        current = attach_snapshot(client)
        expired_generation = SimpleNamespace(
            id=current.generation.id,
            contains=current.generation.contains,
            freshness=lambda _now: "expired",
        )
        attach_snapshot(client, generation=expired_generation)
        expired = client.get("/v1/stops/mot:stop:board/departures", params={"from": FROM})
        assert expired.status_code == 503


def test_departure_reference_database_failure_is_unavailable_not_internal_error(client_factory):
    with client_factory(engine_response) as client:
        snapshot = attach_snapshot(client)

        class BrokenReference:
            def stop(self, _stop_ref):
                raise sqlite3.DatabaseError("private database detail")

        client.app.state.snapshot = SimpleNamespace(
            generation=snapshot.generation,
            motis=snapshot.motis,
            reference=BrokenReference(),
            routing_verified=True,
        )
        response = client.get(
            "/v1/stops/mot:stop:board/departures",
            params={"from": FROM},
        )
    assert response.status_code == 503
    assert response.json()["code"] == "DATA_UNAVAILABLE"
    assert "private database detail" not in response.text


def test_api_changed_cursor_is_422_and_engine_404_stays_404(client_factory):
    with client_factory(engine_response) as client:
        attach_snapshot(client)
        first = client.get(
            "/v1/stops/mot:stop:board/departures",
            params={"from": FROM, "limit": 1},
        )
        cursor = first.json()["page"]["nextCursor"]
        changed = client.get(
            "/v1/stops/mot:stop:board/departures",
            params={"from": FROM, "limit": 2, "cursor": cursor},
        )
        assert changed.status_code == 422
        assert changed.json()["code"] == "INVALID_CURSOR"

    with client_factory(lambda request: engine_response(request, trip_status=404)) as client:
        attach_snapshot(client)
        missing = client.get(f"/v1/trips/{TRIP_IDS['loop_trip']}")
        assert missing.status_code == 404
        assert missing.json()["code"] == "NOT_FOUND"


def test_api_bad_engine_response_and_engine_timeout_are_service_errors(client_factory):
    with client_factory(lambda request: engine_response(request, malformed=True)) as client:
        attach_snapshot(client)
        bad = client.get(f"/v1/trips/{TRIP_IDS['loop_trip']}")
        assert bad.status_code == 503

    def limit_error(request):
        if request.url.path.endswith("/stoptimes"):
            return httpx.Response(500, json={"error": "window exceeds engine result limit"})
        return engine_response(request)

    with client_factory(limit_error) as client:
        attach_snapshot(client)
        overflow = client.get("/v1/stops/mot:stop:board/departures", params={"from": FROM})
        assert overflow.status_code == 503

    def timeout(_request):
        raise httpx.ReadTimeout("timed out", request=_request)

    with client_factory(timeout) as client:
        attach_snapshot(client)
        failed = client.get(f"/v1/trips/{TRIP_IDS['loop_trip']}")
        assert failed.status_code == 504


def test_api_request_keeps_the_snapshot_captured_before_await(client_factory):
    started, release = Event(), Event()

    async def handler(request):
        if request.url.path.endswith("/trip"):
            started.set()
            await asyncio.to_thread(release.wait, 3)
        return engine_response(request)

    with client_factory(handler) as client:
        original = attach_snapshot(client)
        original.generation = replace(original.generation, id="generation-before")
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(client.get, f"/v1/trips/{TRIP_IDS['loop_trip']}")
            assert started.wait(2)
            newer = replace(original.generation, id="generation-after")
            attach_snapshot(client, generation=newer)
            release.set()
            response = pending.result(timeout=3)
        assert response.status_code == 200
        assert response.json()["meta"]["generationId"] == "generation-before"


def test_configured_deadline_applies_to_trips_and_departures(client_factory):
    async def slow(request):
        await asyncio.sleep(0.2)
        return engine_response(request)

    with client_factory(slow, deadline=0.1) as client:
        attach_snapshot(client)
        trip_response = client.get(f"/v1/trips/{TRIP_IDS['loop_trip']}")
        assert trip_response.status_code == 504
        assert trip_response.json()["code"] == "ENGINE_TIMEOUT"

        departures_response = client.get(
            "/v1/stops/mot:stop:board/departures", params={"from": FROM}
        )
        assert departures_response.status_code == 504
        assert departures_response.json()["code"] == "ENGINE_TIMEOUT"
