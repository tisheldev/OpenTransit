"""S8: the built web client at /app/ (off by default, outside the API contract)."""

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from opentransit.api.app import create_app
from opentransit.api.client import CONTENT_SECURITY_POLICY
from opentransit.api.rate_limit import classify
from opentransit.config import Settings

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob: "
    "https://tiles.openfreemap.org; font-src 'self'; connect-src 'self' "
    "https://tiles.openfreemap.org; worker-src 'self' blob:; manifest-src 'self'; "
    "object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
INDEX = "<!doctype html><title>OpenTransit</title>"
SECRET = "outside the client directory"


@pytest.fixture
def dist(tmp_path):
    """A Vite-shaped build: hashed assets, un-hashed public files, a secret beside it."""
    (tmp_path / "secret.txt").write_text(SECRET, encoding="utf-8")
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX, encoding="utf-8")
    (root / "icon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    (root / "manifest.webmanifest").write_text('{"name": "OpenTransit"}', encoding="utf-8")
    (root / "assets" / "index-AbC123.js").write_text("export {};", encoding="utf-8")
    (root / "assets" / "index-AbC123.js.map").write_text('{"version": 3}', encoding="utf-8")
    (root / "assets" / "index-AbC123.css").write_text("body{}", encoding="utf-8")
    (root / "assets" / "style-AbC123.json").write_text("{}", encoding="utf-8")
    (root / "assets" / "blob-AbC123.bin").write_bytes(b"\x00\x01")
    return root


def make_client(tmp_path, **settings) -> TestClient:
    # No lifespan: no generation is loaded, so /readyz is 503 while files still serve.
    return TestClient(create_app(Settings(tmp_path / "missing-manifest.json", **settings)))


def assert_security_headers(response) -> None:
    assert response.headers["content-security-policy"] == CSP
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_csp_matches_the_contract_verbatim():
    assert CONTENT_SECURITY_POLICY == CSP


def test_off_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENTRANSIT_CLIENT_DIR", raising=False)
    assert Settings.from_env().client_dir is None
    monkeypatch.setenv("OPENTRANSIT_CLIENT_DIR", "")
    assert Settings.from_env().client_dir is None
    client = make_client(tmp_path)
    for path in ("/app", "/app/", "/app/index.html"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 404
        assert "content-security-policy" not in response.headers


def test_environment_enables_the_mount(tmp_path, dist, monkeypatch):
    monkeypatch.setenv("OPENTRANSIT_CLIENT_DIR", str(dist))
    assert Settings.from_env().client_dir == dist


def test_serves_index_and_redirects_the_bare_prefix(tmp_path, dist):
    client = make_client(tmp_path, client_dir=dist)
    redirect = client.get("/app", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "/app/"
    assert_security_headers(redirect)
    for path in ("/app/", "/app/index.html"):
        page = client.get(path)
        assert page.status_code == 200
        assert page.text == INDEX
        assert page.headers["content-type"] == "text/html; charset=utf-8"
        assert page.headers["cache-control"] == "no-store"
        assert "x-request-id" in page.headers
        assert_security_headers(page)
    assert client.head("/app/").status_code == 200
    assert client.get("/readyz").status_code == 503


@pytest.mark.parametrize(
    ("path", "content_type", "cache"),
    [
        ("/app/assets/index-AbC123.js", "text/javascript; charset=utf-8", "immutable"),
        ("/app/assets/index-AbC123.css", "text/css; charset=utf-8", "immutable"),
        ("/app/assets/index-AbC123.js.map", "application/json", "immutable"),
        ("/app/assets/style-AbC123.json", "application/json", "immutable"),
        ("/app/assets/blob-AbC123.bin", "application/octet-stream", "immutable"),
        ("/app/icon.svg", "image/svg+xml", "no-cache"),
        ("/app/manifest.webmanifest", "application/manifest+json", "no-cache"),
    ],
)
def test_content_types_and_cache_rules(tmp_path, dist, path, content_type, cache):
    client = make_client(tmp_path, client_dir=dist)
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"] == content_type
    expected = "public, max-age=31536000, immutable" if cache == "immutable" else cache
    assert response.headers["cache-control"] == expected
    assert_security_headers(response)


def test_revalidation_keeps_the_rules(tmp_path, dist):
    client = make_client(tmp_path, client_dir=dist)
    first = client.get("/app/assets/index-AbC123.js")
    again = client.get(
        "/app/assets/index-AbC123.js", headers={"If-None-Match": first.headers["etag"]}
    )
    assert again.status_code == 304
    assert again.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert_security_headers(again)


@pytest.mark.parametrize(
    "path",
    [
        "/app/missing.js",
        "/app/assets/",
        "/app/assets",
        "/app/compare",  # hash routing: no SPA fallback to index.html
        "/app/%2e%2e/secret.txt",
        "/app/assets/%2e%2e/%2e%2e/secret.txt",
        "/app/..%2fsecret.txt",
        "/app/..%5csecret.txt",
        "/app/assets/..%5c..%5csecret.txt",
        "/app/%2e%2e%5csecret.txt",
        "/app/C:%5cWindows%5cwin.ini",
        "/app/%00",
    ],
)
def test_unknown_directories_and_traversal_are_404(tmp_path, dist, path):
    client = make_client(tmp_path, client_dir=dist)
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 404
    assert SECRET not in response.text
    assert INDEX not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert_security_headers(response)


async def _raw_get(app, path: str) -> tuple[int, bytes]:
    """Send an unnormalised path straight to the ASGI app (clients collapse '..')."""
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
        "client": ("203.0.113.5", 40000),
        "server": ("testserver", 80),
        "state": {},
    }
    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], body


@pytest.mark.parametrize(
    "path",
    [
        "/app/../secret.txt",
        "/app/assets/../../secret.txt",
        "/app/..\\secret.txt",
        "/app/../v1/status",
    ],
)
def test_literal_dot_segments_cannot_escape(tmp_path, dist, path):
    app = create_app(Settings(tmp_path / "missing-manifest.json", client_dir=dist))
    status, body = asyncio.run(_raw_get(app, path))
    assert status == 404
    assert SECRET.encode() not in body


def test_openapi_is_byte_identical_with_and_without_the_client(tmp_path, dist):
    without = make_client(tmp_path).get("/openapi.json")
    with_client = make_client(tmp_path, client_dir=dist).get("/openapi.json")
    assert without.status_code == with_client.status_code == 200
    assert with_client.content == without.content
    assert all(not path.startswith("/app") for path in with_client.json()["paths"])


def test_client_files_are_not_rate_limited(tmp_path, dist):
    client = make_client(
        tmp_path, client_dir=dist, rate_limit_standard_burst=1, rate_limit_standard_per_minute=1
    )
    for _ in range(10):
        assert client.get("/app/").status_code == 200
        assert client.get("/app/assets/index-AbC123.js").status_code == 200
        assert client.get("/app", follow_redirects=False).status_code == 307
    assert client.get("/v1/status").status_code != 429
    assert client.get("/v1/status").status_code == 429
    assert classify("GET", "/app/") is None
    assert classify("GET", "/app") is None
    assert classify("GET", "/apple") == "standard"
    assert classify("GET", "/application/x") == "standard"


def test_only_get_and_head(tmp_path, dist):
    client = make_client(tmp_path, client_dir=dist)
    response = client.post("/app/index.html", content=b"")
    assert response.status_code == 405
    assert_security_headers(response)


def test_request_log_keeps_its_shape(tmp_path, dist, caplog):
    client = make_client(tmp_path, client_dir=dist)
    with caplog.at_level(logging.INFO):
        client.get("/app/assets/index-AbC123.js")
    lines = [r.getMessage() for r in caplog.records if "request_id=" in r.getMessage()]
    assert lines
    assert all(" status=200 duration_ms=" in line for line in lines)


@pytest.mark.parametrize("layout", ["missing", "file", "no-index"])
def test_invalid_client_dir_fails_startup(tmp_path, monkeypatch, layout):
    target = tmp_path / "client"
    if layout == "file":
        target.write_text("not a directory", encoding="utf-8")
    elif layout == "no-index":
        (target / "assets").mkdir(parents=True)
    with pytest.raises(ValueError, match="OPENTRANSIT_CLIENT_DIR"):
        Settings(tmp_path / "manifest.json", client_dir=target)
    monkeypatch.setenv("OPENTRANSIT_CLIENT_DIR", str(target))
    with pytest.raises(ValueError, match="OPENTRANSIT_CLIENT_DIR"):
        Settings.from_env()
