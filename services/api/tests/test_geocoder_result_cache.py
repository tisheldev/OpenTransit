"""Geocoder result caches (Photon, MOTIS place search) and Photon verification off the loop.

A cache hit must equal a fresh provider answer; only complete, source-verified, non-empty
answers are stored; nothing produced by a failing provider is stored; every cache is bound
to one snapshot (one generation) and dies with it.
"""

import asyncio
import gc
import threading
import time
from types import SimpleNamespace

import httpx
import pytest
from test_photon_geocoder import GENERATION, HOUSE, STREET, _binding, _feature

import opentransit.search_cache as search_cache
from opentransit.geocoding import geocode_places
from opentransit.motis_geocoder import GeocoderUnavailable, MotisGeocoder
from opentransit.motis_geocoder import geocode_places as motis_geocode_places
from opentransit.photon_geocoder import PhotonGeocoder, PhotonUnavailable
from opentransit.search_cache import GeocoderCaches, geocoder_caches

PHOTON_OK = {"type": "FeatureCollection", "features": [{**_feature(name=None, street="Herzl")}]}
PHOTON_EMPTY = {"type": "FeatureCollection", "features": []}


class Snap:
    """A weak-referenceable stand-in for RuntimeSnapshot."""

    def __init__(self, generation_id="generation-a", *, motis=None, provider=None, required=False):
        self.generation = SimpleNamespace(id=generation_id)
        self.motis = motis
        self.reference = None
        self.address_provider = provider
        self.address_provider_required = required


def _unnamed_house():
    house = HOUSE.copy()
    house.pop("name")
    return house


def _photon(handler, caches=None, *, thread_log=None):
    rows = {("N", "300"): _unnamed_house(), ("W", "300"): STREET}

    def lookup(osm_type, osm_id):
        if thread_log is not None:
            thread_log.append(threading.get_ident())
        return rows.get((osm_type, osm_id))

    client = httpx.AsyncClient(
        base_url="http://photon.test:2322", transport=httpx.MockTransport(handler)
    )
    binding = _binding(client, rows=rows)
    binding.catalog = SimpleNamespace(lookup=lookup)
    geocoder = PhotonGeocoder(binding, GENERATION)
    geocoder.cache = caches
    return geocoder, client


def _run_photon(geocoder, client, *calls):
    async def run():
        try:
            return [await geocoder.search(**call) for call in calls]
        finally:
            await client.aclose()

    return asyncio.run(run())


SEARCH = {"query": "Herzl", "language": "en", "limit": 10}


def test_photon_hit_skips_the_provider_and_equals_a_fresh_answer():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=PHOTON_OK)

    caches = GeocoderCaches(GENERATION)
    geocoder, client = _photon(handle, caches)
    first, second = _run_photon(geocoder, client, SEARCH, SEARCH)
    assert len(calls) == 1
    assert second.items == first.items and second.items
    assert second.items is not first.items
    # Editing a returned item never edits what the cache serves.
    second.items[0]["coordinates"]["latitude"] = 0.0
    second.items.append({"junk": True})
    geocoder, client = _photon(handle, caches)
    (third,) = _run_photon(geocoder, client, SEARCH)
    assert len(calls) == 1 and third.items == first.items


def test_photon_key_is_the_exact_provider_request():
    calls = []

    def handle(request):
        calls.append(list(request.url.params.multi_items()))
        return httpx.Response(200, json=PHOTON_OK)

    caches = GeocoderCaches(GENERATION)
    geocoder, client = _photon(handle, caches)
    _run_photon(
        geocoder,
        client,
        SEARCH,
        {**SEARCH, "query": "  Herzl  "},  # the provider receives the stripped text
        {**SEARCH, "language": "he"},
        {**SEARCH, "limit": 5},
        {**SEARCH, "near": (32.08, 34.78)},
        {**SEARCH, "near": (32.08, 34.78000001)},
        {**SEARCH, "near": (32.08, 34.780000001)},  # same 8-decimal request as the one above
        {**SEARCH, "query": "herzl"},  # case may matter to the provider: separate entry
    )
    assert len(calls) == 6


