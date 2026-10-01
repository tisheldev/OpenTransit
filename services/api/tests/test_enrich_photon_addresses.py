import json
from pathlib import Path

import pytest

from tools.enrich_photon_addresses import point_in_geometry, transform_dump

TEST_PBF_HASH = "a" * 64


def _polygon(*, hole=None):
    outer = [[0.0, 0.0], [0.02, 0.0], [0.02, 0.02], [0.0, 0.02], [0.0, 0.0]]
    rings = [outer]
    if hole:
        rings.append(hole)
    return {"type": "Polygon", "coordinates": rings}


def _context_rows(*, street_tags=None, localities=None):
    return [
        {
            "type": "ContextHeader",
            "schemaVersion": 1,
            "sourceSha256": TEST_PBF_HASH,
        },
        {
            "type": "Street",
            "osmType": "W",
            "osmId": "100",
            "tags": street_tags
            or {
                "highway": "residential",
                "name": "Main",
                "name:he": "רחוב ראשי",
                "name:en": "Main Street",
            },
            "coordinates": [[0.0, 0.005], [0.01, 0.005]],
        },
        *(
            localities
            if localities is not None
            else [
                {
                    "type": "Locality",
                    "osmType": "R",
                    "osmId": "200",
                    "tags": {
                        "boundary": "administrative",
                        "admin_level": "8",
                        "name": "Town",
                        "name:he": "עיר",
                        "name:en": "Town English",
                    },
                    "geometry": _polygon(),
                }
            ]
        ),
    ]


def _house(*, lon=0.005, lat=0.005, tags=None, address=None, osm_id="300"):
    raw_tags = tags or {
        "addr:housenumber": "24",
        "addr:street": "Main",
        "addr:city": "Town",
    }
    mapped_address = address or {"street": "Main", "city": "Town"}
    return {
        "type": "Place",
        "content": [
            {
                "place_id": f"N{osm_id}",
                "object_type": "N",
                "object_id": int(osm_id),
                "osm_key": "addr:housenumber",
                "osm_value": raw_tags["addr:housenumber"],
                "address_type": "house",
                "housenumber": raw_tags["addr:housenumber"],
                "address": mapped_address,
                "extra": raw_tags,
                "centroid": [lon, lat],
            }
        ],
    }


def _write_jsonl(path: Path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def _run(tmp_path, *, house_rows=None, context_rows=None):
    houses = tmp_path / "houses.jsonl"
    context = tmp_path / "context.jsonl"
    output = tmp_path / "enriched.jsonl"
    provenance = tmp_path / "enriched.provenance.json"
    header = {
        "type": "NominatimDumpFile",
        "content": {
            "version": "0.1.0",
            "generator": "test source",
            "database_version": f"source PBF SHA-256 {TEST_PBF_HASH}",
            "features": {"sorted_by_country": False, "has_addresslines": False},
        },
    }
    _write_jsonl(houses, [header, *(house_rows or [_house()])])
    _write_jsonl(context, context_rows or _context_rows())
    result = transform_dump(
        houses,
        context,
        output,
        provenance,
        expected_source_sha256=TEST_PBF_HASH,
        expected_house_dump_sha256=None,
        expected_house_count=None,
    )
    dump_rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    return result, dump_rows, json.loads(provenance.read_text(encoding="utf-8"))


def test_explicit_source_aliases_enrich_house_without_changing_source_identity(tmp_path):
    source_house = _house()
    result, rows, provenance = _run(tmp_path, house_rows=[source_house])
    enriched_house = rows[1]["content"][0]
    street_doc = rows[2]["content"][0]

    assert enriched_house["address"] == {
        "street": "Main",
        "city": "Town",
        "city:he": "עיר",
        "city:en": "Town English",
        "street:he": "רחוב ראשי",
        "street:en": "Main Street",
    }
    for key in ("place_id", "object_type", "object_id", "centroid", "housenumber", "extra"):
        assert enriched_house[key] == source_house["content"][0][key]
    assert street_doc["place_id"] == "W100"
    assert street_doc["object_type"] == "W"
    assert street_doc["object_id"] == 100
    assert street_doc["osm_key"] == "highway"
    assert street_doc["osm_value"] == "residential"
    assert street_doc["address_type"] == "street"
    assert street_doc["name"] == {
        "name": "Main",
        "name:he": "רחוב ראשי",
        "name:en": "Main Street",
    }
    assert street_doc["address"] == {
        "city": "Town",
        "city:he": "עיר",
        "city:en": "Town English",
    }
    assert "housenumber" not in street_doc
    assert street_doc["centroid"] == [0.005, 0.005]
    assert result["sourceContributions"][0]["streetWayIds"] == ["100"]
    assert result["sourceContributions"][0]["localitySourceIds"] == [
        {"osmType": "R", "osmId": "200"}
    ]
    assert result["streetDocumentLocalityContributions"] == [
        {
            "streetWayId": "100",
            "localitySourceId": {"osmType": "R", "osmId": "200"},
        }
    ]
    assert result["method"]["targetCorpusRead"] is False
    assert provenance["sourceHashes"]["sourcePbfSha256"] == TEST_PBF_HASH


def test_conflicting_explicit_tags_and_conflicting_source_translations_are_not_overwritten(
    tmp_path,
):
    second_way = {
        "type": "Street",
        "osmType": "W",
        "osmId": "101",
        "tags": {
            "highway": "residential",
            "name": "Main",
            "name:en": "Different English Name",
        },
        "coordinates": [[0.0, 0.005], [0.01, 0.005]],
    }
    house = _house(
        tags={
            "addr:housenumber": "24",
            "addr:street": "Main",
            "addr:city": "Town",
            "addr:street:en": "Explicit House English",
            "addr:city:he": "Explicit City Hebrew",
        },
        address={
            "street": "Main",
            "city": "Town",
            "street:en": "Explicit House English",
            "city:he": "Explicit City Hebrew",
        },
    )
    result, rows, _ = _run(
        tmp_path, house_rows=[house], context_rows=[*_context_rows(), second_way]
    )
    enriched = rows[1]["content"][0]
    assert enriched["address"]["street:en"] == "Explicit House English"
    assert enriched["address"]["city:he"] == "Explicit City Hebrew"
    assert enriched["address"]["street:he"] == "רחוב ראשי"
    conflict_fields = {row["field"] for row in result["sourceContributions"][0]["conflicts"]}
    assert "street:en" in conflict_fields
    assert "city:he" in conflict_fields


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        ((0.005, 0.005), "outside"),  # inside a hole
        ((0.0, 0.005), "boundary"),
        ((0.015, 0.015), "inside"),
    ],
)
def test_polygon_containment_respects_holes_and_boundaries(point, expected):
    hole = [[0.004, 0.004], [0.006, 0.004], [0.006, 0.006], [0.004, 0.006], [0.004, 0.004]]
    assert point_in_geometry(point, _polygon(hole=hole)) == expected


