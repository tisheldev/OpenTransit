"""Scheduled dated trip and stop departure endpoints."""

from __future__ import annotations

import asyncio
import re
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from opentransit.api.responses import metadata
from opentransit.core.time import parse_utc_instant
from opentransit.motis_timetable import (
    InvalidDepartureCursor,
    TimetableFailure,
    departures,
    trip_detail,
)
from opentransit.runtime import capture_snapshot

_EXPLICIT_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z")


def timetable_router(clock, problem) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/trips/{trip_ref}")
    async def trip(trip_ref: str, request: Request):
        snapshot = capture_snapshot(request.app.state)
        now = clock()
        if snapshot is None:
            return problem(request, 503, "DATA_UNAVAILABLE", "No verified schedule is configured.")
        generation = snapshot.generation
        if not snapshot.routing_verified:
            return problem(
                request, 503, "DATA_UNAVAILABLE", "The candidate engine needs verification."
            )
        if not generation.contains(now) or generation.freshness(now) == "expired":
            return problem(request, 503, "FEED_EXPIRED", "The generation needs a fresh build.")
        try:
            semaphore = request.app.state.planning_semaphore
            if semaphore.locked():
                return problem(request, 503, "SERVER_OVERLOADED", "Schedule capacity is busy.")
            async with asyncio.timeout(1.5):
                async with semaphore:
                    data = await trip_detail(snapshot, trip_ref)
        except TimetableFailure as exc:
            return problem(
                request, exc.status, exc.code, "The scheduled trip is temporarily unavailable."
            )
        except TimeoutError:
            return problem(request, 504, "ENGINE_TIMEOUT", "The scheduled trip lookup timed out.")
        except OSError, ValueError, TypeError, sqlite3.Error:
            return problem(
                request, 503, "DATA_UNAVAILABLE", "The scheduled trip index is unavailable."
            )
        if data is None:
            return problem(request, 404, "NOT_FOUND", "The dated trip occurrence is absent.")
        data = {key: value for key, value in data.items() if not key.startswith("_")}
        return JSONResponse(
            jsonable_encoder({"data": data, "meta": metadata(request, snapshot, now)})
        )

    @router.get("/v1/stops/{stop_id}/departures")
    async def stop_departures(
        stop_id: str,
        request: Request,
        from_time: Annotated[str, Query(alias="from", min_length=20, max_length=40)],
        horizon: Annotated[int, Query(alias="horizonMinutes", ge=1, le=1440)] = 120,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
    ):
        if not stop_id.startswith("mot:stop:") or len(stop_id) > 250:
            return problem(request, 422, "INVALID_REQUEST", "Use a returned stop reference.")
        if not _EXPLICIT_TIME.fullmatch(from_time):
            return problem(
                request, 422, "INVALID_REQUEST", "Use an ISO timestamp with an explicit offset."
            )
        try:
            start = parse_utc_instant(from_time)
        except ValueError:
            return problem(
                request,
                422,
                "INVALID_REQUEST",
                "Use a valid ISO timestamp with an explicit offset.",
            )
        snapshot = capture_snapshot(request.app.state)
        now = clock()
        if snapshot is None:
            return problem(request, 503, "DATA_UNAVAILABLE", "No verified schedule is configured.")
        generation = snapshot.generation
        if not snapshot.routing_verified:
            return problem(
                request, 503, "DATA_UNAVAILABLE", "The candidate engine needs verification."
            )
        if not generation.contains(now) or generation.freshness(now) == "expired":
            return problem(request, 503, "FEED_EXPIRED", "The generation needs a fresh build.")
        try:
            semaphore = request.app.state.planning_semaphore
            if semaphore.locked():
                return problem(request, 503, "SERVER_OVERLOADED", "Schedule capacity is busy.")
            async with asyncio.timeout(1.5):
                async with semaphore:
                    data = await departures(snapshot, stop_id, start, horizon, limit, cursor)
        except TimetableFailure as exc:
            return problem(
                request,
                exc.status,
                exc.code,
                "The scheduled departures are temporarily unavailable.",
            )
        except TimeoutError:
            return problem(request, 504, "ENGINE_TIMEOUT", "The departures lookup timed out.")
        except InvalidDepartureCursor:
            return problem(
                request, 422, "INVALID_CURSOR", "Restart pagination from the first page."
            )
        except ValueError:
            return problem(
                request, 503, "ENGINE_INVALID_RESPONSE", "The scheduled departure data is invalid."
            )
        except OSError, TypeError, sqlite3.Error:
            return problem(
                request, 503, "DATA_UNAVAILABLE", "The scheduled departure index is unavailable."
            )
        if data is None:
            return problem(request, 404, "NOT_FOUND", "The stop is absent from this generation.")
        payload = {
            "data": data["items"],
            "page": {"nextCursor": data["nextCursor"]},
            "meta": metadata(request, snapshot, now),
        }
        return JSONResponse(jsonable_encoder(payload))

    return router
