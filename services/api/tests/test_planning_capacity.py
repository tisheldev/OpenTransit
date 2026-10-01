import asyncio

import httpx

from opentransit.api.app import create_app
from opentransit.config import Settings


def test_capacity_rejects_seventeenth_request_and_recovers(manifest, query):
    async def run():
        release = asyncio.Event()
        occupied = asyncio.Event()
        entered = 0

        async def engine(request):
            nonlocal entered
            entered += 1
            if entered == 16:
                occupied.set()
            await release.wait()
            return httpx.Response(200, json={"itineraries": [], "direct": []})

        app = create_app(Settings(manifest), transport=httpx.MockTransport(engine))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                base_url="http://api.test", transport=httpx.ASGITransport(app=app)
            ) as client:
                pending = [
                    asyncio.create_task(client.post("/v1/journeys", json=query)) for _ in range(16)
                ]
                try:
                    await asyncio.wait_for(occupied.wait(), 1)
                    rejected = await asyncio.wait_for(client.post("/v1/journeys", json=query), 0.5)
                    assert rejected.status_code == 503
                    assert rejected.json()["code"] == "SERVER_OVERLOADED"
                    assert entered == 16
                finally:
                    release.set()
                    responses = await asyncio.gather(*pending)
                assert all(response.status_code == 200 for response in responses)
                recovered = await client.post("/v1/journeys", json=query)
                assert recovered.status_code == 200
                assert entered == 17

    asyncio.run(run())


def test_cancelled_request_releases_capacity(manifest, query):
    async def run():
        occupied = asyncio.Event()
        release = asyncio.Event()
        cancelled = asyncio.Event()

        async def engine(request):
            occupied.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return httpx.Response(200, json={"itineraries": [], "direct": []})

        app = create_app(Settings(manifest), transport=httpx.MockTransport(engine))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                base_url="http://api.test", transport=httpx.ASGITransport(app=app)
            ) as client:
                request = asyncio.create_task(client.post("/v1/journeys", json=query))
                await asyncio.wait_for(occupied.wait(), 1)
                request.cancel()
                await asyncio.gather(request, return_exceptions=True)
                await asyncio.wait_for(cancelled.wait(), 1)
                assert app.state.planning_semaphore._value == 16
                release.set()
                assert (await client.post("/v1/journeys", json=query)).status_code == 200

    asyncio.run(run())
