from conftest import NOW
from fastapi.testclient import TestClient

from opentransit.api.app import create_app
from opentransit.config import Settings


def test_playground_is_opt_in_and_not_part_of_api_contract(manifest):
    for enabled in (False, True):
        app = create_app(Settings(manifest, playground_enabled=enabled), clock=lambda: NOW)
        with TestClient(app) as client:
            page = client.get("/playground/")
            assert page.status_code == (200 if enabled else 404)
            paths = client.get("/openapi.json").json()["paths"]
            assert {
                "/healthz",
                "/v1/journeys",
            } <= set(paths)
            assert all(not path.startswith("/playground") for path in paths)
            if enabled:
                assert "Journey playground" in page.text
                for asset in (
                    "app.mjs",
                    "time.mjs",
                    "style.css",
                    "vendor/leaflet.js",
                    "explorer.mjs",
                    "explorer-request.mjs",
                    "explorer.css",
                ):
                    assert client.get("/playground/" + asset).status_code == 200
                explorer = client.get("/playground/explorer.html")
                assert explorer.status_code == 200
                assert "API explorer" in explorer.text
            else:
                assert client.get("/playground/explorer.html").status_code == 404


def test_playground_enable_environment_is_explicit(monkeypatch):
    monkeypatch.delenv("OPENTRANSIT_PLAYGROUND", raising=False)
    assert not Settings.from_env().playground_enabled
    monkeypatch.setenv("OPENTRANSIT_PLAYGROUND", "1")
    assert Settings.from_env().playground_enabled
