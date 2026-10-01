import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from opentransit.core.generation import Generation, instant
from opentransit.motis import normalize

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "motis-v2.11.2"


def generation(start="2026-10-24T20:00:00+00:00", end="2026-10-25T03:00:00+00:00"):
    now = datetime(2026, 9, 30, tzinfo=UTC)
    return Generation(
        id="time-test",
        built_at=now,
        validated_at=now,
        coverage_from=instant(start),
        coverage_until=instant(end),
        engine_digest="sha256:" + "a" * 64,
    )


def location(name, lat, lon):
    return {"name": name, "lat": lat, "lon": lon}


def walk(start, end, origin, destination, distance):
    return {
        "mode": "WALK",
        "from": origin,
        "to": destination,
        "scheduledStartTime": start,
        "scheduledEndTime": end,
        "distance": distance,
    }


def test_real_engine_first_two_samples_keep_recorded_contract_and_provenance():
    result_path = Path(__file__).parents[1] / "results" / "m1-20260930.json"
    results = json.loads(result_path.read_text(encoding="utf-8"))
    provenance = json.loads((FIXTURE_DIR / "responses-provenance.json").read_text(encoding="utf-8"))
    fixture_path = FIXTURE_DIR / "real-plan-depart-at.json"
    fixture_bytes = fixture_path.read_bytes()
    assert hashlib.sha256(fixture_bytes).hexdigest() == provenance["cases"][0]["fixtureSha256"]
    assert provenance["generationId"] == results["generation"]["generationId"]
    for source_name in ("israel-public-transportation.zip", "TripIdToDate.zip"):
        assert (
            provenance["inputs"][source_name]["sha256"]
            == results["generation"]["inputs"][source_name]["sha256"]
        )

    raw = json.loads(fixture_bytes)
    source_response = raw["itineraries"]
    assert len(source_response) == 3
    gen = generation(
        results["generation"]["coverage"]["from"],
        results["generation"]["coverage"]["until"],
    )
    departure = instant("2026-10-01T08:00:00+03:00")
    first, second = [normalize(source_response[i], gen, departure) for i in (0, 1)]

    assert first.durationSeconds == results["actualExample"]["durationSeconds"]
    assert first.transfers == results["actualExample"]["transfers"]
    assert (
        first.timing.scheduledDeparture.isoformat()
        == results["actualExample"]["scheduledDeparture"]
    )
    assert first.timing.scheduledArrival.isoformat() == results["actualExample"]["scheduledArrival"]
    assert second.durationSeconds == 7620
    assert len(first.legs) == 7 and len(second.legs) == 11
    with pytest.raises(ValueError, match="Unexpected live data"):
        normalize(source_response[2], gen, departure)


def test_fall_back_elapsed_times_waits_walk_and_gtfs_service_identity():
    a = location("A", 32.0, 34.0)
    b = location("B", 32.01, 34.01)
    c = location("C", 32.02, 34.02)
    d = location("D", 32.03, 34.03)
    legs = [
        walk("2026-10-25T01:50:00+03:00", "2026-10-25T01:10:00+02:00", a, b, 500),
        {
            "mode": "BUS",
            "from": b,
            "to": c,
            "scheduledStartTime": "2026-10-25T01:20:00+02:00",
            "scheduledEndTime": "2026-10-25T01:50:00+02:00",
            "distance": 1000,
            "agencyId": "1",
            "agencyName": "Test operator",
            "routeId": "route-1",
            "tripId": "20261024_24:20_mot60day_521247",
        },
        walk("2026-10-25T02:10:00+02:00", "2026-10-25T02:20:00+02:00", c, d, 400),
    ]
    journey = normalize(
        {"transfers": 0, "legs": legs},
        generation(),
        instant("2026-10-25T01:40:00+03:00"),
    )

    assert [leg.durationSeconds for leg in journey.legs] == [1200, 1800, 600]
    assert journey.durationSeconds == 5400
    assert journey.walkingSeconds == 1800
    assert journey.legs[1].timing.scheduledDeparture.isoformat() == "2026-10-25T01:20:00+02:00"
    transit = journey.legs[1].transit
    assert transit.engineTripId == "20261024_24:20_mot60day_521247"
    assert transit.sourceTripId == "521247"
    assert transit.serviceDate.isoformat() == "2026-10-24"
    assert transit.startTime == "24:20"


def test_generation_coverage_and_freshness_compare_fallback_instants():
    gen = generation("2026-10-25T01:30:00+03:00", "2026-10-25T01:30:00+02:00")
    assert gen.contains(instant("2026-10-25T01:15:00+02:00"))

    checked = datetime.fromisoformat("2026-10-25T01:50:00+03:00")
    gen = Generation(
        id="freshness-test",
        built_at=checked,
        validated_at=checked,
        coverage_from=instant("2026-10-24T00:00:00+00:00"),
        coverage_until=instant("2026-10-26T00:00:00+00:00"),
        engine_digest="sha256:" + "a" * 64,
        source_checked_at=checked,
        source_check_recorded=True,
    )
    now = datetime.fromisoformat("2026-10-25T01:10:00+02:00")
    assert gen.freshness(now) == "current"
