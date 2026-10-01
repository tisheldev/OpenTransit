import asyncio
import json
import logging
from types import SimpleNamespace

import httpx
import pytest

from opentransit import motis_geocoder
from opentransit.core.place_ref import decode_place_ref
from opentransit.motis_geocoder import (
    GeocoderUnavailable,
    MotisGeocoder,
    geocode_places,
)

GENERATION = "geocoder-generation"


def snapshot(client):
    return SimpleNamespace(
        generation=SimpleNamespace(id=GENERATION),
        motis=SimpleNamespace(client=client),
    )


def address(name, lat, lon, *, street=None, number=None):
    value = {"type": "ADDRESS", "name": name, "lat": lat, "lon": lon}
    if street is not None:
        value["street"] = street
    if number is not None:
        value["houseNumber"] = number
    return value


def test_geocoder_wire_params_actual_place_shape_and_generation_bound_ref():
    captured = {}
    actual_motis_match = {
        "type": "PLACE",
        "category": "shop_other_16",
        "tokens": [[0, 9]],
        "name": "Dizengoff Center",
        "id": "way/[30622051]",
        "lat": 32.075301,
        "lon": 34.773702,
        "country": "IL",
        "areas": [
            {"name": "Israel", "adminLevel": 2, "matched": False},
            {"name": "Tel-Aviv", "adminLevel": 8, "unique": True, "default": True},
        ],
        "score": -15,
    }

    def handle(request):
        captured.update(dict(request.url.params))
        return httpx.Response(200, json=[actual_motis_match])

    async def run():
        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:59081", transport=httpx.MockTransport(handle)
        ) as client:
            result = await geocode_places(
                snapshot(client),
                "Dizengoff",
                language="en",
                near=(32.08, 34.78),
                types=("poi", "address"),
                limit=7,
            )
            return result

    result = asyncio.run(run())
    assert captured == {
        "text": "Dizengoff",
        "language": "en",
        "type": "ADDRESS,PLACE",
        "numResults": "7",
        "place": "32.08000000,34.78000000",
        "placeBias": "1",
    }
    assert result.outcome == "matches_found"
    assert result.searched_types == ("poi", "address")
    item = result.items[0]
    assert item["kind"] == "poi"
    assert item["category"] == "shop_other_16"
    assert item["osmId"] == "way/[30622051]"
    assert item["languageUsed"] == "en"
    assert item["locality"] == "Tel-Aviv"
    assert item["locationRef"] == {"kind": "place", "placeRef": item["placeRef"]}
    reference = decode_place_ref(item["placeRef"], GENERATION)
    assert (reference.latitude, reference.longitude) == (32.075301, 34.773702)


def test_empty_address_ids_are_valid_and_distinct_candidates_remain_distinct():
    responses = [
        address("Dizengoff Street", 32.08, 34.78, street="Dizengoff Street"),
        address("Herzl Street", 32.07, 34.77, street="Herzl Street"),
    ]

    def handle(_request):
        return httpx.Response(200, json=responses)

    async def run():
        async with httpx.AsyncClient(
            base_url="http://localhost:59081", transport=httpx.MockTransport(handle)
        ) as client:
            return await MotisGeocoder(client, GENERATION).search(
                "Street", types=("address",), limit=2
            )

    result = asyncio.run(run())
    assert len(result.items) == 2
    assert [item["addressLevel"] for item in result.items] == ["street", "street"]
    assert all("osmId" not in item for item in result.items)
    assert result.items[0]["candidateIdentityHash"] != result.items[1]["candidateIdentityHash"]
    assert result.items[0]["placeRef"] != result.items[1]["placeRef"]


def test_address_number_label_and_actual_language_are_preserved():
    def handle(_request):
        return httpx.Response(
            200,
            json=[
                address(
                    "רחוב דיזנגוף 10",
                    32.08,
                    34.78,
                    street="רחוב דיזנגוף",
                    number="10",
                )
            ],
        )

    async def run():
        async with httpx.AsyncClient(
            base_url="http://localhost:59081", transport=httpx.MockTransport(handle)
        ) as client:
            return await MotisGeocoder(client, GENERATION).search(
                "Dizengoff 10", language="en", types=("address",)
            )

    item = asyncio.run(run()).items[0]
    assert item["languageUsed"] == "he"
    assert item["name"] == "רחוב דיזנגוף 10"
    assert item["street"] == "רחוב דיזנגוף"
    assert item["houseNumber"] == "10"
    assert item["addressLevel"] == "house_number"
    assert item["precision"] == "numbered_label"


def test_empty_success_is_distinct_from_engine_failure_and_bad_payload():
    def empty(_request):
        return httpx.Response(200, json=[])

    def failure(_request):
        return httpx.Response(503, text="disabled")

    def malformed(_request):
        return httpx.Response(200, json={"unexpected": []})

    async def invoke(handler):
        async with httpx.AsyncClient(
            base_url="http://localhost:59081", transport=httpx.MockTransport(handler)
        ) as client:
            return await MotisGeocoder(client, GENERATION).search("Nowhere")

    assert asyncio.run(invoke(empty)).outcome == "no_match"
    with pytest.raises(GeocoderUnavailable) as error:
        asyncio.run(invoke(failure))
    assert error.value.status == 503
    assert error.value.code == "GEOCODER_UNAVAILABLE"
    with pytest.raises(GeocoderUnavailable):
        asyncio.run(invoke(malformed))


