"""Build a bounded lookup index from one preserved, enriched Photon JSONL dump."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from opentransit.address_catalog import CATALOG_SCHEMA_VERSION

_SOURCE_PBF = re.compile(r"source OSM PBF SHA-256 ([0-9a-f]{64})(?:;|$)")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_identity(place: dict[str, Any]) -> tuple[str, str]:
    osm_type = place.get("object_type")
    osm_id = place.get("object_id")
    address_type = place.get("address_type")
    if osm_type not in {"N", "W"} or isinstance(osm_id, bool):
        raise ValueError("Photon place has an unsupported OSM source identity")
    if not isinstance(osm_id, (int, str)) or not str(osm_id).isdigit():
        raise ValueError("Photon place has an invalid full OSM ID")
    osm_id_text = str(osm_id)
    if address_type == "house":
        house_number = place.get("housenumber")
        if osm_type != "N" or not isinstance(house_number, str) or not house_number.strip():
            raise ValueError("Photon house record lacks node identity or house number")
    elif address_type == "street":
        if osm_type != "W" or place.get("housenumber") is not None:
            raise ValueError("Photon street record has invalid way identity or house number")
    else:
        raise ValueError("Photon address catalog accepts only house and street documents")
    centroid = place.get("centroid")
    if (
        not isinstance(centroid, list)
        or len(centroid) != 2
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in centroid
        )
        or not 34 <= centroid[0] <= 36
        or not 29 <= centroid[1] <= 34
    ):
        raise ValueError("Photon source document has invalid coordinates")
    names = place.get("name")
    if names is not None and not isinstance(names, dict):
        raise ValueError("Photon source document has invalid names")
    if address_type == "street" and (
        not isinstance(names, dict)
        or not any(isinstance(value, str) and value.strip() for value in names.values())
    ):
        raise ValueError("Photon street source document lacks source-backed names")
    if not isinstance(place.get("extra"), dict):
        raise ValueError("Photon source document lacks preserved tags")
    if not isinstance(place.get("address", {}), dict):
        raise ValueError("Photon source document has invalid address fields")
    return osm_type, osm_id_text


def build_address_catalog(source_dump: Path, output_path: Path) -> dict[str, Any]:
    """Exclusive-create SQLite rows keyed by full source OSM type and ID."""
    source_dump, output_path = Path(source_dump).resolve(), Path(output_path).resolve()
    if source_dump == output_path or output_path.exists():
        raise FileExistsError("Address catalog output must be a new, distinct path")
    dump_sha256 = _sha256(source_dump)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    count = 0
    pbf_sha256 = None
    seen: set[tuple[str, str]] = set()
    try:
        with os.fdopen(descriptor, "wb"):
            pass
        with sqlite3.connect(output_path) as connection:
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA user_version = 1")
            connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute(
                "CREATE TABLE places ("
                "osm_type TEXT NOT NULL, osm_id TEXT NOT NULL, payload_json TEXT NOT NULL, "
                "PRIMARY KEY (osm_type, osm_id)) WITHOUT ROWID"
            )
            with source_dump.open("r", encoding="utf-8") as source:
                header_line = source.readline()
                try:
                    header = json.loads(header_line)
                except json.JSONDecodeError as exc:
                    raise ValueError("Enriched Photon dump header is invalid") from exc
                content = header.get("content") if isinstance(header, dict) else None
                database_version = (
                    content.get("database_version") if isinstance(content, dict) else None
                )
                generator = content.get("generator") if isinstance(content, dict) else None
                if (
                    not isinstance(content, dict)
                    or header.get("type") != "NominatimDumpFile"
                    or content.get("version") != "0.1.0"
                    or not isinstance(generator, str)
                    or "source-context enrichment" not in generator
                    or not isinstance(database_version, str)
                ):
                    raise ValueError(
                        "Input must be a preserved source-context enriched Photon dump"
                    )
                source_pbf = _SOURCE_PBF.search(database_version)
                if source_pbf is None:
                    raise ValueError("Enriched Photon dump does not pin its PBF hash")
                pbf_sha256 = source_pbf.group(1)
                for line_number, line in enumerate(source, 2):
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Enriched Photon row {line_number} is invalid JSON"
                        ) from exc
                    if not isinstance(row, dict) or row.get("type") != "Place":
                        raise ValueError(f"Enriched Photon row {line_number} is not a Place")
                    content_rows = row.get("content")
                    if not isinstance(content_rows, list) or len(content_rows) != 1:
                        raise ValueError(f"Enriched Photon row {line_number} content is malformed")
                    place = content_rows[0]
                    if not isinstance(place, dict):
                        raise ValueError(f"Enriched Photon row {line_number} place is malformed")
                    identity = _source_identity(place)
                    if identity in seen:
                        raise ValueError(
                            "Enriched Photon dump contains duplicate source identities"
                        )
                    seen.add(identity)
                    payload = json.dumps(
                        place, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    )
                    connection.execute(
                        "INSERT INTO places (osm_type, osm_id, payload_json) VALUES (?, ?, ?)",
                        (*identity, payload),
                    )
                    count += 1
            metadata = {
                "schema_version": str(CATALOG_SCHEMA_VERSION),
                "source_dump_sha256": dump_sha256,
                "source_pbf_sha256": pbf_sha256,
                "record_count": str(count),
            }
            connection.executemany(
                "INSERT INTO metadata (key, value) VALUES (?, ?)", metadata.items()
            )
            connection.commit()
    except BaseException:
        # Keep the exclusive-created path as evidence of a failed build; never overwrite it.
        raise
    return {
        **metadata,
        "source_dump_path": str(source_dump),
        "catalog_path": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dump", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_address_catalog(args.source_dump, args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
