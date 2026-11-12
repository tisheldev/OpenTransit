"""House numbers mapped on building outlines (OSM ways) reach the address index.

Found on 12 November 2026: only nodes with ``addr:housenumber`` were exported, but mappers
often put the address on the building outline instead (in Herzliya 1,762 outlines against
383 nodes), so most mapped house numbers there could not be found.
"""

import asyncio
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest
from test_address_catalog import _place, _source_dump
from test_photon_geocoder import GENERATION, STREET, _geocoder
from test_photon_pipeline_units import FakeOsmium, _location, _tag, fake_world

from opentransit.address_catalog import AddressCatalog
from opentransit.build import photon_source
from opentransit.build.address_catalog import build_address_catalog
from opentransit.core.place_ref import decode_place_ref
from opentransit.photon_geocoder import PhotonUnavailable

SQUARE = [
    (34.7800, 32.0800),
    (34.7802, 32.0800),
    (34.7802, 32.0802),
    (34.7800, 32.0802),
    (34.7800, 32.0800),
]


def _outline(way_id, ring=SQUARE, valid=True, **tags):
    return SimpleNamespace(
        id=way_id,
        tags=_tag(**tags),
        nodes=[SimpleNamespace(location=_location(lon, lat, valid)) for lon, lat in ring],
    )


def _world():
    base = fake_world()  # one address node (N11), the street W500 and its locality
    handler = base.SimpleHandler()
    nodes, ways, areas = [], [], []
    handler.node, handler.way, handler.area = nodes.append, ways.append, areas.append
    handler.apply_file("unused")
    ways += [
        _outline(700, building="yes", addr__housenumber="13", addr__street="Herzl"),
        _outline(701, building="yes", addr__housenumber="15"),  # no street: not an address
        _outline(  # a named highway is a street document under the same way identity
            702,
            highway="pedestrian",
            name="Herzl Square",
            addr__housenumber="1",
            addr__street="Herzl",
        ),
        _outline(703, valid=False, building="yes", addr__housenumber="17", addr__street="Herzl"),
    ]
    return FakeOsmium(nodes, ways, areas)


def _export(tmp_path, world):
    pbf = tmp_path / "source.osm.pbf"
    pbf.write_bytes(b"synthetic pbf")
    seen = {}
    original = world.SimpleHandler.apply_file

    def apply_file(self, path, locations=False, idx=None):
        seen.update(locations=locations, idx=idx)
        return original(self, path, locations, idx)

    world.SimpleHandler.apply_file = apply_file
    result = photon_source.export_house_dump(pbf, tmp_path / "houses.jsonl", osmium=world)
    lines = (tmp_path / "houses.jsonl").read_text(encoding="utf-8").splitlines()
    return pbf, result, [json.loads(line)["content"][0] for line in lines[1:]], seen


def test_house_export_writes_building_outlines_at_their_centre(tmp_path):
    _pbf, result, places, seen = _export(tmp_path, _world())
    assert [place["place_id"] for place in places] == ["N11", "W700"]
    outline = places[1]
    assert outline["object_type"] == "W" and outline["object_id"] == 700
    assert outline["address_type"] == "house" and outline["housenumber"] == "13"
    assert outline["osm_key"] == "addr:housenumber"
    assert outline["address"] == {"street": "Herzl"}
    assert outline["centroid"] == pytest.approx([34.7801, 32.0801], abs=1e-9)
    assert result["houseRecords"] == 2
    assert result["houseNodeRecords"] == 1 and result["houseWayRecords"] == 1
    assert result["waysSkipped"] == {"namedHighway": 1, "unlocatedNode": 1}
    # Way nodes carry coordinates only when the reader is asked to resolve them.
    assert seen == {"locations": True, "idx": "flex_mem"}


