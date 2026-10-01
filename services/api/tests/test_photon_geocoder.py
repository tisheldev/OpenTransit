import asyncio
import json
import logging
from types import SimpleNamespace

import httpx
import pytest

from opentransit.core.place_ref import decode_place_ref
from opentransit.photon_geocoder import PhotonGeocoder, PhotonUnavailable

GENERATION = "photon-test-generation"
HOUSE = {
    "object_type": "N",
    "object_id": 300,
    "address_type": "house",
    "housenumber": "24",
    "centroid": [34.78, 32.08],
    "name": {"name": "Herzl 24", "name:he": "הרצל 24"},
    "address": {"street": "Herzl", "street:en": "Herzl Street", "city": "Rehovot"},
    "extra": {"addr:housenumber": "24", "addr:street": "הרצל", "addr:street:en": "Herzl Street"},
}
STREET = {
    "object_type": "W",
    "object_id": 300,
    "address_type": "street",
    "centroid": [34.78, 32.08],
    "name": {"name": "הרצל", "name:en": "Herzl Street"},
    "address": {"city": "Rehovot", "city:en": "Rehovot"},
    "extra": {"highway": "residential", "name:en": "Herzl Street"},
}


def _binding(client, *, rows=None, artifact_identity="a" * 64):
    source_rows = {("N", "300"): HOUSE, ("W", "300"): STREET} if rows is None else rows
    catalog = SimpleNamespace(lookup=lambda osm_type, osm_id: source_rows.get((osm_type, osm_id)))
    return SimpleNamespace(
        client=client,
        origin="http://photon.test:2322",
        artifact_identity=artifact_identity,
        index_uuid="index-uuid-1",
        catalog=catalog,
    )


def _feature(
    osm_type="node",
    osm_id=300,
    *,
    lon=34.78,
    lat=32.08,
    name="Herzl Street",
    number="24",
    street=None,
):
    properties = {
        "osm_type": osm_type,
        "osm_id": osm_id,
        "layer": "house" if osm_type in {"node", "N"} else "street",
    }
    if name is not None:
        properties["name"] = name
    if street is not None:
        properties["street"] = street
    if osm_type in {"node", "N"}:
        properties["housenumber"] = number
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }


def _geocoder(handler, *, rows=None):
    client = httpx.AsyncClient(
        base_url="http://photon.test:2322", transport=httpx.MockTransport(handler)
    )
    return PhotonGeocoder(_binding(client, rows=rows), GENERATION), client


def test_photon_search_preserves_source_identity_precision_and_explicit_language():
    captured = {}
    unnamed_house = HOUSE.copy()
    unnamed_house.pop("name")

    def handle(request):
        captured["params"] = list(request.url.params.multi_items())
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [_feature(name=None, street="Herzl Street")],
            },
        )

    async def run():
        geocoder, client = _geocoder(
            handle, rows={("N", "300"): unnamed_house, ("W", "300"): STREET}
        )
        try:
            return await geocoder.search(
                "Herzl Rehovot",
                language="en",
                limit=10,
                near=(32.081, 34.781),
                request_id="ab" * 16,
            )
        finally:
            await client.aclose()

    result = asyncio.run(run())
    assert captured["params"].count(("layer", "house")) == 1
    assert captured["params"].count(("layer", "street")) == 1
    assert ("q", "Herzl Rehovot") in captured["params"]
    assert ("limit", "10") in captured["params"]
    assert ("lat", "32.08100000") in captured["params"]
    assert result.outcome == "success"
    item = result.items[0]
    assert item["osmType"] == "N" and item["osmId"] == "300"
    assert item["precision"] == "address_node"
    assert item["houseNumber"] == "24"
    assert item["languageUsed"] == "en"
    assert item["displayName"] == "Herzl Street 24, Rehovot"
    assert item["locality"] == "Rehovot"
    reference = decode_place_ref(item["placeRef"], GENERATION)
    assert (reference.latitude, reference.longitude) == (32.08, 34.78)
    with pytest.raises(ValueError, match="generation"):
        decode_place_ref(item["placeRef"], "other-generation")


def test_street_way_midpoint_precision_and_latin_base_name_stays_unknown():
    source = STREET | {
        "name": {"name": "Herzl"},
        "extra": {"highway": "residential", "name": "Herzl"},
    }

    def handle(_request):
        return httpx.Response(
            200,
            json={"type": "FeatureCollection", "features": [_feature("way", name="Herzl")]},
        )

    async def run():
        geocoder, client = _geocoder(handle, rows={("W", "300"): source})
        try:
            return await geocoder.search("Herzl Rehovot", language="en", limit=5)
        finally:
            await client.aclose()

    item = asyncio.run(run()).items[0]
    assert item["precision"] == "street_way_midpoint"
    assert item["addressLevel"] == "street"
    assert item["houseNumber"] is None
    assert item["languageUsed"] == "unknown"


