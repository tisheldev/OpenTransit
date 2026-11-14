"""A journey pinned to one trip ("Ride it", A3); synthetic engine, no live evidence."""

import json
from dataclasses import replace
from datetime import date
from itertools import count
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from test_motis_timetable import body_for

from opentransit.api.rate_limit import classify
from opentransit.api.schemas import JourneyResponse
from opentransit.core.trip_calls import SourceCall, SourceProfile
from opentransit.motis import geometry
from opentransit.pinned_trip import leg_path

FIXTURES = Path(__file__).parent / "fixtures" / "motis-v2.11.2"
SERVICE_DATE = date(2026, 10, 1)
TRIP = "20261001_08:00_mot60day_pin_trip"
GONE = "20261001_08:00_mot60day_gone_trip"
ROAD_LON = 34.79992  # A northbound road about 7.5 m west of the stops.
# Stop, latitude, seconds after service-day midnight, pickup, drop-off (all at lon 34.8).
CALLS = [
    ("o", 32.000, 28_800, 0, 0),
    ("b", 32.005, 29_100, 0, 0),
    ("m", 32.010, 29_400, 0, 0),
    ("s", 32.012, 29_520, 1, 1),  # Skipped by schedule.
    ("a", 32.015, 29_700, 0, 0),
    ("z", 32.020, 30_000, 0, 0),
]
_generations = count()


def _profile(trip_id):
    return SourceProfile(
        trip_id,
        "service",
        tuple(
            SourceCall(trip_id, "service", ordinal * 2, ordinal, stop, at, at, pickup, drop)
            for ordinal, (stop, _, at, pickup, drop) in enumerate(CALLS)
        ),
    )


PROFILES = {"pin_trip": _profile("pin_trip"), "gone_trip": _profile("gone_trip")}


def encode(points, precision=6):
    """Google polyline encoding of [lon, lat] points, as MOTIS sends geometry."""
    out, previous = [], [0, 0]
    for lon, lat in points:
        for axis, value in enumerate((lat, lon)):
            scaled = round(value * 10**precision)
            delta, previous[axis] = scaled - previous[axis], scaled
            delta = ~(delta << 1) if delta < 0 else delta << 1
            while delta >= 0x20:
                out.append(chr((0x20 | (delta & 0x1F)) + 63))
                delta >>= 5
            out.append(chr(delta + 63))
    return {"points": "".join(out), "precision": precision}


ROAD = [[ROAD_LON, round(32.0 + i * 0.001, 3)] for i in range(21)]


def _trip_body(engine_id):
    body = body_for(PROFILES[engine_id.split("_mot60day_")[1]], engine_id, SERVICE_DATE)
    leg = body["legs"][0]
    for call, (_, lat, *_rest) in zip(
        [leg["from"], *leg["intermediateStops"], leg["to"]], CALLS, strict=True
    ):
        call.update({"lat": lat, "lon": 34.8})
    leg.update(
        {
            "routeId": "mot60day_r8",
            "routeShortName": "8",
            "headsign": "Z",
            "agencyId": "5",
            "agencyName": "דן",
            "legGeometry": encode(ROAD),
        }
    )
    return body


WALK = {
    "transfers": 0,
    "legs": [
        {
            "mode": "WALK",
            "from": {"name": "START", "lat": 31.998, "lon": 34.8},
            "to": {"name": "b", "stopId": "mot60day_b", "lat": 32.005, "lon": 34.8},
            "scheduledStartTime": "2026-10-01T04:00:00Z",
            "scheduledEndTime": "2026-10-01T04:10:00Z",
            "realTime": False,
            "distance": 780.0,
            "legGeometry": encode([[34.8, 31.998], [34.8, 32.005]]),
        }
    ],
}


