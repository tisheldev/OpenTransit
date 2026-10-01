"""Liveness, readiness and status endpoints."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from opentransit.api.responses import metadata
from opentransit.motis import EngineFailure
from opentransit.runtime import capture_snapshot


def health_router(settings, clock, problem) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def health():
        return {"status": "alive"}

    async def readiness(snapshot, now):
        if snapshot is None:
            return False, "unavailable", "unavailable"
        generation = snapshot.generation
        if not generation.contains(now) or generation.freshness(now) == "expired":
            return False, "expired", "unchecked"
        if not snapshot.routing_verified:
            return False, "available", "unverified"
        try:
            async with asyncio.timeout(settings.journey_deadline_seconds):
                healthy = await snapshot.motis.ready(now)
        except EngineFailure, TimeoutError:
            return False, "available", "unavailable"
        if not healthy:
            return False, "available", "unavailable"
        return snapshot.reference is not None, "available", "available"

    @router.get("/readyz")
    async def ready(request: Request):
        snapshot = capture_snapshot(request.app.state)
        usable, _, _ = await readiness(snapshot, clock())
        if not usable:
            return problem(request, 503, "NOT_READY", "A complete usable generation is required.")
        return {"status": "ready", "generationId": snapshot.generation.id}

    @router.get("/v1/status")
    async def status(request: Request):
        snapshot = capture_snapshot(request.app.state)
        now = clock()
        usable, static_state, engine_state = await readiness(snapshot, now)
        data = {
            "ready": usable,
            "staticData": static_state,
            "routing": engine_state,
            "reference": "available" if snapshot and snapshot.reference else "unavailable",
            "realtime": "not_enabled",
            "alerts": "not_enabled",
        }
        if snapshot is None:
            return {
                "data": data,
                "meta": {
                    "requestId": request.state.request_id,
                    "generatedAt": now,
                    "generationId": None,
                },
            }
        generation = snapshot.generation
        data["lastValidatedAt"] = (
            generation.source_checked_at
            if generation.source_check_recorded
            else generation.validated_at
        )
        return JSONResponse(
            jsonable_encoder({"data": data, "meta": metadata(request, snapshot, now)})
        )

    return router
