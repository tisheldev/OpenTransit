import asyncio
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from opentransit.core.trip_calls import (
    SourceCall,
    SourceProfile,
    project_profile,
)
from opentransit.motis_timetable import (
    TimetableFailure,
    _decode_departure_cursor,
    _departure_cursor,
    _service_day_utc,
    departures,
    hydrate_trip,
    parse_dated_trip_id,
    trip_detail,
)


def profile(trip_id, *, loop=False, pickup=0):
    if loop:
        rows = [
            (5, "origin", 28_800, 28_800),
            (9, "board", 29_400, 29_400),
            (13, "middle", 29_400, 29_400),
            (17, "board", 29_400, 29_400),
            (21, "destination", 30_000, 30_000),
        ]
        # A valid same-time loop keeps both distinct source occurrences.
        rows[3] = (17, "board", 29_400, 29_400)
    else:
        rows = [
            (0, "origin", 28_800, 28_800),
            (2, "board", 29_400, 29_400),
            (8, "destination", 30_000, 30_000),
        ]
    return SourceProfile(
        trip_id,
        "service",
        tuple(
            SourceCall(trip_id, "service", seq, ordinal, stop, arr, dep, pickup, 0)
            for ordinal, (seq, stop, arr, dep) in enumerate(rows)
        ),
    )


def body_for(source, engine_id, service_date):
    projection = project_profile(source)
    base = _service_day_utc(service_date)
    event_map = {
        (event.ordinal, event.kind): base + timedelta(seconds=event.effective_seconds)
        for event in projection.events
    }
    calls = []
    for ordinal, call in enumerate(source.calls):
        value = {
            "stopId": f"mot60day_{call.stop_id}",
            "name": call.stop_id,
            "lat": 32.0,
            "lon": 35.0,
            "stopCode": f"p{ordinal}",
            "pickupType": "NOT_ALLOWED" if call.pickup_type == 1 else "NORMAL",
        }
        if (ordinal, "arrival") in event_map:
            value["scheduledArrival"] = (
                event_map[ordinal, "arrival"].isoformat().replace("+00:00", "Z")
            )
        if (ordinal, "departure") in event_map:
            value["scheduledDeparture"] = (
                event_map[ordinal, "departure"].isoformat().replace("+00:00", "Z")
            )
        calls.append(value)
    return {
        "legs": [
            {
                "mode": "BUS",
                "tripId": engine_id,
                "routeId": "mot60day_route_7",
                "routeShortName": "7",
                "headsign": "destination",
                "realTime": False,
                "cancelled": False,
                "from": calls[0],
                "intermediateStops": calls[1:-1],
                "to": calls[-1],
                "legGeometry": None,
            }
        ]
    }


def test_full_dated_trip_id_and_service_day_dst_basis():
    service_date, start_time, source = parse_dated_trip_id(
        "20261025_01:10_mot60day_full_trip_id_with_suffix"
    )
    assert service_date == date(2026, 10, 25)
    assert start_time == "01:10"
    assert source == "full_trip_id_with_suffix"
    assert _service_day_utc(date(2026, 10, 25)) == datetime(2026, 10, 24, 22, tzinfo=UTC)
    assert _service_day_utc(date(2026, 10, 24)) == datetime(2026, 10, 23, 21, tzinfo=UTC)


def test_hydration_reconciles_full_loop_vector_and_keeps_original_sequences():
    source = profile("loop_trip_id", loop=True)
    engine_id = "20261001_08:00_mot60day_loop_trip_id"
    result = hydrate_trip(source, engine_id, body_for(source, engine_id, date(2026, 10, 1)))
    assert [call["callSequence"] for call in result["calls"]] == [5, 9, 13, 17, 21]
    assert [call["stopId"] for call in result["calls"]].count("mot:stop:board") == 2
    assert result["calls"][0]["scheduledArrival"] is None
    assert result["calls"][-1]["scheduledDeparture"] is None
    assert result["tripRef"] == engine_id
    assert result["sourceTripId"] == "loop_trip_id"


def test_hydration_rejects_wrong_full_identity_or_one_minute_clock_drift():
    source = profile("loop_trip_id", loop=True)
    service_date = date(2026, 10, 1)
    engine_id = "20261001_08:00_mot60day_loop_trip_id"
    body = body_for(source, engine_id, service_date)
    body["legs"][0]["intermediateStops"][0]["scheduledDeparture"] = "2026-10-01T05:11:00Z"
    with pytest.raises(ValueError):
        hydrate_trip(source, engine_id, body)
    with pytest.raises(ValueError):
        hydrate_trip(source, "20261001_08:00_mot60day_loop_trip_id_other", body)


