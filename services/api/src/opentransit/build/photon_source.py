"""Read a pinned OSM PBF into the Photon house dump and the street/locality context file.

These are the two osmium (pyosmium) scans that feed ``tools/enrich_photon_addresses.py``.
They were first written as one-off scripts for the preserved September 4 extract; here the PBF
hash is computed from the file actually supplied (the snapshot's recorded input), not pinned to
one extract. ``osmium`` is not a locked dependency: it is imported lazily, optionally from a
directory such as ``.runtime/osm-reader-20260930`` supplied by the operator.

``extract_context`` is the tracked form of the M4 context extractor
(``extract_photon_context.py``, SHA-256 ``EXTRACTOR_SCRIPT_SHA256``): the same Street and
administrative level 8 Locality selection and records, written with the same ContextHeader, so
one scan serves both the reference localities (``opentransit.localities``) and the Photon
enrichment. Beside the JSONL it exclusive-creates ``extraction-manifest.json``, which
``load_locality_context`` checks and copies reader identity from.
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
EXTRACTOR_SCRIPT_SHA256 = "aa1fd2e15c819442a5703cacb88432484283be2f3b969feb5f8d2018e2347de5"
EXTRACTION_MANIFEST_NAME = "extraction-manifest.json"
GEOMETRY_SOURCE = "pyosmium locations and AreaManager; no bounding-box approximation"
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


def house_record(
    object_type: str, object_id: int, lon: float, lat: float, tags: dict[str, str]
) -> dict:
    """One Photon 0.1.0 house place preserving the OSM identity, coordinates and addr:* tags.

    ``object_type`` is ``N`` for an address node (its own coordinates) or ``W`` for a
    building outline (the centre of its outline).
    """
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
        "place_id": f"{object_type}{object_id}",
        "object_type": object_type,
        "object_id": int(object_id),
        "osm_key": "addr:housenumber",
        "osm_value": house_number,
        "address_type": "house",
        "housenumber": house_number,
        "address": address,
        "extra": {key: value for key, value in tags.items() if key.startswith("addr:")},
        "centroid": [lon, lat],
    }
    return {"type": "Place", "content": [place]}


def _outline_centre(way: Any) -> tuple[float, float] | None:
    """Mean of a way's distinct nodes (a closed outline repeats its first node at the end).

    For a building this is within a few metres of any other centre definition, which is
    all a routing origin or destination needs. ``None`` when a node has no coordinates.
    """
    points: list[tuple[float, float]] = []
    try:
        for node in way.nodes:
            location = node.location
            if not location.valid():
                return None
            points.append((float(location.lon), float(location.lat)))
    except AttributeError, RuntimeError, ValueError, TypeError:
        return None
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if not points:
        return None
    return (
        round(sum(point[0] for point in points) / len(points), 7),
        round(sum(point[1] for point in points) / len(points), 7),
    )


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
    """Exclusive-create a Photon house dump of every addr:housenumber + addr:street object.

    Address nodes are written at their own coordinates. Ways (mappers often put the address
    on the building outline instead of a node) are written at the centre of their outline.
    A way that is also a named highway is left out: the context scan writes it as a street
    document under the same way identity. Relations and interpolation ways are not exported.
    """
    osmium = osmium or load_osmium(reader_path)
    pbf = Path(pbf_path).resolve(strict=True)
    pbf_sha256 = sha256_file(pbf)
    started = datetime.now(UTC).isoformat()
    counts: Counter[str] = Counter()
    skipped: Counter[str] = Counter()

    class Exporter(osmium.SimpleHandler):
        def __init__(self, target) -> None:
            super().__init__()
            self.target = target

        def _write(self, record: dict, kind: str) -> None:
            self.target.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            self.target.write("\n")
            counts["houseRecords"] += 1
            counts[kind] += 1

        def node(self, node) -> None:
            tags = {tag.k: tag.v for tag in node.tags}
            if not _clean(tags.get("addr:housenumber")) or not _clean(tags.get("addr:street")):
                return
            if not node.location.valid():
                return
            record = house_record("N", node.id, node.location.lon, node.location.lat, tags)
            self._write(record, "houseNodeRecords")

        def way(self, way) -> None:
            tags = {tag.k: tag.v for tag in way.tags}
            if not _clean(tags.get("addr:housenumber")) or not _clean(tags.get("addr:street")):
                return
            if tags.get("highway", "").strip() and _has_name(tags):
                skipped["namedHighway"] += 1
                return
            centre = _outline_centre(way)
            if centre is None:
                skipped["unlocatedNode"] += 1
                return
            self._write(house_record("W", way.id, centre[0], centre[1], tags), "houseWayRecords")

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
        # Way nodes carry coordinates only when the reader resolves them through a node index.
        Exporter(target).apply_file(str(pbf), locations=True, idx="flex_mem")
        target.flush()
        os.fsync(target.fileno())
    if counts["houseRecords"] <= 0:
        raise RuntimeError("PBF contains no eligible address objects; preserved empty dump")
    return {
        "output": str(output),
        "outputSha256": sha256_file(output),
        "outputBytes": output.stat().st_size,
        "sourcePbfSha256": pbf_sha256,
        "houseRecords": counts["houseRecords"],
        "houseNodeRecords": counts["houseNodeRecords"],
        "houseWayRecords": counts["houseWayRecords"],
        "waysSkipped": dict(sorted(skipped.items())),
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
    """Exclusive-create the named-highway and admin-level-8 locality context JSONL.

    Also exclusive-creates ``extraction-manifest.json`` beside it (source and output hashes,
    reader identity, counts, extractor identity), the sidecar ``load_locality_context`` verifies.
    """
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

    manifest_path = Path(output_path).resolve().with_name(EXTRACTION_MANIFEST_NAME)
    if manifest_path.exists():
        raise FileExistsError(f"Refusing to overwrite {manifest_path}")
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
    result = {
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
    manifest = {
        "schemaVersion": CONTEXT_SCHEMA_VERSION,
        "status": "extraction_complete",
        "source": {"path": str(pbf), "sha256": pbf_sha256, "bytes": pbf.stat().st_size},
        "output": {
            "path": str(output),
            "format": "UTF-8 JSONL; one ContextHeader followed by source Street/Locality records",
            "sha256": result["outputSha256"],
            "bytes": result["outputBytes"],
        },
        "reader": {
            "library": "pyosmium",
            "version": reader_version,
            "internalPbfPasses": 2,
            "index": "flex_mem",
            "geometrySource": GEOMETRY_SOURCE,
        },
        "extractor": {
            "module": "opentransit.build.photon_source.extract_context",
            "moduleSha256": sha256_file(Path(__file__)),
            "portedFromScriptSha256": EXTRACTOR_SCRIPT_SHA256,
        },
        "counts": result["counts"],
        "elapsedSeconds": result["elapsedSeconds"],
        "startedAtUtc": started,
        "finishedAtUtc": result["finishedAtUtc"],
    }
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    result["manifest"] = str(manifest_path)
    result["manifestSha256"] = sha256_file(manifest_path)
    return result
