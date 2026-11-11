"""Data the eight approved client boards need (client design, 11 November 2026).

API-C3 operator and mode on departures, the nearby summary (board 1), boarding bearing and
side (board 3), the routeId filter and trip exclusion (board 6), a stop's lines (board 7),
and API-C1/API-C2 call and leg fields.
"""

import csv
import json
import zipfile
from dataclasses import replace
from datetime import date
from io import StringIO
from itertools import count
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from test_motis_timetable import body_for, profile
from test_reference_api import reference_client

from opentransit.api.docs import (
    DeparturesResponse,
    NearbyDeparturesResponse,
    StopLinesResponse,
    TripResponse,
)
from opentransit.api.rate_limit import classify
from opentransit.api.schemas import JourneyRequest, JourneyResponse
from opentransit.boarding import boarding_geometry
from opentransit.motis import MODE_MAP, boarding, geometry, location, stopovers
from opentransit.reference import ReferenceStore, build_reference, route_type_mode

FIXTURES = Path(__file__).parent / "fixtures" / "motis-v2.11.2"
SERVICE_DATE = date(2026, 10, 1)
FROM = "2026-10-01T08:00:00+03:00"
TRIPS = {
    "dan_trip": "20261001_08:00_mot60day_dan_trip",
    "dan_later": "20261001_08:05_mot60day_dan_later",
    "egged_trip": "20261001_08:00_mot60day_egged_trip",
    "platform_trip": "20261001_08:00_mot60day_platform_trip",
}
ROUTES = {"dan_trip": "9809", "dan_later": "9809", "egged_trip": "7", "platform_trip": "7"}


def _shifted(source, seconds):
    """The same stops ``seconds`` later (a later trip of the same line)."""
    calls = tuple(
        replace(
            call,
            arrival_seconds=call.arrival_seconds + seconds,
            departure_seconds=call.departure_seconds + seconds,
        )
        for call in source.calls
    )
    return replace(source, calls=calls)


SOURCES = {key: profile(key) for key in TRIPS}
SOURCES["dan_later"] = _shifted(profile("dan_later"), 300)
SOURCES["platform_trip"] = replace(
    profile("platform_trip"),
    calls=tuple(
        replace(call, stop_id="platform") if call.stop_id == "board" else call
        for call in profile("platform_trip").calls
    ),
)
_generations = count()


def _wire(trip_key, *, at="2026-10-01T05:10:00Z", stop="board", **extra):
    agency = ("5", "דן") if ROUTES[trip_key] == "9809" else ("3", "אגד")
    item = {
        "tripId": TRIPS[trip_key],
        "mode": "BUS",
        "realTime": False,
        "cancelled": False,
        "tripCancelled": False,
        "headsign": "Reading" if ROUTES[trip_key] == "9809" else "Port",
        "agencyId": agency[0],
        "agencyName": agency[1],
        "routeId": f"mot60day_{ROUTES[trip_key]}",
        "directionId": "1",
        "place": {"stopId": f"mot60day_{stop}", "scheduledDeparture": at},
    }
    item.update(extra)
    return item


class FakeReference:
    """Stops `board` and `other` near Dizengoff; `station` has the platform `platform`."""

    stops = {
        "mot:stop:board": {"source_id": "board", "platform_code": "Bay 1", "children": []},
        "mot:stop:other": {"source_id": "other", "platform_code": None, "children": []},
        "mot:stop:station": {
            "source_id": "station",
            "platform_code": None,
            "children": [{"stop_id": "mot:stop:platform", "source_id": "platform"}],
        },
    }

    def __init__(self, near_rows=None):
        self.near_rows = near_rows

    def stop_ref(self, stop_ref):
        return self.stops.get(stop_ref)

    def source_profile(self, source_trip_id):
        return SOURCES.get(source_trip_id)

    def service_active(self, _service_id, _service_date):
        return True

    def stops_near(self, lat, lon, radius, limit, cursor):
        return {"items": self.near_rows, "next_cursor": None}

    def stop(self, stop_id):
        if stop_id == "mot:stop:station":
            return _row("station", "Central", None, 10.0)
        return None


