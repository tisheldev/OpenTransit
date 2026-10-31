"""Liveness, readiness and status endpoints."""

import asyncio
import time
import weakref

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from opentransit.api.log import LOG
from opentransit.api.responses import metadata
from opentransit.motis import EngineFailure
from opentransit.runtime import capture_snapshot
from opentransit.search_readiness import enabled_backends, readiness_reasons


def _reason(condition: str, reason: str) -> dict[str, str]:
    return {"condition": condition, "reason": reason}


class EngineHealthCache:
    """One engine health result per snapshot, reused for a few seconds (API-PERF 1.9).

    Each check plans a short journey on the engine; status polls and load-balancer probes
    would otherwise each pay for one. Concurrent callers share a single in-flight check.
    The entry belongs to the snapshot it checked (held weakly, so a retired generation is
    not kept alive), and a new generation is checked afresh.
    """

    def __init__(self, ttl_seconds: float, monotonic=time.monotonic) -> None:
        self.ttl_seconds = ttl_seconds
        self._monotonic = monotonic
        self._lock = asyncio.Lock()
        self._entry: tuple[weakref.ref, float, dict[str, str] | None] | None = None

    def _fresh(self, snapshot):
        entry = self._entry
        if entry is not None and entry[0]() is snapshot and self._monotonic() < entry[1]:
            return True, entry[2]
        return False, None

    async def failure(self, snapshot, check) -> dict[str, str] | None:
        try:
            snapshot_ref = weakref.ref(snapshot)
        except TypeError:
            snapshot_ref = None
        if self.ttl_seconds <= 0 or snapshot_ref is None:
            return await check()
        fresh, failure = self._fresh(snapshot)
        if fresh:
            return failure
        async with self._lock:
            fresh, failure = self._fresh(snapshot)
            if fresh:
                return failure
            failure = await check()
            self._entry = (snapshot_ref, self._monotonic() + self.ttl_seconds, failure)
            return failure


def health_router(settings, clock, problem) -> APIRouter:
    router = APIRouter()
    engine_health = EngineHealthCache(settings.engine_health_cache_seconds)

    @router.get("/healthz")
    async def health():
        return {"status": "alive"}

    async def readiness(snapshot, now, state):
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

        async def check():
            try:
                async with asyncio.timeout(settings.journey_deadline_seconds):
                    return await snapshot.motis.health(now)
            except EngineFailure:
                return {"reason": "ENGINE_UNAVAILABLE"}
            except TimeoutError:
                return {"reason": "ENGINE_TIMEOUT"}

        failure = await engine_health.failure(snapshot, check)
        if failure is not None:
            return False, "available", "unavailable", [{"condition": "engine", **failure}]
        if snapshot.reference is None:
            return False, "available", "available", [_reason("reference", "UNAVAILABLE")]
        # Place search must be truthful too: the stop index must exist and every enabled
        # geocoder backend must have answered its warm-up query.
        enabled = getattr(state, "generation_geocoding", {}).get(generation.id, False)
        reasons = readiness_reasons(
            snapshot,
            getattr(state, "search_warmup", {}).get(generation.id),
            enabled_backends(snapshot, enabled),
        )
        if reasons:
            return False, "available", "available", reasons
        return True, "available", "available", []

    @router.get("/readyz")
    async def ready(request: Request):
        snapshot = capture_snapshot(request.app.state)
        usable, _, _, reasons = await readiness(snapshot, clock(), request.app.state)
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
        usable, static_state, engine_state, _ = await readiness(snapshot, now, request.app.state)
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
