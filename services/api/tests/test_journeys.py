import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest


def test_schedule_response_identity_and_geojson(client_factory, query, engine_route, caplog):
    seen = []

    def engine(request):
        seen.append(request)
        return httpx.Response(200, json=engine_route)

    with client_factory(engine) as client:
        assert client.get("/healthz").json() == {"status": "alive"}
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
        assert set(schema["paths"]) == {"/healthz", "/v1/journeys"}
        response = client.post("/v1/journeys", json=query, headers={"X-Request-ID": "unsafe-id"})
    assert response.status_code == 200
    body = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert body["meta"]["requestId"] == response.headers["x-request-id"] != "unsafe-id"
    assert body["meta"]["mode"] == "fixture"
    assert body["meta"]["capabilities"] == {"realtime": "not_enabled", "alerts": "not_enabled"}
    assert body["data"]["alerts"] is None
    leg = body["data"]["journeys"][0]["legs"][0]
    assert leg["timing"]["timingState"] == "scheduled"
    assert leg["timing"]["expectedDeparture"] is None
    assert leg["timing"]["delaySeconds"] is None
    assert leg["transit"]["sourceTripId"] == "123_300926"
    assert leg["transit"]["serviceDate"] == "2026-09-30"
    assert leg["transit"]["engineTripId"] == "20260930_08:00_mot60day_123_300926"
    assert leg["geometry"]["coordinates"][0] == pytest.approx([34.774846, 32.075721])
    assert seen[0].url.path == "/api/v6/plan"
    assert seen[0].url.params["time"] == query["departAt"]
    assert "32.0757" not in caplog.text
    assert "34.7748" not in caplog.text
    assert "route=/v1/journeys status=200" in caplog.text


def test_empty_search_and_walk_only(client_factory, query, engine_route):
    with client_factory(lambda r: httpx.Response(200, json={"itineraries": [], "direct": []})) as c:
        response = c.post("/v1/journeys", json=query)
        assert response.status_code == 200
        assert response.json()["data"] == {"outcome": "no_route", "journeys": [], "alerts": None}
    leg = engine_route["itineraries"][0]["legs"][0]
    leg["mode"] = "WALK"
    engine_route["direct"] = engine_route.pop("itineraries")
    engine_route["itineraries"] = []
    with client_factory(lambda r: httpx.Response(200, json=engine_route)) as c:
        data = c.post("/v1/journeys", json=query).json()["data"]
    assert data["outcome"] == "routes_found"
    assert data["journeys"][0]["legs"][0]["transit"] is None
    assert data["journeys"][0]["walkingSeconds"] == 1200


@pytest.mark.parametrize(
    "field,value",
    [
        ("departAt", "2026-09-30T08:00:00"),
        ("departAt", "2026-09-30"),
        ("departAt", 1790744400),
        ("departAt", "2026-11-30T08:00:00+02:00"),
        ("arriveBy", "2026-09-30T08:00:00+03:00"),
        ("results", 3),
    ],
)
def test_time_and_unsupported_fields(client_factory, query, field, value):
    def unused(request):
        pytest.fail("Invalid query reached engine")

    query[field] = value
    with client_factory(unused) as c:
        response = c.post("/v1/journeys", json=query)
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize("latitude", [True, "32.07571234", 99, None])
def test_coordinate_validation_and_redaction(client_factory, query, latitude, caplog):
    query["from"]["latitude"] = latitude
    query["from"]["32.07571234"] = "secret sentinel"
    with client_factory(lambda r: pytest.fail("Invalid query reached engine")) as c:
        response = c.post("/v1/journeys", json=query)
        malformed = c.post(
            "/v1/journeys",
            content='{"secret sentinel":',
            headers={"Content-Type": "application/json"},
        )
        unknown = c.get("/32.07571234?location=secret-sentinel")
    assert response.status_code == malformed.status_code == 422
    assert unknown.status_code == 404
    for text in (response.text, malformed.text, unknown.text, caplog.text):
        assert "32.07571234" not in text
        assert "secret sentinel" not in text


