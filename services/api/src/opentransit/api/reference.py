"""Bounded schedule reference endpoints; no live data or operator controls."""

import math
import sqlite3
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from opentransit.api.schemas import Coverage, Metadata
from opentransit.runtime import capture_snapshot

PageLimit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=2048)]


def metadata(request: Request, snapshot, now: datetime) -> Metadata:
    generation = snapshot.generation
    freshness = generation.freshness(now)
    return Metadata(
        requestId=request.state.request_id,
        generationId=generation.id,
        generatedAt=now,
        dataBuiltAt=generation.built_at,
        mode=generation.mode,
        coverage=Coverage(start=generation.coverage_from, until=generation.coverage_until),
        freshness=freshness,
        warnings=[] if freshness == "current" else ["STATIC_DATA_AGING"],
    )


def _public(value):
    """Convert database field names to the provisional HTTP naming convention."""
    names = {
        "stop_id": "stopId",
        "source_id": "sourceId",
        "route_id": "routeId",
        "agency_id": "operatorId",
        "short_name": "routeShortName",
        "long_name": "routeLongName",
        "route_type": "routeType",
        "location_type": "locationType",
        "parent_station": "parentStationId",
        "wheelchair_boarding": "wheelchairBoarding",
        "platform_code": "platformCode",
        "distance_m": "distanceMeters",
        "pattern_id": "patternId",
        "direction_id": "directionId",
        "pickup_type": "pickupType",
        "drop_off_type": "dropOffType",
        "text_color": "textColor",
        "fare_url": "fareUrl",
        "zone_id": "zoneId",
    }
    if isinstance(value, dict):
        return {names.get(key, key): _public(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_public(item) for item in value]
    return value


def reference_router(clock, problem) -> APIRouter:
    router = APIRouter()

    def serve(request: Request, operation, *, paginated=False, cursor=None):
        snapshot = capture_snapshot(request.app.state)  # Capture before any work/await.
        now = clock()
        if snapshot is None or snapshot.reference is None:
            return problem(request, 503, "DATA_UNAVAILABLE", "No verified reference is configured.")
        generation = snapshot.generation
        if not generation.contains(now) or generation.freshness(now) == "expired":
            return problem(request, 503, "FEED_EXPIRED", "The generation needs a fresh build.")
        try:
            data = operation(snapshot.reference)
        except ValueError:
            code = "INVALID_CURSOR" if cursor else "INVALID_REQUEST"
            return problem(request, 422, code, "Check the declared selectors and pagination.")
        except OSError, sqlite3.Error:
            return problem(request, 503, "DATA_UNAVAILABLE", "Reference data is unavailable.")
        if data is None:
            return problem(request, 404, "NOT_FOUND", "Resource absent in this generation.")
        payload = {"data": _public(data), "meta": metadata(request, snapshot, now)}
        if paginated:
            payload["data"] = _public(data["items"])
            payload["page"] = {"nextCursor": data["next_cursor"]}
        return JSONResponse(jsonable_encoder(payload))

    @router.get("/v1/stops")
    def stops(
        request: Request,
        near: Annotated[str | None, Query(max_length=100)] = None,
        bbox: Annotated[str | None, Query(max_length=150)] = None,
        radius: Annotated[float, Query(gt=0, le=5000)] = 500,
        limit: PageLimit = 20,
        cursor: Cursor = None,
    ):
        try:
            if (near is None) == (bbox is None) or (
                bbox is not None and "radius" in request.query_params
            ):
                raise ValueError
            if near is not None:
                lat, lon = [float(item) for item in near.split(",")]
                if not (
                    math.isfinite(lat)
                    and math.isfinite(lon)
                    and 29 <= lat <= 34
                    and 34 <= lon <= 36
                ):
                    raise ValueError

                def operation(ref):
                    return ref.stops_near(lat, lon, radius, limit, cursor)
            else:
                west, south, east, north = [float(item) for item in bbox.split(",")]
                if not (29 <= south < north <= 34 and 34 <= west < east <= 36):
                    raise ValueError

                def operation(ref):
                    return ref.stops_in_bbox(south, west, north, east, limit, cursor)
        except ValueError, TypeError:
            return problem(
                request, 422, "INVALID_REQUEST", "Use near=lat,lon or bbox=west,south,east,north."
            )
        return serve(request, operation, paginated=True, cursor=cursor)

    @router.get("/v1/stops/{stop_id}")
    def stop(stop_id: str, request: Request):
        if not stop_id.startswith("mot:stop:") or len(stop_id) > 250:
            return problem(request, 422, "INVALID_REQUEST", "Use a returned stop reference.")
        return serve(request, lambda ref: ref.stop(stop_id))

    @router.get("/v1/routes")
    def routes(
        request: Request,
        stopId: Annotated[str | None, Query(max_length=250)] = None,
        operatorId: Annotated[str | None, Query(max_length=250)] = None,
        routeShortName: Annotated[str | None, Query(max_length=100)] = None,
        limit: PageLimit = 20,
        cursor: Cursor = None,
    ):
        if stopId is not None and not stopId.startswith("mot:stop:"):
            return problem(request, 422, "INVALID_REQUEST", "Use a returned stop reference.")
        return serve(
            request,
            lambda ref: ref.routes(stopId, operatorId, routeShortName, limit, cursor),
            paginated=True,
            cursor=cursor,
        )

    @router.get("/v1/routes/{route_id}")
    def route(route_id: str, request: Request):
        if not route_id.startswith("mot:route:") or len(route_id) > 250:
            return problem(request, 422, "INVALID_REQUEST", "Use a returned route reference.")
        return serve(request, lambda ref: ref.route(route_id))

    @router.get("/v1/routes/{route_id}/patterns")
    def patterns(route_id: str, request: Request, limit: PageLimit = 20, cursor: Cursor = None):
        if not route_id.startswith("mot:route:") or len(route_id) > 250:
            return problem(request, 422, "INVALID_REQUEST", "Use a returned route reference.")

        def read(ref):
            if ref.route(route_id) is None:
                return None
            return ref.patterns(route_id, limit, cursor)

        return serve(request, read, paginated=True, cursor=cursor)

    return router
