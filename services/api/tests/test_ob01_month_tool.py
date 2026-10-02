"""OB-01 month driver end to end on synthetic per-day files (no archive, no downloads)."""

import json
import sys
from datetime import date, timedelta

import pytest

from opentransit.history.month import MIN_SAMPLES, DayWriter
from opentransit.history.schedule import service_origin
from tools import ob01_month

CALIBRATION = [date(2025, 11, 2) + timedelta(days=offset) for offset in range(5)]  # Sun-Thu
HELD_OUT = [date(2026, 1, 4), date(2026, 1, 5)]


def write_day(work, day, delays):
    directory = work / "days" / day.isoformat()
    writer = DayWriter(directory)
    base = service_origin(day) + 8 * 3600
    for trip, delay in enumerate(delays):
        writer.write((f"t{trip}", "7", 1, "A", base, delay, 60, ""))
        writer.write((f"t{trip}", "7", 2, "B", base + 300, delay + 30, 60, ""))
    writer.close()
    summary = {
        "serviceDate": day.isoformat(),
        "dayType": "weekday",
        "inputs": {
            "gtfsKey": f"gtfs_archive/{day:%Y/%m/%d}/israel-public-transportation.zip",
            "gtfsEtag": "e-16",
            "gtfsMembersSha256": dict.fromkeys(
                ("stop_times.txt", "trips.txt", "calendar.txt", "routes.txt"), "ab"
            ),
            "siriManifestSha256": "cd",
            "manifestFileSha256": "ef",
            "siriMinutesRead": 1790,
            "siriMinutesExpected": 1800,
            "siriMinutesMissing": 10,
        },
        "pings": {"serviceDatePings": 100},
        "matching": {
            "scheduledTrips": len(delays),
            "scheduledTripsObserved": len(delays),
            "scheduledTripCoverage": 1.0,
        },
        "calls": {"observed": 2 * len(delays)},
        "interpolationCheckAbsErrorSeconds": {"n": 1, "p10": 0, "p50": 4, "p90": 9},
        "byAgency": {"3": {"scheduledTrips": len(delays), "observedTrips": len(delays)}},
        "files": {"calls-00.csv.gz": "00"},
    }
    (directory / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


def run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["ob01_month.py", *map(str, argv)])
    return ob01_month.main()


def test_aggregate_then_validate_pins_inputs_and_scores_held_out(tmp_path, monkeypatch):
    work, results = tmp_path / "work", tmp_path / "results"
    per_day = MIN_SAMPLES // len(CALIBRATION) + 1
    for day in CALIBRATION:
        write_day(work, day, [60 * (trip % 10) for trip in range(per_day * 2)])
    for day in HELD_OUT:
        write_day(work, day, [60 * (trip % 10) for trip in range(per_day * 2)])
    month = results / "month.json"
    common = ["--raw-cache", tmp_path / "raw", "--work", work]
    assert (
        run(
            monkeypatch,
            "aggregate",
            "--start",
            "2025-11-01",
            "--end",
            "2025-11-30",
            *common,
            "--name",
            "202511",
            "--output",
            month,
        )
        == 0
    )
    report = json.loads(month.read_text(encoding="utf-8"))
    assert report["serviceDays"] == len(CALIBRATION)
    assert [pin["gtfsKey"][13:23] for pin in report["archivePins"]][0] == "2025/11/02"
    assert report["keys"]["delayKeysPublishable"] == 2
    assert report["keys"]["segmentKeysPublishable"] == 1
    assert len(report["tables"]["files"]) == 32
    with pytest.raises(SystemExit):  # never overwrite a result or a table set
        run(
            monkeypatch,
            "aggregate",
            "--start",
            "2025-11-01",
            "--end",
            "2025-11-30",
            *common,
            "--name",
            "202511",
            "--output",
            results / "other.json",
        )

    held_out = results / "held-out.json"
    assert (
        run(
            monkeypatch,
            "validate",
            "--start",
            "2026-01-01",
            "--end",
            "2026-01-31",
            *common,
            "--calibration",
            "202511",
            "--calibration-report",
            month,
            "--output",
            held_out,
        )
        == 0
    )
    check = json.loads(held_out.read_text(encoding="utf-8"))
    assert check["heldOut"]["serviceDays"] == len(HELD_OUT)
    band = check["stopDelay"]["byStratum"]["publishable"]
    assert band["observations"] == 2 * 2 * len(HELD_OUT) * per_day
    assert 0.0 < band["belowP50"] < 1.0  # same distribution: roughly central
    segment = check["segmentRunTime"]["byStratum"]["publishable"]
    assert segment["medianAbsErrorSeconds"]["calibrationP50"] <= 30


def test_review_targets_merge_pilot_pairs_and_slowest_rows_by_route_and_stops():
    row = {
        "routeId": "7",
        "fromStopId": "A",
        "toStopId": "B",
        "hour": 8,
        "dayType": "weekday",
        "samples": 30,
        "coverage": 0.9,
        "serviceDays": 5,
        "scheduledSecondsMedian": 120,
        "runP10Seconds": 100,
        "runP50Seconds": 900,
        "runP90Seconds": 1500,
        "publishable": True,
        "ratioP50": 7.5,
    }
    report = {
        "pilotOutlierStopPairs": [row],
        "slowestPublishableSegmentsVsSchedule": [row | {"hour": 9}, row | {"routeId": "8"}],
    }
    targets = ob01_month.review_targets(report, top=10)
    assert [(t["routeId"], [r["hour"] for r in t["monthRows"]]) for t in targets] == [
        ("7", [8, 9]),
        ("8", [8]),
    ]
    stops = {
        "A": {"name": "a", "lat": 31.78, "lon": 35.23},
        "B": {"name": "b", "lat": 32.0, "lon": 35.0},
    }
    assert ob01_month.nearest_stop(stops, (31.7801, 35.23))["stopId"] == "A"
