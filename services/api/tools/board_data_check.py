"""Live check of the board data additions against a running API (read-only HTTP).

Exercises the fields and endpoints added for the eight approved client boards (client
design, 11 November 2026) and writes a JSON evidence file. It only sends GET requests and
journey searches; it changes nothing on the API or engine.

    uv run --project services/api --locked python services/api/tools/board_data_check.py \
        --api http://127.0.0.1:8510 --corpus <probe-queries.json> --output <results json>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx

from opentransit.api.docs import (
    DeparturesResponse,
    NearbyDeparturesResponse,
    StopLinesResponse,
    TripResponse,
)
from opentransit.api.schemas import JourneyResponse

# Dizengoff Center/Dizengoff (bus) and Tel Aviv Savidor Center (rail), as in the boards.
BUS_STOP = "mot:stop:13583"
RAIL_STOP = "mot:stop:37358"
NEAR = {"dizengoff-center": "32.0755,34.7751", "savidor-center": "32.0835,34.7981"}


def timed(client: httpx.Client, method: str, path: str, **kwargs):
    started = time.perf_counter()
    response = client.request(method, path, **kwargs)
    return response, round((time.perf_counter() - started) * 1000, 1)


def check(name: str, ok: bool, detail: dict, checks: list) -> None:
    checks.append({"check": name, "status": "PASS" if ok else "FAIL", **detail})


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--when", required=True, help="explicit-offset time inside coverage")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    checks: list[dict] = []
    client = httpx.Client(base_url=args.api, timeout=30)
    status = client.get("/v1/status").json()

    # API-C3 departures, and the routeId filter (board 6: next of the same line).
    response, ms = timed(
        client, "GET", f"/v1/stops/{BUS_STOP}/departures", params={"from": args.when, "limit": 20}
    )
    body = response.json()
    DeparturesResponse.model_validate(body)
    items = body["data"]
    check(
        "departures carry operator and mode (API-C3)",
        response.status_code == 200
        and bool(items)
        and all(i["operatorId"] and i["operatorName"] and i["mode"] for i in items),
        {
            "stop": BUS_STOP,
            "items": len(items),
            "ms": ms,
            "operators": sorted(Counter(i["operatorName"] for i in items).items()),
            "modes": sorted(Counter(i["mode"] for i in items).items()),
        },
        checks,
    )
    route_id = items[0]["routeId"]
    response, ms = timed(
        client,
        "GET",
        f"/v1/stops/{BUS_STOP}/departures",
        params={"from": args.when, "routeId": route_id, "limit": 5},
    )
    filtered = response.json()["data"]
    check(
        "departures routeId filter",
        response.status_code == 200 and filtered and {i["routeId"] for i in filtered} == {route_id},
        {"routeId": route_id, "items": len(filtered), "ms": ms},
        checks,
    )
    rail, ms = timed(
        client, "GET", f"/v1/stops/{RAIL_STOP}/departures", params={"from": args.when, "limit": 5}
    )
    rail_items = rail.json()["data"]
    check(
        "rail departures say rail",
        rail.status_code == 200 and rail_items and {i["mode"] for i in rail_items} == {"rail"},
        {"stop": RAIL_STOP, "operators": sorted({i["operatorName"] for i in rail_items}), "ms": ms},
        checks,
    )

    # API-C1 on the trip detail.
    trip, ms = timed(client, "GET", f"/v1/trips/{items[0]['tripRef']}")
    trip_body = trip.json()
    TripResponse.model_validate(trip_body)
    calls = trip_body["data"]["calls"]
    check(
        "trip calls carry name and position (API-C1); trip carries operator and mode",
        trip.status_code == 200
        and all(c["name"] and c["latitude"] and c["longitude"] for c in calls)
        and trip_body["data"]["operatorId"] == items[0]["operatorId"]
        and trip_body["data"]["mode"] == items[0]["mode"],
        {"calls": len(calls), "ms": ms},
        checks,
    )

    # Board 1: nearby stops with next departures; cold then warm.
    for label, near in NEAR.items():
        timings = []
        for _ in range(3):
            response, ms = timed(
                client,
                "GET",
                "/v1/departures/nearby",
                params={"near": near, "from": args.when, "stops": 8, "perStop": 3},
            )
            timings.append(ms)
        body = response.json()
        NearbyDeparturesResponse.model_validate(body)
        stops = body["data"]
        check(
            f"nearby departures ({label})",
            response.status_code == 200
            and bool(stops)
            and all(s["departuresState"] == "available" for s in stops),
            {
                "msColdThenWarm": timings,
                "bytes": len(response.content),
                "stops": [
                    {
                        "stopId": s["stop"]["stopId"],
                        "name": s["stop"]["name"],
                        "distanceMeters": round(s["stop"]["distanceMeters"]),
                        "complete": s["complete"],
                        "lines": [
                            [d["routeShortName"], d["operatorName"], d["mode"], d["headsign"]]
                            for d in s["departures"] or []
                        ],
                    }
                    for s in stops
                ],
            },
            checks,
        )

    # Board 7: a stop's lines, serving and both directions.
    for stop in (BUS_STOP, RAIL_STOP):
        for patterns in ("serving", "all"):
            response, ms = timed(
                client,
                "GET",
                f"/v1/stops/{stop}/lines",
                params={"patterns": patterns, "limit": 20},
            )
            body = response.json()
            StopLinesResponse.model_validate(body)
            lines = body["data"]
            served = [p for line in lines for p in line["patterns"] if p["servesStop"]]
            check(
                f"stop lines {stop} patterns={patterns}",
                response.status_code == 200
                and bool(lines)
                and all(line["operatorName"] and line["mode"] for line in lines)
                and all(p["stopIndex"] is not None for p in served),
                {
                    "ms": ms,
                    "bytes": len(response.content),
                    "routes": len(lines),
                    "patterns": sum(len(line["patterns"]) for line in lines),
                    "oppositeDirectionPatterns": sum(
                        1 for line in lines for p in line["patterns"] if not p["servesStop"]
                    ),
                    "morePages": body["page"]["nextCursor"] is not None,
                },
                checks,
            )

    # Board 3 and API-C2 on journeys; board 6 exclusion.
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    cases = corpus["cases"] if isinstance(corpus, dict) else corpus
    sides, reasons, bearings, offsets, platforms = Counter(), Counter(), Counter(), [], Counter()
    excluded_ok, durations = [], []
    for case in cases:
        lat1, lon1 = (float(v) for v in case["params"]["fromPlace"].split(","))
        lat2, lon2 = (float(v) for v in case["params"]["toPlace"].split(","))
        request = {
            "from": {"kind": "coordinate", "latitude": lat1, "longitude": lon1},
            "to": {"kind": "coordinate", "latitude": lat2, "longitude": lon2},
            "departAt": args.when,
            "results": 3,
        }
        response, ms = timed(client, "POST", "/v1/journeys", json=request)
        durations.append(ms)
        if response.status_code != 200:
            reasons[f"http_{response.status_code}"] += 1
            continue
        body = response.json()
        JourneyResponse.model_validate(body)
        for journey in body["data"]["journeys"]:
            for leg in journey["legs"]:
                if leg["kind"] != "transit":
                    continue
                board = leg["boarding"]
                bearings[board["bearingSource"]] += 1
                key = (leg["mode"], board["stopSide"] or board["stopSideUnavailableReason"])
                sides[key] += 1
                if board["stopOffsetMeters"] is not None:
                    offsets.append(board["stopOffsetMeters"])
                platforms[(leg["mode"], leg["from"]["platformCode"] is not None)] += 1
        trips = [
            leg["transit"]["engineTripId"]
            for leg in (body["data"]["journeys"] or [{"legs": []}])[0]["legs"]
            if leg["kind"] == "transit"
        ]
        if trips:
            again = client.post("/v1/journeys", json={**request, "excludeTripRefs": trips[:1]})
            used = {
                leg["transit"]["engineTripId"]
                for journey in again.json()["data"]["journeys"]
                for leg in journey["legs"]
                if leg["kind"] == "transit"
            }
            excluded_ok.append(
                {
                    "case": case["id"],
                    "status": again.status_code,
                    "excludedAbsent": trips[0] not in used,
                    "journeys": len(again.json()["data"]["journeys"]),
                    "warnings": again.json()["meta"]["warnings"],
                }
            )
    bus_sides = {side: n for (mode, side), n in sides.items() if mode == "bus"}
    check(
        "boarding bearing and side on journey legs (board 3)",
        bool(bus_sides) and bearings.get(None, 0) == 0,
        {
            "cases": len(cases),
            "journeyMsMedian": statistics.median(durations),
            "bearingSources": dict(bearings),
            "sideByMode": {f"{mode}:{side}": n for (mode, side), n in sorted(sides.items())},
            "busStopOffsetMetersMedian": statistics.median(offsets) if offsets else None,
            "originPlatformKnownByMode": {
                f"{mode}:{known}": n for (mode, known), n in sorted(platforms.items())
            },
        },
        checks,
    )
    check(
        "excludeTripRefs removes the missed trip (board 6)",
        bool(excluded_ok) and all(e["status"] == 200 and e["excludedAbsent"] for e in excluded_ok),
        {"replans": excluded_ok},
        checks,
    )
    result = {
        "recordedAt": datetime.now(UTC).isoformat(),
        "purpose": "Live mechanical check of the API additions for the eight approved client "
        "boards (API-BOARDS). Structural only: not human review of any screen.",
        "api": args.api,
        "generationId": status["meta"]["generationId"],
        "coverage": status["meta"]["coverage"],
        "queryTime": args.when,
        "checks": checks,
        "summary": {
            "pass": sum(c["status"] == "PASS" for c in checks),
            "fail": sum(c["status"] == "FAIL" for c in checks),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    args.output.write_bytes(text.encode("utf-8"))  # LF on every platform
    print(json.dumps(result["summary"]))
    for item in checks:
        print(item["status"], item["check"])
    return 0 if result["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
