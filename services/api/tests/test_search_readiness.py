"""Place-search readiness: the stop index and geocoder warm-up precede publication.

All clocks, sleeps and backends are fixed mocks; nothing here touches a live service.
"""

import asyncio
import gc
import json
import sqlite3
import threading
import weakref
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from test_activation import FakeClient, make_binding, select_file
from test_reference_api import reference_client

import opentransit.api.lifecycle as lifecycle
import opentransit.search_readiness as readiness_module
import opentransit.stop_search as stop_search_module
from opentransit.activation import SnapshotLease, SnapshotManager
from opentransit.api.app import create_app
from opentransit.build.activation import read_binding
from opentransit.build.prepare import sha256
from opentransit.config import Settings
from opentransit.core.generation import Generation
from opentransit.geocoding import GeocodingResult
from opentransit.reference import STOP_PREFIX
from opentransit.search_readiness import (
    READY,
    UNAVAILABLE,
    WARMING,
    WARMUP_QUERY,
    SearchWarmup,
    enabled_backends,
    prepare_search,
    readiness_reasons,
    retry_until_ready,
)
from opentransit.stop_search import prepare_search_index, search_index_ready

pytest_plugins = ["test_activation"]


def _row():
    return {
        "source_id": "s1",
        "stop_id": STOP_PREFIX + "s1",
        "parent_station": None,
        "location_type": 0,
        "name": "Central Station",
        "description": None,
        "translations": {},
        "code": None,
        "latitude": 32.08,
        "longitude": 34.78,
    }


class FakeReference:
    def __init__(self, gate=None, entered=None, error=None):
        self.gate, self.entered, self.error = gate, entered, error

    def stop_search_candidates(self):
        if self.entered is not None:
            self.entered.set()
        if self.gate is not None:
            assert self.gate.wait(10)
        if self.error is not None:
            raise self.error
        return [_row()]


def _snapshot(reference=None, *, photon=False, generation_id="g1"):
    return SimpleNamespace(
        generation=SimpleNamespace(id=generation_id),
        reference=reference,
        address_provider=SimpleNamespace() if photon else None,
        address_provider_required=photon,
    )


def _no_sleep():
    delays = []

    async def sleep(seconds):
        delays.append(seconds)

    return sleep, delays


def _fake_geocoder(monkeypatch, outcomes):
    """Replace the warm-up geocoder; outcomes are results or exceptions consumed per call."""
    calls = []

    async def fake(snapshot, query, **kwargs):
        calls.append((query, kwargs["types"], kwargs["limit"]))
        outcome = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return await outcome()
        return outcome

    monkeypatch.setattr(readiness_module, "geocode_places", fake)
    return calls


# --- stop index ownership ------------------------------------------------------------


def test_prepare_builds_once_and_search_never_rebuilds(monkeypatch):
    built = []
    real = stop_search_module._SearchIndex

    def counting(*args, **kwargs):
        built.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(stop_search_module, "_SearchIndex", counting)
    reference = FakeReference()
    assert not search_index_ready(reference)
    prepare_search_index(reference)
    assert search_index_ready(reference) and len(built) == 1
    result = stop_search_module.search_stops(reference, "Central")
    prepare_search_index(reference)
    assert [item["id"] for item in result["items"]] == [STOP_PREFIX + "s1"]
    assert len(built) == 1


def test_index_is_released_with_its_reference_and_failed_build_is_not_cached():
    reference = FakeReference()
    prepare_search_index(reference)
    watcher = weakref.ref(reference)
    del reference
    gc.collect()
    assert watcher() is None

    broken = FakeReference(error=sqlite3.OperationalError("boom"))
    with pytest.raises(sqlite3.OperationalError):
        prepare_search_index(broken)
    assert not search_index_ready(broken)
    assert not search_index_ready(None)