class Ref:
    def __init__(self, profiles):
        self.profiles = profiles

    def stop(self, _stop_id):
        return {"source_id": "board", "platform_code": None, "children": []}

    def source_profile(self, source_id):
        return self.profiles.get(source_id)

    def service_active(self, _service_id, _service_date):
        return True


class Generation:
    id = "timetable-test"
    coverage_from = datetime(2026, 9, 30, tzinfo=UTC)
    coverage_until = datetime(2026, 10, 3, tzinfo=UTC)

    @staticmethod
    def contains(_instant):
        return True


class Snapshot:
    generation = Generation()
    routing_verified = True

    def __init__(self, ref, client):
        self.reference = ref
        self.motis = type("Motis", (), {"client": client})()


def test_departures_page_preserves_same_time_trips_and_loop_occurrences():
    sources = {
        "loop_trip": profile("loop_trip", loop=True, pickup=2),
        "other_trip": profile("other_trip", pickup=3),
        "prohibited_trip": profile("prohibited_trip", pickup=1),
    }
    service_date = date(2026, 10, 1)
    ids = {
        "loop_trip": "20261001_08:00_mot60day_loop_trip",
        "other_trip": "20261001_08:00_mot60day_other_trip",
        "prohibited_trip": "20261001_08:00_mot60day_prohibited_trip",
    }

    def handler(request):
        if request.url.path.endswith("/stoptimes"):
            assert request.url.params["n"] == "1"
            assert request.url.params["window"] == "7200"
            return httpx.Response(
                200,
                json={
                    "stopTimes": [
                        {
                            "tripId": ids[source_id],
                            "realTime": False,
                            "cancelled": False,
                            "tripCancelled": False,
                            "pickupDropoffType": "NORMAL",
                            "headsign": "head",
                            "place": {
                                "stopId": "mot60day_board",
                                "scheduledDeparture": (
                                    _service_day_utc(service_date) + timedelta(seconds=29_400)
                                )
                                .isoformat()
                                .replace("+00:00", "Z"),
                                "stopCode": "Bay A",
                            },
                        }
                        for source_id in sources
                    ]
                    + [
                        {
                            "tripId": "not-a-valid-dated-trip",
                            "realTime": False,
                            "pickupDropoffType": "NORMAL",
                            "place": {
                                "stopId": "mot60day_board",
                                "scheduledDeparture": (
                                    _service_day_utc(service_date) + timedelta(seconds=8_000)
                                )
                                .isoformat()
                                .replace("+00:00", "Z"),
                            },
                        }
                    ]
                },
            )
        engine_id = request.url.params["tripId"]
        source_id = next(key for key, value in ids.items() if value == engine_id)
        return httpx.Response(200, json=body_for(sources[source_id], engine_id, service_date))

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://engine"
        ) as client:
            snapshot = Snapshot(Ref(sources), client)
            first = await departures(
                snapshot,
                "mot:stop:board",
                _service_day_utc(service_date) + timedelta(seconds=28_800),
                120,
                1,
                None,
            )
            all_events = list(first["items"])
            cursor = first["nextCursor"]
            while cursor:
                page = await departures(
                    snapshot,
                    "mot:stop:board",
                    _service_day_utc(service_date) + timedelta(seconds=28_800),
                    120,
                    1,
                    cursor,
                )
                all_events.extend(page["items"])
                cursor = page["nextCursor"]
        return all_events

    events = asyncio.run(run())
    keys = [
        (event["scheduledDeparture"], event["tripRef"], event["callSequence"]) for event in events
    ]
    assert len(keys) == 3
    assert len(set(keys)) == 3
    assert [event["callSequence"] for event in events if event["tripRef"] == ids["loop_trip"]] == [
        9,
        17,
    ]
    assert all(event["platformCode"] is None for event in events)
    assert [event["pickupType"] for event in events] == [2, 2, 3]