def _engine(seen, *, direct=(WALK,)):
    def handle(request):
        path = request.url.path
        if path.endswith("/trip"):
            engine_id = request.url.params["tripId"]
            if engine_id == GONE:
                return httpx.Response(404)
            return httpx.Response(200, json=_trip_body(engine_id))
        if path.endswith("/plan"):
            params = dict(request.url.params)
            if params.get("transitModes") == "":
                seen.append(params)
                return httpx.Response(200, json={"itineraries": [], "direct": list(direct)})
            return httpx.Response(200, json={"itineraries": [], "direct": []})
        return httpx.Response(404)

    return handle


class PinReference:
    """Stops `o` to `z` of the pinned trip; `station` holds the platform `a`."""

    def stop_ref(self, stop_id):
        if stop_id == "mot:stop:station":
            children = [{"stop_id": "mot:stop:a", "source_id": "a"}]
            return {"stop_id": stop_id, "source_id": "station", "children": children}
        source = stop_id.removeprefix("mot:stop:")
        if source not in {call[0] for call in CALLS}:
            return None
        code = {"b": "2", "a": "1"}.get(source)
        return {"stop_id": stop_id, "source_id": source, "platform_code": code, "children": []}

    def source_profile(self, source_trip_id):
        return PROFILES.get(source_trip_id)

    def service_active(self, _service_id, _service_date):
        return True


def _attach(client):
    current = client.app.state.snapshot
    client.app.state.snapshot_manager = None
    client.app.state.snapshot = SimpleNamespace(
        generation=replace(current.generation, id=f"pinned-{next(_generations)}"),
        motis=current.motis,
        reference=PinReference(),
        routing_verified=True,
    )


def _query(**pin):
    origin = pin.pop("origin", {"kind": "coordinate", "latitude": 31.998, "longitude": 34.8})
    depart = pin.pop("departAt", "2026-10-01T07:50:00+03:00")
    return {
        "from": origin,
        "to": {"kind": "coordinate", "latitude": 32.015, "longitude": 34.8},
        "departAt": depart,
        "pinnedTrip": {
            "tripRef": TRIP,
            "boardStopId": "mot:stop:b",
            "alightStopId": "mot:stop:a",
        }
        | pin,
    }


def _plan(client_factory, body, seen=None, **engine):
    seen = [] if seen is None else seen
    with client_factory(_engine(seen, **engine)) as client:
        _attach(client)
        return client.post("/v1/journeys", json=body)


