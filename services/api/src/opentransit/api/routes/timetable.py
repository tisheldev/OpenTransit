"""Scheduled dated trip and stop departure endpoints."""

from __future__ import annotations

import asyncio
import math
import re
import sqlite3
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from opentransit.api.docs import DEPARTURES_DOC, NEARBY_DOC, TRIP_DOC
from opentransit.api.responses import metadata
from opentransit.api.routes.reference import _public
from opentransit.core.time import as_utc_instant, parse_utc_instant
from opentransit.motis_timetable import (
    NEARBY_ENGINE_CONCURRENCY,
    NEARBY_MAX_PER_STOP,
    NEARBY_MAX_STOPS,
    InvalidDepartureCursor,
    TimetableFailure,
    departures,
    next_departures,
    trip_detail,
)
from opentransit.runtime import capture_snapshot

_EXPLICIT_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z")

# Stops read from the reference before folding platforms into their stations.
_NEARBY_CANDIDATES = 100
NEARBY_MAX_RADIUS_M = 1000
NEARBY_MAX_HORIZON_MINUTES = 180
_PIN_FIELDS = (
    "stop_id",
    "source_id",
    "code",
    "name",
    "description",
    "latitude",
    "longitude",
    "location_type",
    "parent_station",
    "wheelchair_boarding",
    "platform_code",
)


def _nearby_pins(reference, lat: float, lon: float, radius: float, count: int) -> list[dict]:
    """The nearest stops, a platform folded into its station, in distance order."""
    found = reference.stops_near(lat, lon, radius, _NEARBY_CANDIDATES, None)["items"]
    pins: dict[str, dict] = {}
    for row in found:
        parent_id = row.get("parent_station")
        if parent_id:
            if parent_id in pins:
                continue
            parent = reference.stop(parent_id)
            if parent is None:
                continue
            row = {key: parent.get(key) for key in _PIN_FIELDS} | {"distance_m": row["distance_m"]}
        if row["stop_id"] in pins:
            continue
        pins[row["stop_id"]] = {key: row.get(key) for key in _PIN_FIELDS} | {
            "distance_m": row["distance_m"]
        }
        if len(pins) >= count:
            break
    return list(pins.values())


