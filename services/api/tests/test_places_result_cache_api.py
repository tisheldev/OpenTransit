"""/v1/places with the result caches and short-query path: same answers, same gates.

The freshness gate runs before any cached answer, expired data still returns 503, places
stay ``no-store``, a provider failure is retried (never frozen into the cache), and
activating another generation serves that generation's data from empty caches.
"""

import json
from dataclasses import replace

import httpx
from test_geocode_places_api import _client, _geocoder_transport

from opentransit import stop_search as stop_search_module
from opentransit.core.generation import Generation
from opentransit.search_cache import geocoder_caches
from opentransit.stop_search import STOP_PREFIX

STOP_PARAMS = [("q", "Central"), ("lang", "en"), ("type", "stop"), ("type", "station")]
SHORT_PARAMS = [("q", "ce"), ("lang", "en"), ("type", "stop"), ("type", "station")]
POI_PARAMS = [("q", "central"), ("lang", "en"), ("type", "poi")]
PLACE = {
    "type": "PLACE",
    "name": "Central Park",
    "lat": 32.08,
    "lon": 34.79,
    "category": "park",
    "id": "way/42",
    "areas": [],
}


def _stable(response):
    """The body without the fields that differ per request."""
    body = response.json()
    body["meta"].pop("requestId")
    body["meta"].pop("generatedAt")
    return body


def test_cold_warm_and_exhaustive_responses_are_identical_and_never_cacheable(
    manifest, engine_route
):
    client = _client(manifest, engine_route)
    with client:
        for params in (STOP_PARAMS, SHORT_PARAMS, [*SHORT_PARAMS, ("near", "32.08,34.78")]):
            cold = client.get("/v1/places", params=params)
            warm = client.get("/v1/places", params=params)
            index = stop_search_module._search_index(client.app.state.snapshot.reference)
            assert index.results.hits >= 1
            # The unchanged exhaustive implementation: maps off, nothing cached.
            index.results.clear()
            maps = (index.short_literal, index.short_folded)
            index.short_literal = index.short_folded = None
            try:
                exhaustive = client.get("/v1/places", params=params)
            finally:
                index.short_literal, index.short_folded = maps
            assert cold.status_code == warm.status_code == exhaustive.status_code == 200
            assert _stable(cold) == _stable(warm) == _stable(exhaustive)
            assert json.dumps(_stable(cold)) == json.dumps(_stable(exhaustive))
            for response in (cold, warm, exhaustive):
                assert response.headers["Cache-Control"] == "no-store"
                assert "ETag" not in response.headers
            assert warm.json()["meta"]["requestId"] != cold.json()["meta"]["requestId"]
        assert warm.json()["data"], "the short query is a real match"


def test_the_freshness_gate_runs_before_a_cached_answer(monkeypatch, manifest, engine_route):
    client = _client(manifest, engine_route, geocoding=True)
    with client:

        def engine(_request):
            return httpx.Response(200, json={"matches": [PLACE]})

        _geocoder_transport(client, engine)
        for params in (STOP_PARAMS, POI_PARAMS):
            assert client.get("/v1/places", params=params).status_code == 200
            assert client.get("/v1/places", params=params).status_code == 200  # warm
        # Time passes on the same snapshot: its caches are warm, its data is now expired.
        monkeypatch.setattr(Generation, "freshness", lambda self, now: "expired")
        for params in (STOP_PARAMS, SHORT_PARAMS, POI_PARAMS):
            expired = client.get("/v1/places", params=params)
            assert expired.status_code == 503
            assert expired.json()["code"] == "FEED_EXPIRED"
            assert expired.headers["Cache-Control"] == "no-store"
        monkeypatch.undo()
        assert client.get("/v1/places", params=STOP_PARAMS).status_code == 200


def test_a_provider_failure_is_retried_and_never_frozen_into_the_cache(manifest, engine_route):
    client = _client(manifest, engine_route, geocoding=True)
    calls = []
    mode = {"down": True}

    def engine(_request):
        calls.append(1)
        if mode["down"]:
            return httpx.Response(503, json={"error": "down"})
        return httpx.Response(200, json={"matches": [PLACE]})

    with client:
        _geocoder_transport(client, engine)
        params = [("q", "central"), ("lang", "en"), ("type", "stop"), ("type", "poi")]
        for _ in range(2):
            degraded = client.get("/v1/places", params=params).json()
            assert degraded["unavailableTypes"] == ["poi"] and degraded["partial"] is True
            assert [item["kind"] for item in degraded["data"]] == ["stop"]
        assert len(calls) == 2, "each degraded request asked the provider again"
        mode["down"] = False
        recovered = client.get("/v1/places", params=params).json()
        again = client.get("/v1/places", params=params).json()
        assert len(calls) == 3, "the recovered answer is complete, so the repeat is a hit"
        for body in (recovered, again):
            assert body["unavailableTypes"] == [] and body["partial"] is False
            assert [item["kind"] for item in body["data"]] == ["stop", "poi"]
        assert recovered["data"] == again["data"]


def test_activating_another_generation_serves_its_data_from_empty_caches(manifest, engine_route):
    class OtherReference:
        def stop_search_candidates(self):
            return [
                {
                    "source_id": "other",
                    "stop_id": STOP_PREFIX + "other",
                    "parent_station": None,
                    "location_type": 0,
                    "name": "Central Other",
                    "description": None,
                    "translations": {"en": "Central Other"},
                    "code": None,
                    "latitude": 32.0,
                    "longitude": 34.8,
                    "route_count": 0,
                }
            ]

    client = _client(manifest, engine_route, geocoding=True)
    with client:
        old = client.app.state.snapshot
        before = client.get("/v1/places", params=STOP_PARAMS).json()
        client.get("/v1/places", params=STOP_PARAMS)
        old_index = stop_search_module._search_index(old.reference)
        assert old_index.results.hits >= 1 and before["data"][0]["id"] != STOP_PREFIX + "other"
        # Activation publishes a new snapshot object for the new generation.
        new = replace(old, reference=OtherReference())
        client.app.state.snapshot = new
        after = client.get("/v1/places", params=STOP_PARAMS).json()
        assert [item["id"] for item in after["data"]] == [STOP_PREFIX + "other"]
        new_index = stop_search_module._search_index(new.reference)
        assert new_index.results is not old_index.results and new_index.results.hits == 0
        assert geocoder_caches(new) is not geocoder_caches(old)
        # The retired snapshot still serves its own data to requests it already holds.
        client.app.state.snapshot = old
        assert client.get("/v1/places", params=STOP_PARAMS).json()["data"] == before["data"]
