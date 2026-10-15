"""Photon warm-up: Hebrew passes after the readiness probe, never changing readiness.

Readiness semantics are those of test_search_readiness: the English probe alone decides
READY or UNAVAILABLE (reason codes ADDRESS_PROVIDER_* / PLACE_PROVIDER_*); the Hebrew
passes only warm the backend, always ask the backend (never the result cache), and send
nothing but fixed constants.
"""

import asyncio

import httpx
from test_geocoder_result_cache import PHOTON_OK, Snap, _unnamed_house
from test_photon_geocoder import GENERATION, STREET, _binding

import opentransit.search_readiness as readiness
from opentransit.geocoding import GeocodingResult
from opentransit.search_cache import geocoder_caches
from opentransit.search_readiness import (
    READY,
    UNAVAILABLE,
    WARMUP_QUERIES_HE,
    WARMUP_QUERY,
    SearchWarmup,
    prepare_search,
    retry_until_ready,
)


async def _no_sleep(_seconds):
    return None


def _fake_geocoder(monkeypatch, outcomes):
    calls = []

    async def fake(snapshot, query, **kwargs):
        calls.append((query, kwargs["language"], kwargs["types"], kwargs["use_cache"]))
        outcome = outcomes(query)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(readiness, "geocode_places", fake)
    return calls


def _prepare(snapshot, kinds):
    return asyncio.run(
        prepare_search(
            snapshot, kinds, attempts=2, retry_seconds=0, timeout_seconds=1.0, sleep=_no_sleep
        )
    )


def test_hebrew_passes_follow_a_successful_address_probe_and_bypass_the_cache(monkeypatch):
    calls = _fake_geocoder(monkeypatch, lambda query: GeocodingResult([], ("address",)))
    record = _prepare(Snap(), ("address",))
    assert record.backends == {"address": READY}
    assert calls[0] == (WARMUP_QUERY, "en", ("address",), False)
    assert [call[0] for call in calls[1:]] == list(WARMUP_QUERIES_HE)
    assert all(call[1:] == ("he", ("address",), False) for call in calls[1:])
    assert all(any("֐" <= char <= "׿" for char in query) for query in WARMUP_QUERIES_HE)


def test_the_place_backend_gets_no_hebrew_passes(monkeypatch):
    calls = _fake_geocoder(monkeypatch, lambda query: GeocodingResult([], ("poi",)))
    record = _prepare(Snap(), ("poi",))
    assert record.backends == {"poi": READY}
    assert calls == [(WARMUP_QUERY, "en", ("poi",), False)]


def test_a_failing_hebrew_pass_does_not_change_readiness_or_log_the_query(monkeypatch, caplog):
    def outcome(query):
        if query in WARMUP_QUERIES_HE:
            return RuntimeError("sentinel-private-detail")
        return GeocodingResult([], ("address",))

    calls = _fake_geocoder(monkeypatch, outcome)
    with caplog.at_level("INFO"):
        record = _prepare(Snap(), ("address",))
    assert record.backends == {"address": READY}
    assert len(calls) == 1 + len(WARMUP_QUERIES_HE), "every Hebrew pass is still attempted"
    assert "sentinel-private-detail" not in caplog.text
    for query in (WARMUP_QUERY, *WARMUP_QUERIES_HE):
        assert query not in caplog.text


def test_a_hung_hebrew_pass_is_bounded_and_readiness_still_follows_the_probe(monkeypatch):
    async def hang(snapshot, query, **kwargs):
        if kwargs["language"] == "he":
            await asyncio.sleep(30)
        return GeocodingResult([], ("address",))

    monkeypatch.setattr(readiness, "geocode_places", hang)
    record = asyncio.run(
        prepare_search(
            Snap(),
            ("address",),
            attempts=1,
            retry_seconds=0,
            timeout_seconds=0.05,
            sleep=_no_sleep,
        )
    )
    assert record.backends == {"address": READY}


def test_a_failing_probe_stays_unavailable_and_sends_no_hebrew_pass(monkeypatch):
    calls = _fake_geocoder(monkeypatch, lambda query: RuntimeError("down"))
    record = _prepare(Snap(), ("address",))
    assert record.backends == {"address": UNAVAILABLE}
    assert [call[0] for call in calls] == [WARMUP_QUERY, WARMUP_QUERY]


def test_a_backend_reporting_the_category_unavailable_gets_no_hebrew_pass(monkeypatch):
    calls = _fake_geocoder(monkeypatch, lambda query: GeocodingResult([], ("poi",), ("address",)))
    record = _prepare(Snap(), ("address",))
    assert record.backends == {"address": UNAVAILABLE}
    assert {call[0] for call in calls} == {WARMUP_QUERY}


def test_background_recovery_also_warms_hebrew_after_the_probe_succeeds(monkeypatch):
    state = {"up": False}

    def outcome(query):
        if query == WARMUP_QUERY and not state["up"]:
            state["up"] = True  # the second probe succeeds
            return RuntimeError("down")
        return GeocodingResult([], ("address",))

    calls = _fake_geocoder(monkeypatch, outcome)
    record = SearchWarmup({"address": UNAVAILABLE})
    asyncio.run(
        retry_until_ready(
            Snap(),
            record,
            is_current=lambda: True,
            timeout_seconds=1.0,
            interval_seconds=0,
            sleep=_no_sleep,
        )
    )
    assert record.backends == {"address": READY}
    assert [call[0] for call in calls] == [WARMUP_QUERY, WARMUP_QUERY, *WARMUP_QUERIES_HE]


def test_a_cached_answer_never_vouches_for_the_backend():
    """With the real adapters: probes reach Photon even when the same request is cached."""
    calls = []

    def handle(request):
        calls.append(request.url.params["q"])
        return httpx.Response(200, json=PHOTON_OK)

    async def run():
        client = httpx.AsyncClient(
            base_url="http://photon.test:2322", transport=httpx.MockTransport(handle)
        )
        try:
            binding = _binding(client, rows={("N", "300"): _unnamed_house(), ("W", "300"): STREET})
            snapshot = Snap(GENERATION, provider=binding)
            # A passenger request with exactly the probe's parameters fills the cache.
            await readiness.geocode_places(
                snapshot, WARMUP_QUERY, language="en", types=("address",), limit=1
            )
            assert geocoder_caches(snapshot).size("photon") == 1 and calls == [WARMUP_QUERY]
            assert await readiness._probe(snapshot, "address", 1.0) is True
            return calls
        finally:
            await client.aclose()

    calls = asyncio.run(run())
    assert calls == [WARMUP_QUERY, WARMUP_QUERY, *WARMUP_QUERIES_HE]