@pytest.mark.parametrize(
    "failure,status,code",
    [
        ("connect", 503, "ENGINE_UNAVAILABLE"),
        ("timeout", 504, "ENGINE_TIMEOUT"),
        ("http", 503, "ENGINE_UNAVAILABLE"),
        ("malformed", 503, "ENGINE_INVALID_RESPONSE"),
    ],
)
def test_dependency_failures_are_not_no_route(client_factory, query, failure, status, code):
    def engine(request):
        if failure == "connect":
            raise httpx.ConnectError("sensitive-location", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("sensitive-location", request=request)
        return httpx.Response(500 if failure == "http" else 200, json={"private": "engine error"})

    with client_factory(engine) as c:
        response = c.post("/v1/journeys", json=query)
    assert response.status_code == status
    assert response.json()["code"] == code
    assert "sensitive-location" not in response.text
    assert "engine error" not in response.text


def test_absolute_deadline(client_factory, query):
    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json={"itineraries": [], "direct": []})

    with client_factory(slow, deadline=0.05) as c:
        response = c.post("/v1/journeys", json=query)
    assert response.status_code == 504


@pytest.mark.parametrize(
    "mutation", ["live", "reversed", "bad_identity", "bad_shape", "empty", "leg_type", "shape_type"]
)
def test_invalid_itinerary_is_dependency_error(client_factory, query, engine_route, mutation):
    leg = engine_route["itineraries"][0]["legs"][0]
    if mutation == "live":
        leg["realTime"] = True
    elif mutation == "reversed":
        leg["scheduledEndTime"] = "2026-09-30T05:00:00Z"
    elif mutation == "bad_identity":
        leg["tripId"] = "123"
    elif mutation == "bad_shape":
        leg["legGeometry"]["points"] = "?"
    elif mutation == "leg_type":
        engine_route["itineraries"][0]["legs"] = ["unexpected"]
    elif mutation == "shape_type":
        leg["legGeometry"] = ["unexpected"]
    else:
        engine_route["itineraries"][0]["legs"] = []
    with client_factory(lambda r: httpx.Response(200, json=engine_route)) as c:
        response = c.post("/v1/journeys", json=query)
    assert response.status_code == 503
    assert response.json()["code"] == "ENGINE_INVALID_RESPONSE"


def test_service_date_is_not_boarding_date(client_factory, query, engine_route):
    query["departAt"] = "2026-09-30T00:00:00+03:00"
    leg = engine_route["itineraries"][0]["legs"][0]
    leg["tripId"] = "20260929_24:30_mot60day_123_290926"
    leg["scheduledStartTime"] = "2026-09-29T21:30:00Z"
    leg["scheduledEndTime"] = "2026-09-29T22:00:00Z"
    with client_factory(lambda r: httpx.Response(200, json=engine_route)) as c:
        body = c.post("/v1/journeys", json=query).json()
    trip = body["data"]["journeys"][0]["legs"][0]["transit"]
    assert trip["serviceDate"] == "2026-09-29"
    assert trip["startTime"] == "24:30"
    assert trip["sourceTripId"] == "123_290926"


def test_missing_expired_and_aging_generation(client_factory, query, manifest):
    def handler(request):
        return httpx.Response(200, json={"itineraries": [], "direct": []})

    with client_factory(handler, path=manifest.parent / "missing.json") as c:
        assert c.get("/healthz").status_code == 200
        assert c.post("/v1/journeys", json=query).json()["code"] == "DATA_UNAVAILABLE"
    with client_factory(handler, now=datetime(2026, 10, 31, tzinfo=UTC)) as c:
        assert c.post("/v1/journeys", json=query).json()["code"] == "FEED_EXPIRED"
    with client_factory(handler, now=datetime(2026, 10, 3, tzinfo=UTC)) as c:
        body = c.post("/v1/journeys", json=query).json()
        assert body["meta"]["freshness"] == "stale"
        assert body["meta"]["warnings"]
    data = json.loads(manifest.read_text())
    data["state"] = "building"
    manifest.write_text(json.dumps(data))
    with client_factory(handler) as c:
        assert c.post("/v1/journeys", json=query).json()["code"] == "DATA_UNAVAILABLE"


def test_body_limit_without_content_length(client_factory):
    with client_factory(lambda r: pytest.fail("Oversized query reached engine")) as c:
        response = c.post("/v1/journeys", content=iter([b"x" * 8000] * 3))
    assert response.status_code == 413
