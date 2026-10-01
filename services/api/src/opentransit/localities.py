"""Source-backed localities (OSM administrative level 8) for the reference database.

Locality records come from the pinned OSM PBF through the pyosmium context
extraction (``ContextHeader`` + ``Locality`` JSONL records). This module only
reads that file: it needs no OSM reader, no network and no Docker, and every
output is a deterministic function of the context file bytes and the stop
coordinates. Stops are assigned to localities by point-in-polygon containment
(holes excluded). Nothing here is curated or guessed: names are the OSM name
tags as published, the representative point is computed from the polygon.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONTEXT_SCHEMA_VERSION = 1
LOCALITY_SOURCE = "osm-admin-level-8-localities-v1"
LOCALITY_SELECTION = "boundary=administrative; admin_level=8; named; Polygon/MultiPolygon"
LOCALITY_ASSIGNMENT = (
    "stop point inside Polygon/MultiPolygon (holes excluded, boundary counts as inside); "
    "a stop may belong to several overlapping localities"
)
# Name tags kept as searchable names: name, alt_name, short_name, official_name,
# old_name and loc_name, each optionally with a language suffix (name:he, alt_name:en).
_NAME_TAG = re.compile(
    r"^(name|alt_name|short_name|official_name|old_name|loc_name)(?::([A-Za-z]{2,3}(?:-[A-Za-z0-9]+)*))?$"
)
# OSM separates alternative values with ';'; bilingual plain names use ' | '.
_NAME_SEPARATORS = re.compile(r"\s*[;|]\s*")
_BAND_COUNT = 64
_BOUNDARY_EPSILON = 1e-11


@dataclass(frozen=True)
class Locality:
    locality_id: str
    osm_type: str
    osm_id: int
    name: str | None
    name_he: str | None
    name_en: str | None
    place: str | None
    wikidata: str | None
    # (language, name, tag): language is "" for untagged names such as plain "name".
    names: tuple[tuple[str, str, str], ...]
    geometry: dict[str, Any]
    center: tuple[float, float]
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class LocalityDataset:
    localities: tuple[Locality, ...]
    provenance: dict[str, Any]


def locality_id(osm_type: str, osm_id: int) -> str:
    kind = {"R": "relation", "W": "way", "N": "node"}[osm_type]
    return f"osm:{kind}:{osm_id}"


def name_entries(tags: dict[str, str]) -> tuple[tuple[str, str, str], ...]:
    """Searchable (language, name, tag) triples from OSM name tags, sorted and unique."""
    entries: set[tuple[str, str, str]] = set()
    for tag, value in tags.items():
        match = _NAME_TAG.match(tag)
        if match is None or not isinstance(value, str):
            continue
        language = (match.group(2) or "").casefold()
        for part in _NAME_SEPARATORS.split(value):
            cleaned = part.strip()
            if cleaned:
                entries.add((language, cleaned, tag))
    return tuple(sorted(entries))


def _polygons(geometry: dict[str, Any]) -> list[list[list[tuple[float, float]]]]:
    kind, coordinates = geometry.get("type"), geometry.get("coordinates")
    if kind == "Polygon":
        raw = [coordinates]
    elif kind == "MultiPolygon":
        raw = coordinates
    else:
        raise ValueError("Locality geometry must be a Polygon or MultiPolygon")
    polygons = []
    for polygon in raw:
        rings = []
        for ring in polygon:
            points = [(float(position[0]), float(position[1])) for position in ring]
            if len(points) < 4 or points[0] != points[-1]:
                raise ValueError("Locality polygon ring is not closed")
            if not all(math.isfinite(x) and math.isfinite(y) for x, y in points):
                raise ValueError("Locality polygon coordinate is not finite")
            rings.append(points)
        if not rings:
            raise ValueError("Locality polygon has no rings")
        polygons.append(rings)
    if not polygons:
        raise ValueError("Locality geometry has no polygons")
    return polygons


def _bounds(points: Iterable[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs, ys = zip(*points, strict=True)
    return min(ys), min(xs), max(ys), max(xs)  # (min_lat, min_lon, max_lat, max_lon)


class _PreparedPolygon:
    """One polygon (outer ring plus holes) with its edges bucketed by latitude band."""

    def __init__(self, rings: list[list[tuple[float, float]]]) -> None:
        self.min_lat, self.min_lon, self.max_lat, self.max_lon = _bounds(
            point for ring in rings for point in ring
        )
        span = (self.max_lat - self.min_lat) or 1.0
        self.band_height = span / _BAND_COUNT
        self.bands: list[list[tuple[float, float, float, float]]] = [[] for _ in range(_BAND_COUNT)]
        for ring in rings:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
                first, last = sorted((self._band(y1), self._band(y2)))
                for band in range(first, last + 1):
                    self.bands[band].append((x1, y1, x2, y2))

    def _band(self, lat: float) -> int:
        return min(_BAND_COUNT - 1, max(0, int((lat - self.min_lat) / self.band_height)))

    def contains(self, lat: float, lon: float) -> bool:
        if not (self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon):
            return False
        inside = False
        for x1, y1, x2, y2 in self.bands[self._band(lat)]:
            if _on_segment(lon, lat, x1, y1, x2, y2):
                return True
            if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
        # Even-odd over the outer ring and the holes: a point in a hole is outside.
        return inside


def _on_segment(x: float, y: float, x1: float, y1: float, x2: float, y2: float) -> bool:
    if not (min(x1, x2) - _BOUNDARY_EPSILON <= x <= max(x1, x2) + _BOUNDARY_EPSILON):
        return False
    if not (min(y1, y2) - _BOUNDARY_EPSILON <= y <= max(y1, y2) + _BOUNDARY_EPSILON):
        return False
    cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
    return abs(cross) <= _BOUNDARY_EPSILON * (abs(x2 - x1) + abs(y2 - y1) + 1.0)


class PreparedGeometry:
    """Point containment for a Polygon/MultiPolygon, holes excluded."""

    def __init__(self, geometry: dict[str, Any]) -> None:
        self._polygons = [_PreparedPolygon(rings) for rings in _polygons(geometry)]
        bounds = [(p.min_lat, p.min_lon, p.max_lat, p.max_lon) for p in self._polygons]
        self.bbox = (
            min(b[0] for b in bounds),
            min(b[1] for b in bounds),
            max(b[2] for b in bounds),
            max(b[3] for b in bounds),
        )

    def contains(self, lat: float, lon: float) -> bool:
        return any(polygon.contains(lat, lon) for polygon in self._polygons)


def _ring_centroid(ring: list[tuple[float, float]], scale: float) -> tuple[float, float, float]:
    """Signed area and area moments of one ring in a locally equirectangular plane."""
    area = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
        x1, x2 = x1 * scale, x2 * scale
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    return area / 2.0, cx / 6.0, cy / 6.0


def representative_point(geometry: dict[str, Any]) -> tuple[float, float]:
    """(lat, lon) inside the locality: the area centroid, or a scanline point when
    the centroid falls outside (concave shapes, holes, multi-part localities)."""
    polygons = _polygons(geometry)
    prepared = PreparedGeometry(geometry)
    mid_lat = (prepared.bbox[0] + prepared.bbox[2]) / 2.0
    scale = math.cos(math.radians(mid_lat))
    total = mx = my = 0.0
    for rings in polygons:
        for index, ring in enumerate(rings):
            area, cx, cy = _ring_centroid(ring, scale)
            sign = 1.0 if index == 0 else -1.0
            # Rings may be wound either way; weight outer and hole rings by magnitude.
            weight = sign * (1.0 if area >= 0 else -1.0)
            total += weight * area
            mx += weight * cx
            my += weight * cy
    if total != 0.0:
        lat, lon = my / total, mx / total / scale
        if prepared.contains(lat, lon):
            return round(lat, 7), round(lon, 7)
    return _scanline_point(polygons, prepared)


def _scanline_point(
    polygons: list[list[list[tuple[float, float]]]], prepared: PreparedGeometry
) -> tuple[float, float]:
    best: tuple[float, float, float] | None = None  # (width, lat, lon)
    min_lat, _, max_lat, _ = prepared.bbox
    # A fixed deterministic set of latitudes; the widest interior interval wins.
    for step in range(1, 20):
        lat = min_lat + (max_lat - min_lat) * step / 20.0
        for rings in polygons:
            crossings = []
            for ring in rings:
                for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
                    if (y1 > lat) != (y2 > lat):
                        crossings.append(x1 + (lat - y1) * (x2 - x1) / (y2 - y1))
            crossings.sort()
            for left, right in zip(crossings[0::2], crossings[1::2], strict=False):
                lon = (left + right) / 2.0
                if (best is None or right - left > best[0]) and prepared.contains(lat, lon):
                    best = (right - left, lat, lon)
    if best is not None:
        return round(best[1], 7), round(best[2], 7)
    x, y = polygons[0][0][0]
    return y, x  # a boundary vertex always counts as inside


def build_locality(
    osm_type: str, osm_id: str | int, tags: dict[str, str], geometry: dict
) -> Locality:
    identifier = int(osm_id)
    prepared = PreparedGeometry(geometry)
    name_he = tags.get("name:he") or None
    name_en = tags.get("name:en") or None
    return Locality(
        locality_id=locality_id(osm_type, identifier),
        osm_type=osm_type,
        osm_id=identifier,
        name=tags.get("name") or None,
        name_he=name_he,
        name_en=name_en,
        place=tags.get("place") or None,
        wikidata=tags.get("wikidata") or None,
        names=name_entries(tags),
        geometry=geometry,
        center=representative_point(geometry),
        bbox=prepared.bbox,
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_locality_context(path: Path, *, expected_osm_sha256: str | None = None) -> LocalityDataset:
    """Read the Locality records of a pinned OSM context extraction (JSONL).

    ``expected_osm_sha256`` binds the extraction to the generation's OSM input: a
    context made from a different PBF is rejected. If ``extraction-manifest.json``
    sits beside the file it must agree with the file's hash and source hash, and the
    reader identity is recorded as provenance.
    """
    path = Path(path)
    context_sha256 = _file_sha256(path)
    osm_sha256: str | None = None
    records: dict[str, Locality] = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if line_number == 1:
                if (
                    row.get("type") != "ContextHeader"
                    or row.get("schemaVersion") != CONTEXT_SCHEMA_VERSION
                    or not isinstance(row.get("sourceSha256"), str)
                ):
                    raise ValueError("Locality context header is missing or unsupported")
                osm_sha256 = row["sourceSha256"]
                if expected_osm_sha256 is not None and osm_sha256 != expected_osm_sha256:
                    raise ValueError("Locality context was extracted from a different OSM input")
                continue
            if row.get("type") != "Locality":
                continue
            tags = row.get("tags")
            geometry = row.get("geometry")
            if (
                row.get("osmType") not in {"R", "W"}
                or not isinstance(row.get("osmId"), str)
                or not isinstance(tags, dict)
                or tags.get("boundary") != "administrative"
                or tags.get("admin_level") != "8"
                or not isinstance(geometry, dict)
            ):
                raise ValueError(f"Locality record on line {line_number} is invalid")
            locality = build_locality(row["osmType"], row["osmId"], tags, geometry)
            if locality.locality_id in records:
                raise ValueError(f"Duplicate locality {locality.locality_id}")
            records[locality.locality_id] = locality
    if osm_sha256 is None:
        raise ValueError("Locality context is empty")
    if not records:
        raise ValueError("Locality context has no localities")
    provenance: dict[str, Any] = {
        "source": LOCALITY_SOURCE,
        "osmPbfSha256": osm_sha256,
        "contextSha256": context_sha256,
        "contextBytes": path.stat().st_size,
        "contextSchemaVersion": CONTEXT_SCHEMA_VERSION,
        "selection": LOCALITY_SELECTION,
        "assignment": LOCALITY_ASSIGNMENT,
        "localityCount": len(records),
        "reader": None,
    }
    manifest_path = path.with_name("extraction-manifest.json")
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("output", {}).get("sha256") != context_sha256
            or manifest.get("source", {}).get("sha256") != osm_sha256
        ):
            raise ValueError("Locality extraction manifest disagrees with the context file")
        reader = manifest.get("reader", {})
        provenance["reader"] = {
            "library": reader.get("library"),
            "version": reader.get("version"),
            "geometrySource": reader.get("geometrySource"),
        }
    return LocalityDataset(
        tuple(records[key] for key in sorted(records)),
        provenance,
    )


def assign_stops(
    localities: Iterable[Locality], stops: Iterable[tuple[str, float | None, float | None]]
) -> list[tuple[str, str]]:
    """(stop_id, locality_id) for every locality that contains a located stop, sorted."""
    prepared = [
        (locality.locality_id, PreparedGeometry(locality.geometry)) for locality in localities
    ]
    cell = 0.1
    grid: dict[tuple[int, int], list[int]] = {}
    for index, (_, geometry) in enumerate(prepared):
        min_lat, min_lon, max_lat, max_lon = geometry.bbox
        for row in range(math.floor(min_lat / cell), math.floor(max_lat / cell) + 1):
            for column in range(math.floor(min_lon / cell), math.floor(max_lon / cell) + 1):
                grid.setdefault((row, column), []).append(index)
    assignments: list[tuple[str, str]] = []
    for stop_id, lat, lon in stops:
        if lat is None or lon is None:
            continue
        for index in grid.get((math.floor(lat / cell), math.floor(lon / cell)), ()):
            locality_key, geometry = prepared[index]
            if geometry.contains(lat, lon):
                assignments.append((stop_id, locality_key))
    return sorted(assignments)