def test_departure_cursor_binds_generation_query_and_all_sort_fields():
    query = {
        "stop": "mot:stop:board",
        "stopIds": ["board"],
        "from": "2026-10-01T05:00:00+00:00",
        "until": "2026-10-01T07:00:00+00:00",
        "limit": 1,
    }
    position = [
        "2026-10-01T05:10:00+00:00",
        "20261001_08:00_mot60day_full_trip_id",
        "board",
        17,
    ]
    cursor = _departure_cursor("generation-a", query, position)
    assert _decode_departure_cursor(cursor, "generation-a", query) == [
        "2026-10-01T05:10:00+00:00",
        "20261001_08:00_mot60day_full_trip_id",
        "board",
        17,
    ]
    with pytest.raises(ValueError):
        _decode_departure_cursor(cursor, "generation-b", query)
    with pytest.raises(ValueError):
        _decode_departure_cursor(cursor, "generation-a", {**query, "stop": "mot:stop:elsewhere"})
    with pytest.raises(ValueError):
        invalid = _departure_cursor("generation-a", query, ["time", "full_trip", "board", 17])
        _decode_departure_cursor(invalid, "generation-a", query)


def test_trip_detail_checks_occurrence_coverage_before_engine_request():
    source = profile("covered_trip")

    def unexpected_request(_request):
        raise AssertionError("Outside-coverage occurrences must not query the engine")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(unexpected_request), base_url="http://engine"
        ) as client:
            snapshot = Snapshot(Ref({"covered_trip": source}), client)
            snapshot.generation = type(
                "OutsideGeneration",
                (),
                {"id": "outside", "contains": staticmethod(lambda _instant: False)},
            )()
            await trip_detail(snapshot, "20261001_08:00_mot60day_covered_trip")

    with pytest.raises(TimetableFailure) as error:
        asyncio.run(run())
    assert error.value.status == 422
    assert error.value.code == "OUTSIDE_SERVICE_WINDOW"


def test_trip_engine_404_is_not_rewritten_as_an_empty_trip():
    source = profile("missing_occurrence")

    def handler(_request):
        return httpx.Response(404, json={"error": "not found"})

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://engine"
        ) as client:
            snapshot = Snapshot(Ref({"missing_occurrence": source}), client)
            await trip_detail(snapshot, "20261001_08:00_mot60day_missing_occurrence")

    with pytest.raises(TimetableFailure) as error:
        asyncio.run(run())
    assert error.value.status == 404
    assert error.value.code == "NOT_FOUND"


def test_upstream_stoptimes_limit_error_is_not_returned_as_a_partial_page():
    def handler(request):
        if request.url.path.endswith("/stoptimes"):
            return httpx.Response(500, json={"error": "too many stop times"})
        raise AssertionError("A possibly truncated window must not hydrate trip IDs")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://engine"
        ) as client:
            snapshot = Snapshot(Ref({}), client)
            await departures(
                snapshot,
                "mot:stop:board",
                datetime(2026, 10, 1, 5, tzinfo=UTC),
                60,
                20,
                None,
            )

    with pytest.raises(TimetableFailure) as error:
        asyncio.run(run())
    assert error.value.status == 503


def test_in_window_wire_event_without_matching_source_call_is_a_failure():
    source = profile("mismatch_trip")
    engine_id = "20261001_08:00_mot60day_mismatch_trip"

    def handler(request):
        if request.url.path.endswith("/stoptimes"):
            return httpx.Response(
                200,
                json={
                    "stopTimes": [
                        {
                            "tripId": engine_id,
                            "realTime": False,
                            "pickupDropoffType": "NORMAL",
                            "place": {
                                "stopId": "mot60day_board",
                                "scheduledDeparture": "2026-10-01T05:11:00Z",
                            },
                        }
                    ]
                },
            )
        return httpx.Response(200, json=body_for(source, engine_id, date(2026, 10, 1)))

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://engine"
        ) as client:
            await departures(
                Snapshot(Ref({"mismatch_trip": source}), client),
                "mot:stop:board",
                datetime(2026, 10, 1, 5, tzinfo=UTC),
                60,
                20,
                None,
            )

    with pytest.raises(TimetableFailure) as error:
        asyncio.run(run())
    assert error.value.status == 503


