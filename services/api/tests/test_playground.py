from fastapi.testclient import TestClient

from opentransit.api.app import create_app
from opentransit.config import Settings


def test_playground_is_opt_in_and_not_part_of_api_contract(manifest):
    for enabled in (False, True):
        with TestClient(create_app(Settings(manifest, playground_enabled=enabled))) as client:
            page = client.get("/playground/")
            assert page.status_code == (200 if enabled else 404)
            assert set(client.get("/openapi.json").json()["paths"]) == {
                "/healthz",
                "/v1/journeys",
            }
            if enabled:
                assert "Journey playground" in page.text
                for asset in ("app.mjs", "time.mjs", "style.css", "vendor/leaflet.js"):
                    assert client.get("/playground/" + asset).status_code == 200


def test_playground_enable_environment_is_explicit(monkeypatch):
    monkeypatch.delenv("OPENTRANSIT_PLAYGROUND", raising=False)
    assert not Settings.from_env().playground_enabled
    monkeypatch.setenv("OPENTRANSIT_PLAYGROUND", "1")
    assert Settings.from_env().playground_enabled
