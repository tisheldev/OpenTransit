from datetime import UTC, datetime

from test_reference_api import reference_client

from opentransit.api.app import problem
from opentransit.api.places import places_router


def places_client(manifest, engine_route):
    now = datetime(2026, 9, 30, 9, tzinfo=UTC)
    client = reference_client(manifest, engine_route, now=now)
    client.app.include_router(places_router(lambda: now, problem))
    return client


def test_places_search_returns_resolvable_parent_deduplicated_candidate(manifest, engine_route):
    with places_client(manifest, engine_route) as client:
        response = client.get(
            "/v1/places",
            params=[("q", "Central A"), ("lang", "en"), ("type", "stop"), ("type", "station")],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["partial"] is False
        assert body["matchedTypes"] == ["stop", "station"]
        assert len(body["data"]) == 1
        place = body["data"][0]
        assert place["kind"] == "station"
        assert place["id"] == "mot:stop:station"
        assert place["platformIds"] == ["mot:stop:platform_a", "mot:stop:platform_b"]
        assert place["locationRef"] == {"kind": "stop", "stopId": "mot:stop:station"}
        resolved = client.get(f"/v1/stops/{place['id']}")
        assert resolved.status_code == 200
        assert resolved.json()["data"]["stopId"] == place["id"]


def test_places_report_unavailable_categories_and_validate_bounds(manifest, engine_route):
    with places_client(manifest, engine_route) as client:
        partial = client.get(
            "/v1/places", params=[("q", "central"), ("type", "station"), ("type", "address")]
        )
        assert partial.status_code == 200
        assert partial.json()["partial"] is True
        assert partial.json()["unavailableTypes"] == ["address"]
        unavailable = client.get("/v1/places", params={"q": "central", "type": "poi"})
        assert unavailable.status_code == 503
        assert unavailable.json()["code"] == "CATEGORY_UNAVAILABLE"
        for params in (
            {"q": "x"},
            {"q": "central", "near": "35,32"},
            {"q": "central", "type": "unknown"},
            {"q": "central", "limit": 21},
        ):
            assert client.get("/v1/places", params=params).status_code == 422


def test_missing_reference_is_not_reported_as_empty_search(manifest, engine_route):
    with places_client(manifest, engine_route) as client:
        snapshot = client.app.state.snapshot
        from dataclasses import replace

        client.app.state.snapshot = replace(snapshot, reference=None)
        response = client.get("/v1/places", params={"q": "central"})
        assert response.status_code == 503
        assert response.json()["code"] == "DATA_UNAVAILABLE"