def _row(source, name, parent, distance):
    return {
        "stop_id": f"mot:stop:{source}",
        "source_id": source,
        "code": None,
        "name": name,
        "description": None,
        "latitude": 32.0755,
        "longitude": 34.7751,
        "location_type": 1 if source == "station" else 0,
        "parent_station": parent,
        "wheelchair_boarding": None,
        "platform_code": None,
        "distance_m": distance,
    }


def _engine(stop_times, trip_requests=None, *, failing_stops=()):
    def handle(request):
        if request.url.path.endswith("/stoptimes"):
            stop = request.url.params["stopId"].removeprefix("mot60day_")
            if stop in failing_stops:
                return httpx.Response(500)
            return httpx.Response(200, json={"stopTimes": stop_times.get(stop, [])})
        if request.url.path.endswith("/trip"):
            engine_id = request.url.params["tripId"]
            if trip_requests is not None:
                trip_requests.append(engine_id)
            key = next(key for key, value in TRIPS.items() if value == engine_id)
            body = body_for(SOURCES[key], engine_id, SERVICE_DATE)
            body["legs"][0].update(
                {
                    "routeId": f"mot60day_{ROUTES[key]}",
                    "agencyId": "5" if ROUTES[key] == "9809" else "3",
                    "agencyName": "דן" if ROUTES[key] == "9809" else "אגד",
                    "directionId": "1",
                }
            )
            return httpx.Response(200, json=body)
        return httpx.Response(404)

    return handle


def _attach(client, reference=None):
    current = client.app.state.snapshot
    client.app.state.snapshot_manager = None
    client.app.state.snapshot = SimpleNamespace(
        generation=replace(current.generation, id=f"board-data-{next(_generations)}"),
        motis=current.motis,
        reference=reference or FakeReference(),
        routing_verified=True,
    )


# --- API-C3: operator, mode and direction on departure items; routeId filter -----------


def test_departures_carry_operator_mode_and_direction(client_factory):
    times = {"board": [_wire("dan_trip"), _wire("egged_trip")]}
    with client_factory(_engine(times)) as client:
        _attach(client)
        response = client.get("/v1/stops/mot:stop:board/departures", params={"from": FROM})
    assert response.status_code == 200
    body = response.json()
    DeparturesResponse.model_validate(body)
    by_route = {item["routeId"]: item for item in body["data"]}
    assert by_route["mot:route:9809"]["operatorId"] == "5"
    assert by_route["mot:route:9809"]["operatorName"] == "דן"
    assert by_route["mot:route:7"]["operatorId"] == "3"
    assert {item["mode"] for item in body["data"]} == {"bus"}
    assert {item["directionId"] for item in body["data"]} == {"1"}


def test_departures_without_engine_operator_fields_are_null_not_guessed(client_factory):
    bare = _wire("dan_trip")
    for key in ("agencyId", "agencyName", "mode", "directionId"):
        bare.pop(key)

    def handle(request):
        if request.url.path.endswith("/trip"):
            body = body_for(SOURCES["dan_trip"], TRIPS["dan_trip"], SERVICE_DATE)
            body["legs"][0]["mode"] = None
            return httpx.Response(200, json=body)
        return _engine({"board": [bare]})(request)

    with client_factory(handle) as client:
        _attach(client)
        item = client.get("/v1/stops/mot:stop:board/departures", params={"from": FROM}).json()[
            "data"
        ][0]
    assert item["operatorId"] is None
    assert item["operatorName"] is None
    assert item["mode"] is None
    assert item["directionId"] is None


def test_unmapped_engine_mode_is_other():
    from opentransit.motis_timetable import public_mode

    assert public_mode("BUS") == "bus"
    assert public_mode("TRAM") == "light_rail"
    assert public_mode("REGIONAL_RAIL") == "rail"
    assert public_mode("AIRPLANE") == "other"
    assert public_mode(None) is None


