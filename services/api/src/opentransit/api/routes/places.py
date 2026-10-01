"""Place search over one captured immutable generation."""

import math
import sqlite3
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from opentransit.api.responses import metadata
from opentransit.geocoding import geocode_places
from opentransit.motis_geocoder import GeocoderUnavailable
from opentransit.runtime import capture_snapshot
from opentransit.stop_search import search_stops

_VALID_TYPES = ("stop", "station", "poi", "address")
_RANKING_POLICY = "alternating-stop-and-geocoder-order-v1"


def places_router(clock, problem) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/places")
    async def places(
        request: Request,
        q: Annotated[str, Query(min_length=1, max_length=250)],
        lang: Annotated[str, Query()] = "he",
        near: Annotated[str | None, Query(max_length=100)] = None,
        type: Annotated[list[str] | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=20)] = 10,
    ):
        # Capture before any backend await so all response evidence names one generation.
        snapshot = capture_snapshot(request.app.state)
        now: datetime = clock()
        if snapshot is None:
            return problem(
                request, 503, "DATA_UNAVAILABLE", "No verified generation is configured."
            )
        generation = snapshot.generation
        if not generation.contains(now) or generation.freshness(now) == "expired":
            return problem(request, 503, "FEED_EXPIRED", "The generation needs a fresh build.")

        try:
            near_point = None
            if near is not None:
                pieces = near.split(",")
                if len(pieces) != 2:
                    raise ValueError
                latitude, longitude = (float(part) for part in pieces)
                if not (
                    math.isfinite(latitude)
                    and math.isfinite(longitude)
                    and 29 <= latitude <= 34
                    and 34 <= longitude <= 36
                ):
                    raise ValueError
                near_point = (latitude, longitude)
            requested_types = tuple(type or _VALID_TYPES)
            if (
                not 2 <= len(q.strip()) <= 200
                or lang not in {"he", "en"}
                or not requested_types
                or len(set(requested_types)) != len(requested_types)
                or any(category not in _VALID_TYPES for category in requested_types)
            ):
                raise ValueError
        except ValueError, TypeError:
            return problem(
                request,
                422,
                "INVALID_REQUEST",
                "Check q, lang, near, type, and limit bounds.",
            )

        requested_stops = tuple(kind for kind in requested_types if kind in {"stop", "station"})
        requested_geocoders = tuple(kind for kind in requested_types if kind in {"poi", "address"})
        matched_types: list[str] = []
        unavailable_types: list[str] = []
        stop_items: list[dict] = []
        geocoder_items: list[dict] = []

        if requested_stops:
            if snapshot.reference is None:
                unavailable_types.extend(requested_stops)
            else:
                try:
                    result = search_stops(
                        snapshot.reference,
                        q,
                        language=lang,
                        near=near_point,
                        types=requested_stops,
                        limit=limit,
                    )
                    stop_items = result["items"]
                    matched_types.extend(requested_stops)
                    for item in stop_items:
                        item["locationRef"] = {"kind": "stop", "stopId": item["id"]}
                except ValueError, TypeError:
                    return problem(
                        request,
                        422,
                        "INVALID_REQUEST",
                        "Check q, lang, near, type, and limit bounds.",
                    )
                except OSError, sqlite3.Error:
                    unavailable_types.extend(requested_stops)

        if requested_geocoders:
            enabled = getattr(request.app.state, "generation_geocoding", {})
            motis_geocoding_enabled = enabled.get(generation.id, False)
            address_provider = getattr(snapshot, "address_provider", None)
            address_provider_required = getattr(snapshot, "address_provider_required", False)
            available_geocoders = tuple(
                kind
                for kind in requested_geocoders
                if (
                    kind == "address"
                    and (address_provider is not None or address_provider_required)
                )
                or (kind == "poi" and motis_geocoding_enabled)
                or (
                    kind == "address"
                    and address_provider is None
                    and not address_provider_required
                    and motis_geocoding_enabled
                )
            )
            unavailable_types.extend(
                kind for kind in requested_geocoders if kind not in available_geocoders
            )
            if available_geocoders:
                try:
                    result = await geocode_places(
                        snapshot,
                        q,
                        language=lang,
                        near=near_point,
                        types=available_geocoders,
                        limit=limit,
                        request_id=getattr(request.state, "request_id", None),
                    )
                    geocoder_items = result.items
                    # A valid 2xx empty response still means these categories were searched.
                    matched_types.extend(result.searched_types)
                    unavailable_types.extend(result.unavailable_types)
                except ValueError:
                    return problem(
                        request,
                        422,
                        "INVALID_REQUEST",
                        "Check q, lang, near, type, and limit bounds.",
                    )
                except GeocoderUnavailable:
                    unavailable_types.extend(available_geocoders)

        if not matched_types:
            if snapshot.reference is None:
                return problem(request, 503, "DATA_UNAVAILABLE", "Reference data is unavailable.")
            return problem(
                request,
                503,
                "CATEGORY_UNAVAILABLE",
                "Requested place categories are unavailable in this generation.",
            )

        payload = {
            "data": _merge_candidates(stop_items, geocoder_items, limit),
            "meta": metadata(request, snapshot, now),
            "matchedTypes": [kind for kind in _VALID_TYPES if kind in matched_types],
            "unavailableTypes": [kind for kind in _VALID_TYPES if kind in unavailable_types],
            "partial": bool(unavailable_types),
            "rankingPolicy": _RANKING_POLICY,
        }
        return JSONResponse(jsonable_encoder(payload))

    return router


def _merge_candidates(stops: list[dict], geocoders: list[dict], limit: int) -> list[dict]:
    """Alternate incomparable backend orders and deduplicate before the final bound."""
    merged = []
    seen = set()
    for index in range(max(len(stops), len(geocoders))):
        for pool in (stops, geocoders):
            if index >= len(pool):
                continue
            item = pool[index]
            location_ref = item.get("locationRef") or {}
            identity = location_ref.get("stopId", location_ref.get("placeRef"))
            key = (location_ref.get("kind"), identity)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged
