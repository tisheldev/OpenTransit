"""Offline comparison of stop bearing estimates against journey-leg boarding geometry.

Picks bus and light rail stops at random (fixed seed), plans a journey from each to a stop
3-12 km away on a running API (read-only ``POST /v1/journeys``), and compares, for every
transit leg boarding at a distinct stop, the reference-only bearing estimates E0-E4 with two
truths taken from the leg's ``boarding`` object: the travel bearing (``bearingDegrees`` read
from the leg's street path) and the road direction (stop to ``pathPoint`` when the stop is at
least 3 m off the path, snapped to N/E/S/W). Mechanical check, not human review.

    uv run --project services/api --locked python \
        services/api/tools/compare_stop_bearing_estimates.py \
        --reference C:/ot/generations/nov11a/reference.sqlite \
        --api http://127.0.0.1:8520 --out <results json>

The default API is :8520 (stack ot-acc-boards1, generation nov11a): on 12 November 2026 the
nov11a stack on :8500 ran code whose journey legs carry no ``boarding`` object.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from opentransit.reference import route_type_mode
from opentransit.stop_facets import initial_bearing, load_stop_facets, mean_bearing

DEFAULT_API = "http://127.0.0.1:8520"
DEFAULT_TIMES = (
    "2026-11-16T08:00:00+02:00",
    "2026-11-16T13:00:00+02:00",
    "2026-11-16T18:30:00+02:00",
)
ESTIMATES = ("E0", "E1", "E2", "E3", "E4a", "E4b")
DEFINITIONS = {
    "E0": "Current API (load_stop_facets): circular mean of stop-to-next-stop bearings over "
    "every pattern call at the stop (previous-to-stop when no call has a next stop); null when "
    "the mean unit vector is shorter than 0.8. Per pattern: stop-to-next (previous-to-stop "
    "when there is no next).",
    "E1": "Chord: per call, bearing previous stop to next stop (stop-to-next without a "
    "previous call, previous-to-stop without a next); pooled per stop by circular mean, null "
    "below 0.8.",
    "E2": "Bisector: per call, the normalised sum of the unit vectors previous-to-stop and "
    "stop-to-next (either alone when the other is missing); pooled as E1.",
    "E3": "As E2 with each unit vector weighted by 1 / (its length in metres); pooled as E1.",
    "E4a": "Arrival: per call, bearing previous-to-stop (stop-to-next when there is no "
    "previous call); pooled as E1. The mirror of E0, testing whether the street a stop is on "
    "is better told by the approach than by the departure. (E3's inverse-distance weights "
    "already equal the three-point quadratic tangent, so that is not a separate variant.)",
    "E4b": "E1 chord with the per-stop agreement threshold lowered from 0.8 to 0.5 (fewer "
    "nulls). Per pattern it equals E1.",
}
COMMON_RULES = (
    "A neighbour call at the same stop_id (consecutive duplicate) is skipped; a neighbour less "
    "than 1 m from the stop counts as missing; a call whose own value cannot be formed "
    "contributes nothing. Implied road direction = estimate - 90 degrees (keep right: the road "
    "is to the left of the direction of travel, seen from the stop), snapped to N/E/S/W."
)
THRESHOLD = {"E0": 0.8, "E1": 0.8, "E2": 0.8, "E3": 0.8, "E4a": 0.8, "E4b": 0.5}
STREET_MODES = ("bus", "light_rail")
SNAP = ("N", "E", "S", "W")
_EARTH_RADIUS_METRES = 6_371_008.8


def distance_m(a, b) -> float:
    phi1, phi2 = math.radians(a[0]), math.radians(b[0])
    h = (
        math.sin((phi2 - phi1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_METRES * math.asin(min(1.0, math.sqrt(h)))


def bearing(a, b) -> float | None:
    if a is None or b is None:
        return None
    return initial_bearing(a[0], a[1], b[0], b[1])


def unit(b: float) -> tuple[float, float]:
    return math.sin(math.radians(b)), math.cos(math.radians(b))


def vector_bearing(east: float, north: float) -> float | None:
    if math.hypot(east, north) < 1e-9:
        return None
    return math.degrees(math.atan2(east, north)) % 360.0


def angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def snap(b: float) -> str:
    return SNAP[round((b % 360.0) / 90.0) % 4]


def call_values(p, s, n) -> dict[str, float | None]:
    """Per-call bearing for each estimate; ``p``/``s``/``n`` are (lat, lon) or None."""
    to_prev = bearing(p, s)
    to_next = bearing(s, n)
    d_prev = distance_m(p, s) if to_prev is not None else None
    d_next = distance_m(s, n) if to_next is not None else None
    values: dict[str, float | None] = {"E0": to_next if to_next is not None else to_prev}
    if to_prev is not None and to_next is not None:
        values["E1"] = bearing(p, n)
    else:
        values["E1"] = to_next if to_next is not None else to_prev

    def combine(w_prev: float, w_next: float) -> float | None:
        east = north = 0.0
        if to_prev is not None:
            ue, un = unit(to_prev)
            east, north = east + w_prev * ue, north + w_prev * un
        if to_next is not None:
            ue, un = unit(to_next)
            east, north = east + w_next * ue, north + w_next * un
        return vector_bearing(east, north)

    if to_prev is None and to_next is None:
        values.update({"E2": None, "E3": None, "E4a": None})
    else:
        values["E2"] = combine(1.0, 1.0)
        values["E3"] = combine(1.0 / d_prev if d_prev else 0.0, 1.0 / d_next if d_next else 0.0)
        values["E4a"] = to_prev if to_prev is not None else to_next
    values["E4b"] = values["E1"]
    return values


def dedupe(stops: list[str]) -> list[str]:
    out: list[str] = []
    for stop in stops:
        if not out or out[-1] != stop:
            out.append(stop)
    return out


def load_reference(path: Path):
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True)
    positions, source_to_stop, location_type = {}, {}, {}
    for stop_id, source_id, lat, lon, loc_type in connection.execute(
        "SELECT stop_id, source_id, latitude, longitude, location_type FROM stops"
    ):
        positions[stop_id] = (lat, lon) if lat is not None and lon is not None else None
        source_to_stop[source_id] = stop_id
        location_type[stop_id] = loc_type
    facets = load_stop_facets(connection, route_type_mode)
    route_modes = {
        route_id: route_type_mode(route_type)
        for route_id, route_type in connection.execute("SELECT route_id, route_type FROM routes")
    }
    stop_route_modes: dict[str, set[str]] = defaultdict(set)
    for route_id, stop_id in connection.execute("SELECT route_id, stop_id FROM route_stops"):
        stop_route_modes[stop_id].add(route_modes.get(route_id, "other"))
    pattern_calls: dict[str, list[str]] = defaultdict(list)
    for pattern_id, stop_id in connection.execute(
        "SELECT pattern_id, stop_id FROM pattern_stops ORDER BY pattern_id, sequence"
    ):
        pattern_calls[pattern_id].append(stop_id)
    pooled_calls: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for calls in pattern_calls.values():
        calls = dedupe(calls)
        for index, stop in enumerate(calls):
            p = positions.get(calls[index - 1]) if index > 0 else None
            n = positions.get(calls[index + 1]) if index + 1 < len(calls) else None
            for name, value in call_values(p, positions.get(stop), n).items():
                if value is not None:
                    pooled_calls[stop][name].append(value)
    per_stop: dict[str, dict[str, float | None]] = {}
    for stop_id in positions:
        values = {"E0": facets[stop_id].bearing_degrees}
        for name in ESTIMATES[1:]:
            values[name] = mean_bearing(pooled_calls[stop_id][name], THRESHOLD[name])
        per_stop[stop_id] = values
    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    return {
        "connection": connection,
        "positions": positions,
        "sourceToStop": source_to_stop,
        "locationType": location_type,
        "facets": facets,
        "stopRouteModes": stop_route_modes,
        "perStop": per_stop,
        "referenceGenerationId": json.loads(metadata["generationId"]),
    }


def trip_calls(reference, source_trip_id: str) -> list[str] | None:
    row = (
        reference["connection"]
        .execute("SELECT profile_id FROM trip_profiles WHERE source_trip_id = ?", (source_trip_id,))
        .fetchone()
    )
    if row is None:
        return None
    sources = [
        stop
        for (stop,) in reference["connection"].execute(
            "SELECT stop_id FROM clock_profile_calls WHERE profile_id = ? ORDER BY ordinal",
            (row[0],),
        )
    ]
    return dedupe([reference["sourceToStop"].get(stop, stop) for stop in sources])


def per_pattern_values(reference, leg) -> tuple[dict[str, float | None] | None, str | None]:
    calls = trip_calls(reference, leg["transit"]["sourceTripId"])
    if calls is None:
        return None, "trip_not_in_reference"
    stop = leg["from"]["stopId"]
    next_stop = (leg["boarding"].get("nextStop") or {}).get("stopId")
    indices = [i for i, s in enumerate(calls) if s == stop]
    if not indices:
        return None, "stop_not_in_trip"
    chosen = indices[0]
    for i in indices:
        if i + 1 < len(calls) and calls[i + 1] == next_stop:
            chosen = i
            break
    positions = reference["positions"]
    p = positions.get(calls[chosen - 1]) if chosen > 0 else None
    n = positions.get(calls[chosen + 1]) if chosen + 1 < len(calls) else None
    return call_values(p, positions.get(stop), n), None


def street_stops(reference) -> list[str]:
    return sorted(
        stop_id
        for stop_id, modes in reference["stopRouteModes"].items()
        if modes & set(STREET_MODES)
        and reference["positions"].get(stop_id) is not None
        and reference["locationType"].get(stop_id) in (0, None)
    )


def post_journey(client, body, state, max_requests, interval, log):
    """POST with pacing and 429 back-off; every attempt counts toward ``max_requests``."""
    while state["sent"] < max_requests:
        wait = state["last"] + interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        state["last"] = time.monotonic()
        state["sent"] += 1
        try:
            response = client.post("/v1/journeys", json=body)
        except httpx.HTTPError as error:
            log.append({**body_summary(body), "status": f"error:{type(error).__name__}"})
            return None
        log.append({**body_summary(body), "status": response.status_code})
        if response.status_code == 429:
            retry = float(response.headers.get("Retry-After", "10"))
            time.sleep(max(retry, interval))
            continue
        return response
    return None


def body_summary(body) -> dict:
    return {
        "from": body["from"]["stopId"],
        "to": body["to"]["stopId"],
        "departAt": body["departAt"],
    }


def summarise(rows, key: str, has_estimate_key: str) -> dict:
    travel = [r for r in rows if r["truthBearing"] is not None]
    road = [r for r in rows if r["truthRoad"] is not None]
    with_estimate = [r for r in travel if r[has_estimate_key].get(key) is not None]
    diffs = [angle_diff(r[has_estimate_key][key], r["truthBearing"]) for r in with_estimate]
    road_est = [r for r in road if r[has_estimate_key].get(key) is not None]
    agree = sum(snap(r[has_estimate_key][key] - 90.0) == r["truthRoad"] for r in road_est)
    opposite = sum(
        (SNAP.index(snap(r[has_estimate_key][key] - 90.0)) - SNAP.index(r["truthRoad"])) % 4 == 2
        for r in road_est
    )

    def share(count, total):
        return round(count / total, 4) if total else None

    within45 = sum(d <= 45 for d in diffs)
    within30 = sum(d <= 30 for d in diffs)
    return {
        "legs": len(travel),
        "withEstimate": len(with_estimate),
        "null": len(travel) - len(with_estimate),
        "nullShare": share(len(travel) - len(with_estimate), len(travel)),
        "within45ShareOfEstimated": share(within45, len(with_estimate)),
        "within45ShareOfAll": share(within45, len(travel)),
        "within30ShareOfEstimated": share(within30, len(with_estimate)),
        "within30ShareOfAll": share(within30, len(travel)),
        "medianAbsDiffDegrees": round(statistics.median(diffs), 1) if diffs else None,
        "p90AbsDiffDegrees": (
            round(statistics.quantiles(diffs, n=10, method="inclusive")[8], 1)
            if len(diffs) >= 2
            else None
        ),
        "pole": {
            "legsWithRoadTruth": len(road),
            "withEstimate": len(road_est),
            "agree": agree,
            "agreeShareOfEstimated": share(agree, len(road_est)),
            "agreeShareOfAll": share(agree, len(road)),
            "opposite": opposite,
            "oppositeShareOfEstimated": share(opposite, len(road_est)),
            "oppositeShareOfAll": share(opposite, len(road)),
        },
    }


def coverage(reference) -> dict:
    by_mode: dict[str, Counter] = defaultdict(Counter)
    for stop_id, values in reference["perStop"].items():
        mode = reference["facets"][stop_id].mode or "unserved"
        by_mode[mode]["total"] += 1
        for name, value in values.items():
            by_mode[mode][name] += value is not None
    out = {}
    for mode, counts in sorted(by_mode.items()):
        total = counts["total"]
        out[mode] = {
            "stops": total,
            **{
                name: {
                    "withEstimateShare": round(counts[name] / total, 4),
                    "nullShare": round(1 - counts[name] / total, 4),
                }
                for name in ESTIMATES
            },
        }
    total = sum(c["total"] for c in by_mode.values())
    out["all"] = {
        "stops": total,
        **{
            name: {
                "withEstimateShare": round(sum(c[name] for c in by_mode.values()) / total, 4),
                "nullShare": round(1 - sum(c[name] for c in by_mode.values()) / total, 4),
            }
            for name in ESTIMATES
        },
    }
    return out


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261112)
    parser.add_argument("--target-legs", type=int, default=300)
    parser.add_argument("--max-requests", type=int, default=248, help="journey POSTs, retries too")
    parser.add_argument("--per-minute", type=float, default=20.0)
    parser.add_argument("--min-km", type=float, default=3.0)
    parser.add_argument("--max-km", type=float, default=12.0)
    parser.add_argument("--min-offset-m", type=float, default=3.0)
    parser.add_argument("--times", nargs="+", default=list(DEFAULT_TIMES))
    parser.add_argument(
        "--prior-requests",
        type=Path,
        help="JSON list of journey requests sent outside this run, recorded verbatim; an "
        "entry may carry 'count' when it stands for several requests",
    )
    args = parser.parse_args(argv)
    # Read before any request is sent, so a bad file cannot waste the request budget.
    prior = json.loads(args.prior_requests.read_text("utf-8-sig")) if args.prior_requests else []
    prior_count = sum(int(entry.get("count", 1)) for entry in prior)

    reference = load_reference(args.reference)
    candidates = street_stops(reference)
    rng = random.Random(args.seed)
    client = httpx.Client(base_url=args.api, timeout=60)
    status = client.get("/v1/status").json()
    state = {"sent": 0, "last": 0.0}
    log: list[dict] = []
    rows: list[dict] = []
    seen_stops: set[str] = set()
    counts: Counter = Counter()
    interval = 60.0 / args.per_minute
    positions = reference["positions"]
    attempt = 0
    while state["sent"] < args.max_requests and len(rows) < args.target_legs:
        origin = rng.choice(candidates)
        destination = None
        for _ in range(2000):
            pick = rng.choice(candidates)
            if (
                args.min_km * 1000
                <= distance_m(positions[origin], positions[pick])
                <= (args.max_km * 1000)
            ):
                destination = pick
                break
        if destination is None:
            counts["originsWithoutDestination"] += 1
            continue
        body = {
            "from": {"kind": "stop", "stopId": origin},
            "to": {"kind": "stop", "stopId": destination},
            "departAt": args.times[attempt % len(args.times)],
            "results": 3,
        }
        attempt += 1
        response = post_journey(client, body, state, args.max_requests, interval, log)
        if response is None or response.status_code != 200:
            counts["requestsWithoutAnswer"] += 1
            continue
        journeys = response.json()["data"]["journeys"]
        counts["journeys"] += len(journeys)
        for journey in journeys:
            for leg in journey["legs"]:
                if leg["kind"] != "transit":
                    continue
                counts["transitLegs"] += 1
                counts[f"transitLegsMode:{leg['mode']}"] += 1
                if leg["mode"] not in STREET_MODES:
                    continue
                stop = leg["from"]["stopId"]
                if stop in seen_stops:
                    counts["streetLegsAtRepeatedStop"] += 1
                    continue
                seen_stops.add(stop)
                board = leg.get("boarding")
                if board is None:
                    raise SystemExit("A transit leg has no boarding object: stopping.")
                truth_bearing = (
                    board["bearingDegrees"] if board["bearingSource"] == "leg_geometry" else None
                )
                truth_road = None
                stop_pos = (leg["from"]["latitude"], leg["from"]["longitude"])
                offset = board["stopOffsetMeters"]
                if offset is not None and offset >= args.min_offset_m and board["pathPoint"]:
                    road = bearing(stop_pos, (board["pathPoint"][1], board["pathPoint"][0]))
                    truth_road = snap(road) if road is not None else None
                pattern, pattern_reason = per_pattern_values(reference, leg)
                rows.append(
                    {
                        "stopId": stop,
                        "mode": leg["mode"],
                        "routeId": leg["transit"]["routeId"],
                        "sourceTripId": leg["transit"]["sourceTripId"],
                        "nextStopId": (board.get("nextStop") or {}).get("stopId"),
                        "bearingSource": board["bearingSource"],
                        "truthBearing": truth_bearing,
                        "stopOffsetMeters": offset,
                        "truthRoad": truth_road,
                        "stopPositionMatchesReference": positions.get(stop) is not None
                        and distance_m(positions[stop], stop_pos) < 0.5,
                        "perStop": {
                            k: (round(v, 1) if v is not None else None)
                            for k, v in reference["perStop"].get(stop, {}).items()
                        },
                        "perPattern": {
                            k: (round(v, 1) if v is not None else None)
                            for k, v in (pattern or dict.fromkeys(ESTIMATES)).items()
                        },
                        "perPatternUnavailableReason": pattern_reason,
                    }
                )

    ceiling_rows = [r for r in rows if r["truthRoad"] is not None and r["truthBearing"] is not None]
    ceiling_agree = sum(snap(r["truthBearing"] - 90.0) == r["truthRoad"] for r in ceiling_rows)
    ceiling_opposite = sum(
        (SNAP.index(snap(r["truthBearing"] - 90.0)) - SNAP.index(r["truthRoad"])) % 4 == 2
        for r in ceiling_rows
    )
    result = {
        "recordedAt": datetime.now(UTC).isoformat(),
        "purpose": "Offline comparison of reference-only stop bearing estimates (E0 current, "
        "E1-E4) against journey-leg boarding geometry on the nov11a generation.",
        "humanReview": "None. This is a mechanical check, not human review.",
        "commit": git_commit(),
        "scriptSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "generation": {
            "reference": str(args.reference),
            "referenceComponentGenerationId": reference["referenceGenerationId"],
            "publicGenerationId": status["meta"]["generationId"],
        },
        "api": args.api,
        "options": {
            "seed": args.seed,
            "targetLegs": args.target_legs,
            "maxRequests": args.max_requests,
            "perMinute": args.per_minute,
            "destinationKm": [args.min_km, args.max_km],
            "roadTruthMinOffsetMeters": args.min_offset_m,
            "departAtCycle": args.times,
            "results": 3,
        },
        "definitions": {**DEFINITIONS, "commonRules": COMMON_RULES},
        "truths": {
            "travelBearing": "boarding.bearingDegrees when bearingSource is leg_geometry "
            "(first 30 m of the leg's street path); other legs have no travel truth.",
            "roadDirection": "bearing from the leg's from latitude/longitude to "
            "boarding.pathPoint when stopOffsetMeters >= the minimum, snapped to N/E/S/W.",
            "perPatternIdentification": "transit.sourceTripId -> trip_profiles.profile_id -> "
            "clock_profile_calls by ordinal (source stop ids mapped through stops.source_id); "
            "boarding stop occurrence chosen whose next call is boarding.nextStop.",
        },
        "sample": {
            "requestsSentThisRun": state["sent"],
            "priorRequestsOutsideRun": prior_count,
            "requestsSentTotal": state["sent"] + prior_count,
            "streetLegsAtDistinctStops": len(rows),
            "distinctStops": len(seen_stops),
            "legsWithTravelTruth": sum(r["truthBearing"] is not None for r in rows),
            "legsWithRoadTruth": sum(r["truthRoad"] is not None for r in rows),
            "perPatternIdentified": sum(r["perPatternUnavailableReason"] is None for r in rows),
            "perPatternUnavailable": dict(
                Counter(
                    r["perPatternUnavailableReason"]
                    for r in rows
                    if r["perPatternUnavailableReason"]
                )
            ),
            "stopPositionMatchesReference": sum(r["stopPositionMatchesReference"] for r in rows),
            "bearingSources": dict(Counter(r["bearingSource"] for r in rows)),
            "counts": dict(counts),
        },
        "results": {
            "perStop": {name: summarise(rows, name, "perStop") for name in ESTIMATES},
            "perPattern": {name: summarise(rows, name, "perPattern") for name in ESTIMATES},
            "ceiling": {
                "rule": "true travel bearing - 90, snapped, against snapped true road direction",
                "legs": len(ceiling_rows),
                "agree": ceiling_agree,
                "agreeShare": round(ceiling_agree / len(ceiling_rows), 4) if ceiling_rows else None,
                "opposite": ceiling_opposite,
                "oppositeShare": (
                    round(ceiling_opposite / len(ceiling_rows), 4) if ceiling_rows else None
                ),
            },
        },
        "allStopsCoverageByMode": coverage(reference),
        "priorRequests": prior,
        "requests": log,
        "legs": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, ensure_ascii=False, indent=1) + "\n"
    args.out.write_bytes(text.encode("utf-8"))  # LF on every platform
    print(json.dumps(result["sample"], indent=1))
    for scope in ("perStop", "perPattern"):
        for name, item in result["results"][scope].items():
            print(
                scope,
                name,
                item["withEstimate"],
                item["null"],
                item["within45ShareOfEstimated"],
                item["within30ShareOfEstimated"],
                item["medianAbsDiffDegrees"],
                item["p90AbsDiffDegrees"],
                item["pole"]["agreeShareOfEstimated"],
                item["pole"]["agreeShareOfAll"],
                item["pole"]["oppositeShareOfEstimated"],
            )
    print("ceiling", result["results"]["ceiling"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