def test_house_display_name_is_accepted_only_when_explicitly_source_backed():
    def handle(_request):
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [_feature(name="הרצל 24")],
            },
        )

    async def run():
        geocoder, client = _geocoder(handle)
        try:
            return await geocoder.search("Herzl 24", language="en", limit=10)
        finally:
            await client.aclose()

    item = asyncio.run(run()).items[0]
    assert item["displayName"] == "הרצל 24"
    assert item["languageUsed"] == "he"


@pytest.mark.parametrize(
    "feature",
    [
        _feature(osm_id=999),
        _feature(lon=34.7801),
        _feature(number="25"),
        _feature(name="Forged Place Name"),
        _feature(name=None, street="Forged Street"),
        _feature("relation", name="Herzl Street"),
    ],
)
def test_unknown_or_mutated_source_candidate_fails_entire_category(feature):
    def handle(_request):
        return httpx.Response(
            200,
            json={"type": "FeatureCollection", "features": [feature]},
        )

    async def run():
        geocoder, client = _geocoder(handle)
        try:
            return await geocoder.search("Herzl 24", language="he", limit=10)
        finally:
            await client.aclose()

    with pytest.raises(PhotonUnavailable):
        asyncio.run(run())


def test_valid_empty_down_oversize_and_malformed_responses_are_distinct():
    def empty(_request):
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})

    def unavailable(_request):
        return httpx.Response(503, text="private backend body")

    def oversize(_request):
        return httpx.Response(
            200,
            content=b"[]",
            headers={"content-length": str(2_000_001)},
        )

    def malformed(_request):
        return httpx.Response(200, json={"features": ["not a feature"]})

    async def invoke(handler):
        geocoder, client = _geocoder(handler)
        try:
            return await geocoder.search("Herzl 24", language="he", limit=10)
        finally:
            await client.aclose()

    assert asyncio.run(invoke(empty)).outcome == "validempty"
    for handler in (unavailable, oversize, malformed):
        with pytest.raises(PhotonUnavailable):
            asyncio.run(invoke(handler))


def test_close_coordinates_and_distinct_full_node_ids_remain_distinct():
    second = HOUSE | {
        "object_id": 301,
        "centroid": [34.7801, 32.08],
        "housenumber": "25",
    }
    rows = {("N", "300"): HOUSE, ("N", "301"): second}

    def handle(_request):
        first = _feature(name=None, street="Herzl Street", number="24")
        second_feature = _feature(
            osm_id=301,
            lon=34.7801,
            name=None,
            street="Herzl Street",
            number="25",
        )
        return httpx.Response(
            200,
            json={"type": "FeatureCollection", "features": [first, second_feature]},
        )

    async def run():
        geocoder, client = _geocoder(handle, rows=rows)
        try:
            return await geocoder.search("Herzl", language="en", limit=10)
        finally:
            await client.aclose()

    results = asyncio.run(run()).items
    assert [row["osmId"] for row in results] == ["300", "301"]
    assert results[0]["placeRef"] != results[1]["placeRef"]


def test_invalid_artifact_identity_fails_closed():
    async def handle(_request):
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})

    async def run():
        client = httpx.AsyncClient(
            base_url="http://photon.test:2322", transport=httpx.MockTransport(handle)
        )
        try:
            with pytest.raises(ValueError, match="artifact identity"):
                PhotonGeocoder(_binding(client, artifact_identity="not-a-hash"), GENERATION)
        finally:
            await client.aclose()

    asyncio.run(run())


def test_cancellation_propagates():
    entered = asyncio.Event()

    async def slow(_request):
        entered.set()
        await asyncio.sleep(30)
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})

    async def run():
        geocoder, client = _geocoder(slow)
        task = asyncio.create_task(geocoder.search("Herzl 24", language="he", limit=10))
        await asyncio.wait_for(entered.wait(), timeout=2)
        task.cancel()
        try:
            await task
        finally:
            await client.aclose()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())


def test_phase_log_is_request_correlated_and_contains_no_query_or_response_data(caplog):
    def handle(_request):
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [_feature(name=None, street="Herzl Street")],
            },
        )

    async def run():
        geocoder, client = _geocoder(handle)
        try:
            await geocoder.search(
                "secret place query", language="he", limit=10, request_id="bc" * 16
            )
        finally:
            await client.aclose()

    with caplog.at_level(logging.INFO, logger="opentransit.requests.photon"):
        asyncio.run(run())
    record = next(row for row in caplog.records if row.name == "opentransit.requests.photon")
    fields = json.loads(record.getMessage())
    assert fields["request_id"] == "bc" * 16
    assert fields["outcome"] == "success"
    assert fields["backend_ms"] >= 0 and fields["normalize_ms"] >= 0
    assert set(fields) == {
        "request_id",
        "genid",
        "backend_ms",
        "normalize_ms",
        "responsebytes",
        "resultcount",
        "outcome",
    }
    assert "secret place query" not in record.getMessage()
    assert "Herzl Street" not in record.getMessage()