def test_geocoder_timeout_and_redirect_fail_closed():
    async def slow(_request):
        await asyncio.sleep(0.05)
        return httpx.Response(200, json=[])

    def redirect(_request):
        return httpx.Response(302, headers={"location": "http://outside.invalid/"})

    async def invoke(handler, timeout=0.005):
        async with httpx.AsyncClient(
            base_url="http://localhost:59081", transport=httpx.MockTransport(handler)
        ) as client:
            return await MotisGeocoder(
                client,
                GENERATION,
                timeout_seconds=timeout,
            ).search("Dizengoff")

    with pytest.raises(GeocoderUnavailable):
        asyncio.run(invoke(slow))
    with pytest.raises(GeocoderUnavailable):
        asyncio.run(invoke(redirect, timeout=0.5))


def test_geocoder_response_byte_cap_and_input_bounds():
    def large(_request):
        return httpx.Response(200, content=b"[{}]", headers={"content-length": "4"})

    async def run():
        async with httpx.AsyncClient(
            base_url="http://localhost:59081", transport=httpx.MockTransport(large)
        ) as client:
            return await MotisGeocoder(client, GENERATION, max_response_bytes=3).search("test")

    with pytest.raises(GeocoderUnavailable):
        asyncio.run(run())

    async def invalid():
        async with httpx.AsyncClient(base_url="http://localhost:59081") as client:
            return await MotisGeocoder(client, GENERATION).search("x", types=("address",), limit=21)

    with pytest.raises(ValueError):
        asyncio.run(invalid())


def test_phase_timing_is_correlated_sanitized_and_split(monkeypatch, caplog):
    request_id = "ab" * 16
    generation_id = "12" * 32
    response_body = [address("Sensitive Label", 32.08, 34.78)]

    def handle(_request):
        return httpx.Response(200, json=response_body)

    clock = iter([10.0, 10.005, 10.005, 10.012])
    monkeypatch.setattr(motis_geocoder, "perf_counter", lambda: next(clock))

    async def run():
        async with httpx.AsyncClient(
            base_url="http://localhost:59081", transport=httpx.MockTransport(handle)
        ) as client:
            return await geocode_places(
                SimpleNamespace(generation=SimpleNamespace(id=generation_id), motis=client),
                "private query",
                near=(32.08, 34.78),
                types=("address",),
                request_id=request_id,
            )

    with caplog.at_level(logging.INFO, logger="opentransit.requests.geocoder"):
        result = asyncio.run(run())

    assert len(result.items) == 1
    records = [
        record for record in caplog.records if record.name == "opentransit.requests.geocoder"
    ]
    assert len(records) == 1
    record = records[0]
    message_fields = json.loads(record.getMessage())
    assert set(message_fields) == {
        "request_id",
        "genid",
        "backend_ms",
        "normalize_ms",
        "responsebytes",
        "resultcount",
        "outcome",
    }
    assert message_fields["genid"] == generation_id
    assert record.request_id == request_id
    assert record.genid == generation_id
    assert record.backend_ms == 5.0
    assert record.normalize_ms == 7.0
    assert record.responsebytes > 0
    assert record.resultcount == 1
    assert record.outcome == "success"
    standard = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message"}
    assert set(record.__dict__) - set(standard) == {
        "request_id",
        "genid",
        "backend_ms",
        "normalize_ms",
        "responsebytes",
        "resultcount",
        "outcome",
    }
    assert "private query" not in record.getMessage()
    assert "Sensitive Label" not in record.getMessage()


def test_phase_timing_distinguishes_valid_empty_and_unavailable_without_raw_errors(
    monkeypatch, caplog
):
    clock = iter([1.0, 1.004, 2.0, 2.004, 3.0, 3.004])
    monkeypatch.setattr(motis_geocoder, "perf_counter", lambda: next(clock))

    async def invoke(handler, request_id):
        async with httpx.AsyncClient(
            base_url="http://localhost:59081", transport=httpx.MockTransport(handler)
        ) as client:
            return await geocode_places(
                snapshot(client),
                "private query",
                types=("address",),
                request_id=request_id,
            )

    def empty(_request):
        return httpx.Response(200, json=[])

    def unavailable(_request):
        return httpx.Response(503, text="secret backend diagnostic")

    with caplog.at_level(logging.INFO, logger="opentransit.requests.geocoder"):
        empty_result = asyncio.run(invoke(empty, "cd" * 16))
        with pytest.raises(GeocoderUnavailable):
            asyncio.run(invoke(unavailable, "not-a-request-id\nsecret"))

    assert empty_result.items == []
    records = [
        record for record in caplog.records if record.name == "opentransit.requests.geocoder"
    ]
    assert [record.outcome for record in records] == ["validempty", "unavailable"]
    assert records[0].resultcount == 0 and records[0].responsebytes == 2
    assert records[0].request_id == "cd" * 16
    assert records[1].request_id is None
    assert records[1].genid is None
    assert records[1].resultcount is None and records[1].responsebytes is None
    assert all(record.backend_ms >= 0 and record.normalize_ms >= 0 for record in records)
    assert "secret backend diagnostic" not in " ".join(record.getMessage() for record in records)
    assert all(
        set(json.loads(record.getMessage()))
        == {
            "request_id",
            "genid",
            "backend_ms",
            "normalize_ms",
            "responsebytes",
            "resultcount",
            "outcome",
        }
        for record in records
    )
