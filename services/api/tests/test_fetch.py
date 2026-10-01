import hashlib
import io
import zipfile
from datetime import UTC, datetime, timedelta

from opentransit.build.fetch import SourceSpec, fetch_sources


def zip_bytes(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class Response:
    status = 200
    headers = {"Last-Modified": "Wed, 30 Sep 2026 00:00:00 GMT"}

    def __init__(self, body):
        self.body = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.body.close()

    def read(self, size):
        return self.body.read(size)


def test_fetch_records_hash_and_renews_check_without_replacing_identical_input(
    tmp_path, monkeypatch
):
    body = zip_bytes({"feed.txt": "id\n1\n"})
    requested = []

    def urlopen(request, timeout):
        requested.append(request.get_method())
        return Response(body)

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    spec = {"feed": SourceSpec("feed.zip", "https://example.test/feed", ("feed.txt",))}
    first_time = datetime(2026, 9, 30, tzinfo=UTC)
    first = fetch_sources(tmp_path / "inputs", spec, now=first_time)
    first_path = first.results["feed"].path
    second = fetch_sources(tmp_path / "inputs", spec, now=first_time + timedelta(hours=1))

    assert requested == ["GET", "GET"]
    assert first.results["feed"].status == "new"
    assert second.results["feed"].status == "unchanged"
    assert second.results["feed"].path == first_path
    assert second.results["feed"].acquired_at == first_time.isoformat()
    assert second.results["feed"].checked_at == (first_time + timedelta(hours=1)).isoformat()
    assert second.results["feed"].sha256 == hashlib.sha256(body).hexdigest()
    assert len(list((tmp_path / "inputs").glob("*/objects/feed/*"))) == 1


def test_fetch_keeps_changed_sources_and_failed_archives_non_destructive(tmp_path, monkeypatch):
    bodies = [zip_bytes({"feed.txt": "id\n1\n"}), zip_bytes({"feed.txt": "id\n2\n"}), b"not a zip"]
    original = bodies[0]

    def urlopen(request, timeout):
        return Response(bodies.pop(0))

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    spec = {"feed": SourceSpec("feed.zip", "https://example.test/feed", ("feed.txt",))}
    base_time = datetime(2026, 9, 30, tzinfo=UTC)
    first = fetch_sources(tmp_path / "inputs", spec, now=base_time).results["feed"]
    changed = fetch_sources(tmp_path / "inputs", spec, now=base_time + timedelta(days=1)).results[
        "feed"
    ]
    failed = fetch_sources(tmp_path / "inputs", spec, now=base_time + timedelta(days=2)).results[
        "feed"
    ]

    assert first.status == "new"
    assert changed.status == "changed"
    assert first.path.exists() and changed.path.exists()
    assert failed.status == "failed"
    assert first.path.read_bytes() == original
    assert list((tmp_path / "inputs").glob("*/.staging/*.part")) == []


def test_osm_weekly_policy_reuses_last_verified_input_without_get(tmp_path, monkeypatch):
    body = b"pbf bytes"
    calls = []

    def urlopen(request, timeout):
        calls.append(request.get_method())
        return Response(body)

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    spec = {
        "osm": SourceSpec("region.osm.pbf", "https://example.test/osm", cadence=timedelta(days=7))
    }
    now = datetime(2026, 9, 30, tzinfo=UTC)
    first = fetch_sources(tmp_path / "inputs", spec, now=now).results["osm"]
    skipped = fetch_sources(tmp_path / "inputs", spec, now=now + timedelta(days=2)).results["osm"]

    assert calls == ["GET"]
    assert first.status == "new"
    assert skipped.status == "skipped"
    assert skipped.path == first.path
    assert skipped.checked_at == first.checked_at