def test_route_filter_keeps_one_line_and_skips_other_trip_lookups(client_factory):
    times = {
        "board": [
            _wire("dan_trip"),
            _wire("egged_trip"),
            _wire("dan_later", at="2026-10-01T05:15:00Z"),
        ]
    }
    lookups = []
    with client_factory(_engine(times, lookups)) as client:
        _attach(client)
        params = {"from": FROM, "routeId": "mot:route:9809", "limit": 1}
        first = client.get("/v1/stops/mot:stop:board/departures", params=params)
        assert first.status_code == 200
        assert [item["routeId"] for item in first.json()["data"]] == ["mot:route:9809"]
        assert TRIPS["egged_trip"] not in lookups
        cursor = first.json()["page"]["nextCursor"]
        assert cursor
        second = client.get(
            "/v1/stops/mot:stop:board/departures", params={**params, "cursor": cursor}
        )
        assert second.status_code == 200
        assert [item["tripRef"] for item in first.json()["data"]] == [TRIPS["dan_trip"]]
        assert [item["tripRef"] for item in second.json()["data"]] == [TRIPS["dan_later"]]
        # A cursor is bound to its filter.
        unfiltered = client.get(
            "/v1/stops/mot:stop:board/departures",
            params={"from": FROM, "limit": 1, "cursor": cursor},
        )
        assert unfiltered.status_code == 422
        assert unfiltered.json()["code"] == "INVALID_CURSOR"
        bad = client.get(
            "/v1/stops/mot:stop:board/departures", params={"from": FROM, "routeId": "9809"}
        )
        assert bad.status_code == 422


# --- API-C1: names, positions and platforms on trip calls; operator and mode on trips ---


def test_trip_detail_calls_carry_name_position_and_platform(client_factory):
    with client_factory(_engine({})) as client:
        _attach(client)
        response = client.get(f"/v1/trips/{TRIPS['dan_trip']}")
    assert response.status_code == 200
    body = response.json()
    TripResponse.model_validate(body)
    data = body["data"]
    assert (data["operatorId"], data["operatorName"], data["mode"]) == ("5", "דן", "bus")
    assert data["directionId"] == "1"
    calls = data["calls"]
    assert [call["name"] for call in calls] == ["origin", "board", "destination"]
    assert {(call["latitude"], call["longitude"]) for call in calls} == {(32.0, 35.0)}
    # The fake reference knows only `board` (Bay 1); unknown stops have no platform.
    assert [call["platformCode"] for call in calls] == [None, "Bay 1", None]


# --- Board 1: nearby stops with their next departures ----------------------------------


