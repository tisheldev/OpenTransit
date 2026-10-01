"""Versioned, generation-bound coordinate selection references for places.

The token is a stable selector, not an authentication token and not proof that
an OSM identity or coordinate is authoritative.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any

PLACE_REF_PREFIX = "mot:place:v1:"
MAX_PLACE_REF_CHARS = 768
_IDENTITY_HASH = re.compile(r"[a-f0-9]{64}\Z")


@dataclass(frozen=True)
class PlaceReference:
    generation_id: str
    kind: str
    candidate_identity_hash: str
    latitude: float
    longitude: float


def candidate_identity_hash(kind: str, identity: dict[str, Any]) -> str:
    """Hash exact candidate identity fields using canonical UTF-8 JSON."""
    if kind not in {"address", "place"} or not isinstance(identity, dict) or not identity:
        raise ValueError("Invalid place identity")
    try:
        canonical = json.dumps(
            {"kind": kind, "identity": identity},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("Invalid place identity") from exc
    if len(canonical) > 4096:
        raise ValueError("Place identity is too large")
    return hashlib.sha256(canonical).hexdigest()


def encode_place_ref(
    generation_id: str,
    kind: str,
    identity_sha256: str,
    latitude: float,
    longitude: float,
) -> str:
    generation = _generation_id(generation_id)
    lat, lon = _coordinates(latitude, longitude)
    if kind not in {"address", "place"}:
        raise ValueError("Place reference kind is invalid")
    if not isinstance(identity_sha256, str) or not _IDENTITY_HASH.fullmatch(identity_sha256):
        raise ValueError("Place identity SHA-256 is invalid")
    payload = {
        "candidateIdentityHash": identity_sha256,
        "coordinates": [lat, lon],
        "generationId": generation,
        "kind": kind,
    }
    encoded = (
        base64.urlsafe_b64encode(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        .decode("ascii")
        .rstrip("=")
    )
    reference = PLACE_REF_PREFIX + encoded
    if len(reference) > MAX_PLACE_REF_CHARS:
        raise ValueError("Place reference is too large")
    return reference


def decode_place_ref(value: str, expected_generation_id: str) -> PlaceReference:
    """Decode a strict v1 selector and reject malformed or stale references."""
    if not isinstance(value, str) or len(value) > MAX_PLACE_REF_CHARS:
        raise ValueError("Place reference is invalid")
    if not value.startswith(PLACE_REF_PREFIX):
        raise ValueError("Place reference version is unsupported")
    encoded = value.removeprefix(PLACE_REF_PREFIX)
    if not encoded or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded) or len(encoded) % 4 == 1:
        raise ValueError("Place reference encoding is invalid")
    try:
        payload_bytes = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        if base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=") != encoded:
            raise ValueError("Place reference encoding is not canonical")
        payload = json.loads(payload_bytes, object_pairs_hook=_unique_object)
    except (ValueError, TypeError, UnicodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValueError("Place reference payload is invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "candidateIdentityHash",
        "coordinates",
        "generationId",
        "kind",
    }:
        raise ValueError("Place reference fields are invalid")
    generation = _generation_id(payload["generationId"])
    if generation != _generation_id(expected_generation_id):
        raise ValueError("Place reference belongs to another generation")
    kind = payload["kind"]
    identity_hash = payload["candidateIdentityHash"]
    coords = payload["coordinates"]
    if not isinstance(kind, str) or kind not in {"address", "place"}:
        raise ValueError("Place reference kind is invalid")
    if not isinstance(identity_hash, str) or not _IDENTITY_HASH.fullmatch(identity_hash):
        raise ValueError("Place reference identity is invalid")
    if not isinstance(coords, list) or len(coords) != 2:
        raise ValueError("Place reference coordinates are invalid")
    lat, lon = _coordinates(coords[0], coords[1])
    return PlaceReference(generation, kind, identity_hash, lat, lon)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate place reference field")
        result[key] = value
    return result


def _generation_id(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise ValueError("Generation ID is invalid")
    if any(ord(char) < 0x21 or ord(char) > 0x7E for char in value):
        raise ValueError("Generation ID is invalid")
    return value


def _coordinates(latitude: Any, longitude: Any) -> tuple[float, float]:
    if (
        isinstance(latitude, bool)
        or isinstance(longitude, bool)
        or not isinstance(latitude, (int, float))
        or not isinstance(longitude, (int, float))
    ):
        raise ValueError("Place coordinates are invalid")
    lat, lon = float(latitude), float(longitude)
    if not (math.isfinite(lat) and math.isfinite(lon) and 29 <= lat <= 34 and 34 <= lon <= 36):
        raise ValueError("Place coordinates are outside supported coverage")
    return lat, lon
