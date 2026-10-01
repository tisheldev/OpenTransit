"""Liveness, readiness and status endpoints."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from opentransit.api.log import LOG
from opentransit.api.responses import metadata
from opentransit.motis import EngineFailure
from opentransit.runtime import capture_snapshot


def _reason(condition: str, reason: str) -> dict[str, str]:
    return {"condition": condition, "reason": reason}


def health_router(settings, clock, problem) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def health():
        return {"status": "alive"}

    async def readiness(snapshot, now):
        """Return usability, static/engine states and one safe reason per failing condition."""
        if snapshot is None:
            return False, "unavailable", "unavailable", [_reason("generation", "UNAVAILABLE")]
        generation = snapshot.generation
        reasons = []
        if not generation.contains(now):
            reasons.append(_reason("coverage", "OUTSIDE_COVERAGE"))
        if not generation.freshness_serviceable(now):
            reasons.append(_reason("freshness", "SOURCE_CHECK_EXPIRED"))
        if reasons:
            return False, "expired", "unchecked", reasons
        if not snapshot.routing_verified:
            return False, "available", "unverified", [_reason("routing", "PROBE_UNVERIFIED")]
        try:
            async with asyncio.timeout(settings.journey_deadline_seconds):
                failure = await snapshot.motis.health(now)
        except EngineFailure:
            failure = {"reason": "ENGINE_UNAVAILABLE"}
        except TimeoutError:
            failure = {"reason": "ENGINE_TIMEOUT"}
        if failure is not None:
            return False, "available", "unavailable", [{"condition": "engine", **failure}]
        if snapshot.reference is None:
            return False, "available", "available", [_reason("reference", "UNAVAILABLE")]
        return True, "available", "available", []

    @router.get("/readyz")
    async def ready(request: Request):
        snapshot = capture_snapshot(request.app.state)
        usable, _, _, reasons = await readiness(snapshot, clock())
        if not usable:
            LOG.warning(
                "readiness_failed reasons=%s",
                ",".join(f"{item['condition']}:{item['reason']}" for item in reasons),
            )
            return problem(
                request,
                503,
                "NOT_READY",
                "A complete usable generation is required.",
                errors=reasons,
            )
        return {"status": "ready", "generationId": snapshot.generation.id}

    @router.get("/v1/status")
    async def status(request: Request):
        snapshot = capture_snapshot(request.app.state)
        now = clock()
        usable, static_state, engine_state, _ = await readiness(snapshot, now)
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
