"""Export the OpenAPI snapshot and `synthetic-*` fixtures from the API's own app.

The API's test harness serves a synthetic GTFS feed in fixture mode with a mocked
engine, in process: no Docker, network or generation. This captures response shapes
the recorded evidence lacks (status, nearby stops, routes, patterns, a 429). The data
is synthetic and every fixture says so; it is not real-API evidence.

Run from the repository root (pytest supplies the API suite's conftest fixtures):

    PYTHONPATH=services/api/tests uv run --project services/api --locked \
        pytest apps/web/scripts/synthetic_api_fixtures.py -p conftest -q -p no:cacheprovider
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from test_reference_api import reference_client

WEB = Path(__file__).resolve().parents[1]
FIXTURES = WEB / "src" / "api" / "fixtures"
SANITISED_REQUEST_ID = "0" * 32


def _sanitise(value):
    if isinstance(value, list):
        return [_sanitise(item) for item in value]
    if isinstance(value, dict):
        return {
            key: SANITISED_REQUEST_ID
            if key == "requestId" and isinstance(item, str)
            else _sanitise(item)
            for key, item in value.items()
        }
    return value


def _write(path: Path, value) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")  # LF on every platform


def test_export(manifest, engine_route):
    written = {}

    def capture(name, client, method, path, params=None, keep_headers=()):
        response = client.request(method, path, params=params)
        fixture = {
            "request": {"method": method, "path": path, "params": params, "body": None},
            "status": response.status_code,
            "body": _sanitise(response.json()),
        }
        headers = {key: response.headers[key] for key in keep_headers if key in response.headers}
        if headers:
            fixture["headers"] = headers
        _write(FIXTURES / f"{name}.json", fixture)
        written[name] = response
        return response

    with reference_client(manifest, engine_route) as client:
        schema = client.get("/openapi.json").json()
        (WEB / "openapi").mkdir(exist_ok=True)
        _write(WEB / "openapi" / "openapi.json", schema)

        capture("synthetic-status-ready", client, "GET", "/v1/status")
        first = capture(
            "synthetic-stops-near-page-1",
            client,
            "GET",
            "/v1/stops",
            {"near": "32.08,34.78", "limit": 1},
        )
        capture(
            "synthetic-stops-near-page-2",
            client,
            "GET",
            "/v1/stops",
            {"near": "32.08,34.78", "limit": 1, "cursor": first.json()["page"]["nextCursor"]},
        )
        capture(
            "synthetic-stops-bbox", client, "GET", "/v1/stops", {"bbox": "34.77,32.07,34.79,32.09"}
        )
        capture("synthetic-stop-station", client, "GET", "/v1/stops/mot:stop:station")
        capture("synthetic-routes", client, "GET", "/v1/routes", {"operatorId": "op_1"})
        capture("synthetic-route", client, "GET", "/v1/routes/mot:route:bus_7")
        capture("synthetic-route-patterns", client, "GET", "/v1/routes/mot:route:bus_7/patterns")
        capture("synthetic-problem-stop-not-found", client, "GET", "/v1/stops/mot:stop:missing")
        capture("synthetic-problem-invalid-request", client, "GET", "/v1/stops", {"near": "99,35"})
        for _ in range(30):
            if client.get("/v1/status").status_code == 429:
                break
        capture(
            "synthetic-problem-rate-limited",
            client,
            "GET",
            "/v1/status",
            keep_headers=("retry-after",),
        )

    with _engine_down(manifest, engine_route) as client:
        capture("synthetic-status-routing-unavailable", client, "GET", "/v1/status")

    expired_manifest = _fresh_manifest(manifest, "expired")
    with reference_client(
        expired_manifest, engine_route, now=datetime(2026, 11, 1, tzinfo=UTC)
    ) as client:
        capture("synthetic-status-expired", client, "GET", "/v1/status")
        capture(
            "synthetic-problem-feed-expired", client, "GET", "/v1/routes", {"operatorId": "op_1"}
        )

    assert all(
        response.status_code == 200 for name, response in written.items() if "-problem-" not in name
    )
    assert written["synthetic-status-ready"].json()["data"]["ready"] is True
    assert written["synthetic-problem-rate-limited"].status_code == 429
    assert (
        written["synthetic-status-routing-unavailable"].json()["data"]["routing"] == "unavailable"
    )
    assert written["synthetic-problem-feed-expired"].json()["code"] == "FEED_EXPIRED"

    manifest_path = FIXTURES / "manifest.json"
    entries = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    harness = WEB.parents[1] / "services" / "api" / "tests" / "test_reference_api.py"
    for name in written:
        entries[name] = {
            "provenance": "synthetic",
            "source": (
                "services/api/tests/test_reference_api.py::reference_client "
                "(fixture mode, synthetic feed, mocked engine)"
            ),
            "sourceSha256": hashlib.sha256(harness.read_bytes()).hexdigest(),
            "exporter": "apps/web/scripts/synthetic_api_fixtures.py",
        }
    _write(manifest_path, dict(sorted(entries.items())))


def _fresh_manifest(manifest: Path, name: str) -> Path:
    """Copy the base manifest into its own directory; reference_client writes beside it."""
    directory = manifest.parent / name
    directory.mkdir()
    target = directory / "manifest.json"
    target.write_text(manifest.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _engine_down(manifest: Path, engine_route):
    return reference_client(
        _fresh_manifest(manifest, "engine-down"), engine_route, engine_down=True
    )
