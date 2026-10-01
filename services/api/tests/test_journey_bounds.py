"""M3.6: 1.5 s journey deadline, one 16-permit semaphore and a 16 KiB body limit."""

import asyncio
import json
import time
from contextlib import asynccontextmanager

import httpx
from conftest import NOW

from opentransit.api.lifecycle import PLANNING_CONCURRENCY
from opentransit.api.middleware import MAX_BODY_BYTES
from opentransit.config import Settings

EMPTY = {"itineraries": [], "direct": []}


@asynccontextmanager
async def running(manifest, handler, **settings):
    from opentransit.api.app import create_app

    app = create_app(
        Settings(manifest, **settings),
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            base_url="http://api.test", transport=httpx.ASGITransport(app=app)
        ) as client:
            yield app, client


def test_documented_bounds_are_the_configured_values(manifest):
    assert Settings(manifest).journey_deadline_seconds == 1.5
    assert Settings(manifest).engine_timeout_seconds < 1.5
    assert PLANNING_CONCURRENCY == 16
    assert MAX_BODY_BYTES == 16 * 1024 == 16_384

    async def run():
        async with running(manifest, lambda r: httpx.Response(200, json=EMPTY)) as (app, _):
            assert app.state.planning_semaphore._value == 16

    asyncio.run(run())


def test_default_deadline_turns_a_hung_engine_into_504_near_one_and_a_half_seconds(manifest, query):
    async def hung(request):
        await asyncio.sleep(30)
        return httpx.Response(200, json=EMPTY)

    async def run():
        async with running(manifest, hung) as (app, client):
            started = time.perf_counter()
            response = await client.post("/v1/journeys", json=query)
            elapsed = time.perf_counter() - started
            assert app.state.planning_semaphore._value == 16  # permit released on timeout
            return response, elapsed

    response, elapsed = asyncio.run(run())
    assert response.status_code == 504
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "ENGINE_TIMEOUT"
    assert 1.4 <= elapsed < 2.5


def test_deadline_applies_to_the_whole_planning_call_and_the_service_recovers(manifest, query):
    state = {"slow": True}

    async def engine(request):
        if state["slow"]:
            await asyncio.sleep(5)
        return httpx.Response(200, json=EMPTY)

    async def run():
        async with running(
            manifest, engine, engine_timeout_seconds=0.04, journey_deadline_seconds=0.05
        ) as (app, client):
            timed_out = await asyncio.wait_for(client.post("/v1/journeys", json=query), 1)
            assert app.state.planning_semaphore._value == 16
            state["slow"] = False
            recovered = await client.post("/v1/journeys", json=query)
            return timed_out, recovered

    timed_out, recovered = asyncio.run(run())
    assert timed_out.status_code == 504 and timed_out.json()["code"] == "ENGINE_TIMEOUT"
    assert recovered.status_code == 200 and recovered.json()["data"]["outcome"] == "no_route"


def test_saturated_semaphore_rejects_fast_without_queueing_and_is_shared(manifest, query):
    async def run():
        release = asyncio.Event()
        occupied = asyncio.Event()
        calls = 0

        async def engine(request):
            nonlocal calls
            calls += 1
            if calls == PLANNING_CONCURRENCY:
                occupied.set()
            await release.wait()
            return httpx.Response(200, json=EMPTY)

        async with running(manifest, engine) as (app, client):
            held = [
                asyncio.create_task(client.post("/v1/journeys", json=query))
                for _ in range(PLANNING_CONCURRENCY)
            ]
            try:
                await asyncio.wait_for(occupied.wait(), 2)
                assert app.state.planning_semaphore.locked()
                timings = []
                rejected = []
                for _ in range(5):
                    started = time.perf_counter()
                    rejected.append(
                        await asyncio.wait_for(client.post("/v1/journeys", json=query), 1)
                    )
                    timings.append(time.perf_counter() - started)
                # The same single semaphore guards trip and departure lookups.
                trip = await asyncio.wait_for(
                    client.get("/v1/trips/20260930_08:00_mot60day_1_1"), 1
                )
                departures = await asyncio.wait_for(
                    client.get(
                        "/v1/stops/mot:stop:1/departures",
                        params={"from": "2026-09-30T08:00:00+03:00"},
                    ),
                    1,
                )
                assert calls == PLANNING_CONCURRENCY  # rejected requests never queued or called
            finally:
                release.set()
                results = await asyncio.gather(*held)
            return rejected, timings, trip, departures, results

    rejected, timings, trip, departures, results = asyncio.run(run())
    for response in [*rejected, trip, departures]:
        assert response.status_code == 503
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "SERVER_OVERLOADED"
    assert max(timings) < 0.25  # well below the 1.5 s deadline: rejection, not a wait
    assert all(response.status_code == 200 for response in results)


def padded_body(query, size):
    raw = json.dumps(query, separators=(",", ":")).encode()
    assert len(raw) <= size
    return raw + b" " * (size - len(raw))


def test_body_limit_boundary_is_inclusive_and_rejected_before_the_engine(client_factory, query):
    seen = []

    def engine(request):
        seen.append(request)
        return httpx.Response(200, json=EMPTY)

    headers = {"Content-Type": "application/json"}
    with client_factory(engine) as client:
        at_limit = client.post(
            "/v1/journeys", content=padded_body(query, MAX_BODY_BYTES), headers=headers
        )
        assert at_limit.status_code == 200 and len(seen) == 1
        over = client.post(
            "/v1/journeys", content=padded_body(query, MAX_BODY_BYTES + 1), headers=headers
        )
        huge = client.post("/v1/journeys", content=b" " * 2_000_000, headers=headers)
    for response in (over, huge):
        assert response.status_code == 413
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "BODY_TOO_LARGE"
        assert response.headers["x-request-id"] == response.json()["requestId"]
    assert len(seen) == 1


def test_body_limit_counts_streamed_chunks_across_the_boundary(client_factory, query):
    def chunks(total):
        body = padded_body(query, total)
        return iter([body[:9000], body[9000:]])

    headers = {"Content-Type": "application/json"}
    with client_factory(lambda r: httpx.Response(200, json=EMPTY)) as client:
        assert (
            client.post("/v1/journeys", content=chunks(MAX_BODY_BYTES), headers=headers).status_code
            == 200
        )
        assert (
            client.post(
                "/v1/journeys", content=chunks(MAX_BODY_BYTES + 1), headers=headers
            ).status_code
            == 413
        )
