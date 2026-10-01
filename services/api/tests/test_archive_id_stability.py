"""The Open Bus archive ID-stability tool, exercised on in-memory zips and a mock S3 only."""

import io
import zipfile
from datetime import date

import httpx

from tools.archive_id_stability import BUCKET, FEED, RangeFile, extract, flicker, semantic

STOPS = "stop_id,stop_code,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
ROUTES = "route_id,agency_id,route_short_name,route_long_name,route_type\n"
TRIPS = "route_id,service_id,trip_id,trip_headsign,direction_id,shape_id\n"


def feed(stops: str, routes: str, trips: str = "", extra: int = 0) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("stop_times.txt", "x" * extra)  # bulky member the tool must skip
        archive.writestr("stops.txt", STOPS + stops)
        archive.writestr("routes.txt", ROUTES + routes)
        archive.writestr("trips.txt", TRIPS + trips)
    return buffer.getvalue()


def s3(objects: dict[str, bytes], ranges: list[str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            key = request.url.params["prefix"]
            if key not in objects:
                return httpx.Response(200, text="<ListBucketResult></ListBucketResult>")
            return httpx.Response(
                200,
                text=f"<Contents><Key>{key}</Key><LastModified>2026-09-30T00:14:09.000Z"
                f"</LastModified><ETag>&quot;abc-2&quot;</ETag><Size>{len(objects[key])}</Size>",
            )
        body = objects[request.url.path.lstrip("/")]
        start, end = map(int, request.headers["Range"].removeprefix("bytes=").split("-"))
        ranges.append(request.headers["Range"])
        return httpx.Response(206, content=body[start : end + 1])

    return httpx.Client(transport=httpx.MockTransport(handler), base_url=BUCKET)


def test_range_file_reads_and_seeks_like_a_local_file():
    data = bytes(range(256)) * 1000
    client = s3({"o": data}, ranges := [])
    remote = RangeFile(client, f"{BUCKET}/o", len(data))
    remote.seek(-10, io.SEEK_END)
    assert remote.read() == data[-10:]
    remote.seek(5)
    assert remote.read(7) == data[5:12] and remote.tell() == 12
    assert len(ranges) == 1  # both reads fall in the single cached block


def test_extract_copies_only_identity_members_and_records_provenance(tmp_path):
    body = feed("1,11,A,32.0,34.8,0,\n", "r1,3,22,X<->Y,3\n", "r1,s1,t1,h,0,9\n", extra=10_000)
    key = "gtfs_archive/2026/09/30/" + FEED
    client = s3({key: body}, [])
    path, meta = extract(client, date(2026, 9, 30), tmp_path)
    with zipfile.ZipFile(path) as archive:
        assert sorted(archive.namelist()) == ["routes.txt", "stops.txt", "trips.txt"]
    assert meta["key"] == key and meta["etag"] == "abc-2" and meta["size"] == len(body)
    assert set(meta["members"]) == {"stops.txt", "routes.txt", "trips.txt"}
    assert extract(client, date(2026, 9, 29), tmp_path) is None  # day absent from the archive
    assert extract(httpx.Client(), date(2026, 9, 30), tmp_path)[0] == path  # cached, no network


def test_semantic_reports_reused_ids_not_mere_overlap():
    old = {
        "stops": {
            "1": {"stop_name": "A", "stop_code": "11", "stop_lat": "32.0", "stop_lon": "34.8"},
            "2": {"stop_name": "B", "stop_code": "12", "stop_lat": "32.0", "stop_lon": "34.8"},
        },
        "routes": {"r1": {"route_short_name": "22", "agency_id": "3"}},
    }
    new = {
        "stops": {
            "1": {"stop_name": "A2", "stop_code": "11", "stop_lat": "32.0", "stop_lon": "34.8"},
            "2": {"stop_name": "B", "stop_code": "12", "stop_lat": "32.01", "stop_lon": "34.8"},
        },
        "routes": {"r1": {"route_short_name": "22", "agency_id": "5"}},
    }
    result = semantic(old, new)
    assert result["stops"]["nameChanged"]["samples"] == ["1"]
    assert result["stops"]["movedOver100m"]["samples"] == ["2"]  # about 1.1 km north
    assert result["stops"]["codeChanged"]["count"] == 0
    assert result["routes"]["agencyChanged"]["samples"] == ["r1"]


def test_flicker_separates_returning_ids_from_permanent_removals():
    days = [date(2026, 9, d) for d in (1, 2, 3, 4)]
    stops = [{"a", "b", "c"}, {"a"}, {"a", "b"}, {"a", "b"}]
    tables = {day: {"stops": ids, "routes": {"r"}} for day, ids in zip(days, stops, strict=True)}
    result = flicker(days, tables.__getitem__)
    assert result["stops"] == {
        "removedAndReturned": 1,
        "removedNotReturned": 1,
        "returnedSamples": ["b"],
    }
    assert result["routes"]["removedAndReturned"] == 0
