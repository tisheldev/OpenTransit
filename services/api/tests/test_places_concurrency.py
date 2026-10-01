"""The places route overlaps stop search with geocoder waits without changing results."""

import asyncio
import time

from test_geocode_places_api import _client

import opentransit.api.routes.places as places_module
from opentransit.geocoding import GeocodingResult
from opentransit.motis_geocoder import GeocoderUnavailable

GEOCODER_ITEM = {
    "kind": "poi",
    "displayName": "Central Park",
    "coordinates": {"latitude": 32.08, "longitude": 34.79},
    "locationRef": {"kind": "place", "placeRef": "mot:place:v1:test"},
}
PARAMS = [("q", "Central A"), ("lang", "en"), ("type", "stop"), ("type", "poi")]


def test_stop_search_overlaps_a_slow_geocoder_and_merged_output_is_unchanged(
    monkeypatch, manifest, engine_route
):
    delay = 0.3
    events = []
    real_search_stops = places_module.search_stops

    async def instant_geocode(snapshot, query, **kwargs):
        return GeocodingResult([dict(GEOCODER_ITEM)], ("poi",))

    async def slow_geocode(snapshot, query, **kwargs):
        events.append("geocode-start")
        await asyncio.sleep(delay)
        events.append("geocode-end")
        return await instant_geocode(snapshot, query, **kwargs)

    def slow_stops(*args, **kwargs):
        events.append("stops-start")
        time.sleep(delay)  # synchronous work occupying the event loop
        events.append("stops-end")
        return real_search_stops(*args, **kwargs)

    with _client(manifest, engine_route, geocoding=True) as client:
        monkeypatch.setattr(places_module, "geocode_places", instant_geocode)
        reference = client.get("/v1/places", params=PARAMS)
        monkeypatch.setattr(places_module, "geocode_places", slow_geocode)
        monkeypatch.setattr(places_module, "search_stops", slow_stops)
        started = time.perf_counter()
        response = client.get("/v1/places", params=PARAMS)
        elapsed = time.perf_counter() - started

    assert response.status_code == 200
    # The geocoder request was dispatched before the blocking stop search ran, so the
    # two waits overlap: about one delay rather than two.
    assert events[:2] == ["geocode-start", "stops-start"]
    assert elapsed < 1.6 * delay
    body = response.json()
    assert body["matchedTypes"] == ["stop", "poi"]
    assert body["unavailableTypes"] == []
    assert [item["kind"] for item in body["data"]] == ["stop", "poi"]
    # Identical merged data and category semantics to an instant-geocoder run.
    assert body["data"] == reference.json()["data"]
    assert body["matchedTypes"] == reference.json()["matchedTypes"]
    assert body["partial"] == reference.json()["partial"]


def test_invalid_stop_request_cancels_the_in_flight_geocoder(monkeypatch, manifest, engine_route):
    cancelled = []

    async def pending_geocode(snapshot, query, **kwargs):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return GeocodingResult([], ("poi",))

    def invalid_stops(*args, **kwargs):
        raise ValueError("invalid")

    monkeypatch.setattr(places_module, "geocode_places", pending_geocode)
    monkeypatch.setattr(places_module, "search_stops", invalid_stops)
    with _client(manifest, engine_route, geocoding=True) as client:
        response = client.get("/v1/places", params=PARAMS)
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    assert cancelled == [True]


def test_geocoder_failure_is_still_reported_as_an_unavailable_category(
    monkeypatch, manifest, engine_route
):
    async def failing_geocode(snapshot, query, **kwargs):
        await asyncio.sleep(0.05)
        raise GeocoderUnavailable("down")

    monkeypatch.setattr(places_module, "geocode_places", failing_geocode)
    with _client(manifest, engine_route, geocoding=True) as client:
        response = client.get("/v1/places", params=PARAMS)
    body = response.json()
    assert response.status_code == 200
    assert body["matchedTypes"] == ["stop"]
    assert body["unavailableTypes"] == ["poi"]
    assert body["partial"] is True
    assert [item["kind"] for item in body["data"]] == ["stop"]
