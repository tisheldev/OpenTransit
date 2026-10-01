"""The places route overlaps stop search with geocoder waits without changing results."""

import asyncio
import json
import logging
import threading
import time

import httpx
from test_geocode_places_api import _client, _geocoder_transport

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


def test_real_geocoder_request_leaves_while_the_stop_search_runs(
    monkeypatch, manifest, engine_route
):
    """A real adapter suspends several times before its request leaves the process.

    httpx/httpcore yield to the event loop for the connection-pool lock and the socket
    write, so one ``sleep(0)`` before a synchronous stop search is not enough: the
    request would only leave after the stop search. The stop search must not occupy
    the event loop.
    """
    delay = 0.3
    events: list[tuple[str, float]] = []
    real_search_stops = places_module.search_stops

    def engine_body():
        return {
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
            ]
        }

    async def instant_engine(request):
        return httpx.Response(200, json=engine_body())

    async def pooled_engine(request):
        for _ in range(3):  # pool lock, connection checkout, socket write
            await asyncio.sleep(0)
        events.append(("geocode-sent", time.perf_counter()))
        await asyncio.sleep(delay)
        return httpx.Response(200, json=engine_body())

    def slow_stops(*args, **kwargs):
        events.append(("stops-start", time.perf_counter()))
        time.sleep(delay)
        events.append(("stops-end", time.perf_counter()))
        return real_search_stops(*args, **kwargs)

    with _client(manifest, engine_route, geocoding=True) as client:
        _geocoder_transport(client, instant_engine)
        reference = client.get("/v1/places", params=PARAMS)
        _geocoder_transport(client, pooled_engine)
        monkeypatch.setattr(places_module, "search_stops", slow_stops)
        started = time.perf_counter()
        response = client.get("/v1/places", params=PARAMS)
        elapsed = time.perf_counter() - started

    assert response.status_code == 200
    moments = dict(events)
    assert moments["geocode-sent"] < moments["stops-end"]
    assert elapsed < 1.6 * delay
    body = response.json()
    assert [item["kind"] for item in body["data"]] == ["stop", "poi"]
    assert body["data"] == reference.json()["data"]
    assert body["matchedTypes"] == reference.json()["matchedTypes"] == ["stop", "poi"]
    assert body["partial"] is reference.json()["partial"] is False


def test_stop_search_runs_off_the_event_loop_thread(monkeypatch, manifest, engine_route):
    threads = []
    real_search_stops = places_module.search_stops

    def recording_stops(*args, **kwargs):
        threads.append(threading.get_ident())
        return real_search_stops(*args, **kwargs)

    async def loop_thread():
        return threading.get_ident()

    with _client(manifest, engine_route) as client:
        monkeypatch.setattr(places_module, "search_stops", recording_stops)
        response = client.get("/v1/places", params=[("q", "Central A"), ("type", "stop")])
        loop_ident = client.portal.call(loop_thread)

    assert response.status_code == 200
    assert len(threads) == 1
    assert threads[0] != loop_ident


def test_stop_search_phase_is_logged_without_query_text(manifest, engine_route, caplog):
    with (
        caplog.at_level(logging.INFO, logger="opentransit.requests.stopsearch"),
        _client(manifest, engine_route) as client,
    ):
        found = client.get("/v1/places", params=[("q", "Central A"), ("type", "stop")])
        empty = client.get("/v1/places", params=[("q", "zzqq private"), ("type", "stop")])

    records = [row for row in caplog.records if row.name == "opentransit.requests.stopsearch"]
    assert [row.request_id for row in records] == [
        found.headers["X-Request-ID"],
        empty.headers["X-Request-ID"],
    ]
    assert [row.outcome for row in records] == ["success", "validempty"]
    assert records[0].resultcount == len(found.json()["data"]) > 0
    assert records[1].resultcount == 0
    for row in records:
        fields = json.loads(row.getMessage())
        assert set(fields) == {"request_id", "genid", "search_ms", "resultcount", "outcome"}
        # Only a SHA-256 generation ID is logged; the fixture's synthetic ID is not one.
        assert found.json()["meta"]["generationId"] == "synthetic-test"
        assert fields["genid"] is None
        assert fields["search_ms"] >= 0
        assert "private" not in row.getMessage() and "Central" not in row.getMessage()


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
