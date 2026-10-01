"""M3.2: every advertised journey constraint maps to an exact engine query parameter.

All engine responses are labelled synthetic; nothing here measures real MOTIS enforcement.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError
from test_journey_features import call_plan, request

from opentransit.api.schemas import JourneyRequest

# public field -> (engine parameter, default minutes, maximum minutes)
CAPS = {
    "maxAccessWalkMinutes": ("maxPreTransitTime", 15),
    "maxEgressWalkMinutes": ("maxPostTransitTime", 15),
    "maxDirectWalkMinutes": ("maxDirectTime", 30),
}
DEFAULT_PARAMS = {engine: str(minutes * 60) for engine, minutes in CAPS.values()}
EMPTY = {"itineraries": [], "direct": []}


def synthetic_itinerary(base, tag, *, transfer_walk_minutes=4, day=None):
    """walk, bus, transfer walk, bus, walk; times are consecutive and coordinates connect."""
    day = day or base.strftime("%Y%m%d")
    plan = [("WALK", 2), ("BUS", 10), ("WALK", transfer_walk_minutes), ("BUS", 10), ("WALK", 3)]
    legs, clock = [], base
    for index, (mode, minutes) in enumerate(plan):
        end = clock + timedelta(minutes=minutes)
        place = lambda i: {  # noqa: E731
            "name": f"P{i}",
            "lat": 32.0 + i * 0.01,
            "lon": 34.8 + i * 0.01,
            "stopId": f"mot60day_{i}",
        }
        leg = {
            "mode": mode,
            "from": place(index),
            "to": place(index + 1),
            "scheduledStartTime": clock.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scheduledEndTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "realTime": False,
            "cancelled": False,
            "distance": 100.0 * minutes,
        }
        if mode == "BUS":
            leg |= {
                "agencyId": "1",
                "agencyName": "Synthetic operator",
                "routeId": "mot60day_7",
                "routeShortName": "7",
                "headsign": "Synthetic",
                "tripId": f"{day}_08:00_mot60day_{tag}_{day}",
            }
        legs.append(leg)
        clock = end
    return {"transfers": 1, "legs": legs}


BASE = datetime(2026, 10, 1, 5, 10, tzinfo=UTC)


def departures(result):
    return [journey.timing.scheduledDeparture.astimezone(UTC) for journey in result.journeys]


# --- exact engine parameters and boundaries -------------------------------------------------


@pytest.mark.parametrize("field", CAPS)
@pytest.mark.parametrize("minutes", [1, 7, 29, 30])
def test_each_cap_sets_only_its_engine_parameter_in_seconds(field, minutes):
    seen = []
    result = call_plan(EMPTY, request(**{field: minutes}), seen=seen)
    engine_parameter, _ = CAPS[field]
    expected = dict(DEFAULT_PARAMS, **{engine_parameter: str(minutes * 60)})
    assert {name: seen[0][name] for name in DEFAULT_PARAMS} == expected
    assert result.applied_constraints[field] == minutes


def test_defaults_are_sent_explicitly_not_left_to_engine_defaults():
    seen = []
    result = call_plan(EMPTY, seen=seen)
    assert {name: seen[0][name] for name in DEFAULT_PARAMS} == {
        "maxPreTransitTime": "900",
        "maxPostTransitTime": "900",
        "maxDirectTime": "1800",
    }
    assert [result.applied_constraints[field] for field in CAPS] == [15, 15, 30]


def test_caps_are_independent_and_no_other_walking_parameter_is_sent():
    seen = []
    call_plan(
        EMPTY,
        request(maxAccessWalkMinutes=2, maxEgressWalkMinutes=11, maxDirectWalkMinutes=23),
        seen=seen,
    )
    params = seen[0]
    assert (params["maxPreTransitTime"], params["maxPostTransitTime"]) == ("120", "660")
    assert params["maxDirectTime"] == "1380"
    # Only walk-mode selectors and the three caps; no transfer or per-leg limit is invented.
    limits = {k for k in params if k.startswith(("max", "pre", "post", "direct"))}
    assert limits == {
        "maxItineraries",
        "maxPreTransitTime",
        "maxPostTransitTime",
        "maxDirectTime",
        "preTransitModes",
        "postTransitModes",
        "directModes",
    }
    assert (
        params["directModes"] == params["preTransitModes"] == params["postTransitModes"] == "WALK"
    )


@pytest.mark.parametrize("field", CAPS)
@pytest.mark.parametrize("value", [0, -1, 31, 3600, 15.0, "15", True, None])
def test_cap_validation_rejects_out_of_range_and_non_integers(field, value):
    with pytest.raises(ValidationError):
        request(**{field: value})


@pytest.mark.parametrize("field", CAPS)
@pytest.mark.parametrize("value", [0, 31, 15.0, "15", True, None])
def test_http_invalid_cap_is_422_problem_and_never_reaches_engine(
    client_factory, query, field, value
):
    query[field] = value
    with client_factory(lambda r: pytest.fail("Invalid cap reached engine")) as client:
        response = client.post("/v1/journeys", json=query)
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == "INVALID_REQUEST" and body["status"] == 422
    assert body["errors"] == [{"field": f"body.{field}", "reason": "Invalid or unsupported field"}]
    assert body["requestId"] == response.headers["x-request-id"]
    assert "15.0" not in response.text


@pytest.mark.parametrize("field", CAPS)
@pytest.mark.parametrize("minutes", [1, 30])
def test_http_boundary_caps_reach_engine_as_seconds(
    client_factory, query, engine_route, field, minutes
):
    seen = []

    def engine(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json=engine_route)

    query[field] = minutes
    with client_factory(engine) as client:
        response = client.post("/v1/journeys", json=query)
    assert response.status_code == 200
    engine_parameter, _ = CAPS[field]
    assert seen[0][engine_parameter] == str(minutes * 60)
    assert response.json()["meta"]["appliedConstraints"][field] == minutes


@pytest.mark.parametrize("unsupported", ["maxWalkMinutesPerLeg", "maxTransferWalkMinutes"])
def test_per_leg_and_transfer_caps_are_rejected_not_approximated(
    client_factory, query, unsupported
):
    query[unsupported] = 5
    with client_factory(lambda r: pytest.fail("Unsupported cap reached engine")) as client:
        response = client.post("/v1/journeys", json=query)
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert unsupported not in response.text  # unknown field names are redacted
    with pytest.raises(ValidationError):
        JourneyRequest.model_validate(
            {
                "from": query["from"],
                "to": query["to"],
                "departAt": query["departAt"],
                unsupported: 5,
            }
        )


# --- OpenAPI contract matches what the adapter does -------------------------------------------


def test_openapi_advertises_exactly_the_three_caps_with_bounds_and_engine_mapping(
    client_factory,
):
    with client_factory(lambda r: pytest.fail("No engine call")) as client:
        schema = client.get("/openapi.json").json()
    components = schema["components"]["schemas"]
    properties = components["JourneyRequest"]["properties"]
    for field, (engine_parameter, default) in CAPS.items():
        item = properties[field]
        assert (item["minimum"], item["maximum"], item["default"]) == (1, 30, default)
        assert item["type"] == "integer"
        assert engine_parameter in item["description"]
    assert not [name for name in properties if "transfer" in name.lower() or "leg" in name.lower()]
    disclosure = components["Metadata"]["properties"]["appliedConstraints"]["description"]
    assert "transferWalkLimit" in disclosure and "not_enforced" in disclosure
    for status in ("413", "422", "503", "504"):
        assert (
            "application/problem+json"
            in schema["paths"]["/v1/journeys"]["post"]["responses"][status]["content"]
        )


# --- other advertised request constraints -----------------------------------------------------


@pytest.mark.parametrize(
    "modes,expected",
    [
        (["bus"], "BUS,COACH"),
        (["rail"], "HIGHSPEED_RAIL,LONG_DISTANCE,NIGHT_RAIL,REGIONAL_RAIL,SUBURBAN"),
        (["light_rail"], "TRAM,SUBWAY"),
        (["light_rail", "bus"], "TRAM,SUBWAY,BUS,COACH"),
    ],
)
def test_mode_selection_maps_to_engine_transit_modes(modes, expected):
    seen = []
    result = call_plan(EMPTY, request(modes=modes), seen=seen)
    assert seen[0]["transitModes"] == expected
    assert result.applied_constraints["modes"] == modes


@pytest.mark.parametrize("results", [1, 2, 5])
def test_result_count_boundaries_reach_engine_and_cap_the_response(results):
    seen = []
    engine_body = {
        "itineraries": [synthetic_itinerary(BASE + timedelta(hours=i), f"t{i}") for i in range(6)],
        "direct": [],
    }
    result = call_plan(engine_body, request(results=results), seen=seen)
    assert seen[0]["numItineraries"] == str(results) and seen[0]["maxItineraries"] == "5"
    assert len(result.journeys) == results


@pytest.mark.parametrize("results", [0, 6, -1, 3.0, "3", True])
def test_result_count_outside_one_to_five_is_rejected(results):
    with pytest.raises(ValidationError):
        request(results=results)


@pytest.mark.parametrize("lang", ["he", "en"])
def test_language_reaches_engine(lang):
    seen = []
    call_plan(EMPTY, request(lang=lang), seen=seen)
    assert seen[0]["language"] == lang


def test_unsupported_language_and_mode_are_validation_errors():
    for changes in ({"lang": "fr"}, {"modes": ["ferry"]}, {"modes": ["bus", "bus"]}):
        with pytest.raises(ValidationError):
            request(**changes)


# --- transfer walking is disclosed, never filtered ---------------------------------------------


def test_http_transfer_walk_is_disclosed_and_a_long_transfer_walk_is_not_filtered(
    client_factory, query
):
    base = datetime(2026, 9, 30, 5, 10, tzinfo=UTC)
    long_transfer = synthetic_itinerary(base, "long", transfer_walk_minutes=40)
    seen = []

    def engine(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json={"itineraries": [long_transfer], "direct": []})

    query.update(maxAccessWalkMinutes=1, maxEgressWalkMinutes=1, maxDirectWalkMinutes=1)
    with client_factory(engine) as client:
        response = client.post("/v1/journeys", json=query)
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["appliedConstraints"]["transferWalkLimit"] == "not_enforced"
    assert body["meta"]["appliedConstraints"]["engineWalkCapConformance"] == "unverified"
    journey = body["data"]["journeys"][0]
    walks = [leg["durationSeconds"] for leg in journey["legs"] if leg["kind"] == "walk"]
    assert walks == [120, 2400, 180]  # the 40-minute transfer walk survives a 1-minute cap
    assert journey["walkingSeconds"] == sum(walks)
    assert all(leg["timing"]["timingState"] == "scheduled" for leg in journey["legs"])
    assert not any("transfer" in name.lower() for name in seen[0] if name != "detailedTransfers")


# --- ordering, dated deduplication and street-path omissions ------------------------------------


def test_feasible_engine_order_is_preserved_not_sorted_by_time():
    late = synthetic_itinerary(BASE + timedelta(hours=3), "late")
    early = synthetic_itinerary(BASE, "early")
    middle = synthetic_itinerary(BASE + timedelta(hours=1), "middle")
    direct = synthetic_itinerary(BASE + timedelta(hours=2), "direct")
    direct["legs"] = direct["legs"][:1]
    direct["transfers"] = 0
    result = call_plan(
        {"itineraries": [late, early, middle], "direct": [direct]}, request(results=5)
    )
    assert departures(result) == [
        BASE + timedelta(hours=3),
        BASE,
        BASE + timedelta(hours=1),
        BASE + timedelta(hours=2),
    ]
    assert result.ranking_policy == "motis-v2.11.2-feasible-engine-order-v1"


def test_deduplication_distinguishes_service_dates_and_counts_after_dedupe():
    today = synthetic_itinerary(BASE, "same")
    repeat = synthetic_itinerary(BASE, "same")
    tomorrow = synthetic_itinerary(BASE + timedelta(days=1), "same")
    other = synthetic_itinerary(BASE + timedelta(hours=1), "other")
    result = call_plan(
        {"itineraries": [today, repeat, tomorrow, other], "direct": []}, request(results=3)
    )
    assert departures(result) == [BASE, BASE + timedelta(days=1), BASE + timedelta(hours=1)]
    assert [j.legs[1].transit.serviceDate.isoformat() for j in result.journeys] == [
        "2026-10-01",
        "2026-10-02",
        "2026-10-01",
    ]
    assert len({j.id for j in result.journeys}) == 3
    assert result.warnings == ["DUPLICATE_ALTERNATIVES_OMITTED"]


def test_missing_street_path_omits_that_alternative_once_and_keeps_the_others_in_order():
    first = synthetic_itinerary(BASE + timedelta(hours=2), "a")
    broken_one = synthetic_itinerary(BASE, "b")
    broken_one["legs"][2]["cancelled"] = True
    broken_two = synthetic_itinerary(BASE + timedelta(hours=1), "c")
    broken_two["legs"][0]["cancelled"] = True
    last = synthetic_itinerary(BASE + timedelta(hours=3), "d")
    result = call_plan(
        {"itineraries": [first, broken_one, broken_two, last], "direct": []}, request(results=5)
    )
    assert departures(result) == [BASE + timedelta(hours=2), BASE + timedelta(hours=3)]
    assert result.warnings == ["INFEASIBLE_STREET_ALTERNATIVES_OMITTED"]


def test_cancelled_non_walk_leg_is_not_a_street_omission_but_an_invalid_alternative():
    from opentransit.motis import EngineFailure

    live = synthetic_itinerary(BASE, "a")
    live["legs"][1]["cancelled"] = True
    with pytest.raises(EngineFailure) as error:
        call_plan({"itineraries": [live], "direct": []})
    assert error.value.code == "ENGINE_INVALID_RESPONSE"


def test_http_all_alternatives_missing_street_paths_is_no_route_with_warning(client_factory, query):
    only = synthetic_itinerary(datetime(2026, 9, 30, 5, 10, tzinfo=UTC), "x")
    only["legs"][0]["cancelled"] = True
    with client_factory(
        lambda r: httpx.Response(200, json={"itineraries": [only], "direct": []})
    ) as c:
        response = c.post("/v1/journeys", json=query)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["outcome"] == "no_route" and body["data"]["journeys"] == []
    assert body["meta"]["warnings"] == ["INFEASIBLE_STREET_ALTERNATIVES_OMITTED"]