def timetable_router(settings, clock, problem) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/trips/{trip_ref}", responses=TRIP_DOC)
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
            async with asyncio.timeout(settings.journey_deadline_seconds):
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

    @router.get("/v1/stops/{stop_id}/departures", responses=DEPARTURES_DOC)
    async def stop_departures(
        stop_id: str,
        request: Request,
        from_time: Annotated[str, Query(alias="from", min_length=20, max_length=40)],
        horizon: Annotated[int, Query(alias="horizonMinutes", ge=1, le=1440)] = 120,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
        route_id: Annotated[
            str | None,
            Query(
                alias="routeId",
                max_length=250,
                description="Only this line's departures (a returned `mot:route:` reference).",
            ),
        ] = None,
    ):
        if not stop_id.startswith("mot:stop:") or len(stop_id) > 250:
            return problem(request, 422, "INVALID_REQUEST", "Use a returned stop reference.")
        if route_id is not None and (
            not route_id.startswith("mot:route:") or route_id == "mot:route:"
        ):
            return problem(request, 422, "INVALID_REQUEST", "Use a returned route reference.")
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
            async with asyncio.timeout(settings.journey_deadline_seconds):
                async with semaphore:
                    data = await departures(
                        snapshot, stop_id, start, horizon, limit, cursor, route_id
                    )
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

    @router.get("/v1/departures/nearby", responses=NEARBY_DOC)
    async def nearby_departures(
        request: Request,
        near: Annotated[str, Query(max_length=100, description="lat,lon of the person")],
        from_time: Annotated[str, Query(alias="from", min_length=20, max_length=40)],
        radius: Annotated[float, Query(gt=0, le=NEARBY_MAX_RADIUS_M)] = 400,
        stops: Annotated[int, Query(ge=1, le=NEARBY_MAX_STOPS)] = 8,
        per_stop: Annotated[int, Query(alias="perStop", ge=1, le=NEARBY_MAX_PER_STOP)] = 3,
        horizon: Annotated[
            int, Query(alias="horizonMinutes", ge=1, le=NEARBY_MAX_HORIZON_MINUTES)
        ] = 60,
    ):
        """Nearby stops, each with the next departure of each of its lines (Home, board 1).

        A platform is folded into its station. Each departure is verified exactly as on the
        stop board. A stop whose departures could not be read says so
        (`departuresState: unavailable`); if no stop could be read the request fails.
        """
        try:
            lat, lon = [float(item) for item in near.split(",")]
            if not (
                math.isfinite(lat) and math.isfinite(lon) and 29 <= lat <= 34 and 34 <= lon <= 36
            ):
                raise ValueError
        except ValueError, TypeError:
            return problem(request, 422, "INVALID_REQUEST", "Use near=lat,lon inside Israel.")
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
        if snapshot is None or snapshot.reference is None:
            return problem(request, 503, "DATA_UNAVAILABLE", "No verified schedule is configured.")
        generation = snapshot.generation
        if not snapshot.routing_verified:
            return problem(
                request, 503, "DATA_UNAVAILABLE", "The candidate engine needs verification."
            )
        if not generation.contains(now) or generation.freshness(now) == "expired":
            return problem(request, 503, "FEED_EXPIRED", "The generation needs a fresh build.")
        start_utc = as_utc_instant(start)
        end_utc = start_utc + timedelta(minutes=horizon)
        if not generation.contains(start_utc) or end_utc > as_utc_instant(
            generation.coverage_until
        ):
            return problem(request, 422, "OUTSIDE_SERVICE_WINDOW", "Choose a time inside coverage.")
        try:
            pins = await asyncio.to_thread(
                _nearby_pins, snapshot.reference, lat, lon, radius, stops
            )
        except OSError, sqlite3.Error, ValueError:
            return problem(request, 503, "DATA_UNAVAILABLE", "Reference data is unavailable.")
        semaphore = request.app.state.planning_semaphore
        if semaphore.locked():
            return problem(request, 503, "SERVER_OVERLOADED", "Schedule capacity is busy.")
        engine_slots = asyncio.Semaphore(NEARBY_ENGINE_CONCURRENCY)
        budget = {"bytes": 0}

        async def summarize(pin):
            async with engine_slots:
                try:
                    result = await next_departures(
                        snapshot, pin["stop_id"], start_utc, horizon, per_stop, budget
                    )
                except TimetableFailure as exc:
                    if exc.code == "ENGINE_TIMEOUT":
                        raise
                    return {"departuresState": "unavailable", "reason": exc.code}
                except ValueError, KeyError, TypeError, IndexError:
                    return {"departuresState": "unavailable", "reason": "ENGINE_INVALID_RESPONSE"}
                except OSError, sqlite3.Error:
                    return {"departuresState": "unavailable", "reason": "DATA_UNAVAILABLE"}
            return {"departuresState": "available", **result}

        try:
            async with asyncio.timeout(settings.journey_deadline_seconds):
                async with semaphore:
                    summaries = await asyncio.gather(*(summarize(pin) for pin in pins))
        except TimeoutError:
            return problem(request, 504, "ENGINE_TIMEOUT", "The departures lookup timed out.")
        except TimetableFailure as exc:
            return problem(
                request,
                exc.status,
                exc.code,
                "The scheduled departures are temporarily unavailable.",
            )
        if pins and all(item["departuresState"] == "unavailable" for item in summaries):
            # Nothing verified at all: a failure, never an empty successful board.
            return problem(
                request, 503, summaries[0]["reason"], "The scheduled departures are unavailable."
            )
        data = []
        for pin, summary in zip(pins, summaries, strict=True):
            available = summary["departuresState"] == "available"
            data.append(
                {
                    "stop": _public(pin),
                    "departuresState": summary["departuresState"],
                    "unavailableReason": None if available else summary["reason"],
                    "complete": summary.get("complete", False),
                    "departures": summary["departures"] if available else None,
                }
            )
        payload = {
            "data": data,
            "query": {
                "near": {"latitude": lat, "longitude": lon},
                "radiusMeters": radius,
                "stops": stops,
                "perStop": per_stop,
                "from": start_utc.isoformat().replace("+00:00", "Z"),
                "until": end_utc.isoformat().replace("+00:00", "Z"),
            },
            "meta": metadata(request, snapshot, now),
        }
        return JSONResponse(jsonable_encoder(payload))

    return router
