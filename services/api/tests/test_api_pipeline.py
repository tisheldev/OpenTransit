"""API-PERF package D: compression, keep-alive and the engine health cache.

Each change must leave response content unchanged: compressed bodies decode to the same
JSON as uncompressed ones, and cached readiness reports what a fresh check reported.
"""

import asyncio
import gc
import gzip
import importlib
import re
import weakref
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from test_reference_api import reference_client

from opentransit.api.app import GZIP_MINIMUM_BYTES
from opentransit.api.routes.health import EngineHealthCache
from opentransit.config import Settings

DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"
# The module, not the package attribute of the same name (which is the click command).
UVICORN_CLI = importlib.import_module("uvicorn.main").main


def _without_request_identity(payload):
    meta = payload.get("meta")
    if isinstance(meta, dict):
        meta.pop("requestId", None)
        meta.pop("generatedAt", None)
    return payload


def test_large_bodies_are_gzipped_and_decode_to_the_same_json(manifest, engine_route, query):
    with reference_client(manifest, engine_route) as client:
        plain = client.post("/v1/journeys", json=query, headers={"Accept-Encoding": "identity"})
        packed = client.post("/v1/journeys", json=query, headers={"Accept-Encoding": "gzip"})
    assert plain.status_code == packed.status_code == 200
    assert len(plain.content) > GZIP_MINIMUM_BYTES
    assert "content-encoding" not in plain.headers
    assert packed.headers["content-encoding"] == "gzip"
    assert "accept-encoding" in packed.headers["vary"].lower()
    # Middleware headers survive compression.
    assert packed.headers["cache-control"] == "no-store"
    assert re.fullmatch(r"[0-9a-f]{32}", packed.headers["x-request-id"])
    assert int(packed.headers["content-length"]) < len(plain.content)
    # httpx decodes transparently; the JSON is identical apart from per-request identity.
    assert _without_request_identity(packed.json()) == _without_request_identity(plain.json())


def test_raw_gzip_frame_is_valid_and_small_bodies_stay_uncompressed(manifest, engine_route, query):
    with reference_client(manifest, engine_route) as client:
        with client.stream(
            "POST", "/v1/journeys", json=query, headers={"Accept-Encoding": "gzip"}
        ) as response:
            raw = b"".join(response.iter_raw())
        assert gzip.decompress(raw).startswith(b"{")
        small = client.get("/healthz", headers={"Accept-Encoding": "gzip"})
        problem = client.get("/v1/stops/mot:stop:missing", headers={"Accept-Encoding": "gzip"})
    assert len(small.content) < GZIP_MINIMUM_BYTES
    assert "content-encoding" not in small.headers
    assert problem.status_code == 404
    assert "content-encoding" not in problem.headers
    assert problem.headers["content-type"] == "application/problem+json"


def test_reference_detail_bodies_are_unchanged_by_compression(manifest, engine_route):
    with reference_client(manifest, engine_route) as client:
        for path in (
            "/v1/stops/mot:stop:station",
            "/v1/routes/mot:route:bus_7",
            "/v1/routes/mot:route:bus_7/patterns",
            "/v1/routes?stopId=mot:stop:station",
        ):
            plain = client.get(path, headers={"Accept-Encoding": "identity"})
            packed = client.get(path, headers={"Accept-Encoding": "gzip"})
            assert plain.status_code == packed.status_code == 200, path
            assert _without_request_identity(packed.json()) == _without_request_identity(
                plain.json()
            ), path


def test_image_keeps_idle_connections_longer_than_a_load_balancer():
    text = DOCKERFILE.read_text(encoding="utf-8")
    match = re.search(r"^ENV UVICORN_TIMEOUT_KEEP_ALIVE=(\d+)$", text, re.MULTILINE)
    assert match is not None
    # Above the ALB's default 60 s idle timeout (and the 30 s assumed in the research).
    assert int(match.group(1)) > 60
    # The uvicorn CLI reads UVICORN_* variables, so commands that replace CMD keep it.
    assert UVICORN_CLI.context_settings.get("auto_envvar_prefix") == "UVICORN"
    assert any(param.name == "timeout_keep_alive" for param in UVICORN_CLI.params)


