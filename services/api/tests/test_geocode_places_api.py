import json
from dataclasses import replace
from datetime import UTC, datetime

import httpx
from test_reference_api import reference_client

import opentransit.api.places as places_module
from opentransit.api.app import problem
from opentransit.api.places import places_router
from opentransit.build.prepare import sha256
from opentransit.geocoding import GeocodingResult


def _client(manifest, engine_route, *, geocoding=False, now=None):
    client = reference_client(manifest, engine_route, now=now)
    if geocoding:
        config = manifest.parent / "config.yml"
        config.write_text("geocoding: true\nreverse_geocoding: false\n", encoding="utf-8")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["artifacts"]["config"]["sha256"] = sha256(config)
        manifest.write_text(json.dumps(data), encoding="utf-8")
        probe = manifest.parent / "probe.json"
        evidence = json.loads(probe.read_text(encoding="utf-8"))
        evidence["configSha256"] = sha256(config)
        probe.write_text(json.dumps(evidence), encoding="utf-8")
    client.app.include_router(
        places_router(lambda: now or datetime(2026, 9, 30, 9, tzinfo=UTC), problem)
    )
    return client


def _geocoder_transport(client, handler):
    client.app.state.snapshot.motis.client._transport = httpx.MockTransport(handler)


def test_place_route_passes_generated_request_id_to_provider(monkeypatch, manifest, engine_route):
    captured = {}

    async def fake_geocode(snapshot, query, **kwargs):
        captured.update(kwargs)
        return GeocodingResult([], ("address",))

    monkeypatch.setattr(places_module, "geocode_places", fake_geocode)
    with _client(manifest, engine_route, geocoding=True) as client:
        response = client.get("/v1/places", params=[("q", "Central A"), ("type", "address")])

    assert response.status_code == 200
    assert captured["request_id"] == response.headers["X-Request-ID"]


def test_declared_photon_address_can_run_when_motis_geocoding_is_disabled(
    monkeypatch, manifest, engine_route
):
    captured = {}

    async def fake_geocode(snapshot, query, **kwargs):
        captured["types"] = kwargs["types"]
        return GeocodingResult([], ("address",))

    monkeypatch.setattr(places_module, "geocode_places", fake_geocode)
    with _client(manifest, engine_route) as client:
        old_snapshot = client.app.state.snapshot
        client.app.state.snapshot = replace(
            old_snapshot, address_provider=object(), address_provider_required=True
        )
        client.app.state.generation_geocoding[old_snapshot.generation.id] = False
        response = client.get("/v1/places", params=[("q", "Central A"), ("type", "address")])

    assert response.status_code == 200
    assert captured["types"] == ("address",)
    assert response.json()["meta"]["requestId"] == response.headers["X-Request-ID"]


def test_default_search_reports_disabled_geocoder_categories_as_partial(manifest, engine_route):
    with _client(manifest, engine_route) as client:
        response = client.get("/v1/places", params={"q": "Central A"})
    assert response.status_code == 200
    body = response.json()
    assert body["matchedTypes"] == ["stop", "station"]
    assert body["unavailableTypes"] == ["poi", "address"]
    assert body["partial"] is True
    assert body["rankingPolicy"] == "alternating-stop-and-geocoder-order-v1"


def test_geocoder_results_include_generation_bound_refs_and_merge_after_stop(
    manifest, engine_route
):
    with _client(manifest, engine_route, geocoding=True) as client:
        calls = []

        def engine(request):
            calls.append(request)
            return httpx.Response(
                200,
                json={
                    "matches": [
                        {
                            "type": "PLACE",
                            "name": "Central Park",
                            "lat": 32.08,
                            "lon": 34.79,
                            "category": "park",
                            "id": "way/42",
                            "areas": [],
                        }
                    ],
                },
            )

        _geocoder_transport(client, engine)
        response = client.get(
            "/v1/places",
            params=[("q", "central"), ("type", "poi"), ("near", "32.08,34.79"), ("lang", "en")],
        )
    assert response.status_code == 200
    body = response.json()
    assert body["matchedTypes"] == ["poi"]
    assert body["unavailableTypes"] == []
    assert body["data"][0]["kind"] == "poi"
    assert body["data"][0]["locationRef"]["kind"] == "place"
    assert body["data"][0]["placeRef"].startswith("mot:place:v1:")
    assert calls[0].url.params["type"] == "PLACE"
    assert calls[0].url.params["place"] == "32.08000000,34.79000000"
    assert calls[0].url.params["placeBias"] == "1"


def test_mixed_search_alternates_backend_orders_and_deduplicates(manifest, engine_route):
    with _client(manifest, engine_route, geocoding=True) as client:

        def engine(_request):
            return httpx.Response(
                200,
                json={
                    "matches": [
                        {
                            "type": "PLACE",
                            "name": "Park A",
                            "lat": 32.08,
                            "lon": 34.79,
                            "category": "park",
                            "id": "way/43",
                            "areas": [],
                        },
                        {
                            "type": "PLACE",
                            "name": "Park B",
                            "lat": 32.09,
                            "lon": 34.80,
                            "category": "park",
                            "id": "way/44",
                            "areas": [],
                        },
                    ]
                },
            )

        _geocoder_transport(client, engine)
        response = client.get(
            "/v1/places",
            params=[
                ("q", "central"),
                ("type", "station"),
                ("type", "poi"),
                ("limit", "3"),
            ],
        )
    assert response.status_code == 200
    assert [item["kind"] for item in response.json()["data"]] == ["station", "poi", "poi"]


def test_valid_empty_geocoder_is_success_but_backend_failure_is_unavailable(manifest, engine_route):
    with _client(manifest, engine_route, geocoding=True) as client:
        _geocoder_transport(client, lambda _request: httpx.Response(200, json={"matches": []}))
        empty = client.get("/v1/places", params=[("q", "central"), ("type", "address")])
        _geocoder_transport(client, lambda _request: httpx.Response(503, json={}))
        failed = client.get("/v1/places", params=[("q", "central"), ("type", "address")])
    assert empty.status_code == 200
    assert empty.json()["matchedTypes"] == ["address"]
    assert empty.json()["data"] == []
    assert failed.status_code == 503
    assert failed.json()["code"] == "CATEGORY_UNAVAILABLE"


def test_place_search_validation_and_snapshot_capture_before_await(manifest, engine_route):
    with _client(manifest, engine_route, geocoding=True) as client:
        original = client.app.state.snapshot
        seen = []

        async def engine(request):
            seen.append(request)
            newer = replace(original, generation=replace(original.generation, id="new-generation"))
            client.app.state.snapshot = newer
            return httpx.Response(200, json={"matches": []})

        _geocoder_transport(client, engine)
        response = client.get("/v1/places", params={"q": "Central A"})
        bad_type = client.get("/v1/places", params=[("q", "central"), ("type", "unknown")])
        bad_lang = client.get("/v1/places", params={"q": "central", "lang": "ar"})
        bad_near = client.get("/v1/places", params={"q": "central", "near": "32,nan"})
    assert response.status_code == 200
    assert response.json()["meta"]["generationId"] == original.generation.id
    assert len(seen) == 1
    assert response.json()["data"][0]["id"] == "mot:stop:station"
    assert [bad_type.status_code, bad_lang.status_code, bad_near.status_code] == [422] * 3
