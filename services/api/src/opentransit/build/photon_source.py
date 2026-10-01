"""Read a pinned OSM PBF into the Photon house dump and the street/locality context file.

These are the two osmium (pyosmium) scans that feed ``tools/enrich_photon_addresses.py``.
They were first written as one-off scripts for the preserved September 4 extract; here the PBF
hash is computed from the file actually supplied (the snapshot's recorded input), not pinned to
one extract. ``osmium`` is not a locked dependency: it is imported lazily, optionally from a
directory such as ``.runtime/osm-reader-20260930`` supplied by the operator.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CONTEXT_SCHEMA_VERSION = 1
_NAME_KEYS = {"alt_name", "short_name", "official_name", "loc_name", "old_name"}


def load_osmium(reader_path: Path | None = None) -> Any:
    """Import pyosmium, optionally from an operator-supplied directory (not a dependency)."""
    if reader_path is not None:
        location = str(Path(reader_path).resolve())
        if location not in sys.path:
            sys.path.insert(0, location)
    try:
        return importlib.import_module("osmium")
    except ImportError as exc:
        raise RuntimeError(
            "pyosmium is required for address preparation; install it or pass --osm-reader-path "
            "pointing at a directory containing the 'osmium' package"
        ) from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.split()) or None


def house_record(node_id: int, lon: float, lat: float, tags: dict[str, str]) -> dict:
    """One Photon 0.1.0 house place preserving the node ID, coordinates and addr:* tags."""
    address: dict[str, str] = {}
    for source_key, dump_key in (("addr:street", "street"), ("addr:city", "city")):
        value = tags.get(source_key)
        if value:
            address[dump_key] = value
        for language in ("he", "en"):
            localized = tags.get(f"{source_key}:{language}")
            if localized:
                address[f"{dump_key}:{language}"] = localized
    house_number = tags["addr:housenumber"]
    place = {
        "place_id": f"N{node_id}",
        "object_type": "N",
        "object_id": int(node_id),
        "osm_key": "addr:housenumber",
        "osm_value": house_number,
        "address_type": "house",
        "housenumber": house_number,
        "address": address,
        "extra": {key: value for key, value in tags.items() if key.startswith("addr:")},
        "centroid": [lon, lat],
    }
    return {"type": "Place", "content": [place]}


def _new_output(path: Path):
    path = Path(path).resolve()
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    return path, os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")


def export_house_dump(
    pbf_path: Path, output_path: Path, *, reader_path: Path | None = None, osmium: Any = None
) -> dict:
    """Exclusive-create a Photon house dump of every node with addr:housenumber and addr:street."""
    osmium = osmium or load_osmium(reader_path)
    pbf = Path(pbf_path).resolve(strict=True)
    pbf_sha256 = sha256_file(pbf)
    started = datetime.now(UTC).isoformat()
    counts: Counter[str] = Counter()

    class Exporter(osmium.SimpleHandler):
        def __init__(self, target) -> None:
            super().__init__()
            self.target = target

        def node(self, node) -> None:
            tags = {tag.k: tag.v for tag in node.tags}
            if not _clean(tags.get("addr:housenumber")) or not _clean(tags.get("addr:street")):
                return
            if not node.location.valid():
                return
            record = house_record(node.id, node.location.lon, node.location.lat, tags)
            self.target.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            self.target.write("\n")
            counts["houseRecords"] += 1

    output, target = _new_output(output_path)
    with target:
        header = {
            "type": "NominatimDumpFile",
            "content": {
                "version": "0.1.0",
                "generator": "OpenTransit Photon house export",
                "database_version": "source OpenStreetMap PBF SHA-256 " + pbf_sha256,
                "features": {"sorted_by_country": False, "has_addresslines": False},
            },
        }
        target.write(json.dumps(header, ensure_ascii=False, separators=(",", ":")) + "\n")
        Exporter(target).apply_file(str(pbf), locations=False)
        target.flush()
        os.fsync(target.fileno())
    if counts["houseRecords"] <= 0:
        raise RuntimeError("PBF contains no eligible address nodes; preserved empty dump")
    return {
        "output": str(output),
        "outputSha256": sha256_file(output),
        "outputBytes": output.stat().st_size,
        "sourcePbfSha256": pbf_sha256,
        "houseRecords": counts["houseRecords"],
        "startedAtUtc": started,
        "finishedAtUtc": datetime.now(UTC).isoformat(),
    }


def _tags(obj: Any) -> dict[str, str]:
    return {str(tag.k): str(tag.v) for tag in obj.tags}


def _has_name(tags: dict[str, str]) -> bool:
    return any(
        value.strip()
        and (
            key == "name"
            or key.startswith("name:")
            or key in _NAME_KEYS
            or key.startswith("alt_name:")
            or key.startswith("short_name:")
        )
        for key, value in tags.items()
    )


def street_record(way: Any) -> tuple[dict[str, Any] | None, str | None]:
    tags = _tags(way)
    if not tags.get("highway", "").strip() or not _has_name(tags):
        return None, None
    coordinates: list[list[float]] = []
    try:
        for node in way.nodes:
            location = node.location
            if not location.valid():
                return None, "invalid_or_missing_way_node_location"
            lon, lat = float(location.lon), float(location.lat)
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                return None, "invalid_or_missing_way_node_location"
            coordinates.append([lon, lat])
    except AttributeError, RuntimeError, ValueError, TypeError:
        return None, "invalid_or_missing_way_node_location"
    if len(coordinates) < 2 or len({(point[0], point[1]) for point in coordinates}) < 2:
        return None, "insufficient_line_geometry"
    return {
        "type": "Street",
        "osmType": "W",
        "osmId": str(int(way.id)),
        "tags": tags,
        "coordinates": coordinates,
    }, None


def locality_record(area: Any, geojson_factory: Any) -> tuple[dict[str, Any] | None, str | None]:
    tags = _tags(area)
    if (
        tags.get("boundary") != "administrative"
        or tags.get("admin_level") != "8"
        or not _has_name(tags)
    ):
        return None, None
    try:
        geometry = json.loads(geojson_factory.create_multipolygon(area))
    except ValueError, RuntimeError, TypeError:
        return None, "invalid_or_unavailable_area_geometry"
    if not isinstance(geometry, dict) or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
        return None, "unsupported_area_geometry_type"
    if not isinstance(geometry.get("coordinates"), list) or not geometry["coordinates"]:
        return None, "empty_area_geometry"
    return {
        "type": "Locality",
        "osmType": "W" if area.from_way() else "R",
        "osmId": str(int(area.orig_id())),
        "tags": tags,
        "geometry": geometry,
    }, None


def _line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"


def extract_context(
    pbf_path: Path, output_path: Path, *, reader_path: Path | None = None, osmium: Any = None
) -> dict:
    """Exclusive-create the named-highway and admin-level-8 locality context JSONL."""
    osmium = osmium or load_osmium(reader_path)
    pbf = Path(pbf_path).resolve(strict=True)
    pbf_sha256 = sha256_file(pbf)
    started = datetime.now(UTC).isoformat()
    clock = time.perf_counter()
    counts: Counter[str] = Counter()

    class Extractor(osmium.SimpleHandler):
        def __init__(self, target) -> None:
            super().__init__()
            self.target = target
            self.geojson_factory = osmium.geom.GeoJSONFactory()

        def node(self, _node: Any) -> None:
            counts["sourceNodesSeen"] += 1

        def relation(self, _relation: Any) -> None:
            counts["sourceRelationsSeen"] += 1

        def way(self, way: Any) -> None:
            counts["sourceWaysSeen"] += 1
            record, omission = street_record(way)
            if omission:
                counts["omittedStreet:" + omission] += 1
            if record is not None:
                self.target.write(_line(record))
                counts["streetRecordsWritten"] += 1

        def area(self, area: Any) -> None:
            counts["areasProducedByOsmium"] += 1
            record, omission = locality_record(area, self.geojson_factory)
            if omission:
                counts["omittedLocality:" + omission] += 1
            if record is not None:
                self.target.write(_line(record))
                counts["localityRecordsWritten"] += 1

    output, target = _new_output(output_path)
    with target:
        target.write(
            _line(
                {
                    "type": "ContextHeader",
                    "sourceSha256": pbf_sha256,
                    "schemaVersion": CONTEXT_SCHEMA_VERSION,
                }
            )
        )
        # The area callback enables pyosmium's area assembly: a relation first pass, then a
        # location-aware second pass; geometry is source-derived, never a bounding box.
        Extractor(target).apply_file(str(pbf), locations=True, idx="flex_mem")
        target.flush()
        os.fsync(target.fileno())
    try:
        reader_version = importlib.metadata.version("osmium")
    except importlib.metadata.PackageNotFoundError:
        reader_version = None
    return {
        "output": str(output),
        "outputSha256": sha256_file(output),
        "outputBytes": output.stat().st_size,
        "sourcePbfSha256": pbf_sha256,
        "counts": dict(sorted(counts.items())),
        "reader": {"library": "pyosmium", "version": reader_version, "index": "flex_mem"},
        "elapsedSeconds": round(time.perf_counter() - clock, 2),
        "startedAtUtc": started,
        "finishedAtUtc": datetime.now(UTC).isoformat(),
    }
