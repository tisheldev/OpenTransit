import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from opentransit.api.schemas import JourneyRequest
from opentransit.core.generation import Generation, instant
from opentransit.motis import RANKING_POLICY, EngineFailure, MotisClient

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "motis-v2.11.2"
REAL_PLAN = json.loads((FIXTURE_DIR / "real-plan-depart-at.json").read_text(encoding="utf-8"))


def generation():
    now = datetime(2026, 9, 30, tzinfo=UTC)
    return Generation(
        id="m3-test",
        built_at=now,
        validated_at=now,
        coverage_from=instant("2026-09-29T00:00:00+03:00"),
        coverage_until=instant("2026-10-31T00:00:00+02:00"),
        engine_digest="sha256:" + "a" * 64,
    )


def request(**changes):
    payload = {
        "from": {"kind": "coordinate", "latitude": 32.0757, "longitude": 34.7748},
        "to": {"kind": "coordinate", "latitude": 32.7775, "longitude": 35.0219},
        "departAt": "2026-10-01T08:00:00+03:00",
    }
    payload.update(changes)
    return JourneyRequest.model_validate(payload)


def call_plan(body, query=None, reference=None, seen=None):
    def respond(req):
        if seen is not None:
            seen.append(dict(req.url.params))
        return httpx.Response(200, json=body)

    async def run():
        async with httpx.AsyncClient(
            base_url="http://motis", transport=httpx.MockTransport(respond)
        ) as client:
            return await MotisClient(client).plan(query or request(), generation(), reference)

    return asyncio.run(run())


@pytest.mark.parametrize(
    "times",
    [
        {},
        {"departAt": "2026-10-01T08:00:00+03:00", "arriveBy": "2026-10-01T09:00:00+03:00"},
        {"departAt": None},
        {"arriveBy": None},
        {"arriveBy": "2026-10-01T09:00:00"},
    ],
)
def test_request_requires_exactly_one_explicit_offset_time(times):
    payload = {
        "from": {"kind": "coordinate", "latitude": 32.1, "longitude": 34.8},
        "to": {"kind": "coordinate", "latitude": 32.2, "longitude": 34.9},
        **times,
    }
    with pytest.raises(ValidationError):
        JourneyRequest.model_validate(payload)


def test_request_defaults_and_strict_constraints():
    query = request()
    assert query.modes == ["bus", "rail", "light_rail"]
    assert query.results == 3 and query.lang == "he"
    assert (query.max_access_walk_minutes, query.max_egress_walk_minutes) == (15, 15)
    assert query.max_direct_walk_minutes == 30
    with pytest.raises(ValidationError):
        request(modes=[])
    with pytest.raises(ValidationError):
        request(modes=["rail", "rail"])
    with pytest.raises(ValidationError):
        request(results=True)
    with pytest.raises(ValidationError):
        request(results=6)
    with pytest.raises(ValidationError):
        request(maxAccessWalkMinutes=31)
    with pytest.raises(ValidationError):
        request(maxAccessWalkMinutes=15.0)
    with pytest.raises(ValidationError):
        request(maxWalkMinutesPerLeg=15)
    assert request(modes=["rail"], results=5, lang="en").modes == ["rail"]


def test_stop_reference_requires_namespace_and_resolves_full_engine_identity():
    query = request(**{"from": {"kind": "stop", "stopId": "mot:stop:station-7"}})

    class Reference:
        def stop(self, stop_id):
            assert stop_id == "mot:stop:station-7"
            return {"source_id": "station-7"}

    seen = []
    response = call_plan({"itineraries": [], "direct": []}, query, Reference(), seen)
    assert response.journeys == []
    assert seen[0]["fromPlace"] == "mot60day_station-7"

    with pytest.raises(EngineFailure) as missing_store:
        call_plan({"itineraries": [], "direct": []}, query)
    assert (missing_store.value.code, missing_store.value.status) == ("DATA_UNAVAILABLE", 503)

    class UnknownReference:
        def stop(self, stop_id):
            return None

    with pytest.raises(EngineFailure) as unknown:
        call_plan({"itineraries": [], "direct": []}, query, UnknownReference())
    assert (unknown.value.code, unknown.value.status) == ("NOT_FOUND", 404)

    with pytest.raises(ValidationError):
        request(**{"from": {"kind": "stop", "stopId": "13583"}})