def test_building_outline_houses_pass_enrichment_and_the_catalog(tmp_path):
    from tools.enrich_photon_addresses import transform_dump

    world = _world()
    pbf, _result, _places, _seen = _export(tmp_path, world)
    pbf_sha = hashlib.sha256(pbf.read_bytes()).hexdigest()
    photon_source.extract_context(pbf, tmp_path / "context.jsonl", osmium=world)
    result = transform_dump(
        tmp_path / "houses.jsonl",
        tmp_path / "context.jsonl",
        tmp_path / "enriched.jsonl",
        tmp_path / "enriched.provenance.json",
        expected_source_sha256=pbf_sha,
        expected_house_dump_sha256=None,
        expected_house_count=None,
    )
    assert result["counts"]["houseRecords"] == 2
    linked = {
        (row["sourceHouseOsmType"], row["sourceHouseId"]): row
        for row in result["sourceContributions"]
    }
    assert linked[("W", "700")]["streetWayIds"] == ["500"]
    assert linked[("W", "700")]["localitySourceIds"] == [{"osmType": "R", "osmId": "9001"}]
    metadata = build_address_catalog(tmp_path / "enriched.jsonl", tmp_path / "catalog.sqlite")
    # Two houses (node and outline) and the street documents of W500 and W702.
    assert int(metadata["record_count"]) == 4
    with AddressCatalog(tmp_path / "catalog.sqlite", metadata["source_dump_sha256"]) as catalog:
        outline = catalog.lookup("W", "700")
        assert outline["address_type"] == "house" and outline["housenumber"] == "13"
        assert outline["address"]["city"] == "Tel Aviv"
        assert catalog.lookup("W", "702")["address_type"] == "street"


def test_catalog_accepts_a_way_house_but_never_one_without_a_number(tmp_path):
    source = tmp_path / "enriched.jsonl"
    _source_dump(
        source,
        rows=[_place("W", "700", "house", housenumber="13"), _place("W", "300", "street")],
    )
    metadata = build_address_catalog(source, tmp_path / "catalog.sqlite")
    assert int(metadata["record_count"]) == 2

    numberless = _place("W", "701", "house", housenumber="13")
    del numberless["content"][0]["housenumber"]
    _source_dump(tmp_path / "bad.jsonl", rows=[numberless])
    with pytest.raises(ValueError, match="house number"):
        build_address_catalog(tmp_path / "bad.jsonl", tmp_path / "bad.sqlite")


OUTLINE_HOUSE = {
    "object_type": "W",
    "object_id": 700,
    "address_type": "house",
    "housenumber": "13",
    "centroid": [34.7801, 32.0801],
    "address": {"street": "Herzl", "city": "Rehovot"},
    "extra": {"addr:housenumber": "13", "addr:street": "Herzl", "building": "yes"},
}


def _search(feature_properties):
    def handle(_request):
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [34.7801, 32.0801]},
            "properties": feature_properties,
        }
        return httpx.Response(200, json={"type": "FeatureCollection", "features": [feature]})

    async def run():
        geocoder, client = _geocoder(
            handle, rows={("W", "700"): OUTLINE_HOUSE, ("W", "300"): STREET}
        )
        try:
            return await geocoder.search("Herzl 13 Rehovot", language="en", limit=10)
        finally:
            await client.aclose()

    return asyncio.run(run())


def test_search_returns_a_building_outline_house_with_its_own_precision():
    result = _search(
        {"osm_type": "W", "osm_id": 700, "layer": "house", "housenumber": "13", "street": "Herzl"}
    )
    item = result.items[0]
    assert item["osmType"] == "W" and item["osmId"] == "700"
    assert item["addressLevel"] == "house_number" and item["houseNumber"] == "13"
    assert item["precision"] == "building_centroid"
    assert item["displayName"] == "Herzl 13, Rehovot"
    reference = decode_place_ref(item["placeRef"], GENERATION)
    assert (reference.latitude, reference.longitude) == (32.0801, 34.7801)


def test_search_still_rejects_a_way_house_whose_number_differs_from_the_catalog():
    with pytest.raises(PhotonUnavailable):
        _search(
            {
                "osm_type": "W",
                "osm_id": 700,
                "layer": "house",
                "housenumber": "14",
                "street": "Herzl",
            }
        )
    with pytest.raises(PhotonUnavailable):  # the catalog says house; Photon says street
        _search({"osm_type": "W", "osm_id": 700, "layer": "street", "name": "Herzl"})