def test_photon_failure_is_not_cached_and_the_next_call_retries_the_provider():
    calls = []
    answers = [httpx.Response(503), httpx.Response(200, json=PHOTON_OK)]

    def handle(_request):
        calls.append(1)
        return answers[min(len(calls), len(answers)) - 1]

    caches = GeocoderCaches(GENERATION)
    geocoder, client = _photon(handle, caches)

    async def run():
        try:
            with pytest.raises(PhotonUnavailable):
                await geocoder.search(**SEARCH)
            assert caches.size("photon") == 0
            fresh = await geocoder.search(**SEARCH)
            hit = await geocoder.search(**SEARCH)
            return fresh, hit
        finally:
            await client.aclose()

    fresh, hit = asyncio.run(run())
    assert len(calls) == 2 and hit.items == fresh.items and fresh.items


def test_photon_unverifiable_answer_is_never_stored():
    calls = []

    def handle(_request):
        calls.append(1)
        return httpx.Response(200, json={**PHOTON_OK, "features": [_feature(osm_id=999)]})

    caches = GeocoderCaches(GENERATION)
    geocoder, client = _photon(handle, caches)

    async def run():
        try:
            for _ in range(2):
                with pytest.raises(PhotonUnavailable):
                    await geocoder.search(**SEARCH)
        finally:
            await client.aclose()

    asyncio.run(run())
    assert len(calls) == 2 and caches.size("photon") == 0


def test_an_observed_failure_drops_the_cached_answers_of_that_backend():
    state = {"fail": False, "calls": 0}

    def handle(request):
        state["calls"] += 1
        if state["fail"] and request.url.params["q"] == "Other":
            return httpx.Response(500)
        return httpx.Response(200, json=PHOTON_OK)

    caches = GeocoderCaches(GENERATION)
    geocoder, client = _photon(handle, caches)

    async def run():
        try:
            await geocoder.search(**SEARCH)
            await geocoder.search(**SEARCH)
            assert state["calls"] == 1
            state["fail"] = True
            with pytest.raises(PhotonUnavailable):
                await geocoder.search(**{**SEARCH, "query": "Other"})
            # The outage was seen: the earlier answer is asked for again, not replayed.
            await geocoder.search(**SEARCH)
            return state["calls"]
        finally:
            await client.aclose()

    assert asyncio.run(run()) == 3


def test_an_empty_valid_answer_is_not_cached():
    calls = []

    def handle(_request):
        calls.append(1)
        return httpx.Response(200, json=PHOTON_EMPTY)

    caches = GeocoderCaches(GENERATION)
    geocoder, client = _photon(handle, caches)
    first, second = _run_photon(geocoder, client, SEARCH, SEARCH)
    assert first.items == second.items == [] and len(calls) == 2


def test_photon_without_a_cache_behaves_as_before():
    calls = []

    def handle(_request):
        calls.append(1)
        return httpx.Response(200, json=PHOTON_OK)

    geocoder, client = _photon(handle, None)
    _run_photon(geocoder, client, SEARCH, SEARCH)
    assert len(calls) == 2


def test_photon_verification_runs_off_the_event_loop_thread():
    threads = []

    def handle(_request):
        return httpx.Response(200, json=PHOTON_OK)

    geocoder, client = _photon(handle, None, thread_log=threads)
    main = threading.get_ident()
    (result,) = _run_photon(geocoder, client, SEARCH)
    assert result.items and threads and all(ident != main for ident in threads)