def test_actual_three_are_kept_with_unrouted_transfer_disclosed_and_query_is_pinned():
    seen = []
    result = call_plan(REAL_PLAN, seen=seen)
    assert len(result.journeys) == 3
    assert result.ranking_policy == RANKING_POLICY
    # The real third alternative's rail->bus transfer at Haifa Center HaShmona (37380 -> 2410)
    # is a timetable footpath MOTIS could not street-route: kept, path and distance unknown.
    assert result.warnings == ["TRANSFER_STREET_PATH_UNAVAILABLE"]
    assert result.journeys[0].durationSeconds == 6420
    assert result.journeys[1].durationSeconds == 7620
    third = result.journeys[2]
    transfer = third.legs[4]
    assert (transfer.kind, transfer.origin.stopId, transfer.destination.stopId) == (
        "walk",
        "mot:stop:37380",
        "mot:stop:2410",
    )
    assert transfer.geometry is None and transfer.distanceMeters is None
    assert transfer.geometryUnavailableReason == "street_path_unavailable"
    assert transfer.durationSeconds > 0
    assert third.walkingDistanceMeters is None
    assert third.walkingSeconds == sum(x.durationSeconds for x in third.legs if x.kind == "walk")
    assert result.journeys[0].walkingDistanceMeters == 88.0 + 455.0 + 189.0 + 333.0
    assert result.journeys[0].legs[1].transit.engineTripId.startswith("20261001_")
    assert result.journeys[0].legs[1].origin.stopId.startswith("mot:stop:")
    assert result.journeys[0].legs[1].transit.routeId.startswith("mot:route:")

    params = seen[0]
    assert params["arriveBy"] == "false"
    assert params["time"] == "2026-10-01T08:00:00+03:00"
    assert (
        params["transitModes"]
        == "BUS,COACH,HIGHSPEED_RAIL,LONG_DISTANCE,NIGHT_RAIL,REGIONAL_RAIL,SUBURBAN,TRAM,SUBWAY"
    )
    assert params["numItineraries"] == "3" and params["maxItineraries"] == "5"
    assert params["realtimeMode"] == "OFF" and params["timetableView"] == "true"
    assert params["detailedLegs"] == "true" and params["joinInterlinedLegs"] == "false"
    assert params["detailedTransfers"] == "true"
    assert params["preTransitModes"] == params["postTransitModes"] == "WALK"
    assert params["maxPreTransitTime"] == "900"
    assert params["maxPostTransitTime"] == "900"
    assert params["maxDirectTime"] == "1800"
    assert result.applied_constraints["transferWalkLimit"] == "not_enforced"
    assert result.applied_constraints["engineWalkCapConformance"] == "unverified"


def test_arrive_by_and_walk_caps_are_converted_to_engine_seconds():
    query = JourneyRequest.model_validate(
        {
            "from": {"kind": "coordinate", "latitude": 32.0757, "longitude": 34.7748},
            "to": {"kind": "coordinate", "latitude": 32.7775, "longitude": 35.0219},
            "arriveBy": "2026-10-01T10:00:00+03:00",
            "modes": ["light_rail"],
            "maxAccessWalkMinutes": 5,
            "maxEgressWalkMinutes": 7,
            "maxDirectWalkMinutes": 12,
            "lang": "en",
        }
    )
    seen = []
    result = call_plan({"itineraries": [], "direct": []}, query, seen=seen)
    assert result.applied_constraints["timeMode"] == "arriveBy"
    assert seen[0]["arriveBy"] == "true"
    assert seen[0]["time"] == "2026-10-01T10:00:00+03:00"
    assert seen[0]["transitModes"] == "TRAM,SUBWAY"
    assert seen[0]["preTransitModes"] == seen[0]["postTransitModes"] == "WALK"
    assert seen[0]["maxPreTransitTime"] == "300"
    assert seen[0]["maxPostTransitTime"] == "420"
    assert seen[0]["maxDirectTime"] == "720"
    assert seen[0]["language"] == "en"


def test_deduplication_uses_dated_trip_identity_and_empty_results_only_for_empty_engine():
    one = REAL_PLAN["itineraries"][0]
    duplicate = json.loads(json.dumps(one))
    result = call_plan({"itineraries": [one, duplicate], "direct": []}, request(results=5))
    assert len(result.journeys) == 1
    assert "DUPLICATE_ALTERNATIVES_OMITTED" in result.warnings
    assert result.journeys[0].id.startswith("journey-")

    empty = call_plan({"itineraries": [], "direct": []})
    assert empty.journeys == [] and empty.warnings == []


def test_all_nonempty_but_invalid_alternatives_are_engine_failure():
    with pytest.raises(EngineFailure) as error:
        call_plan({"itineraries": [{"legs": [], "transfers": 0}], "direct": []})
    assert error.value.code == "ENGINE_INVALID_RESPONSE"


def test_unexpected_live_data_fails_whole_scheduled_response():
    live = json.loads(json.dumps(REAL_PLAN["itineraries"][1]))
    live["legs"][1]["realTime"] = True
    with pytest.raises(EngineFailure) as error:
        call_plan({"itineraries": [REAL_PLAN["itineraries"][0], live], "direct": []})
    assert error.value.code == "ENGINE_INVALID_RESPONSE"


def test_engine_alternative_outside_requested_modes_is_not_returned():
    bus_only_query = request(modes=["rail"])
    bus_alternative = json.loads(json.dumps(REAL_PLAN["itineraries"][0]))
    bus_alternative["legs"] = [leg for leg in bus_alternative["legs"] if leg["mode"] != "RAIL"]
    with pytest.raises(EngineFailure) as error:
        call_plan({"itineraries": [bus_alternative], "direct": []}, bus_only_query)
    assert error.value.code == "ENGINE_INVALID_RESPONSE"


def test_departure_and_arrival_anchors_reject_alternatives_on_wrong_side():
    raw = json.loads(json.dumps(REAL_PLAN["itineraries"][0]))
    with pytest.raises(EngineFailure) as early_departure:
        call_plan(
            {"itineraries": [raw], "direct": []}, request(departAt="2026-10-01T09:00:00+03:00")
        )
    assert early_departure.value.code == "ENGINE_INVALID_RESPONSE"

    arrive_by_query = JourneyRequest.model_validate(
        {
            "from": {"kind": "coordinate", "latitude": 32.0757, "longitude": 34.7748},
            "to": {"kind": "coordinate", "latitude": 32.7775, "longitude": 35.0219},
            "arriveBy": "2026-10-01T10:00:00+03:00",
        }
    )
    late = json.loads(json.dumps(raw))
    late["legs"][-1]["scheduledEndTime"] = "2026-10-01T07:01:00Z"
    with pytest.raises(EngineFailure) as late_arrival:
        call_plan({"itineraries": [late], "direct": []}, arrive_by_query)
    assert late_arrival.value.code == "ENGINE_INVALID_RESPONSE"
