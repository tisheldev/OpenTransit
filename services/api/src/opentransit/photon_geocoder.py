"""Bounded Photon adapter that accepts only candidates in a pinned source catalog."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from opentransit.core.place_ref import candidate_identity_hash, encode_place_ref

MAX_PHOTON_RESPONSE_BYTES = 2_000_000
MAX_PHOTON_TIMEOUT_SECONDS = 1.5
MAX_SOURCE_COORDINATE_DELTA_METERS = 2.0
_REQUEST_ID = re.compile(r"[0-9a-fA-F]{32}\Z")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
_OSM_TYPES = {"N": "N", "node": "N", "W": "W", "way": "W"}
_LOGGER = logging.getLogger("opentransit.requests.photon")


class PhotonUnavailable(RuntimeError):
    """Photon is unavailable or returned a candidate that cannot be source-verified."""


@dataclass(frozen=True)
class PhotonAddressResult:
    items: list[dict[str, Any]]
    searched_types: tuple[str, ...] = ("address",)

    @property
    def outcome(self) -> str:
        return "success" if self.items else "validempty"


class PhotonGeocoder:
    def __init__(
        self, binding, generation_id: str, *, timeout_seconds: float = MAX_PHOTON_TIMEOUT_SECONDS
    ):
        if not isinstance(generation_id, str) or not generation_id:
            raise ValueError("A generation ID is required")
        if (
            not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= MAX_PHOTON_TIMEOUT_SECONDS
        ):
            raise ValueError("Photon timeout must be in (0, 1.5] seconds")
        self.binding = binding
        self.client = getattr(binding, "client", None)
        self.origin = _checked_origin(getattr(binding, "origin", None))
        self.artifact_identity = getattr(binding, "artifact_identity", None)
        self.index_uuid = getattr(binding, "index_uuid", None)
        self.catalog = getattr(binding, "catalog", None)
        if not isinstance(self.artifact_identity, str) or not _SHA256.fullmatch(
            self.artifact_identity
        ):
            raise ValueError("Photon artifact identity is invalid")
        if (
            not isinstance(self.index_uuid, str)
            or not self.index_uuid
            or len(self.index_uuid) > 128
        ):
            raise ValueError("Photon index identity is invalid")
        if self.catalog is None or not callable(getattr(self.catalog, "lookup", None)):
            raise ValueError("Photon source catalog is unavailable")
        if not isinstance(self.client, httpx.AsyncClient) or self.client.is_closed:
            raise PhotonUnavailable("Photon client is unavailable")
        self.generation_id = generation_id
        self.timeout_seconds = timeout_seconds

    async def search(
        self,
        query: str,
        *,
        language: str,
        limit: int,
        near: tuple[float, float] | None = None,
        request_id: str | None = None,
    ) -> PhotonAddressResult:
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200:
            raise ValueError("Photon query must contain 2 to 200 characters")
        if language not in {"he", "en"}:
            raise ValueError("Photon language must be he or en")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError("Photon result limit must be between 1 and 20")
        if near is not None:
            _validate_near(near)
        safe_request_id = (
            request_id.lower()
            if isinstance(request_id, str) and _REQUEST_ID.fullmatch(request_id)
            else None
        )
        params = [
            ("q", query.strip()),
            ("lang", language),
            ("limit", str(limit)),
            ("layer", "house"),
            ("layer", "street"),
        ]
        if near is not None:
            params.extend((("lat", f"{near[0]:.8f}"), ("lon", f"{near[1]:.8f}")))
        started = time.perf_counter()
        raw: bytes | None = None
        normalize_started = None
        result_count = None
        outcome = "unavailable"
        try:
            raw = await self._request(params)
            backend_ms = _elapsed_ms(started)
            normalize_started = time.perf_counter()
            features = _features(json.loads(raw), limit)
            items = [self._candidate(feature) for feature in features]
            result_count = len(items)
            outcome = "success" if items else "validempty"
            return PhotonAddressResult(items)
        except PhotonUnavailable:
            raise
        except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError) as exc:
            raise PhotonUnavailable("Photon response could not be source-verified") from exc
        finally:
            if normalize_started is None:
                backend_ms = _elapsed_ms(started)
                normalize_ms = 0.0
            else:
                normalize_ms = _elapsed_ms(normalize_started)
            _log_phase(
                safe_request_id,
                self.generation_id,
                backend_ms,
                normalize_ms,
                len(raw) if raw is not None else None,
                result_count,
                outcome,
            )

    async def _request(self, params: list[tuple[str, str]]) -> bytes:
        if self.client.is_closed:
            raise PhotonUnavailable("Photon client is unavailable")
        response = None
        try:
            async with asyncio.timeout(self.timeout_seconds):
                request = self.client.build_request("GET", "/api", params=params)
                authority = request.url.netloc.decode("ascii").lower()
                request_origin = f"{request.url.scheme}://{authority}".lower()
                if request_origin != self.origin or request.url.path != "/api":
                    raise PhotonUnavailable("Photon request origin changed")
                response = await self.client.send(request, stream=True, follow_redirects=False)
                if response.is_redirect or not 200 <= response.status_code < 300:
                    raise PhotonUnavailable("Photon returned a non-success status")
                declared_length = response.headers.get("content-length")
                if declared_length is not None:
                    try:
                        if int(declared_length) > MAX_PHOTON_RESPONSE_BYTES:
                            raise PhotonUnavailable("Photon response exceeded its byte bound")
                    except ValueError as exc:
                        raise PhotonUnavailable("Photon content length is invalid") from exc
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_PHOTON_RESPONSE_BYTES:
                        raise PhotonUnavailable("Photon response exceeded its byte bound")
                return bytes(data)
        except PhotonUnavailable:
            raise
        except (httpx.HTTPError, TimeoutError, OSError, ValueError) as exc:
            raise PhotonUnavailable("Photon request failed") from exc
        finally:
            if response is not None:
                try:
                    await response.aclose()
                except httpx.HTTPError:
                    pass

    def _candidate(self, feature: dict[str, Any]) -> dict[str, Any]:
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise PhotonUnavailable("Photon feature shape is invalid")
        osm_type = _OSM_TYPES.get(properties.get("osm_type"))
        osm_id = properties.get("osm_id")
        if (
            osm_type not in {"N", "W"}
            or isinstance(osm_id, bool)
            or not isinstance(osm_id, (int, str))
        ):
            raise PhotonUnavailable("Photon feature source identity is invalid")
        osm_id = str(osm_id)
        if not osm_id.isdigit():
            raise PhotonUnavailable("Photon feature source identity is invalid")
        try:
            source = self.catalog.lookup(osm_type, osm_id)
        except sqlite3.Error as exc:
            raise PhotonUnavailable("Photon source catalog is unavailable") from exc
        if source is None:
            raise PhotonUnavailable("Photon returned a source absent from its pinned catalog")
        address_type = source.get("address_type")
        if (osm_type, address_type) not in {("N", "house"), ("W", "street")}:
            raise PhotonUnavailable("Photon source has a mutated address type")
        expected_layer = address_type
        returned_layer = properties.get("layer")
        if returned_layer is not None and returned_layer != expected_layer:
            raise PhotonUnavailable("Photon feature layer differs from source address type")
        source_id = source.get("object_id")
        if source.get("object_type") != osm_type or str(source_id) != osm_id:
            raise PhotonUnavailable("Photon source identity differs from catalog")
        coordinates = _feature_coordinates(geometry)
        source_centroid = source.get("centroid")
        if not _coordinates_match(coordinates, source_centroid):
            raise PhotonUnavailable("Photon feature coordinates differ from source catalog")
        tags = source.get("extra", {})
        address = source.get("address", {})
        if not isinstance(tags, dict) or not isinstance(address, dict):
            raise PhotonUnavailable("Photon source address fields are malformed")
        house_number = source.get("housenumber") if address_type == "house" else None
        if address_type == "house":
            returned_number = properties.get("housenumber")
            if not isinstance(house_number, str) or returned_number != house_number:
                raise PhotonUnavailable("Photon house number differs from source catalog")
        elif properties.get("housenumber") not in {None, ""}:
            raise PhotonUnavailable("Photon street feature unexpectedly has a house number")
        returned_street = properties.get("street")
        street = _source_street(properties, source)
        locality = _source_locality(properties, source)
        display_name = properties.get("name")
        if display_name is not None:
            if not isinstance(display_name, str) or not display_name.strip():
                raise PhotonUnavailable("Photon feature display name is invalid")
            display_name = display_name.strip()
            if address_type == "house" and display_name not in _source_values(
                source, "name", "name:he", "name:en"
            ):
                raise PhotonUnavailable("Photon house name differs from source catalog")
        elif address_type == "house":
            if (
                not isinstance(returned_street, str)
                or not returned_street.strip()
                or street is None
            ):
                raise PhotonUnavailable("Photon house lacks a source-verified street label")
            suffix = f"{returned_street.strip()} {house_number}"
            display_name = f"{suffix}, {locality}" if locality else suffix
        if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 500:
            raise PhotonUnavailable("Photon feature display name is invalid")
        display_name = display_name.strip()
        if address_type == "street" and display_name not in _source_values(
            source, "name", "name:he", "name:en"
        ):
            raise PhotonUnavailable("Photon street name differs from source catalog")
        language_used = _source_language(display_name, properties, source)
        latitude, longitude = coordinates[1], coordinates[0]
        identity = {
            "osmType": osm_type,
            "osmId": osm_id,
            "addressType": address_type,
            "houseNumber": house_number,
            "street": street,
            "locality": locality,
            "coordinates": [latitude, longitude],
            "providerArtifactIdentity": self.artifact_identity,
            "indexUuid": self.index_uuid,
        }
        identity_hash = candidate_identity_hash("address", identity)
        place_ref = encode_place_ref(
            self.generation_id,
            "address",
            identity_hash,
            latitude,
            longitude,
        )
        return {
            "kind": "address",
            "name": display_name,
            "displayName": display_name,
            "languageUsed": language_used,
            "locality": locality,
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "street": street,
            "houseNumber": house_number,
            "addressLevel": "house_number" if address_type == "house" else "street",
            "precision": "address_node" if address_type == "house" else "street_way_midpoint",
            "osmType": osm_type,
            "osmId": osm_id,
            "candidateIdentityHash": identity_hash,
            "placeRef": place_ref,
            "locationRef": {"kind": "place", "placeRef": place_ref},
        }


def _checked_origin(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Photon origin is invalid")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.path not in {"", "/"}:
        raise ValueError("Photon origin is invalid")
    if parts.query or parts.fragment or parts.username or parts.password:
        raise ValueError("Photon origin is invalid")
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


def _validate_near(near: tuple[float, float]) -> None:
    if not isinstance(near, tuple) or len(near) != 2:
        raise ValueError("Photon near must be a latitude/longitude pair")
    latitude, longitude = near
    if (
        isinstance(latitude, bool)
        or isinstance(longitude, bool)
        or not isinstance(latitude, (int, float))
        or not isinstance(longitude, (int, float))
        or not math.isfinite(float(latitude))
        or not math.isfinite(float(longitude))
        or not 29 <= latitude <= 34
        or not 34 <= longitude <= 36
    ):
        raise ValueError("Photon near coordinate is outside supported coverage")


def _features(payload: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise PhotonUnavailable("Photon FeatureCollection is invalid")
    features = payload.get("features")
    if (
        not isinstance(features, list)
        or len(features) > limit
        or any(not isinstance(feature, dict) for feature in features)
    ):
        raise PhotonUnavailable("Photon feature list is invalid")
    return features


def _feature_coordinates(geometry: dict[str, Any]) -> tuple[float, float]:
    coordinates = geometry.get("coordinates")
    if geometry.get("type") != "Point" or not isinstance(coordinates, list) or len(coordinates) < 2:
        raise PhotonUnavailable("Photon feature geometry is invalid")
    longitude, latitude = coordinates[:2]
    if (
        isinstance(latitude, bool)
        or isinstance(longitude, bool)
        or not isinstance(latitude, (int, float))
        or not isinstance(longitude, (int, float))
        or not math.isfinite(float(latitude))
        or not math.isfinite(float(longitude))
        or not 29 <= latitude <= 34
        or not 34 <= longitude <= 36
    ):
        raise PhotonUnavailable("Photon feature coordinates are invalid")
    return float(longitude), float(latitude)


def _coordinates_match(coordinates: tuple[float, float], centroid: Any) -> bool:
    if not isinstance(centroid, list) or len(centroid) != 2:
        return False
    lon, lat = centroid
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (lon, lat)):
        return False
    p1, p2 = math.radians(float(lat)), math.radians(coordinates[1])
    dlat = p2 - p1
    dlon = math.radians(coordinates[0] - float(lon))
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    distance = 2 * 6_371_008.8 * math.asin(math.sqrt(a))
    return distance <= MAX_SOURCE_COORDINATE_DELTA_METERS


def _source_values(source: dict[str, Any], *keys: str) -> set[str]:
    values = set()
    for collection_name in ("address", "extra", "name"):
        collection = source.get(collection_name)
        if isinstance(collection, dict):
            values.update(
                value.strip()
                for key, value in collection.items()
                if key in keys and isinstance(value, str) and value.strip()
            )
    return values


def _source_language(display_name: str, properties: dict[str, Any], source: dict[str, Any]) -> str:
    for language in ("he", "en"):
        keys = {
            f"name:{language}",
            f"street:{language}",
            f"city:{language}",
            f"addr:street:{language}",
            f"addr:city:{language}",
        }
        if display_name in _source_values(source, *keys):
            return language
        returned_street = properties.get("street")
        if isinstance(returned_street, str) and returned_street in _source_values(source, *keys):
            return language
    return "unknown"


def _source_street(properties: dict[str, Any], source: dict[str, Any]) -> str | None:
    address = source.get("address", {})
    tags = source.get("extra", {})
    names = source.get("name", {})
    provider_street = properties.get("street")
    if isinstance(provider_street, str) and provider_street.strip():
        source_street_labels = _source_values(
            source,
            "street",
            "street:he",
            "street:en",
            "addr:street",
            "addr:street:he",
            "addr:street:en",
            "name",
            "name:he",
            "name:en",
        )
        if provider_street.strip() not in source_street_labels:
            raise PhotonUnavailable("Photon street label differs from source catalog")
        return provider_street.strip()
    for value in (
        address.get("street") if isinstance(address, dict) else None,
        tags.get("addr:street") if isinstance(tags, dict) else None,
        names.get("name") if isinstance(names, dict) else None,
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _source_locality(properties: dict[str, Any], source: dict[str, Any]) -> str | None:
    address = source.get("address", {})
    if isinstance(address, dict):
        value = address.get("city")
        if isinstance(value, str) and value.strip():
            return value.strip()
        for key in ("city:he", "city:en"):
            value = address.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _elapsed_ms(started: float) -> float:
    return round(max(0.0, (time.perf_counter() - started) * 1000), 3)


def _log_phase(
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
        "genid": generation_id.lower() if _SHA256.fullmatch(generation_id) else None,
        "backend_ms": backend_ms,
        "normalize_ms": normalize_ms,
        "responsebytes": response_bytes,
        "resultcount": result_count,
        "outcome": outcome,
    }
    _LOGGER.info(json.dumps(fields, sort_keys=True, separators=(",", ":")), extra=fields)
