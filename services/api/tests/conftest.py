"""Small synthetic engine response; no test result is live or H3 evidence."""

import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from opentransit.api.app import create_app
from opentransit.config import Settings

NOW = datetime(2026, 9, 30, 9, tzinfo=UTC)


@pytest.fixture
def manifest(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "state": "ready",
                "generationId": "synthetic-test",
                "engineDigest": "sha256:" + "a" * 64,
                "mode": "fixture",
                "builtAt": NOW.isoformat(),
                "validatedAt": NOW.isoformat(),
                "coverage": {
                    "from": "2026-09-29T00:00:00+03:00",
                    "until": "2026-10-30T00:00:00+02:00",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def query():
    return {
        "from": {"kind": "coordinate", "latitude": 32.0757, "longitude": 34.7748},
        "to": {"kind": "coordinate", "latitude": 32.0831, "longitude": 34.8050},
        "departAt": "2026-09-30T08:00:00+03:00",
    }


@pytest.fixture
def engine_route():
    start = {"name": "Synthetic origin", "lat": 32.0757, "lon": 34.7748, "stopId": "mot60day_1"}
    end = {"name": "Synthetic destination", "lat": 32.0831, "lon": 34.8050, "stopId": "mot60day_2"}
    return {
        "itineraries": [
            {
                "transfers": 0,
                "legs": [
                    {
                        "mode": "BUS",
                        "from": start,
                        "to": end,
                        "scheduledStartTime": "2026-09-30T05:10:00Z",
                        "scheduledEndTime": "2026-09-30T05:30:00Z",
                        "realTime": False,
                        "cancelled": False,
                        "distance": 1000,
                        "agencyId": "1",
                        "agencyName": "Synthetic operator",
                        "routeId": "mot60day_7",
                        "routeShortName": "7",
                        "headsign": "Synthetic destination",
                        "tripId": "20260930_08:00_mot60day_123_300926",
                        "legGeometry": {"points": "q{vd|@{rniaA}DrB", "precision": 6},
                    }
                ],
            }
        ],
        "direct": [],
    }


@pytest.fixture
def client_factory(manifest):
    def make(handler, now=NOW, deadline=1.5, path=None):
        app = create_app(
            Settings(
                path or manifest,
                engine_timeout_seconds=deadline * 0.8,
                journey_deadline_seconds=deadline,
            ),
            transport=httpx.MockTransport(handler),
            clock=lambda: now,
        )
        return TestClient(app)

    return make
