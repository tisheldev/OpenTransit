import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest


@pytest.mark.integration
def test_real_dizengoff_to_technion():
    base = os.getenv("OPENTRANSIT_TEST_URL")
    if not base:
        pytest.skip("Set OPENTRANSIT_TEST_URL for the explicit real-data integration test")
    day = datetime.now(ZoneInfo("Asia/Jerusalem")) + timedelta(days=1)
    departure = os.getenv(
        "OPENTRANSIT_TEST_DEPART_AT",
        day.replace(hour=8, minute=0, second=0, microsecond=0).isoformat(),
    )
    response = httpx.post(
        base + "/v1/journeys",
        json={
            "from": {"kind": "coordinate", "latitude": 32.0757, "longitude": 34.7748},
            "to": {"kind": "coordinate", "latitude": 32.7775, "longitude": 35.0219},
            "departAt": departure,
        },
        timeout=10,
        trust_env=False,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data"]["outcome"] == "routes_found"
    assert body["meta"]["mode"] == "real"
    assert body["meta"]["capabilities"]["realtime"] == "not_enabled"
    journey = body["data"]["journeys"][0]
    assert any(leg["kind"] == "transit" for leg in journey["legs"])
    assert all(leg["timing"]["timingState"] == "scheduled" for leg in journey["legs"])
    assert journey["timing"]["scheduledArrival"] > journey["timing"]["scheduledDeparture"]