def test_collapsed_not_allowed_wire_event_expands_boardable_loop_sequence():
    base = profile("collapsed_loop", loop=True)
    source = SourceProfile(
        base.trip_id,
        base.service_id,
        tuple(
            SourceCall(
                call.trip_id,
                call.service_id,
                call.sequence,
                call.ordinal,
                call.stop_id,
                call.arrival_seconds,
                call.departure_seconds,
                1 if call.sequence == 9 else 0,
                call.drop_off_type,
            )
            for call in base.calls
        ),
    )
    engine_id = "20261001_08:00_mot60day_collapsed_loop"

    def handler(request):
        if request.url.path.endswith("/stoptimes"):
            return httpx.Response(
                200,
                json={
                    "stopTimes": [
                        {
                            "tripId": engine_id,
                            "realTime": False,
                            "pickupDropoffType": "NOT_ALLOWED",
                            "place": {
                                "stopId": "mot60day_board",
                                "scheduledDeparture": "2026-10-01T05:10:00Z",
                            },
                        }
                    ]
                },
            )
        return httpx.Response(200, json=body_for(source, engine_id, date(2026, 10, 1)))

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://engine"
        ) as client:
            return await departures(
                Snapshot(Ref({"collapsed_loop": source}), client),
                "mot:stop:board",
                datetime(2026, 10, 1, 5, tzinfo=UTC),
                60,
                20,
                None,
            )

    page = asyncio.run(run())
    assert [item["callSequence"] for item in page["items"]] == [17]


def test_parent_scope_expands_deduplicated_same_time_child_platform_calls():
    source = SourceProfile(
        "platform_trip",
        "service",
        tuple(
            SourceCall(
                "platform_trip", "service", sequence, ordinal, stop, arrival, departure, 0, 0
            )
            for ordinal, (sequence, stop, arrival, departure) in enumerate(
                [
                    (0, "origin", 28_800, 28_800),
                    (9, "platform_a", 29_400, 29_400),
                    (17, "platform_b", 29_400, 29_400),
                    (21, "destination", 30_000, 30_000),
                ]
            )
        ),
    )
    engine_id = "20261001_08:00_mot60day_platform_trip"

    class ParentRef(Ref):
        def stop(self, stop_ref):
            if stop_ref == "mot:stop:parent":
                return {
                    "source_id": "parent",
                    "platform_code": None,
                    "children": [
                        {"source_id": "platform_a", "platform_code": "A"},
                        {"source_id": "platform_b", "platform_code": "B"},
                    ],
                }
            source_id = stop_ref.removeprefix("mot:stop:")
            return {"source_id": source_id, "platform_code": source_id, "children": []}

    def handler(request):
        if request.url.path.endswith("/stoptimes"):
            return httpx.Response(
                200,
                json={
                    "stopTimes": [
                        {
                            "tripId": engine_id,
                            "realTime": False,
                            "pickupDropoffType": "NORMAL",
                            "place": {
                                "stopId": "mot60day_platform_a",
                                "scheduledDeparture": "2026-10-01T05:10:00Z",
                            },
                        }
                    ]
                },
            )
        return httpx.Response(200, json=body_for(source, engine_id, date(2026, 10, 1)))

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://engine"
        ) as client:
            snapshot = Snapshot(ParentRef({"platform_trip": source}), client)
            parent = await departures(
                snapshot,
                "mot:stop:parent",
                datetime(2026, 10, 1, 5, tzinfo=UTC),
                60,
                20,
                None,
            )
            child = await departures(
                snapshot,
                "mot:stop:platform_b",
                datetime(2026, 10, 1, 5, tzinfo=UTC),
                60,
                20,
                None,
            )
            return parent, child

    parent, child = asyncio.run(run())
    assert [item["callSequence"] for item in parent["items"]] == [9, 17]
    assert [item["stopId"] for item in parent["items"]] == [
        "mot:stop:platform_a",
        "mot:stop:platform_b",
    ]
    assert [item["callSequence"] for item in child["items"]] == [17]


def test_engine_event_for_inactive_source_service_fails_closed():
    source = profile("inactive_trip")
    engine_id = "20261001_08:00_mot60day_inactive_trip"

    class InactiveRef(Ref):
        def service_active(self, _service_id, _service_date):
            return False

    def handler(request):
        if request.url.path.endswith("/stoptimes"):
            return httpx.Response(
                200,
                json={
                    "stopTimes": [
                        {
                            "tripId": engine_id,
                            "realTime": False,
                            "pickupDropoffType": "NORMAL",
                            "place": {
                                "stopId": "mot60day_board",
                                "scheduledDeparture": "2026-10-01T05:10:00Z",
                            },
                        }
                    ]
                },
            )
        raise AssertionError("Calendar mismatch must fail before whole-trip hydration")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://engine"
        ) as client:
            await departures(
                Snapshot(InactiveRef({"inactive_trip": source}), client),
                "mot:stop:board",
                datetime(2026, 10, 1, 5, tzinfo=UTC),
                60,
                20,
                None,
            )

    with pytest.raises(TimetableFailure) as error:
        asyncio.run(run())
    assert error.value.status == 503
