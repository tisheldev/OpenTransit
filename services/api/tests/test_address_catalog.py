import hashlib
import json
import sqlite3

import pytest

from opentransit.address_catalog import AddressCatalog
from opentransit.build.address_catalog import build_address_catalog

PBF_SHA = "a" * 64


def _place(osm_type, osm_id, address_type, *, housenumber=None):
    place = {
        "place_id": f"{osm_type}{osm_id}",
        "object_type": osm_type,
        "object_id": int(osm_id),
        "osm_key": "addr:housenumber" if address_type == "house" else "highway",
        "osm_value": housenumber or "residential",
        "address_type": address_type,
        "name": {"name": "Example", "name:en": "Example English"},
        "extra": {"addr:housenumber": housenumber} if housenumber else {"highway": "residential"},
        "address": {"street": "Example Street", "city": "Example Town"},
        "centroid": [34.78, 32.08],
    }
    if housenumber:
        place["housenumber"] = housenumber
    return {"type": "Place", "content": [place]}


def _source_dump(path, rows=None):
    header = {
        "type": "NominatimDumpFile",
        "content": {
            "version": "0.1.0",
            "generator": "OpenTransit source-context enrichment",
            "database_version": f"source OSM PBF SHA-256 {PBF_SHA}; context hash pinned",
        },
    }
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in [
                header,
                *(
                    rows
                    or [_place("N", "300", "house", housenumber="24"), _place("W", "300", "street")]
                ),
            ]
        ),
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_catalog_pins_dump_and_preserves_full_composite_osm_identity(tmp_path):
    source = tmp_path / "enriched.jsonl"
    output = tmp_path / "catalog.sqlite"
    unnamed_house = _place("N", "300", "house", housenumber="24")
    del unnamed_house["content"][0]["name"]
    source_sha = _source_dump(source, rows=[unnamed_house, _place("W", "300", "street")])
    metadata = build_address_catalog(source, output)
    assert metadata["source_dump_sha256"] == source_sha
    with AddressCatalog(output, source_sha) as catalog:
        # Node N300 and way W300 are distinct despite sharing their numeric OSM ID.
        assert catalog.lookup("N", "300")["address_type"] == "house"
        assert catalog.lookup("W", "300")["address_type"] == "street"
        assert catalog.lookup("N", "0300") is None
        assert catalog.source_pbf_sha256 == PBF_SHA
        assert catalog.record_count == 2
        with pytest.raises(TypeError):
            catalog.metadata["source_dump_sha256"] = "b" * 64


def test_catalog_rejects_dump_hash_mismatch_and_is_read_only(tmp_path):
    source = tmp_path / "enriched.jsonl"
    output = tmp_path / "catalog.sqlite"
    source_sha = _source_dump(source)
    build_address_catalog(source, output)
    with pytest.raises(ValueError, match="metadata"):
        AddressCatalog(output, "b" * 64)
    catalog = AddressCatalog(output, source_sha)
    try:
        with pytest.raises(sqlite3.OperationalError):
            catalog._connection.execute("DELETE FROM places")
    finally:
        catalog.close()


def test_catalog_builder_rejects_duplicate_identity_and_existing_output(tmp_path):
    source = tmp_path / "enriched.jsonl"
    output = tmp_path / "catalog.sqlite"
    _source_dump(source, rows=[_place("N", "300", "house", housenumber="24")] * 2)
    with pytest.raises(ValueError, match="duplicate"):
        build_address_catalog(source, output)
    with pytest.raises(FileExistsError):
        build_address_catalog(source, output)