def test_walk_then_the_pinned_ride(client_factory):
    seen = []
    response = _plan(client_factory, _query(), seen)
    assert response.status_code == 200, response.text
    body = response.json()
    JourneyResponse.model_validate(body)
    assert body["data"]["outcome"] == "routes_found"
    [journey] = body["data"]["journeys"]
    walk, ride = journey["legs"]
    # The engine's walking route, moved to arrive at the departure (08:05).
    assert walk["kind"] == "walk" and walk["distanceMeters"] == 780.0
    assert walk["timing"]["scheduledDeparture"] == "2026-10-01T07:55:00+03:00"
    assert walk["timing"]["scheduledArrival"] == "2026-10-01T08:05:00+03:00"
    assert walk["to"]["stopId"] == "mot:stop:b" and walk["geometry"]["coordinates"]
    [request] = seen
    assert (request["fromPlace"], request["toPlace"]) == ("31.998,34.8", "mot60day_b")
    assert (request["arriveBy"], request["directModes"]) == ("true", "WALK")
    assert request["time"] == "2026-10-01T08:05:00+03:00"
    # The ride: the trip from b to a, like an engine transit leg.
    assert ride["kind"] == "transit" and ride["mode"] == "bus"
    assert ride["from"] == {
        "name": "b",
        "latitude": 32.005,
        "longitude": 34.8,
        "stopId": "mot:stop:b",
        "stopCode": "p1",
        "platformCode": "2",
    }
    assert ride["to"]["stopId"] == "mot:stop:a" and ride["to"]["stopCode"] == "p4"
    assert ride["timing"]["scheduledDeparture"] == "2026-10-01T08:05:00+03:00"
    assert ride["timing"]["scheduledArrival"] == "2026-10-01T08:15:00+03:00"
    assert ride["durationSeconds"] == 600
    assert ride["transit"] == {
        "operatorId": "5",
        "operatorName": "דן",
        "routeId": "mot:route:r8",
        "routeShortName": "8",
        "headsign": "Z",
        "engineTripId": TRIP,
        "sourceTripId": "pin_trip",
        "serviceDate": "2026-10-01",
        "startTime": "08:00",
    }
    assert [stop["stopId"] for stop in ride["intermediateStops"]] == ["mot:stop:m"]
    assert ride["intermediateStops"][0]["scheduledArrival"] == "2026-10-01T08:10:00+03:00"
    path = ride["geometry"]["coordinates"]
    assert path[0] == [34.8, 32.005] and path[-1] == [34.8, 32.015]
    assert path[1:-1] == ROAD[5:16]
    assert ride["geometryUnavailableReason"] is None
    board = ride["boarding"]
    assert (board["bearingSource"], board["stopSide"]) == ("leg_geometry", "right")
    assert board["bearingDegrees"] == pytest.approx(0, abs=0.5)
    assert (board["stopCount"], board["nextStop"]["stopId"], board["towards"]) == (
        2,
        "mot:stop:m",
        "Z",
    )
    assert journey["transfers"] == 0
    assert (journey["walkingSeconds"], journey["walkingDistanceMeters"]) == (600, 780.0)
    assert journey["durationSeconds"] == 1200
    assert journey["id"].startswith("journey-")
    meta = body["meta"]
    assert meta["rankingPolicy"] == "pinned-trip-v1"
    assert meta["appliedConstraints"]["pinnedTrip"]["tripRef"] == TRIP
    assert "PINNED_TRIP_MISSED_BY_WALK" not in meta["warnings"]


def test_a_walk_that_cannot_make_the_departure_is_still_returned_with_a_warning(client_factory):
    response = _plan(client_factory, _query(departAt="2026-10-01T07:58:00+03:00"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["data"]["journeys"]) == 1
    assert "PINNED_TRIP_MISSED_BY_WALK" in body["meta"]["warnings"]


def test_no_walk_when_starting_at_the_stop(client_factory):
    seen = []
    near = {"kind": "coordinate", "latitude": 32.0051, "longitude": 34.8}  # About 11 m.
    for origin in (near, {"kind": "stop", "stopId": "mot:stop:b"}):
        response = _plan(client_factory, _query(origin=origin), seen)
        assert response.status_code == 200, response.text
        [journey] = response.json()["data"]["journeys"]
        assert [leg["kind"] for leg in journey["legs"]] == ["transit"]
        assert journey["walkingSeconds"] == 0 and journey["walkingDistanceMeters"] == 0
    assert seen == []  # No walk was asked of the engine.
    late = _plan(client_factory, _query(origin=near, departAt="2026-10-01T08:06:00+03:00"))
    assert "PINNED_TRIP_MISSED_BY_WALK" in late.json()["meta"]["warnings"]


def test_alighting_at_a_station_rides_to_its_platform(client_factory):
    response = _plan(client_factory, _query(alightStopId="mot:stop:station"))
    assert response.status_code == 200, response.text
    ride = response.json()["data"]["journeys"][0]["legs"][-1]
    assert ride["to"]["stopId"] == "mot:stop:a" and ride["to"]["platformCode"] == "1"


def test_no_walk_route_is_no_route_with_a_disclosure(client_factory):
    response = _plan(client_factory, _query(), direct=())
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"outcome": "no_route", "journeys": [], "alerts": None}
    assert "PINNED_TRIP_WALK_UNAVAILABLE" in body["meta"]["warnings"]