def test_slow_address_verification_does_not_hold_the_event_loop():
    ticks = []

    def handle(_request):
        return httpx.Response(200, json=PHOTON_OK)

    geocoder, client = _photon(handle, None)
    real_lookup = geocoder.catalog.lookup

    def slow_lookup(osm_type, osm_id):
        time.sleep(0.3)  # a catalog read that blocks its thread
        return real_lookup(osm_type, osm_id)

    geocoder.catalog = SimpleNamespace(lookup=slow_lookup)

    async def ticker(stop):
        while not stop.is_set():
            ticks.append(time.perf_counter())
            await asyncio.sleep(0.01)

    async def run():
        stop = asyncio.Event()
        task = asyncio.create_task(ticker(stop))
        try:
            await geocoder.search(**SEARCH)
        finally:
            stop.set()
            await task
            await client.aclose()

    asyncio.run(run())
    gaps = [later - earlier for earlier, later in zip(ticks, ticks[1:], strict=False)]
    assert len(ticks) > 10, "the loop kept running while the lookup blocked its thread"
    assert max(gaps) < 0.15


def _motis_client(handler):
    return httpx.AsyncClient(
        base_url="http://127.0.0.1:59081", transport=httpx.MockTransport(handler)
    )


PLACE = {
    "type": "PLACE",
    "name": "Central Park",
    "lat": 32.08,
    "lon": 34.79,
    "category": "park",
    "id": "way/42",
    "areas": [],
}


def test_motis_hit_skips_the_engine_and_reports_the_current_calls_types():
    calls = []

    def handle(request):
        calls.append(dict(request.url.params))
        return httpx.Response(200, json={"matches": [PLACE]})

    async def run():
        async with _motis_client(handle) as client:
            snapshot = Snap(motis=SimpleNamespace(client=client))
            first = await motis_geocode_places(snapshot, "Central", types=("poi",))
            second = await motis_geocode_places(snapshot, "Central", types=("poi",))
            third = await motis_geocode_places(snapshot, "Central", types=("poi",), limit=5)
            return first, second, third

    first, second, third = asyncio.run(run())
    assert len(calls) == 2
    assert second.items == first.items and second.searched_types == ("poi",)
    assert second.items is not first.items and third.items == first.items


def test_motis_failure_and_invalid_answers_are_not_cached():
    calls = []
    answers = [
        httpx.Response(503),
        httpx.Response(200, json={"matches": [{**PLACE, "name": ""}]}),
        httpx.Response(200, json={"matches": [PLACE]}),
    ]

    def handle(_request):
        calls.append(1)
        return answers[min(len(calls), len(answers)) - 1]

    async def run():
        async with _motis_client(handle) as client:
            snapshot = Snap(motis=SimpleNamespace(client=client))
            for _ in range(2):
                with pytest.raises(GeocoderUnavailable):
                    await motis_geocode_places(snapshot, "Central", types=("poi",))
            assert geocoder_caches(snapshot).size("motis") == 0
            ok = await motis_geocode_places(snapshot, "Central", types=("poi",))
            hit = await motis_geocode_places(snapshot, "Central", types=("poi",))
            return ok, hit

    ok, hit = asyncio.run(run())
    assert len(calls) == 3 and hit.items == ok.items and ok.items


def test_use_cache_false_always_asks_the_backend_and_stores_nothing():
    calls = []

    def handle(_request):
        calls.append(1)
        return httpx.Response(200, json={"matches": [PLACE]})

    async def run():
        async with _motis_client(handle) as client:
            snapshot = Snap(motis=SimpleNamespace(client=client))
            for _ in range(2):
                await motis_geocode_places(snapshot, "Central", types=("poi",), use_cache=False)
            return snapshot

    snapshot = asyncio.run(run())
    assert len(calls) == 2 and geocoder_caches(snapshot).size("motis") == 0


