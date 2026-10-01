"""Enrich a frozen Photon house dump from source-linked OSM ways and localities."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_SHA256 = "8a34b30f91a63ef9239961ba0e4d660ae22deda2f6da4b85ba4772a6b7c4c74f"
EXPECTED_HOUSE_DUMP_SHA256 = "6ddee9f640e11b7ec696690663da7d9d571e15a10f5b8836aac14ec73fc6faca"
EXPECTED_HOUSE_COUNT = 125_857
CELL_DEGREES = 0.01
MAX_CELLS_PER_OBJECT = 10_000
MAX_STREET_ASSOCIATION_METERS = 180.0
EPSILON = 1e-10
PHOTON_DUMP_VERSION = "0.1.0"


@dataclass(frozen=True)
class Locality:
    osm_type: str
    osm_id: str
    tags: dict[str, str]
    geometry: dict[str, Any]
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class Street:
    osm_id: str
    tags: dict[str, str]
    coordinates: tuple[tuple[float, float], ...]
    bbox: tuple[float, float, float, float]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    clean = " ".join(value.split())
    return clean or None


def _label_key(value: str) -> str:
    return " ".join(value.split()).casefold()


def _positions(value: Any):
    if not isinstance(value, list):
        return
    if (
        len(value) >= 2
        and not isinstance(value[0], bool)
        and not isinstance(value[1], bool)
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        lon, lat = float(value[0]), float(value[1])
        if math.isfinite(lon) and math.isfinite(lat):
            yield lon, lat
        return
    for child in value:
        yield from _positions(child)


def _bbox(points) -> tuple[float, float, float, float] | None:
    points = list(points)
    if not points:
        return None
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return min(lons), min(lats), max(lons), max(lats)


class GridIndex:
    """Small fixed grid to bound polygon and nearby-way candidate lookup."""

    def __init__(self, cell_degrees: float = CELL_DEGREES) -> None:
        self.cell_degrees = cell_degrees
        self.cells: dict[tuple[int, int], set[str]] = defaultdict(set)
        self.global_ids: set[str] = set()

    def _cell(self, lon: float, lat: float) -> tuple[int, int]:
        return math.floor(lon / self.cell_degrees), math.floor(lat / self.cell_degrees)

    def add(self, identity: str, bbox: tuple[float, float, float, float]) -> None:
        x0, y0 = self._cell(bbox[0], bbox[1])
        x1, y1 = self._cell(bbox[2], bbox[3])
        size = (x1 - x0 + 1) * (y1 - y0 + 1)
        if size > MAX_CELLS_PER_OBJECT:
            self.global_ids.add(identity)
            return
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                self.cells[(x, y)].add(identity)

    def nearby(self, lon: float, lat: float, radius_cells: int = 0) -> set[str]:
        x, y = self._cell(lon, lat)
        result = set(self.global_ids)
        for cell_x in range(x - radius_cells, x + radius_cells + 1):
            for cell_y in range(y - radius_cells, y + radius_cells + 1):
                result.update(self.cells.get((cell_x, cell_y), ()))
        return result


def _valid_lon_lat(point: Any) -> bool:
    return (
        isinstance(point, (tuple, list))
        and len(point) >= 2
        and all(
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(float(value))
            for value in point[:2]
        )
        and -180 <= float(point[0]) <= 180
        and -90 <= float(point[1]) <= 90
    )


def _point_on_segment(point, start, end) -> bool:
    px, py = point
    ax, ay = start
    bx, by = end
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > EPSILON:
        return False
    return (
        min(ax, bx) - EPSILON <= px <= max(ax, bx) + EPSILON
        and min(ay, by) - EPSILON <= py <= max(ay, by) + EPSILON
    )


def _ring_state(point: tuple[float, float], ring: Any) -> str:
    if not isinstance(ring, list) or len(ring) < 4:
        return "outside"
    inside = False
    for index, raw_start in enumerate(ring):
        raw_end = ring[(index + 1) % len(ring)]
        if not _valid_lon_lat(raw_start) or not _valid_lon_lat(raw_end):
            return "outside"
        start, end = tuple(raw_start[:2]), tuple(raw_end[:2])
        if _point_on_segment(point, start, end):
            return "boundary"
        x1, y1 = start
        x2, y2 = end
        if (y1 > point[1]) != (y2 > point[1]):
            crossing_x = (x2 - x1) * (point[1] - y1) / (y2 - y1) + x1
            if point[0] < crossing_x:
                inside = not inside
    return "inside" if inside else "outside"


def point_in_geometry(point: tuple[float, float], geometry: dict[str, Any]) -> str:
    """Return inside/outside/boundary for GeoJSON Polygon or MultiPolygon."""
    kind, coordinates = geometry.get("type"), geometry.get("coordinates")
    polygons = [coordinates] if kind == "Polygon" else coordinates if kind == "MultiPolygon" else []
    if not isinstance(polygons, list):
        return "outside"
    has_inside = False
    has_boundary = False
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            continue
        outer = _ring_state(point, polygon[0])
        if outer == "boundary":
            has_boundary = True
            continue
        if outer != "inside":
            continue
        in_hole = False
        hole_boundary = False
        for hole in polygon[1:]:
            state = _ring_state(point, hole)
            if state == "boundary":
                hole_boundary = True
                break
            if state == "inside":
                in_hole = True
                break
        if hole_boundary:
            has_boundary = True
        elif not in_hole:
            has_inside = True
    if has_boundary:
        return "boundary"
    return "inside" if has_inside else "outside"


def _parse_context(
    path: Path, expected_source_sha256: str
) -> tuple[list[Street], list[Locality], str]:
    streets: list[Street] = []
    localities: list[Locality] = []
    street_ids: set[str] = set()
    locality_ids: set[tuple[str, str]] = set()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        first_line = source.readline()
        digest.update(first_line)
        try:
            header = json.loads(first_line)
        except json.JSONDecodeError as exc:
            raise ValueError("Context JSONL header is not valid JSON") from exc
        if (
            not isinstance(header, dict)
            or header.get("type") != "ContextHeader"
            or header.get("schemaVersion") != 1
            or header.get("sourceSha256") != expected_source_sha256
        ):
            raise ValueError("Context header schema or sourceSha256 does not match the pinned PBF")
        for line_number, raw_line in enumerate(source, 2):
            digest.update(raw_line)
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Context JSONL line {line_number} is not valid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Context JSONL line {line_number} is not an object")
            tags = row.get("tags")
            if not isinstance(tags, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in tags.items()
            ):
                raise ValueError(f"Context tags must be source strings on line {line_number}")
            osm_type, osm_id = row.get("osmType"), row.get("osmId")
            if not isinstance(osm_id, str) or not osm_id.isdigit():
                raise ValueError(
                    f"Context OSM ID must be a full digit string on line {line_number}"
                )
            if row.get("type") == "Street":
                if osm_type != "W" or osm_id in street_ids:
                    raise ValueError(
                        f"Street source identity is invalid or duplicated on line {line_number}"
                    )
                coords = row.get("coordinates")
                if (
                    not isinstance(coords, list)
                    or len(coords) < 2
                    or any(not _valid_lon_lat(point) for point in coords)
                ):
                    raise ValueError(f"Street coordinates are malformed on line {line_number}")
                if tags.get("highway") and any(
                    _clean(tags.get(key)) for key in ("name", "name:he", "name:en")
                ):
                    points = tuple((float(point[0]), float(point[1])) for point in coords)
                    streets.append(Street(osm_id, tags, points, _bbox(points)))
                    street_ids.add(osm_id)
            elif row.get("type") == "Locality":
                identity = (osm_type, osm_id)
                if osm_type not in {"W", "R"} or identity in locality_ids:
                    raise ValueError(
                        f"Locality source identity is invalid or duplicated on line {line_number}"
                    )
                locality_ids.add(identity)
                geometry = row.get("geometry")
                if (
                    tags.get("boundary") != "administrative"
                    or tags.get("admin_level") != "8"
                    or not any(_clean(tags.get(key)) for key in ("name", "name:he", "name:en"))
                    or not isinstance(geometry, dict)
                    or geometry.get("type") not in {"Polygon", "MultiPolygon"}
                ):
                    continue
                bounds = _bbox(_positions(geometry.get("coordinates")))
                if bounds is not None:
                    localities.append(Locality(osm_type, osm_id, tags, geometry, bounds))
            else:
                raise ValueError(f"Unknown context row type on line {line_number}")
    return streets, localities, digest.hexdigest()


def _street_name_keys(tags: dict[str, str]) -> set[str]:
    return {
        _label_key(cleaned)
        for key, raw in tags.items()
        if key == "name" or key in {"name:he", "name:en"}
        if (cleaned := _clean(raw)) is not None
    }


def _segment_distance_and_point(
    point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
) -> tuple[float, tuple[float, float]]:
    lon0, lat0 = point
    cosine = max(0.01, math.cos(math.radians(lat0)))
    x_scale, y_scale = 111_320.0 * cosine, 110_574.0
    ax, ay = (start[0] - lon0) * x_scale, (start[1] - lat0) * y_scale
    bx, by = (end[0] - lon0) * x_scale, (end[1] - lat0) * y_scale
    dx, dy = bx - ax, by - ay
    denominator = dx * dx + dy * dy
    fraction = 0.0 if denominator == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / denominator))
    near_lon = start[0] + fraction * (end[0] - start[0])
    near_lat = start[1] + fraction * (end[1] - start[1])
    distance = math.hypot(ax + fraction * dx, ay + fraction * dy)
    return distance, (near_lon, near_lat)


def street_distance_m(
    point: tuple[float, float], coordinates: tuple[tuple[float, float], ...]
) -> tuple[float, tuple[float, float]]:
    if len(coordinates) == 1:
        return _segment_distance_and_point(point, coordinates[0], coordinates[0])
    return min(
        (
            _segment_distance_and_point(point, start, end)
            for start, end in zip(coordinates, coordinates[1:], strict=False)
        ),
        key=lambda row: row[0],
    )


def _resolve_locality(
    point: tuple[float, float], candidates: set[str], by_id: dict[str, Locality]
) -> tuple[Locality | None, str]:
    interior: list[Locality] = []
    boundaries: list[Locality] = []
    for locality_id in candidates:
        locality = by_id[locality_id]
        state = point_in_geometry(point, locality.geometry)
        if state == "inside":
            interior.append(locality)
        elif state == "boundary":
            boundaries.append(locality)
    if len(interior) == 1 and not boundaries:
        return interior[0], "unique_containing_locality"
    if interior or len(boundaries) > 1:
        return None, "ambiguous_multiple_localities"
    if boundaries:
        return None, "point_on_locality_boundary"
    return None, "no_containing_locality"


def _source_name_aliases(tags: dict[str, str], prefix: str) -> dict[str, str]:
    aliases = {}
    for language in ("he", "en"):
        value = _clean(tags.get(f"name:{language}"))
        if value:
            aliases[f"{prefix}:{language}"] = value
    return aliases


def _add_alias(
    address: dict[str, str],
    target_key: str,
    target_value: str,
    original_tags: dict[str, str],
    source_key: str,
    conflicts: list[dict[str, str]],
    added: list[str],
) -> None:
    existing = _clean(address.get(target_key))
    if existing is None:
        existing = _clean(original_tags.get(source_key))
    if existing is not None:
        if _label_key(existing) != _label_key(target_value):
            conflicts.append(
                {
                    "field": target_key,
                    "existingExplicitValue": existing,
                    "sourceValue": target_value,
                    "sourceField": source_key,
                }
            )
        return
    address[target_key] = target_value
    added.append(target_key)


def _locality_additions(
    locality: Locality,
    address: dict[str, str],
    original_tags: dict[str, str],
    conflicts: list[dict[str, str]],
    added: list[str],
) -> None:
    base_name = _clean(locality.tags.get("name"))
    if base_name:
        _add_alias(address, "city", base_name, original_tags, "addr:city", conflicts, added)
    for target_key, source_key in _source_name_aliases(locality.tags, "city").items():
        language = target_key.split(":", 1)[1]
        _add_alias(
            address,
            target_key,
            source_key,
            original_tags,
            f"addr:city:{language}",
            conflicts,
            added,
        )


def _matching_nearby_streets(
    house_point: tuple[float, float],
    house_tags: dict[str, str],
    locality: Locality,
    street_by_id: dict[str, Street],
    street_index: GridIndex,
    names_to_ids: dict[str, set[str]],
) -> tuple[list[Street], str]:
    labels = {
        _label_key(value)
        for key, raw in house_tags.items()
        if key == "addr:street" or key.startswith("addr:street:")
        if (value := _clean(raw)) is not None
    }
    named_ids = (
        set().union(*(names_to_ids.get(label, set()) for label in labels)) if labels else set()
    )
    spatial_ids = street_index.nearby(*house_point, radius_cells=1)
    possible = named_ids & spatial_ids
    matches = []
    for street_id in possible:
        street = street_by_id[street_id]
        distance, nearest = street_distance_m(house_point, street.coordinates)
        if distance > MAX_STREET_ASSOCIATION_METERS:
            continue
        if point_in_geometry(nearest, locality.geometry) != "inside":
            continue
        matches.append(street)
    return matches, "matched" if matches else "no_matching_nearby_source_way"


def _street_midpoint(street: Street) -> tuple[float, float]:
    lengths = []
    for start, end in zip(street.coordinates, street.coordinates[1:], strict=False):
        mean_lat = math.radians((start[1] + end[1]) / 2)
        dx = (end[0] - start[0]) * 111_320.0 * math.cos(mean_lat)
        dy = (end[1] - start[1]) * 110_574.0
        lengths.append(math.hypot(dx, dy))
    total = sum(lengths)
    target = total / 2
    if not lengths or total == 0:
        midpoint = street.coordinates[0]
    else:
        midpoint = street.coordinates[-1]
        walked = 0.0
        for index, length in enumerate(lengths):
            if walked + length >= target:
                fraction = (target - walked) / length if length else 0.0
                start, end = street.coordinates[index], street.coordinates[index + 1]
                midpoint = (
                    start[0] + fraction * (end[0] - start[0]),
                    start[1] + fraction * (end[1] - start[1]),
                )
                break
            walked += length
    return midpoint


def _street_document(street: Street, locality: Locality | None) -> dict[str, Any]:
    names = {
        key: value
        for key in ("name", "name:he", "name:en")
        if (value := _clean(street.tags.get(key))) is not None
    }
    address: dict[str, str] = {}
    if locality is not None:
        city = _clean(locality.tags.get("name"))
        if city:
            address["city"] = city
        address.update(_source_name_aliases(locality.tags, "city"))
    midpoint = _street_midpoint(street)
    place = {
        "place_id": f"W{street.osm_id}",
        "object_type": "W",
        "object_id": int(street.osm_id),
        "osm_key": "highway",
        "osm_value": street.tags["highway"],
        "address_type": "street",
        "name": names,
        "extra": dict(street.tags),
        "centroid": [midpoint[0], midpoint[1]],
    }
    if address:
        place["address"] = address
    return {"type": "Place", "content": [place]}


def _house_record(
    item: dict[str, Any],
    street_by_id: dict[str, Street],
    locality_by_id: dict[str, Locality],
    locality_index: GridIndex,
    street_index: GridIndex,
    names_to_ids: dict[str, set[str]],
) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
    original = copy.deepcopy(item)
    target = original["content"][0]
    tags = target.get("extra")
    address = target.get("address")
    centroid = target.get("centroid")
    if (
        not isinstance(tags, dict)
        or not isinstance(address, dict)
        or not _valid_lon_lat(centroid)
        or target.get("object_type") != "N"
        or target.get("address_type") != "house"
    ):
        raise ValueError("Input house record does not match the frozen Photon house schema")
    house_id = str(target.get("object_id"))
    point = (float(centroid[0]), float(centroid[1]))
    locality_candidates = locality_index.nearby(*point)
    locality, locality_status = _resolve_locality(point, locality_candidates, locality_by_id)
    conflicts: list[dict[str, str]] = []
    added: list[str] = []
    street_ids: list[str] = []
    if locality is not None:
        _locality_additions(locality, address, tags, conflicts, added)
        street_candidates, street_status = _matching_nearby_streets(
            point,
            tags,
            locality,
            street_by_id,
            street_index,
            names_to_ids,
        )
        street_ids = sorted({street.osm_id for street in street_candidates}, key=int)
        source_aliases: dict[str, set[str]] = {"street:he": set(), "street:en": set()}
        for street in street_candidates:
            for language in ("he", "en"):
                value = _clean(street.tags.get(f"name:{language}"))
                if value:
                    source_aliases[f"street:{language}"].add(value)
        for field, values in source_aliases.items():
            if len({_label_key(value) for value in values}) == 1 and values:
                value = sorted(values, key=lambda entry: (entry.casefold(), entry))[0]
                language = field.split(":", 1)[1]
                _add_alias(
                    address,
                    field,
                    value,
                    tags,
                    f"addr:street:{language}",
                    conflicts,
                    added,
                )
            elif len(values) > 1:
                conflicts.append(
                    {
                        "field": field,
                        "existingExplicitValue": "",
                        "sourceValue": " | ".join(sorted(values)),
                        "sourceField": "multiple nearby matching highway ways",
                    }
                )
        street_status = (
            street_status
            if street_status != "matched"
            else (
                "matched_with_aliases"
                if source_aliases["street:he"] or source_aliases["street:en"]
                else "matched_no_translation"
            )
        )
    else:
        street_status = "not_attempted_without_unique_locality"

    linkage = None
    if locality is not None or street_ids or conflicts or added:
        linkage = {
            "sourceHouseNodeId": house_id,
            "localitySourceIds": (
                [{"osmType": locality.osm_type, "osmId": locality.osm_id}] if locality else []
            ),
            "streetWayIds": street_ids,
            "addedAddressAliases": sorted(set(added)),
            "conflicts": conflicts,
            "localityStatus": locality_status,
            "streetStatus": street_status,
        }
    return original, linkage, locality_status


def transform_dump(
    houses_path: Path,
    context_path: Path,
    output_path: Path,
    provenance_path: Path,
    *,
    expected_source_sha256: str = EXPECTED_SOURCE_SHA256,
    expected_house_dump_sha256: str | None = EXPECTED_HOUSE_DUMP_SHA256,
    expected_house_count: int | None = EXPECTED_HOUSE_COUNT,
) -> dict[str, Any]:
    output_path = output_path.resolve()
    provenance_path = provenance_path.resolve()
    houses_path, context_path = houses_path.resolve(), context_path.resolve()
    if output_path in {houses_path, context_path} or provenance_path in {
        houses_path,
        context_path,
        output_path,
    }:
        raise ValueError("Input and output paths must be distinct")
    if output_path.exists() or provenance_path.exists():
        raise FileExistsError("Refusing to overwrite Photon dump or provenance")
    houses_hash = sha256_file(houses_path)
    if expected_house_dump_sha256 and houses_hash != expected_house_dump_sha256:
        raise ValueError("Preserved house dump SHA-256 does not match the pinned export")
    streets, localities, context_hash = _parse_context(context_path, expected_source_sha256)
    house_header = None
    locality_index, street_index = GridIndex(), GridIndex()
    locality_by_id = {f"{locality.osm_type}{locality.osm_id}": locality for locality in localities}
    street_by_id = {street.osm_id: street for street in streets}
    names_to_ids: dict[str, set[str]] = defaultdict(set)
    for locality in localities:
        locality_index.add(f"{locality.osm_type}{locality.osm_id}", locality.bbox)
    for street in streets:
        street_index.add(street.osm_id, street.bbox)
        for label in _street_name_keys(street.tags):
            names_to_ids[label].add(street.osm_id)

    counts: Counter[str] = Counter()
    ambiguity_counts: Counter[str] = Counter()
    contributions: list[dict[str, Any]] = []
    ambiguity_examples: list[dict[str, str]] = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            with houses_path.open("r", encoding="utf-8") as source:
                for line_number, line in enumerate(source, 1):
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"House dump line {line_number} is invalid JSON") from exc
                    if line_number == 1:
                        if (
                            not isinstance(item, dict)
                            or item.get("type") != "NominatimDumpFile"
                            or item.get("content", {}).get("version") != PHOTON_DUMP_VERSION
                            or expected_source_sha256
                            not in str(item.get("content", {}).get("database_version", ""))
                        ):
                            raise ValueError(
                                "House dump header is not the expected pinned Photon export"
                            )
                        house_header = copy.deepcopy(item)
                        content = house_header["content"]
                        content["generator"] = "OpenTransit source-context enrichment"
                        content["database_version"] = (
                            f"source OSM PBF SHA-256 {expected_source_sha256}; "
                            f"house dump SHA-256 {houses_hash}; "
                            f"context JSONL SHA-256 {context_hash}"
                        )
                        content["features"] = {
                            "sorted_by_country": False,
                            "has_addresslines": False,
                        }
                        output.write(
                            json.dumps(house_header, ensure_ascii=False, separators=(",", ":"))
                            + "\n"
                        )
                        continue
                    if not isinstance(item, dict) or item.get("type") != "Place":
                        raise ValueError(f"Unexpected Photon dump row on line {line_number}")
                    content = item.get("content")
                    if not isinstance(content, list) or len(content) != 1:
                        raise ValueError(f"Input Place content is malformed on line {line_number}")
                    place = content[0]
                    if place.get("osm_key") != "addr:housenumber":
                        raise ValueError("Input dump contains a non-house document")
                    original_identity = (
                        place.get("place_id"),
                        place.get("object_type"),
                        place.get("object_id"),
                        place.get("centroid"),
                        place.get("housenumber"),
                        place.get("extra"),
                    )
                    enriched, linkage, locality_status = _house_record(
                        item,
                        street_by_id,
                        locality_by_id,
                        locality_index,
                        street_index,
                        names_to_ids,
                    )
                    enriched_place = enriched["content"][0]
                    if original_identity != (
                        enriched_place.get("place_id"),
                        enriched_place.get("object_type"),
                        enriched_place.get("object_id"),
                        enriched_place.get("centroid"),
                        enriched_place.get("housenumber"),
                        enriched_place.get("extra"),
                    ):
                        raise AssertionError(
                            "House identity, coordinates, number or source tags changed"
                        )
                    counts["houseRecords"] += 1
                    counts[f"locality:{locality_status}"] += 1
                    if linkage:
                        counts["housesWithSourceContext"] += 1
                        counts["addedAliases"] += len(linkage["addedAddressAliases"])
                        counts["conflictingAliases"] += len(linkage["conflicts"])
                        counts["housesWithStreetWay"] += bool(linkage["streetWayIds"])
                        if (
                            linkage["conflicts"]
                            or locality_status.startswith("ambiguous")
                            or locality_status.endswith("boundary")
                        ):
                            ambiguity_counts[
                                locality_status
                                if not linkage["conflicts"]
                                else "explicit_or_source_name_conflict"
                            ] += 1
                            if len(ambiguity_examples) < 200:
                                ambiguity_examples.append(
                                    {
                                        "sourceHouseNodeId": str(place["object_id"]),
                                        "localityStatus": locality_status,
                                    }
                                )
                        contributions.append(linkage)
                    output.write(
                        json.dumps(enriched, ensure_ascii=False, separators=(",", ":")) + "\n"
                    )

            if house_header is None:
                raise ValueError("House dump is empty")
            if expected_house_count is not None and counts["houseRecords"] != expected_house_count:
                raise ValueError(
                    f"Expected {expected_house_count} frozen house records, "
                    f"found {counts['houseRecords']}"
                )
            street_document_ids = []
            street_locality_contributions = []
            for street in streets:
                midpoint = _street_midpoint(street)
                candidates = locality_index.nearby(*midpoint)
                locality, locality_status = _resolve_locality(midpoint, candidates, locality_by_id)
                document = _street_document(street, locality)
                output.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")
                street_document_ids.append(street.osm_id)
                if locality is not None:
                    street_locality_contributions.append(
                        {
                            "streetWayId": street.osm_id,
                            "localitySourceId": {
                                "osmType": locality.osm_type,
                                "osmId": locality.osm_id,
                            },
                        }
                    )
                elif locality_status != "no_containing_locality":
                    ambiguity_counts[f"street_document:{locality_status}"] += 1
            counts["sourceStreetWays"] = len(streets)
            counts["streetDocumentsAdded"] = len(street_document_ids)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        raise

    result = {
        "schemaVersion": 1,
        "createdAtUtc": datetime.now(UTC).isoformat(),
        "scope": "Source-backed Photon house aliases and named highway street documents only.",
        "sourceHashes": {
            "sourcePbfSha256": expected_source_sha256,
            "houseDumpSha256": houses_hash,
            "contextJsonlSha256": context_hash,
            "enricherSha256": sha256_file(Path(__file__).resolve()),
        },
        "outputs": {
            "photonDumpPath": str(output_path),
            "photonDumpSha256": sha256_file(output_path),
            "provenancePath": str(provenance_path),
        },
        "counts": dict(sorted(counts.items())),
        "ambiguityCounts": dict(sorted(ambiguity_counts.items())),
        "ambiguityExamples": ambiguity_examples,
        "contributingStreetWayIds": sorted(
            {way_id for row in contributions for way_id in row["streetWayIds"]}, key=int
        ),
        "contributingLocalityIds": [
            {"osmType": osm_type, "osmId": osm_id}
            for osm_type, osm_id in sorted(
                {
                    (record["osmType"], record["osmId"])
                    for row in contributions
                    for record in row["localitySourceIds"]
                },
                key=lambda identity: (identity[0], int(identity[1])),
            )
        ],
        "sourceContributions": contributions,
        "streetDocumentSourceWayIds": street_document_ids,
        "streetDocumentLocalityContributions": street_locality_contributions,
        "method": {
            "gridCellDegrees": CELL_DEGREES,
            "streetAssociationMaximumMeters": MAX_STREET_ASSOCIATION_METERS,
            "localityContainment": (
                "Strict Polygon/MultiPolygon containment; holes excluded; boundaries unresolved."
            ),
            "streetMatch": (
                "Exact whitespace-normalized raw addr:street label matched to highway name tags, "
                "within source locality and distance bound."
            ),
            "translationPolicy": (
                "Copy only explicit unique source name:he/name:en values; "
                "conflicts remain unresolved."
            ),
            "corpusUse": False,
            "targetCorpusRead": False,
            "expectedCorpusCoordinatesUsed": False,
            "countryCodeAdded": False,
            "houseIdentityCoordinatesNumbersAndOriginalTagsChanged": False,
            "streetDocumentPrecision": "street",
            "streetDocumentHasHouseNumber": False,
        },
    }
    sidecar_fd = os.open(provenance_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(sidecar_fd, "w", encoding="utf-8", newline="\n") as sidecar:
        json.dump(result, sidecar, ensure_ascii=False, indent=2)
        sidecar.write("\n")
    return result


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--house-dump",
        type=Path,
        default=root / ".runtime/m4-photon-spike-20260930/israel-address-nodes-photon-0.1.0.jsonl",
    )
    parser.add_argument(
        "--context-jsonl",
        type=Path,
        default=root / ".runtime/m4-photon-context-20261001/context-v1.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root
        / ".runtime/m4-photon-enrichment-20261001/israel-addresses-enriched-photon-0.1.0.jsonl",
    )
    parser.add_argument("--provenance-output", type=Path)
    parser.add_argument("--allow-house-dump-sha256", action="store_true")
    args = parser.parse_args()
    provenance_path = args.provenance_output or args.output.with_suffix(".provenance.json")
    if args.allow_house_dump_sha256:
        print("--allow-house-dump-sha256 is reserved for focused synthetic tests", file=sys.stderr)
        return 2
    try:
        result = transform_dump(
            args.house_dump,
            args.context_jsonl,
            args.output,
            provenance_path,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Photon enrichment failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "output": result["outputs"]["photonDumpPath"],
                "outputSha256": result["outputs"]["photonDumpSha256"],
                "counts": result["counts"],
                "provenance": result["outputs"]["provenancePath"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