@pytest.mark.parametrize(
    ("pin", "status", "code"),
    [
        ({"tripRef": "20261001_08:00_mot60day_nope"}, 404, "TRIP_NOT_FOUND"),
        ({"tripRef": GONE}, 404, "TRIP_NOT_FOUND"),
        ({"boardStopId": "mot:stop:elsewhere"}, 422, "INVALID_PINNED_TRIP"),
        ({"alightStopId": "mot:stop:elsewhere"}, 422, "INVALID_PINNED_TRIP"),
        ({"boardStopId": "mot:stop:a", "alightStopId": "mot:stop:b"}, 422, "INVALID_PINNED_TRIP"),
        ({"alightStopId": "mot:stop:b"}, 422, "INVALID_PINNED_TRIP"),
        ({"boardStopId": "mot:stop:s"}, 422, "INVALID_PINNED_TRIP"),  # No pickup there.
        ({"tripRef": "not-a-trip"}, 422, "INVALID_REQUEST"),
        ({"boardStopId": "b-without-namespace"}, 422, "INVALID_REQUEST"),
    ],
)
def test_pinned_trip_errors(client_factory, pin, status, code):
    response = _plan(client_factory, _query(**pin))
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == code


def test_validation_names_the_pinned_trip_fields(client_factory):
    response = _plan(client_factory, _query(tripRef="not-a-trip"))
    assert response.json()["errors"][0]["field"] == "body.pinnedTrip.tripRef"


def test_leg_path_cuts_the_trip_shape_where_the_engine_cuts_a_planned_leg():
    """Recorded: the same trip from /api/v6/trip and as a leg of /api/v6/plan (2026-10-01)."""
    trip = json.loads((FIXTURES / "real-trip.json").read_text(encoding="utf-8"))["legs"][0]
    plan = json.loads((FIXTURES / "real-plan-depart-at.json").read_text(encoding="utf-8"))
    leg = plan["itineraries"][0]["legs"][1]
    assert leg["tripId"] == trip["tripId"]
    calls = [trip["from"], *trip["intermediateStops"], trip["to"]]
    ids = [call["stopId"] for call in calls]
    board, alight = ids.index(leg["from"]["stopId"]), ids.index(leg["to"]["stopId"])
    path = leg_path(
        geometry(trip["legGeometry"]).coordinates,
        [(call["lon"], call["lat"]) for call in calls],
        board,
        alight,
    )
    expected = geometry(leg["legGeometry"]).coordinates
    assert len(path) == len(expected) == 129
    for got, want in zip(path, expected, strict=True):
        assert got == pytest.approx(want, abs=1e-6)


def test_leg_path_follows_a_loop_in_trip_order():
    shape = [[0.0, 0.0], [0.0, 0.001], [0.001, 0.001], [0.001, 0.0], [0.0, 0.0], [0.0, 0.001]]
    positions = [(0.0, 0.0), (0.001, 0.0005), (0.0, 0.0), (0.0, 0.001)]
    # The second call at (0, 0) is the pass after the loop, not the first vertex again.
    assert leg_path(shape, positions, 2, 3) == [[0.0, 0.0], [0.0, 0.001]]
    assert leg_path(shape, positions, 1, 2)[0] == [0.001, 0.0005]
    assert leg_path(None, positions, 0, 1) is None
    assert leg_path(shape, [None, (0.0, 0.0)], 0, 1) is None


def test_pinned_journeys_share_the_expensive_bucket_and_openapi(client_factory):
    assert classify("POST", "/v1/journeys") == "expensive"
    with client_factory(_engine([])) as client:
        schema = client.get("/openapi.json").json()
    components = schema["components"]["schemas"]
    assert "pinnedTrip" in components["JourneyRequest"]["properties"]
    assert set(components["PinnedTrip"]["required"]) == {"tripRef", "boardStopId", "alightStopId"}
    assert "404" in schema["paths"]["/v1/journeys"]["post"]["responses"]