def test_snapshots_never_share_cached_results_and_release_them_with_the_snapshot():
    calls = []

    def handle(_request):
        calls.append(1)
        return httpx.Response(200, json={"matches": [PLACE]})

    async def run():
        async with _motis_client(handle) as client:
            old = Snap("generation-a", motis=SimpleNamespace(client=client))
            new = Snap("generation-b", motis=SimpleNamespace(client=client))
            twin = Snap("generation-a", motis=SimpleNamespace(client=client))
            old_first = await motis_geocode_places(old, "Central", types=("poi",))
            await motis_geocode_places(old, "Central", types=("poi",))
            assert len(calls) == 1
            new_first = await motis_geocode_places(new, "Central", types=("poi",))
            await motis_geocode_places(twin, "Central", types=("poi",))
            return old, old_first, new_first

    old, old_first, new_first = asyncio.run(run())
    # Activation publishes a new snapshot: it asks the engine and its place references are
    # bound to its own generation (identical text, different generation, different ref).
    assert len(calls) == 3
    assert old_first.items[0]["placeRef"] != new_first.items[0]["placeRef"]
    assert geocoder_caches(old).generation_id == "generation-a"
    key = id(old)
    assert key in search_cache._REGISTRY
    del old
    gc.collect()
    assert key not in search_cache._REGISTRY


def test_a_snapshot_that_cannot_be_tracked_gets_no_cache():
    assert geocoder_caches(SimpleNamespace(generation=SimpleNamespace(id="g"))) is None
    assert geocoder_caches(object()) is None


def test_partial_failure_caches_only_the_complete_backend_and_retries_the_other():
    photon_calls, motis_calls = [], []
    photon_state = {"down": True}

    def photon(_request):
        photon_calls.append(1)
        if photon_state["down"]:
            return httpx.Response(503)
        return httpx.Response(200, json=PHOTON_OK)

    def motis(_request):
        motis_calls.append(1)
        return httpx.Response(200, json={"matches": [PLACE]})

    async def run():
        async with _motis_client(motis) as motis_client:
            photon_client = httpx.AsyncClient(
                base_url="http://photon.test:2322", transport=httpx.MockTransport(photon)
            )
            try:
                binding = _binding(
                    photon_client, rows={("N", "300"): _unnamed_house(), ("W", "300"): STREET}
                )
                snapshot = Snap(
                    GENERATION, motis=SimpleNamespace(client=motis_client), provider=binding
                )
                args = {"types": ("address", "poi"), "language": "en", "limit": 10}
                first = await geocode_places(snapshot, "Herzl", **args)
                second = await geocode_places(snapshot, "Herzl", **args)
                photon_state["down"] = False
                recovered = await geocode_places(snapshot, "Herzl", **args)
                hit = await geocode_places(snapshot, "Herzl", **args)
                return first, second, recovered, hit
            finally:
                await photon_client.aclose()

    first, second, recovered, hit = asyncio.run(run())
    for degraded in (first, second):
        assert degraded.unavailable_types == ("address",) and degraded.searched_types == ("poi",)
    # The provider that was down is asked again every time; the complete poi answer is reused.
    assert len(photon_calls) == 3 and len(motis_calls) == 1
    assert recovered.unavailable_types == () and recovered.searched_types == ("address", "poi")
    assert hit.items == recovered.items
    assert [item["kind"] for item in hit.items] == ["address", "poi"]


def test_geocoder_and_stop_cache_sizes_are_documented_bounds():
    assert search_cache.STOP_RESULT_CACHE_ENTRIES == 512
    assert search_cache.GEOCODER_CACHE_ENTRIES == 256
    caches = GeocoderCaches("g", max_entries=2)
    for index in range(3):
        caches.put("photon", (str(index),), [{"n": index}])
    assert caches.size("photon") == 2 and caches.get("photon", ("0",)) is None
    assert caches.get("motis", ("2",)) is None, "backends do not share entries"


def test_motis_adapter_without_a_cache_is_unchanged():
    calls = []

    def handle(_request):
        calls.append(1)
        return httpx.Response(200, json={"matches": [PLACE]})

    async def run():
        async with _motis_client(handle) as client:
            geocoder = MotisGeocoder(client, "generation-a")
            await geocoder.search("Central", types=("poi",))
            await geocoder.search("Central", types=("poi",))

    asyncio.run(run())
    assert len(calls) == 2
