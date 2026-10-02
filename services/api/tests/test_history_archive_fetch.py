"""OB-01 archive fetching: S3 listing, verified downloads, member extraction (mock transport)."""

import hashlib
import io
import zipfile
from datetime import UTC, date, datetime

import httpx
import pytest

from opentransit.history.archive_fetch import (
    ArchiveIntegrityError,
    ArchiveObject,
    extract_members,
    fetch_object,
    manifest_digest,
    parse_listing,
    siri_window,
)

LISTING = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Name>b</Name>
<NextContinuationToken>tok+/=</NextContinuationToken><IsTruncated>true</IsTruncated>
<Contents><Key>stride-siri-requester/2025/11/12/00/00.br</Key>
<LastModified>2025-11-12T00:00:47.000Z</LastModified>
<ETag>&quot;266d89d49cfcad799d5c581cc13eeb03&quot;</ETag><Size>9548</Size></Contents>
<Contents><Key>gtfs_archive/2025/11/12/israel-public-transportation.zip</Key>
<LastModified>2025-11-12T03:00:00.000Z</LastModified>
<ETag>&quot;0123456789abcdef0123456789abcdef-16&quot;</ETag><Size>131776523</Size></Contents>
</ListBucketResult>"""


def test_listing_parses_keys_sizes_etags_and_continuation():
    objects, token = parse_listing(LISTING)
    assert token == "tok+/="
    siri, feed = objects
    assert siri == ArchiveObject(
        "stride-siri-requester/2025/11/12/00/00.br", 9548, "266d89d49cfcad799d5c581cc13eeb03"
    )
    assert siri.md5 == "266d89d49cfcad799d5c581cc13eeb03"
    assert feed.md5 is None  # multipart upload: the ETag is not an MD5 of the bytes
    last_page = LISTING.replace("<NextContinuationToken>tok+/=</NextContinuationToken>", "")
    assert parse_listing(last_page)[1] is None


def serve(objects: dict[str, bytes], calls: list):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        key = request.url.path.lstrip("/")
        body = objects[key]
        if "range" in request.headers:
            start, end = (
                int(x) for x in request.headers["range"].removeprefix("bytes=").split("-")
            )
            return httpx.Response(206, content=body[start : end + 1])
        return httpx.Response(200, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://bucket")


def test_fetch_verifies_md5_and_skips_verified_cache(tmp_path):
    body = b"minute snapshot"
    good = ArchiveObject("stride-siri-requester/a.br", len(body), hashlib.md5(body).hexdigest())
    calls = []
    client = serve({good.key: body}, calls)
    target = tmp_path / "a.br"
    record = fetch_object(client, good, target)
    assert target.read_bytes() == body
    assert record == {
        "key": good.key,
        "size": len(body),
        "md5": good.md5,
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    assert fetch_object(client, good, target) == record and len(calls) == 1  # cache hit

    bad = ArchiveObject("stride-siri-requester/a.br", len(body), "0" * 32)
    with pytest.raises(ArchiveIntegrityError):
        fetch_object(client, bad, tmp_path / "b.br")
    assert not (tmp_path / "b.br").exists() and not list(tmp_path.glob("*.partial"))


def test_member_extraction_keeps_only_requested_members_with_provenance(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("trips.txt", "route_id,service_id,trip_id\n7,wk,1\n")
        archive.writestr("shapes.txt", "x" * 50_000)
        archive.writestr("stop_times.txt", "trip_id\n1\n")
    body = buffer.getvalue()
    feed = ArchiveObject(
        "gtfs_archive/2025/11/12/israel-public-transportation.zip", len(body), "e-2"
    )
    calls = []
    client = serve({feed.key: body}, calls)
    target = tmp_path / "schedule.zip"
    meta = extract_members(client, feed, ("trips.txt", "stop_times.txt"), target, block=1024)
    with zipfile.ZipFile(target) as local:
        assert sorted(local.namelist()) == ["stop_times.txt", "trips.txt"]
        assert local.read("stop_times.txt") == b"trip_id\n1\n"
    assert meta["key"] == feed.key and meta["size"] == len(body) and meta["etag"] == "e-2"
    assert (
        meta["members"]["trips.txt"]["sha256"]
        == hashlib.sha256(b"route_id,service_id,trip_id\n7,wk,1\n").hexdigest()
    )
    assert calls and all("range" in call.headers for call in calls)  # never the whole object
    requests = len(calls)
    again = extract_members(client, feed, ("trips.txt", "stop_times.txt"), target, block=1024)
    assert again == meta and len(calls) == requests  # cached metadata reused, no new requests


def test_service_day_window_is_local_midnight_plus_30_hours():
    assert siri_window(date(2025, 11, 12)) == (
        datetime(2025, 11, 11, 22, tzinfo=UTC),
        datetime(2025, 11, 13, 4, tzinfo=UTC),
    )
    start, end = siri_window(date(2026, 6, 10))  # summer time, UTC+3
    assert (start.hour, (end - start).total_seconds()) == (21, 30 * 3600)


def test_manifest_digest_is_order_independent_and_content_sensitive():
    a = {"key": "k1", "size": 1, "sha256": "aa"}
    b = {"key": "k2", "size": 2, "sha256": "bb"}
    assert manifest_digest([a, b]) == manifest_digest([b, a])
    assert manifest_digest([a, b]) != manifest_digest([a, b | {"sha256": "bc"}])