def test_concurrent_first_callers_share_one_build(monkeypatch):
    built = []
    real = stop_search_module._SearchIndex
    monkeypatch.setattr(
        stop_search_module, "_SearchIndex", lambda *a, **k: built.append(1) or real(*a, **k)
    )
    reference = FakeReference()
    threads = [threading.Thread(target=prepare_search_index, args=(reference,)) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(built) == 1


# --- warm-up and reason codes ---------------------------------------------------------


def test_enabled_backends_follow_the_search_endpoint_rules():
    assert enabled_backends(_snapshot(), False) == ()
    assert enabled_backends(_snapshot(), True) == ("poi",)
    assert enabled_backends(_snapshot(photon=True), False) == ("address",)
    assert enabled_backends(_snapshot(photon=True), True) == ("address", "poi")


def test_warmup_uses_one_fixed_query_per_backend_and_marks_ready(monkeypatch):
    calls = _fake_geocoder(monkeypatch, [GeocodingResult([], ("address",))])
    sleep, delays = _no_sleep()
    reference = FakeReference()
    snapshot = _snapshot(reference, photon=True)

    async def run():
        return await prepare_search(
            snapshot,
            ("address",),
            attempts=3,
            retry_seconds=0.5,
            timeout_seconds=1.0,
            sleep=sleep,
        )

    record = asyncio.run(run())
    assert record.backends == {"address": READY} and not record.index_failed
    assert search_index_ready(reference)
    assert calls == [(WARMUP_QUERY, ("address",), 1)] and delays == []
    assert readiness_reasons(snapshot, record, ("address",)) == []


def test_warmup_retries_with_fixed_delay_then_succeeds(monkeypatch):
    outcomes = [
        RuntimeError("cold"),
        TimeoutError(),
        GeocodingResult([], ("poi",)),
    ]
    calls = _fake_geocoder(monkeypatch, outcomes)
    sleep, delays = _no_sleep()
    snapshot = _snapshot(FakeReference())
    record = asyncio.run(
        prepare_search(
            snapshot, ("poi",), attempts=5, retry_seconds=0.25, timeout_seconds=1.0, sleep=sleep
        )
    )
    assert record.backends == {"poi": READY}
    assert len(calls) == 3 and delays == [0.25, 0.25]


@pytest.mark.parametrize(
    ("kind", "warming", "unavailable"),
    [
        ("address", "ADDRESS_PROVIDER_WARMING", "ADDRESS_PROVIDER_UNAVAILABLE"),
        ("poi", "PLACE_PROVIDER_WARMING", "PLACE_PROVIDER_UNAVAILABLE"),
    ],
)
def test_exhausted_warmup_reports_unavailable_reason(monkeypatch, kind, warming, unavailable):
    calls = _fake_geocoder(monkeypatch, [RuntimeError("down")])
    sleep, delays = _no_sleep()
    reference = FakeReference()
    snapshot = _snapshot(reference, photon=kind == "address")
    record = asyncio.run(
        prepare_search(
            snapshot, (kind,), attempts=3, retry_seconds=0.1, timeout_seconds=1.0, sleep=sleep
        )
    )
    assert len(calls) == 3 and delays == [0.1, 0.1]
    assert record.backends == {kind: UNAVAILABLE}
    condition = {"address": "address_search", "poi": "place_search"}[kind]
    assert readiness_reasons(snapshot, record, (kind,)) == [
        {"condition": condition, "reason": unavailable}
    ]
    # Before any outcome (or with no record at all) the same backend is warming.
    assert readiness_reasons(snapshot, SearchWarmup({kind: WARMING}), (kind,)) == [
        {"condition": condition, "reason": warming}
    ]
    assert readiness_reasons(snapshot, None, (kind,))[0]["reason"] == warming


def test_backend_that_reports_its_category_unavailable_is_not_ready(monkeypatch):
    _fake_geocoder(monkeypatch, [GeocodingResult([], ("poi",), ("address",))])
    sleep, _ = _no_sleep()
    snapshot = _snapshot(FakeReference(), photon=True)
    record = asyncio.run(
        prepare_search(
            snapshot, ("address",), attempts=1, retry_seconds=0, timeout_seconds=1.0, sleep=sleep
        )
    )
    assert record.backends == {"address": UNAVAILABLE}


def test_hung_backend_is_bounded_by_the_probe_timeout(monkeypatch):
    async def hang():
        await asyncio.sleep(30)

    _fake_geocoder(monkeypatch, [hang])
    sleep, _ = _no_sleep()
    record = asyncio.run(
        prepare_search(
            _snapshot(FakeReference()),
            ("poi",),
            attempts=2,
            retry_seconds=0,
            timeout_seconds=0.01,
            sleep=sleep,
        )
    )
    assert record.backends == {"poi": UNAVAILABLE}


def test_index_reason_codes_building_then_unavailable_then_ready():
    reference = FakeReference()
    snapshot = _snapshot(reference)
    assert readiness_reasons(snapshot, None, ()) == [
        {"condition": "search_index", "reason": "SEARCH_INDEX_BUILDING"}
    ]
    failed = SearchWarmup(index_failed=True)
    assert readiness_reasons(snapshot, failed, ())[0]["reason"] == "SEARCH_INDEX_UNAVAILABLE"
    prepare_search_index(reference)
    assert readiness_reasons(snapshot, SearchWarmup(), ()) == []


def test_failed_index_build_is_recorded_without_raising(monkeypatch, caplog):
    _fake_geocoder(monkeypatch, [GeocodingResult([], ("poi",))])
    sleep, _ = _no_sleep()
    reference = FakeReference(error=sqlite3.OperationalError("sentinel-private-detail"))
    record = asyncio.run(
        prepare_search(
            _snapshot(reference),
            ("poi",),
            attempts=1,
            retry_seconds=0,
            timeout_seconds=1.0,
            sleep=sleep,
        )
    )
    assert record.index_failed and record.backends == {"poi": READY}
    assert "sentinel-private-detail" not in caplog.text


def test_warmup_failure_logs_only_fixed_constants(monkeypatch, caplog):
    _fake_geocoder(monkeypatch, [RuntimeError("sentinel-private-detail")])
    sleep, _ = _no_sleep()
    with caplog.at_level("INFO"):
        asyncio.run(
            prepare_search(
                _snapshot(), ("poi",), attempts=1, retry_seconds=0, timeout_seconds=1.0, sleep=sleep
            )
        )
    assert "sentinel-private-detail" not in caplog.text
    assert WARMUP_QUERY not in caplog.text


def test_background_retry_recovers_and_stops_when_snapshot_retires(monkeypatch):
    sleep, delays = _no_sleep()
    snapshot = _snapshot()
    _fake_geocoder(monkeypatch, [RuntimeError("down"), GeocodingResult([], ("poi",))])
    record = SearchWarmup({"poi": UNAVAILABLE})
    asyncio.run(
        retry_until_ready(
            snapshot,
            record,
            is_current=lambda: True,
            timeout_seconds=1.0,
            interval_seconds=5.0,
            sleep=sleep,
        )
    )
    assert record.backends == {"poi": READY} and delays == [5.0, 5.0]

    calls = _fake_geocoder(monkeypatch, [RuntimeError("down")])
    stale = SearchWarmup({"poi": UNAVAILABLE})
    asyncio.run(
        retry_until_ready(
            snapshot,
            stale,
            is_current=lambda: False,
            timeout_seconds=1.0,
            interval_seconds=5.0,
            sleep=sleep,
        )
    )
    assert stale.backends == {"poi": UNAVAILABLE} and calls == []


# --- the real app lifespan --------------------------------------------------------------


def test_index_exists_when_the_snapshot_becomes_visible_and_first_search_does_not_build(
    monkeypatch, manifest, engine_route
):
    seen = {}
    original = lifecycle._install_search

    def spy(app, settings, snapshot, record):
        seen["visible"] = app.state.snapshot
        seen["index_ready"] = search_index_ready(snapshot.reference)
        original(app, settings, snapshot, record)

    monkeypatch.setattr(lifecycle, "_install_search", spy)
    with reference_client(manifest, engine_route) as client:
        assert seen == {"visible": None, "index_ready": True}

        def forbidden(*args, **kwargs):
            raise AssertionError("passenger request built the stop index")

        monkeypatch.setattr(stop_search_module, "_SearchIndex", forbidden)
        response = client.get("/v1/places", params={"q": "station", "type": "stop"})
        assert response.status_code == 200
        assert client.get("/readyz").status_code == 200


def test_readyz_reports_index_building_then_ready(manifest, engine_route):
    with reference_client(manifest, engine_route) as client:
        reference = client.app.state.snapshot.reference
        stop_search_module._INDEXES.pop(reference)
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["errors"] == [
            {"condition": "search_index", "reason": "SEARCH_INDEX_BUILDING"}
        ]
        status = client.get("/v1/status").json()["data"]
        assert status["ready"] is False and status["routing"] == "available"
        prepare_search_index(reference)
        assert client.get("/readyz").status_code == 200
        assert client.get("/v1/status").json()["data"]["ready"] is True


def test_readyz_names_warming_and_unavailable_geocoders_then_recovers(
    monkeypatch, manifest, engine_route
):
    geocode_calls = []
    mode = {"fail": True}

    def engine(request):
        if request.url.path == "/api/v1/geocode":
            geocode_calls.append(request.url.params.get("text"))
            if mode["fail"]:
                return httpx.Response(503, json={"error": "sentinel-private-detail"})
            return httpx.Response(200, json=[])
        if request.url.params.get("fromPlace") == "32.0836,34.7981":
            return httpx.Response(200, json={"itineraries": [], "direct": []})
        return httpx.Response(200, json=engine_route)

    client = _geocoding_client_with_engine(manifest, engine_route, engine)
    with client:
        # Two bounded attempts with the fixed query, then honest unavailability.
        assert geocode_calls == [WARMUP_QUERY, WARMUP_QUERY]
        body = client.get("/readyz").json()
        assert body["errors"] == [
            {"condition": "place_search", "reason": "PLACE_PROVIDER_UNAVAILABLE"}
        ]
        assert "sentinel-private-detail" not in json.dumps(body)
        # Existing semantics: the category is reported unavailable, stops still serve.
        places = client.get("/v1/places", params=[("q", "station"), ("type", "stop")])
        assert places.status_code == 200
        poi = client.get("/v1/places", params=[("q", "station"), ("type", "poi")])
        assert poi.status_code == 503

        # Recovery: the warm-up record flips and readiness follows.
        mode["fail"] = False
        generation_id = client.app.state.snapshot.generation.id
        record = client.app.state.search_warmup[generation_id]
        assert record.backends == {"poi": UNAVAILABLE}
        record.backends["poi"] = WARMING
        assert client.get("/readyz").json()["errors"] == [
            {"condition": "place_search", "reason": "PLACE_PROVIDER_WARMING"}
        ]
        record.backends["poi"] = READY
        assert client.get("/readyz").status_code == 200


def _geocoding_client_with_engine(manifest, engine_route, engine):
    """A fixture app with MOTIS geocoding enabled for its generation and a custom engine."""
    client = reference_client(manifest, engine_route, engine=engine)
    config = manifest.parent / "config.yml"
    config.write_text("geocoding: true\nreverse_geocoding: false\n", encoding="utf-8")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["artifacts"]["config"]["sha256"] = sha256(config)
    manifest.write_text(json.dumps(data), encoding="utf-8")
    probe = manifest.parent / "probe.json"
    evidence = json.loads(probe.read_text(encoding="utf-8"))
    evidence["configSha256"] = sha256(config)
    probe.write_text(json.dumps(evidence), encoding="utf-8")
    del client
    return TestClient(
        create_app(
            Settings(
                manifest,
                probe_path=probe,
                warmup_attempts=2,
                warmup_retry_seconds=0.0,
                warmup_recovery_seconds=300.0,
            ),
            transport=httpx.MockTransport(engine),
            clock=lambda: datetime(2026, 9, 30, 9, tzinfo=UTC),
        )
    )


def test_settings_reject_unbounded_warmup():
    with pytest.raises(ValueError):
        Settings(manifest_path="m.json", warmup_attempts=0)
    with pytest.raises(ValueError):
        Settings(manifest_path="m.json", warmup_recovery_seconds=0)


# --- activation ------------------------------------------------------------------------


def test_activation_builds_the_candidate_index_before_swap(generation_factory, tmp_path):
    async def run():
        old_dir = generation_factory("old")
        new_dir = generation_factory("new", geocoding=True)
        old_binding = make_binding(old_dir, "old-token")
        new_binding = make_binding(new_dir, "new-token")
        current = tmp_path / "current.json"
        select_file(current, old_binding)

        old_reference = FakeReference()
        prepare_search_index(old_reference)
        old_generation = Generation.load(old_dir / "manifest.json")
        old_snapshot = SimpleNamespace(
            generation=old_generation,
            motis=None,
            reference=old_reference,
            address_provider=None,
            address_provider_required=False,
        )
        old_lease = SnapshotLease(old_snapshot, FakeClient())

        gate, entered = threading.Event(), threading.Event()
        new_reference = FakeReference(gate=gate, entered=entered)
        app = SimpleNamespace(
            state=SimpleNamespace(
                generation_geocoding={},
                search_warmup={},
                search_warmup_tasks=set(),
                snapshot_manager=None,
            )
        )
        settings = Settings(manifest_path=tmp_path / "unused.json")
        new_client = FakeClient()

        async def factory(binding):
            snapshot = SimpleNamespace(
                generation=Generation.load(binding.generation_dir / "manifest.json"),
                motis=None,
                reference=new_reference,
                address_provider=None,
                address_provider_required=False,
            )
            record = await lifecycle._warm_search(app, settings, snapshot)
            lifecycle._install_search(app, settings, snapshot, record)
            return SnapshotLease(snapshot, new_client)

        manager = SnapshotManager(
            current,
            factory,
            tmp_path / "acks",
            0.02,
            initial_lease=old_lease,
            managed_root=tmp_path,
        )
        app.state.snapshot_manager = manager
        assert read_binding(current, tmp_path).generation_id == old_generation.id

        select_file(current, new_binding)
        reload_task = asyncio.create_task(manager.reload_current("new-token"))
        assert await asyncio.to_thread(entered.wait, 10)
        # The candidate's index is mid-build: the old snapshot, with its own complete
        # index, is still the only thing requests can capture.
        assert manager.current_snapshot is old_snapshot
        assert search_index_ready(old_reference)
        assert not search_index_ready(new_reference)
        gate.set()
        published = await reload_task
        assert manager.current_snapshot is published
        assert published.reference is new_reference and search_index_ready(new_reference)
        assert search_index_ready(old_reference)  # in-flight old requests keep their index
        record = app.state.search_warmup[published.generation.id]
        assert readiness_reasons(published, record, ()) == []
        await manager.aclose()

    asyncio.run(run())