def test_nearby_returns_next_departure_per_line_and_folds_platforms(client_factory):
    rows = [
        _row("board", "Dizengoff", None, 8.0),
        _row("platform", "Central 1", "mot:stop:station", 40.0),
        _row("other", "Ben Zion", None, 60.0),
    ]
    times = {
        "board": [
            _wire("dan_trip"),
            _wire("dan_later", at="2026-10-01T05:15:00Z"),  # Same line: not repeated.
            _wire("egged_trip"),
        ],
        "station": [],
        "platform": [_wire("platform_trip", stop="platform")],
        "other": [],
    }
    lookups = []
    with client_factory(_engine(times, lookups)) as client:
        _attach(client, FakeReference(rows))
        response = client.get(
            "/v1/departures/nearby",
            params={"near": "32.0755,34.7751", "from": FROM, "perStop": 3},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    NearbyDeparturesResponse.model_validate(body)
    assert [item["stop"]["stopId"] for item in body["data"]] == [
        "mot:stop:board",
        "mot:stop:station",
        "mot:stop:other",
    ]
    board = body["data"][0]
    assert board["departuresState"] == "available"
    assert board["complete"] is True
    assert [(d["routeId"], d["operatorName"]) for d in board["departures"]] == [
        ("mot:route:9809", "דן"),
        ("mot:route:7", "אגד"),
    ]
    # The later departure of a line already shown is never looked up.
    assert TRIPS["dan_later"] not in lookups
    station = body["data"][1]
    assert station["stop"]["distanceMeters"] == 40.0
    assert [d["stopId"] for d in station["departures"]] == ["mot:stop:platform"]
    other = body["data"][2]
    assert other["departuresState"] == "available"
    assert other["departures"] == []
    assert body["query"]["perStop"] == 3


def test_nearby_per_stop_bound_and_unavailable_stop(client_factory):
    rows = [_row("board", "Dizengoff", None, 8.0), _row("other", "Ben Zion", None, 60.0)]
    times = {"board": [_wire("dan_trip"), _wire("egged_trip")]}
    with client_factory(_engine(times, failing_stops={"other"})) as client:
        _attach(client, FakeReference(rows))
        body = client.get(
            "/v1/departures/nearby",
            params={"near": "32.0755,34.7751", "from": FROM, "perStop": 1},
        ).json()
    board, other = body["data"]
    assert [d["routeId"] for d in board["departures"]] == ["mot:route:9809"]
    assert other["departuresState"] == "unavailable"
    assert other["departures"] is None
    assert other["unavailableReason"] == "DATA_UNAVAILABLE"
    assert other["complete"] is False


def test_nearby_fails_when_no_stop_can_be_read(client_factory):
    rows = [_row("board", "Dizengoff", None, 8.0)]
    with client_factory(_engine({}, failing_stops={"board"})) as client:
        _attach(client, FakeReference(rows))
        response = client.get(
            "/v1/departures/nearby", params={"near": "32.0755,34.7751", "from": FROM}
        )
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize(
    "params",
    [
        {"near": "1,2", "from": FROM},
        {"near": "32.07,34.77", "from": "2026-10-01T08:00:00"},
        {"near": "32.07,34.77", "from": FROM, "stops": 13},
        {"near": "32.07,34.77", "from": FROM, "perStop": 6},
        {"near": "32.07,34.77", "from": FROM, "radius": 1001},
        {"near": "32.07,34.77", "from": "2027-10-01T08:00:00+03:00"},
    ],
)
def test_nearby_rejects_unbounded_or_invalid_queries(client_factory, params):
    with client_factory(_engine({})) as client:
        _attach(client, FakeReference([]))
        response = client.get("/v1/departures/nearby", params=params)
    assert response.status_code == 422


def test_nearby_is_rate_limited_as_expensive():
    assert classify("GET", "/v1/departures/nearby") == "expensive"


# --- Board 7: every line through a stop, with ordered stops -----------------------------


def _feed(path):
    members = {
        "agency.txt": (
            ["agency_id", "agency_name", "agency_url", "agency_timezone"],
            [["5", "דן", "https://example.test", "Asia/Jerusalem"]],
        ),
        "routes.txt": (
            ["route_id", "agency_id", "route_short_name", "route_long_name", "route_desc"]
            + ["route_type"],
            [
                ["r1", "5", "8", "Out", "55008-1-0", "3"],
                ["r2", "5", "8", "Back", "55008-2-0", "3"],
                ["r3", "5", "80", "Other", "55080-1-0", "3"],
                ["lr", "5", "R1", "Red", "1-1-0", "0"],
            ],
        ),
        "stops.txt": (
            ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type", "parent_station"],
            [
                ["a", "A", "32.0", "34.8", "0", ""],
                ["b", "B", "32.01", "34.8", "0", ""],
                ["b2", "B opposite", "32.01", "34.8002", "0", ""],
                ["c", "C", "32.02", "34.8", "0", ""],
            ],
        ),
        "trips.txt": (
            ["route_id", "service_id", "trip_id", "direction_id", "trip_headsign"],
            [
                ["r1", "s", "t1", "0", "C"],
                ["r2", "s", "t2", "1", "A"],
                ["r3", "s", "t3", "0", "C"],
                ["lr", "s", "t4", "0", "C"],
            ],
        ),
        "calendar.txt": (
            ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday"]
            + ["saturday", "sunday", "start_date", "end_date"],
            [["s", "1", "1", "1", "1", "1", "1", "1", "20260101", "20261231"]],
        ),
        "stop_times.txt": (
            ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
            [
                ["t1", "08:00:00", "08:00:00", "a", "1"],
                ["t1", "08:05:00", "08:05:00", "b", "2"],
                ["t1", "08:10:00", "08:10:00", "c", "3"],
                ["t2", "09:00:00", "09:00:00", "c", "1"],
                ["t2", "09:05:00", "09:05:00", "b2", "2"],
                ["t2", "09:10:00", "09:10:00", "a", "3"],
                ["t3", "08:00:00", "08:00:00", "a", "1"],
                ["t3", "08:10:00", "08:10:00", "c", "2"],
                ["t4", "08:00:00", "08:00:00", "b", "1"],
                ["t4", "08:10:00", "08:10:00", "c", "2"],
            ],
        ),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, (fields, rows) in members.items():
            stream = StringIO()
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(fields)
            writer.writerows(rows)
            archive.writestr(name, stream.getvalue())
    return path


@pytest.fixture
def lines_store(tmp_path):
    database = tmp_path / "reference.sqlite"
    build_reference(_feed(tmp_path / "feed.zip"), database, "lines-test")
    store = ReferenceStore(database, "lines-test")
    yield store
    store.close()


def test_stop_lines_serving_patterns_fan_out_from_the_stop(lines_store):
    page = lines_store.stop_lines("mot:stop:b")
    assert page["next_cursor"] is None
    by_route = {item["route_id"]: item for item in page["items"]}
    assert set(by_route) == {"mot:route:r1", "mot:route:lr"}  # r2 stops at b2, r3 skips b.
    line = by_route["mot:route:r1"]
    assert (line["agency_id"], line["operatorName"], line["mode"]) == ("5", "דן", "bus")
    assert by_route["mot:route:lr"]["mode"] == "light_rail"
    [pattern] = line["patterns"]
    assert pattern["serves_stop"] is True
    assert pattern["stop_index"] == 1
    assert [stop["stop_id"] for stop in pattern["stops"]] == [
        "mot:stop:a",
        "mot:stop:b",
        "mot:stop:c",
    ]
    assert pattern["stops"][1]["latitude"] == 32.01


def test_stop_lines_all_adds_the_opposite_direction(lines_store):
    page = lines_store.stop_lines("mot:stop:b", all_patterns=True)
    line = next(item for item in page["items"] if item["route_id"] == "mot:route:r1")
    assert [(p["route_id"], p["serves_stop"]) for p in line["patterns"]] == [
        ("mot:route:r1", True),
        ("mot:route:r2", False),
    ]
    opposite = line["patterns"][1]
    assert opposite["stop_index"] is None
    assert [stop["stop_id"] for stop in opposite["stops"]][1] == "mot:stop:b2"
    # Line 80 (another line code) is not a sibling of line 8.
    assert all(p["route_id"] != "mot:route:r3" for p in line["patterns"])


def test_stop_lines_pages_by_route_and_rejects_unknown_stops(lines_store):
    first = lines_store.stop_lines("mot:stop:b", limit=1)
    assert len(first["items"]) == 1
    second = lines_store.stop_lines("mot:stop:b", limit=1, cursor=first["next_cursor"])
    assert {first["items"][0]["route_id"], second["items"][0]["route_id"]} == {
        "mot:route:r1",
        "mot:route:lr",
    }
    assert second["next_cursor"] is None
    assert lines_store.stop_lines("mot:stop:missing") is None
    with pytest.raises(ValueError):
        lines_store.stop_lines("mot:stop:b", limit=51)


def test_stop_lines_endpoint(manifest, engine_route):
    with reference_client(manifest, engine_route) as client:
        response = client.get("/v1/stops/mot:stop:station/lines")
        assert response.status_code == 200, response.text
        body = response.json()
        StopLinesResponse.model_validate(body)
        [line] = body["data"]
        assert line["routeId"] == "mot:route:bus_7"
        assert line["operatorId"] == "op_1"
        assert line["operatorName"] == "Synthetic operator"
        assert line["mode"] == "bus"
        assert {p["stopIndex"] for p in line["patterns"]} == {0, 1}
        assert all(p["geometrySource"] == "stop_sequence" for p in line["patterns"])
        assert client.get("/v1/stops/mot:stop:nope/lines").status_code == 404
        assert client.get("/v1/stops/station/lines").status_code == 422
        assert client.get("/v1/stops/mot:stop:station/lines?patterns=x").status_code == 422


@pytest.mark.parametrize(
    ("route_type", "mode"),
    [(0, "light_rail"), (2, "rail"), (3, "bus"), (715, "bus"), (5, "cable_car"), (8, "other")],
)
def test_route_type_modes(route_type, mode):
    assert route_type_mode(route_type) == mode


# --- Board 3: boarding bearing and side of the road ------------------------------------

_STOP = (34.8, 32.0)  # lon, lat
_EAST_5M = 5 / (111_320 * 0.848)  # degrees of longitude for 5 m at 32° N


def _northbound(offset_lon):
    """A road running north past the stop, offset_lon west (+) or east (-) of it."""
    lon = _STOP[0] - offset_lon
    return [[_STOP[0], _STOP[1]], [lon, 31.99998], [lon, 32.0005], [lon, 32.001]]


def test_stop_east_of_a_northbound_road_is_on_the_right():
    found = boarding_geometry(_STOP, _northbound(_EAST_5M), None, "bus")
    assert found.bearing_degrees == pytest.approx(0, abs=0.5)
    assert found.stop_side == "right"
    assert found.stop_offset_meters == pytest.approx(5, abs=0.3)
    assert found.path_point[1] == pytest.approx(32.0, abs=1e-6)


def test_stop_west_of_a_northbound_road_is_on_the_left():
    found = boarding_geometry(_STOP, _northbound(-_EAST_5M), None, "bus")
    assert found.stop_side == "left"


def test_side_withheld_when_it_cannot_be_told():
    assert boarding_geometry(_STOP, _northbound(0), None, "bus").side_unavailable_reason == (
        "stop_on_path"
    )
    far = boarding_geometry(_STOP, _northbound(_EAST_5M * 20), None, "bus")
    assert (far.stop_side, far.side_unavailable_reason) == (None, "path_far_from_stop")
    rail = boarding_geometry(_STOP, _northbound(_EAST_5M), None, "rail")
    assert (rail.stop_side, rail.side_unavailable_reason) == (None, "not_a_street_mode")
    assert rail.bearing_degrees == pytest.approx(0, abs=0.5)
    assert rail.path_point is None


def test_bearing_falls_back_to_the_next_stop():
    found = boarding_geometry(_STOP, None, (_STOP[0] + 0.001, _STOP[1]), "bus")
    assert (found.bearing_source, found.stop_side) == ("stop_sequence", None)
    assert found.bearing_degrees == pytest.approx(90, abs=0.5)
    nothing = boarding_geometry(_STOP, None, None, "bus")
    assert nothing.bearing_degrees is None


def test_recorded_bus_legs_board_on_the_right_as_israel_drives():
    data = json.loads((FIXTURES / "real-plan-depart-at.json").read_text(encoding="utf-8"))
    sides = []
    for itinerary in data["itineraries"]:
        for leg in itinerary["legs"]:
            if leg["mode"] == "WALK":
                continue
            mode = MODE_MAP[leg["mode"]]
            middle = stopovers(leg["intermediateStops"])
            found = boarding(
                mode,
                location(leg["from"]),
                location(leg["to"]),
                geometry(leg["legGeometry"]),
                middle,
                leg.get("headsign"),
            )
            assert found.bearingSource == "leg_geometry"
            assert found.stopCount == len(middle) + 1
            assert found.nextStop.name == (middle[0].name if middle else leg["to"]["name"])
            sides.append((mode, found.stopSide))
    assert [side for mode, side in sides if mode == "bus"] == ["right"] * 9
    assert [side for mode, side in sides if mode == "rail"] == [None, None]


# --- Journeys: boarding, stopovers, platforms (API-C2) and trip exclusion ---------------


class JourneyReference:
    def stop_ref(self, stop_id):
        return {"mot:stop:1": {"platform_code": "3"}}.get(stop_id)


def _journey_engine(engine_route, seen=None):
    second = json.loads(json.dumps(engine_route["itineraries"][0]))
    second["legs"][0]["tripId"] = "20260930_08:10_mot60day_124_300926"
    second["legs"][0]["scheduledStartTime"] = "2026-09-30T05:20:00Z"
    second["legs"][0]["scheduledEndTime"] = "2026-09-30T05:40:00Z"
    second["legs"][0]["intermediateStops"] = [
        {"name": "Middle", "lat": 32.079, "lon": 34.79, "stopId": "mot60day_9"},
        {
            "name": "Skipped",
            "lat": 32.08,
            "lon": 34.80,
            "stopId": "mot60day_10",
            "pickupType": "NOT_ALLOWED",
            "dropoffType": "NOT_ALLOWED",
        },
    ]
    body = {"itineraries": [engine_route["itineraries"][0], second], "direct": []}

    def handle(request):
        if seen is not None:
            seen.append(dict(request.url.params))
        return httpx.Response(200, json=body)

    return handle


def test_journey_legs_carry_boarding_stopovers_and_platform(client_factory, engine_route, query):
    with client_factory(_journey_engine(engine_route)) as client:
        client.app.state.snapshot = replace(client.app.state.snapshot, reference=JourneyReference())
        response = client.post("/v1/journeys", json=query)
    assert response.status_code == 200, response.text
    body = response.json()
    JourneyResponse.model_validate(body)
    leg = body["data"]["journeys"][1]["legs"][0]
    assert leg["from"]["platformCode"] == "3"
    assert leg["to"]["platformCode"] is None
    assert [stop["name"] for stop in leg["intermediateStops"]] == ["Middle"]
    assert leg["boarding"]["stopCount"] == 2
    assert leg["boarding"]["nextStop"]["name"] == "Middle"
    assert leg["boarding"]["towards"] == "Synthetic destination"
    assert 0 <= leg["boarding"]["bearingDegrees"] < 360
    first = body["data"]["journeys"][0]["legs"][0]
    assert first["intermediateStops"] is None  # The engine sent none: unknown, not zero.
    assert first["boarding"]["stopCount"] is None


def test_excluded_trip_alternatives_are_omitted_and_disclosed(client_factory, engine_route, query):
    seen = []
    excluded = engine_route["itineraries"][0]["legs"][0]["tripId"]
    with client_factory(_journey_engine(engine_route, seen)) as client:
        response = client.post(
            "/v1/journeys", json={**query, "results": 1, "excludeTripRefs": [excluded]}
        )
    assert response.status_code == 200, response.text
    body = response.json()
    [journey] = body["data"]["journeys"]
    assert journey["legs"][0]["transit"]["engineTripId"] != excluded
    assert "EXCLUDED_TRIP_ALTERNATIVES_OMITTED" in body["meta"]["warnings"]
    assert body["meta"]["appliedConstraints"]["excludeTripRefs"] == [excluded]
    assert seen[-1]["numItineraries"] == "5"


def test_every_alternative_excluded_is_no_route_not_an_error(client_factory, engine_route, query):
    trips = ["20260930_08:00_mot60day_123_300926", "20260930_08:10_mot60day_124_300926"]
    with client_factory(_journey_engine(engine_route)) as client:
        response = client.post("/v1/journeys", json={**query, "excludeTripRefs": trips})
    assert response.status_code == 200
    assert response.json()["data"]["outcome"] == "no_route"
    assert response.json()["meta"]["warnings"] == ["EXCLUDED_TRIP_ALTERNATIVES_OMITTED"]


@pytest.mark.parametrize(
    "value", [["not-a-trip"], ["20260930_08:00_mot60day_1"] * 2 + ["x"], [f"{i}" for i in range(6)]]
)
def test_exclusions_are_validated(value, query):
    with pytest.raises(ValueError):
        JourneyRequest.model_validate({**query, "excludeTripRefs": value})


def test_openapi_documents_board_endpoints(client_factory):
    with client_factory(_engine({})) as client:
        schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    for path in (
        "/v1/departures/nearby",
        "/v1/stops/{stop_id}/lines",
        "/v1/stops/{stop_id}/departures",
        "/v1/trips/{trip_ref}",
    ):
        assert "200" in paths[path]["get"]["responses"]
        assert "$ref" in json.dumps(paths[path]["get"]["responses"]["200"])
    names = {item["name"] for item in paths["/v1/stops/{stop_id}/departures"]["get"]["parameters"]}
    assert "routeId" in names
    components = schema["components"]["schemas"]
    assert {"operatorId", "operatorName", "mode"} <= set(components["DepartureItem"]["properties"])
    assert "boarding" in components["Leg"]["properties"]
    assert "excludeTripRefs" in components["JourneyRequest"]["properties"]
