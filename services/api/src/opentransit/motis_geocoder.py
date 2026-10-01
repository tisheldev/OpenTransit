"""Bounded adapter for the pinned local MOTIS geocoder endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

from opentransit.core.place_ref import candidate_identity_hash, encode_place_ref

MAX_GEOCODE_RESPONSE_BYTES = 2_000_000
MAX_GEOCODE_TEXT_CHARS = 200
SUPPORTED_GEOCODE_TYPES = frozenset({"address", "poi"})
_LOGGER = logging.getLogger("opentransit.requests.geocoder")
_REQUEST_ID_PATTERN = re.compile(r"[0-9a-fA-F]{32}\Z")
_GENERATION_ID_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")


class GeocoderUnavailable(RuntimeError):
    """Geocoder failed, was disabled, or returned an invalid response."""

    code = "GEOCODER_UNAVAILABLE"
    status = 503


@dataclass(frozen=True)
class GeocodeResult:
    items: list[dict[str, Any]]
    searched_types: tuple[str, ...] = ()

    @property
    def outcome(self) -> str:
        return "matches_found" if self.items else "no_match"


async def geocode_places(
    snapshot,
    query: str,
    *,
    language: str = "he",
    near: tuple[float, float] | None = None,
    types: tuple[str, ...] = ("poi", "address"),
    limit: int = 10,
    request_id: str | None = None,
) -> GeocodeResult:
    """Search one captured runtime snapshot, preserving success-empty separately from errors."""
    if snapshot is None or getattr(snapshot, "motis", None) is None:
        raise GeocoderUnavailable("Geocoder generation is unavailable")
    generation_id = getattr(getattr(snapshot, "generation", None), "id", None)
    if not isinstance(generation_id, str) or not generation_id:
        raise GeocoderUnavailable("Geocoder generation is unavailable")
    adapter = MotisGeocoder(snapshot.motis, generation_id)
    return await adapter.search(
        query,
        language=language,
        near=near,
        types=types,
        limit=limit,
        request_id=request_id,
    )


class MotisGeocoder:
    def __init__(
        self,
        motis,
        generation_id: str,
        *,
        timeout_seconds: float = 1.5,
        max_response_bytes: int = MAX_GEOCODE_RESPONSE_BYTES,
    ) -> None:
        if not isinstance(generation_id, str) or not generation_id:
            raise ValueError("A generation ID is required")
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 5:
            raise ValueError("Geocoder timeout must be in (0, 5] seconds")
        if not 1 <= max_response_bytes <= MAX_GEOCODE_RESPONSE_BYTES:
            raise ValueError("Geocoder response bound is invalid")
        self.client = getattr(motis, "client", motis)
        self.generation_id = generation_id
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes

    async def search(
        self,
        text: str,
        *,
        language: str = "he",
        types: tuple[str, ...] = ("poi", "address"),
        limit: int = 10,
        near: tuple[float, float] | None = None,
        request_id: str | None = None,
    ) -> GeocodeResult:
        query = _validate_query(text, language, types, limit, near)
        engine_types = tuple(
            engine_type
            for kind, engine_type in (("address", "ADDRESS"), ("poi", "PLACE"))
            if kind in types
        )
        params: list[tuple[str, str]] = [
            ("text", query),
            ("language", language),
            ("type", ",".join(engine_types)),
            ("numResults", str(limit)),
        ]
        if near is not None:
            params.extend(
                [
                    ("place", f"{near[0]:.8f},{near[1]:.8f}"),
                    ("placeBias", "1"),
                ]
            )
        safe_request_id = (
            request_id.lower()
            if isinstance(request_id, str) and _REQUEST_ID_PATTERN.fullmatch(request_id)
            else None
        )
        backend_started = perf_counter()
        try:
            raw = await self._request(params)
        except GeocoderUnavailable:
            _log_phase_timing(
                safe_request_id,
                self.generation_id,
                _milliseconds(backend_started),
                0.0,
                None,
                None,
                "unavailable",
            )
            raise

        backend_ms = _milliseconds(backend_started)
        normalize_started = perf_counter()
        response_bytes = len(raw)
        result_count = None
        outcome = "unavailable"
        try:
            parsed = json.loads(raw)
            matches = _matches_array(parsed)
            if len(matches) > limit:
                raise ValueError("Geocoder exceeded the requested result count")
            items = [_normalize_match(item, self.generation_id) for item in matches]
            if any(item["kind"] not in types for item in items):
                raise ValueError("Geocoder returned a category outside the requested types")
            result_count = len(items)
            outcome = "success" if items else "validempty"
            return GeocodeResult(items, tuple(types))
        except GeocoderUnavailable:
            raise
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise GeocoderUnavailable("Geocoder response was invalid") from exc
        finally:
            _log_phase_timing(
                safe_request_id,
                self.generation_id,
                backend_ms,
                _milliseconds(normalize_started),
                response_bytes,
                result_count,
                outcome,
            )

    async def _request(self, params: list[tuple[str, str]]) -> bytes:
        if not isinstance(self.client, httpx.AsyncClient) or self.client.is_closed:
            raise GeocoderUnavailable("Geocoder client is unavailable")
        try:
            async with asyncio.timeout(self.timeout_seconds):
                request = self.client.build_request("GET", "/api/v1/geocode", params=params)
                response = await self.client.send(
                    request,
                    stream=True,
                    follow_redirects=False,
                )
                try:
                    if response.is_redirect or not 200 <= response.status_code < 300:
                        raise GeocoderUnavailable("Geocoder returned a non-success status")
                    content_length = response.headers.get("content-length")
                    if content_length is not None and int(content_length) > self.max_response_bytes:
                        raise GeocoderUnavailable("Geocoder response exceeded its byte bound")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > self.max_response_bytes:
                            raise GeocoderUnavailable("Geocoder response exceeded its byte bound")
                    return bytes(data)
                finally:
                    await response.aclose()
        except GeocoderUnavailable:
            raise
        except (httpx.HTTPError, TimeoutError, ValueError, OSError) as exc:
            raise GeocoderUnavailable("Geocoder request failed") from exc


def _milliseconds(started: float) -> float:
    return round(max(0.0, (perf_counter() - started) * 1000), 3)


def _log_phase_timing(
    request_id: str | None,
    generation_id: str,
    backend_ms: float,
    normalize_ms: float,
    response_bytes: int | None,
    result_count: int | None,
    outcome: str,
) -> None:
    fields = {
        "request_id": request_id,
        "genid": (
            generation_id.lower() if _GENERATION_ID_PATTERN.fullmatch(generation_id) else None
        ),
        "backend_ms": backend_ms,
        "normalize_ms": normalize_ms,
        "responsebytes": response_bytes,
        "resultcount": result_count,
        "outcome": outcome,
    }
    _LOGGER.info(
        json.dumps(fields, sort_keys=True, separators=(",", ":")),
        extra=fields,
    )


def _validate_query(
    text: str,
    language: str,
    types: tuple[str, ...],
    limit: int,
    near: tuple[float, float] | None,
) -> str:
    if not isinstance(text, str) or not 2 <= len(text.strip()) <= MAX_GEOCODE_TEXT_CHARS:
        raise ValueError("Geocoder text must contain 2 to 200 characters")
    if not isinstance(language, str) or language not in {"he", "en"}:
        raise ValueError("Geocoder language must be he or en")
    if (
        not isinstance(types, tuple)
        or not types
        or any(not isinstance(kind, str) or kind not in SUPPORTED_GEOCODE_TYPES for kind in types)
        or len(set(types)) != len(types)
    ):
        raise ValueError("Geocoder types must be address and/or poi")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("Geocoder limit must be between 1 and 20")
    if near is not None:
        if not isinstance(near, tuple) or len(near) != 2:
            raise ValueError("Near must be a latitude/longitude pair")
        _coordinates(near[0], near[1])
    return text.strip()


def _matches_array(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        matches = payload
    elif isinstance(payload, dict) and set(payload) == {"matches"}:
        matches = payload["matches"]
    else:
        raise ValueError("Unexpected geocoder response shape")
    if not isinstance(matches, list) or any(not isinstance(item, dict) for item in matches):
        raise ValueError("Geocoder matches are malformed")
    return matches


def _normalize_match(match: dict[str, Any], generation_id: str):
    raw_type = match.get("type")
    if raw_type not in {"ADDRESS", "PLACE"}:
        raise ValueError("Unsupported geocoder match type")
    engine_kind = raw_type.casefold()
    kind = "poi" if engine_kind == "place" else "address"
    name = match.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 500:
        raise ValueError("Geocoder match name is invalid")
    label = name.strip()
    latitude, longitude = _coordinates(match.get("lat"), match.get("lon"))
    areas = match.get("areas", [])
    if not isinstance(areas, list) or any(not isinstance(area, dict) for area in areas):
        raise ValueError("Geocoder locality data is invalid")
    locality = _locality(areas)
    language_used = _language_used(label)
    coordinates = {"latitude": latitude, "longitude": longitude}

    if kind == "address":
        street = match.get("street")
        house_number = match.get("houseNumber")
        if street is not None and (not isinstance(street, str) or len(street) > 300):
            raise ValueError("Geocoder street label is invalid")
        if house_number is not None and (
            not isinstance(house_number, str) or len(house_number) > 50
        ):
            raise ValueError("Geocoder house number is invalid")
        street = street.strip() if street and street.strip() else label
        house_number = house_number.strip() if house_number and house_number.strip() else None
        address_level = "house_number" if house_number else "street"
        identity = {
            "label": label,
            "street": street,
            "houseNumber": house_number,
            "locality": locality,
            "coordinates": [latitude, longitude],
        }
        identity_hash = candidate_identity_hash(kind, identity)
        place_ref = encode_place_ref(
            generation_id,
            kind,
            identity_hash,
            latitude=latitude,
            longitude=longitude,
        )
        return {
            "kind": "address",
            "name": label,
            "displayName": label,
            "languageUsed": language_used,
            "locality": locality,
            "coordinates": coordinates,
            "street": street,
            "houseNumber": house_number,
            "addressLevel": address_level,
            "precision": "numbered_label" if house_number else "street",
            "candidateIdentityHash": identity_hash,
            "placeRef": place_ref,
            "locationRef": {"kind": "place", "placeRef": place_ref},
        }

    category = match.get("category")
    osm_id = match.get("id")
    if not isinstance(category, str) or not category or len(category) > 100:
        raise ValueError("Geocoder place category is invalid")
    if not isinstance(osm_id, str) or not osm_id or len(osm_id) > 200:
        raise ValueError("Geocoder place ID is invalid")
    identity = {
        "category": category,
        "osmId": osm_id,
        "coordinates": [latitude, longitude],
    }
    identity_hash = candidate_identity_hash("place", identity)
    place_ref = encode_place_ref(
        generation_id,
        "place",
        identity_hash,
        latitude=latitude,
        longitude=longitude,
    )
    return {
        "kind": "poi",
        "name": label,
        "displayName": label,
        "languageUsed": language_used,
        "locality": locality,
        "coordinates": coordinates,
        "category": category,
        "osmId": osm_id,
        "candidateIdentityHash": identity_hash,
        "placeRef": place_ref,
        "locationRef": {"kind": "place", "placeRef": place_ref},
    }


def _coordinates(latitude: Any, longitude: Any) -> tuple[float, float]:
    if (
        isinstance(latitude, bool)
        or isinstance(longitude, bool)
        or not isinstance(latitude, (int, float))
        or not isinstance(longitude, (int, float))
    ):
        raise ValueError("Geocoder coordinates are invalid")
    lat, lon = float(latitude), float(longitude)
    if not (math.isfinite(lat) and math.isfinite(lon) and 29 <= lat <= 34 and 34 <= lon <= 36):
        raise ValueError("Geocoder coordinates are outside supported coverage")
    return lat, lon


def _locality(areas: list[dict[str, Any]]) -> str | None:
    for area in areas:
        name = area.get("name")
        if (area.get("default") is True or area.get("unique") is True) and isinstance(name, str):
            if name.strip() and len(name) <= 300:
                return name.strip()
    return None


def _language_used(label: str) -> str:
    if any("\u0590" <= char <= "\u05ff" for char in label):
        return "he"
    if any("\u0600" <= char <= "\u06ff" for char in label):
        return "ar"
    if any(char.isalpha() for char in label):
        return "en"
    return "unknown"