class _Snapshot:
    """Stands in for a RuntimeSnapshot: compared by identity and weakly referenceable."""


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def test_health_cache_reuses_a_result_until_it_expires_and_per_snapshot():
    clock = _Clock()
    cache = EngineHealthCache(2.0, monotonic=clock)
    results = iter([None, {"reason": "ENGINE_TIMEOUT"}, None])
    calls = []

    async def check():
        calls.append(clock.now)
        return next(results)

    async def scenario():
        snapshot, other = _Snapshot(), _Snapshot()
        assert await cache.failure(snapshot, check) is None
        clock.now += 1.9
        assert await cache.failure(snapshot, check) is None  # Reused.
        clock.now += 0.2
        assert await cache.failure(snapshot, check) == {"reason": "ENGINE_TIMEOUT"}
        # A failure is cached as well, and a different snapshot is always checked afresh.
        assert await cache.failure(snapshot, check) == {"reason": "ENGINE_TIMEOUT"}
        assert await cache.failure(other, check) is None

    asyncio.run(scenario())
    assert len(calls) == 3


def test_health_cache_shares_one_in_flight_check_and_zero_disables_it():
    cache = EngineHealthCache(2.0)
    calls = 0

    async def slow_check():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return None

    async def concurrent():
        snapshot = _Snapshot()
        return await asyncio.gather(*(cache.failure(snapshot, slow_check) for _ in range(10)))

    assert asyncio.run(concurrent()) == [None] * 10
    assert calls == 1

    disabled = EngineHealthCache(0)
    calls = 0

    async def repeated():
        snapshot = _Snapshot()
        for _ in range(3):
            await disabled.failure(snapshot, slow_check)

    asyncio.run(repeated())
    assert calls == 3


def _counting_engine(engine_route, health_calls, healthy):
    def engine(request):
        if request.url.params.get("fromPlace") == "32.0836,34.7981":
            health_calls.append(request)
            if not healthy["value"]:
                return httpx.Response(503)
            return httpx.Response(200, json={"itineraries": [], "direct": []})
        return httpx.Response(200, json=engine_route)

    return engine


def test_readyz_and_status_share_one_engine_check_within_the_cache_window(manifest, engine_route):
    health_calls, healthy = [], {"value": True}
    engine = _counting_engine(engine_route, health_calls, healthy)
    with reference_client(manifest, engine_route, engine=engine) as client:
        health_calls.clear()  # Startup may probe the engine itself.
        for _ in range(5):
            assert client.get("/readyz").status_code == 200
            assert client.get("/v1/status").json()["data"]["ready"] is True
        assert len(health_calls) == 1


def test_uncached_settings_report_an_engine_outage_on_the_next_request(
    manifest, engine_route, monkeypatch
):
    health_calls, healthy = [], {"value": True}
    engine = _counting_engine(engine_route, health_calls, healthy)
    original = Settings.__init__

    def no_cache(self, *args, **kwargs):
        kwargs.setdefault("engine_health_cache_seconds", 0)
        original(self, *args, **kwargs)

    monkeypatch.setattr(Settings, "__init__", no_cache)
    with reference_client(manifest, engine_route, engine=engine) as client:
        assert client.get("/readyz").status_code == 200
        healthy["value"] = False
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["errors"][0]["reason"] == "ENGINE_HTTP_STATUS"


@pytest.mark.parametrize("seconds", [-1, 10.5])
def test_engine_health_cache_bounds(tmp_path, seconds):
    with pytest.raises(ValueError, match="Engine health cache"):
        Settings(tmp_path / "manifest.json", engine_health_cache_seconds=seconds)


def test_cache_never_keeps_a_retired_snapshot_alive():
    cache = EngineHealthCache(60.0)

    async def check():
        return None

    snapshot = _Snapshot()
    released = weakref.ref(snapshot)
    asyncio.run(cache.failure(snapshot, check))
    del snapshot
    gc.collect()
    assert released() is None

    # Snapshots that cannot be weakly referenced are simply checked every time.
    calls = []

    async def counted():
        calls.append(1)
        return None

    async def scenario():
        plain = SimpleNamespace(id="g")
        await cache.failure(plain, counted)
        await cache.failure(plain, counted)

    asyncio.run(scenario())
    assert len(calls) == 2