def test_house_in_polygon_hole_or_on_boundary_gets_no_locality_aliases(tmp_path):
    hole = [[0.004, 0.004], [0.006, 0.004], [0.006, 0.006], [0.004, 0.006], [0.004, 0.004]]
    locality = _context_rows()[2] | {"geometry": _polygon(hole=hole)}
    context = _context_rows(localities=[locality])
    houses = [_house(lon=0.005, lat=0.005, osm_id="301"), _house(lon=0.0, lat=0.005, osm_id="302")]
    result, rows, _ = _run(tmp_path, house_rows=houses, context_rows=context)
    assert "city:en" not in rows[1]["content"][0]["address"]
    assert "city:en" not in rows[2]["content"][0]["address"]
    assert result["counts"]["locality:no_containing_locality"] == 1
    assert result["counts"]["locality:point_on_locality_boundary"] == 1


def test_overlapping_localities_with_same_numeric_id_leave_aliases_unresolved(tmp_path):
    second = {
        "type": "Locality",
        "osmType": "W",
        "osmId": "200",
        "tags": {
            "boundary": "administrative",
            "admin_level": "8",
            "name": "Other Town",
            "name:en": "Other",
        },
        "geometry": _polygon(),
    }
    result, rows, _ = _run(tmp_path, context_rows=[*_context_rows(), second])
    assert "city:en" not in rows[1]["content"][0]["address"]
    assert "street:en" not in rows[1]["content"][0]["address"]
    assert result["counts"]["locality:ambiguous_multiple_localities"] == 1
    # A way and a relation may share a numeric OSM ID; both must remain distinct.
    assert len(result["streetDocumentLocalityContributions"]) == 0


def test_street_midpoint_in_locality_hole_gets_no_city_context(tmp_path):
    hole = [[0.004, 0.004], [0.006, 0.004], [0.006, 0.006], [0.004, 0.006], [0.004, 0.004]]
    locality = _context_rows()[2] | {"geometry": _polygon(hole=hole)}
    _, rows, provenance = _run(tmp_path, context_rows=_context_rows(localities=[locality]))
    street_doc = rows[2]["content"][0]
    assert "address" not in street_doc
    assert provenance["streetDocumentLocalityContributions"] == []


def test_missing_source_translations_are_not_guessed_and_street_doc_is_not_house_precision(
    tmp_path,
):
    street_tags = {"highway": "residential", "name": "Main"}
    localities = [
        {
            "type": "Locality",
            "osmType": "R",
            "osmId": "200",
            "tags": {"boundary": "administrative", "admin_level": "8", "name": "Town"},
            "geometry": _polygon(),
        }
    ]
    _, rows, _ = _run(
        tmp_path,
        context_rows=_context_rows(street_tags=street_tags, localities=localities),
    )
    house_address = rows[1]["content"][0]["address"]
    street_doc = rows[2]["content"][0]
    assert "street:he" not in house_address and "street:en" not in house_address
    assert "city:he" not in house_address and "city:en" not in house_address
    assert street_doc["name"] == {"name": "Main"}
    assert street_doc["address_type"] == "street"
    assert "housenumber" not in street_doc


def test_context_source_hash_mismatch_is_rejected(tmp_path):
    context = _context_rows()
    context[0]["sourceSha256"] = "b" * 64
    houses = tmp_path / "houses.jsonl"
    context_path = tmp_path / "context.jsonl"
    output = tmp_path / "out.jsonl"
    provenance = tmp_path / "out.provenance.json"
    header = {
        "type": "NominatimDumpFile",
        "content": {
            "version": "0.1.0",
            "database_version": f"source PBF SHA-256 {TEST_PBF_HASH}",
        },
    }
    _write_jsonl(houses, [header, _house()])
    _write_jsonl(context_path, context)
    with pytest.raises(ValueError, match="sourceSha256"):
        transform_dump(
            houses,
            context_path,
            output,
            provenance,
            expected_source_sha256=TEST_PBF_HASH,
            expected_house_dump_sha256=None,
            expected_house_count=None,
        )
