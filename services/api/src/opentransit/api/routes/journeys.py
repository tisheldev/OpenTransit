"""Scheduled journey planning endpoint and place-reference resolution."""

import asyncio

from fastapi import APIRouter, Request

from opentransit.api.schemas import (
    Coordinate,
    Coverage,
    JourneyData,
    JourneyRequest,
    JourneyResponse,
    Metadata,
    Problem,
)
from opentransit.core.place_ref import decode_place_ref
from opentransit.motis import EngineFailure
from opentransit.runtime import capture_snapshot


def journeys_router(settings, clock, problem) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/v1/journeys",
        response_model=JourneyResponse,
        responses={
            status: {
                "content": {"application/problem+json": {"schema": Problem.model_json_schema()}}
            }
            for status in (413, 422, 503, 504)
        },
    )
    async def plan(query: JourneyRequest, request: Request):
        app = request.app
        snapshot = capture_snapshot(app.state)  # Engine/reference/generation stay together.
        now = clock()
        if snapshot is None:
            return problem(request, 503, "DATA_UNAVAILABLE", "No verified graph is configured.")
        generation = snapshot.generation
        if not snapshot.routing_verified:
            return problem(
                request, 503, "DATA_UNAVAILABLE", "The candidate engine needs verification."
            )
        freshness = generation.freshness(now)
        if now >= generation.coverage_until or freshness == "expired":
            return problem(request, 503, "FEED_EXPIRED", "The graph requires a fresh build.")
        if not generation.contains(query.time_anchor):
            return problem(request, 422, "OUTSIDE_SERVICE_WINDOW", "Choose a time inside coverage.")
        try:
            query = _resolve_place_locations(query, generation.id)
        except ValueError:
            return problem(
                request,
                422,
                "INVALID_PLACE_REF",
                "The place reference is invalid or belongs to another generation.",
            )
        semaphore = app.state.planning_semaphore
        if semaphore.locked():
            return problem(request, 503, "SERVER_OVERLOADED", "Planning capacity is busy.")
        try:
            async with asyncio.timeout(settings.journey_deadline_seconds):
                async with semaphore:
                    result = await snapshot.motis.plan(query, generation, snapshot.reference)
        except (EngineFailure, TimeoutError) as exc:
            code = exc.code if isinstance(exc, EngineFailure) else "ENGINE_TIMEOUT"
            status = exc.status if isinstance(exc, EngineFailure) else 504
            return problem(request, status, code, "Scheduled planning is temporarily unavailable.")
        return JourneyResponse(
            data=JourneyData(
                outcome="routes_found" if result.journeys else "no_route",
                journeys=result.journeys,
            ),
            meta=Metadata(
                requestId=request.state.request_id,
                generationId=generation.id,
                generatedAt=now,
                dataBuiltAt=generation.built_at,
                mode=generation.mode,
                coverage=Coverage(start=generation.coverage_from, until=generation.coverage_until),
                freshness=freshness,
                rankingPolicy=result.ranking_policy,
                appliedConstraints=result.applied_constraints,
                warnings=([] if freshness == "current" else ["STATIC_DATA_AGING"])
                + result.warnings,
            ),
        )

    return router


def _resolve_place_locations(query: JourneyRequest, generation_id: str) -> JourneyRequest:
    updates = {}
    for field in ("origin", "destination"):
        location = getattr(query, field)
        if getattr(location, "kind", None) != "place":
            continue
        place = decode_place_ref(location.placeRef, generation_id)
        updates[field] = Coordinate(
            kind="coordinate",
            latitude=place.latitude,
            longitude=place.longitude,
        )
    return query.model_copy(update=updates) if updates else query
