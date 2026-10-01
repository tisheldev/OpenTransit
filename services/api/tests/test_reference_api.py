import json
from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient
from test_reference import synthetic_feed

from opentransit.api.app import create_app
from opentransit.build.generations import _tree_artifact
from opentransit.build.prepare import sha256
from opentransit.config import Settings
from opentransit.reference import build_reference


def reference_client(
    manifest, engine_route, *, now=None, corrupt=False, engine_down=False, engine=None
):
    feed = synthetic_feed(manifest.parent / "feed.zip")
    info = json.loads(manifest.read_text(encoding="utf-8"))
    database = manifest.parent / "reference.sqlite"
    build_reference(feed, database, info["generationId"])
    config = manifest.parent / "config.yml"
    config.write_text("synthetic config", encoding="utf-8")
    graph = manifest.parent / "motis"
    graph.mkdir()
    (graph / "graph.bin").write_bytes(b"synthetic graph")
    info["artifacts"] = {
        "reference": {"path": "reference.sqlite", "sha256": "bad" if corrupt else sha256(database)},
        "config": {"path": "config.yml", "sha256": sha256(config)},
        "motis": _tree_artifact(graph),
    }
    info["inputs"] = {"israel-public-transportation.zip": {"sha256": sha256(feed)}}
    manifest.write_text(json.dumps(info), encoding="utf-8")
    probe = manifest.parent / "probe.json"
    probe.write_text(
        json.dumps(
            {
                "generationId": info["generationId"],
                "engineOrigin": "http://127.0.0.1:58081",
                "engineDigest": info["engineDigest"],
                "status": "passed",
                "graphTreeSha256": info["artifacts"]["motis"]["sha256"],
                "configSha256": sha256(config),
                "referenceSha256": sha256(database),
            }
        ),
        encoding="utf-8",
    )

    handler = engine

    def engine(request):
        if engine_down:
            raise httpx.ConnectError("sentinel-private-host", request=request)
        if request.url.params.get("fromPlace") == "32.0836,34.7981":
            return httpx.Response(200, json={"itineraries": [], "direct": []})
        return httpx.Response(200, json=engine_route)

    return TestClient(
        create_app(
            Settings(manifest, probe_path=probe),
            transport=httpx.MockTransport(handler or engine),
            clock=lambda: now or datetime(2026, 9, 30, 9, tzinfo=UTC),
        )
    )


def test_reference_discovery_patterns_and_truthful_readiness(manifest, engine_route):
    with reference_client(manifest, engine_route) as client:
        assert client.get("/readyz").status_code == 200
        status = client.get("/v1/status").json()
        assert status["data"]["ready"]
        assert status["data"]["realtime"] == status["data"]["alerts"] == "not_enabled"
        response = client.get("/v1/stops", params={"near": "32.08,34.78", "limit": 1})
        assert response.status_code == 200
        first = response.json()
        assert first["data"][0]["stopId"] == "mot:stop:station"
        assert first["meta"]["generationId"] == "synthetic-test"
        assert first["meta"]["mode"] == "fixture"
        assert first["meta"]["capabilities"]["alerts"] == "not_enabled"
        cursor = first["page"]["nextCursor"]
        second = client.get(
            "/v1/stops", params={"near": "32.08,34.78", "limit": 1, "cursor": cursor}
        )
        assert second.status_code == 200
        assert second.json()["data"][0]["stopId"] != first["data"][0]["stopId"]
        wrong = client.get("/v1/stops", params={"near": "32.081,34.78", "cursor": cursor})
        assert wrong.status_code == 422
        assert wrong.json()["code"] == "INVALID_CURSOR"
        station = client.get("/v1/stops/mot:stop:station").json()["data"]
        assert len(station["children"]) == 2
        assert station["routes"][0]["routeId"] == "mot:route:bus_7"
        patterns = client.get("/v1/routes/mot:route:bus_7/patterns").json()["data"]
        loop = next(pattern for pattern in patterns if pattern["directionId"] == "0")
        assert loop["stops"][0]["stopId"] == loop["stops"][2]["stopId"]
        assert loop["stops"][1]["pickupType"] == 1
        assert client.get("/v1/routes/mot:route:missing/patterns").status_code == 404


def test_bounds_safe_errors_and_empty_results(manifest, engine_route, caplog):
    with reference_client(manifest, engine_route) as client:
        for params in (
            {},
            {"near": "32,35", "bbox": "34,31,35,32"},
            {"near": "99,35"},
            {"near": "32,35", "radius": 5001},
            {"bbox": "34,29,36,34"},
            {"near": "nan,35"},
            {"near": "32,35", "limit": 101},
        ):
            response = client.get("/v1/stops", params=params)
            assert response.status_code == 422
            assert response.headers["content-type"] == "application/problem+json"
        empty = client.get("/v1/stops", params={"near": "31.71234567,35.21234567"})
        assert empty.status_code == 200 and empty.json()["data"] == []
        assert "31.71234567" not in caplog.text
        assert client.get("/v1/stops/mot:stop:missing").status_code == 404
        assert client.get("/v1/stops/raw-id").status_code == 422


def test_bad_artifact_cannot_become_ready_or_empty(manifest, engine_route):
    with reference_client(manifest, engine_route, corrupt=True) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503
        assert client.get("/v1/status").json()["data"]["staticData"] == "unavailable"
        assert client.get("/v1/routes").status_code == 503


def test_engine_outage_disables_readiness_but_reference_is_usable(manifest, engine_route):
    with reference_client(manifest, engine_route, engine_down=True) as client:
        assert client.get("/readyz").status_code == 503
        response = client.get("/v1/status")
        assert response.json()["data"]["routing"] == "unavailable"
        assert "sentinel-private-host" not in response.text
        assert client.get("/v1/routes", params={"operatorId": "op_1"}).status_code == 200


def test_expired_reference_is_unavailable_not_empty(manifest, engine_route):
    with reference_client(manifest, engine_route, now=datetime(2026, 11, 1, tzinfo=UTC)) as client:
        assert client.get("/readyz").status_code == 503
        response = client.get("/v1/routes")
        assert response.status_code == 503 and response.json()["code"] == "FEED_EXPIRED"
