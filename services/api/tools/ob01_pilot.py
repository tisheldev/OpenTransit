"""OB-01 pilot: one service day of archived SIRI → inferred stop times → delay distributions.

Reads cached Open Bus archive minutes (`<siri-cache>/YYYY/MM/DD/HH/MM.br`, UTC) covering local
00:00 of --service-date to 06:00 the next day, and that day's archived MOT GTFS. Writes a summary
JSON (refuses to overwrite) and full delay/segment tables as gzipped CSV under --tables-dir.
Never downloads; fetch the archive first. Output is historical replay evidence, not live data,
and not approved for public display.

    uv run --project services/api --locked --group history python services/api/tools/ob01_pilot.py
        --service-date 2026-09-15 --siri-cache D:/ot/open-bus-archive/siri
        --feed D:/ot/open-bus-archive/gtfs-full/2026-09-15/israel-public-transportation.zip
        --tables-dir D:/ot/open-bus-archive/ob01/2026-09-15
        --output services/api/results/ob01-pilot-20260915-01.json
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from opentransit.build.prepare import sha256
from opentransit.core.time import JERUSALEM
from opentransit.history.arrivals import (
    BACKWARD_TOLERANCE_M,
    CRUISE_MPS,
    MAX_BRACKET_S,
    MAX_SPEED_MPS,
    ORIGIN_EPSILON_M,
    clean_track,
    observe_calls,
)
from opentransit.history.distributions import (
    Accumulator,
    day_type,
    local_hour,
    percentile,
    summary,
)
from opentransit.history.schedule import load_day, match_ride
from opentransit.history.siri_archive import load_rides, minute_keys

CONSISTENCY_TOLERANCE_M = 100
EARLY_S, LATE_S = -60, 300  # illustrative thresholds, not MOT penalty rules
MIN_SEGMENT_SAMPLES = 3


def consistency(points: dict, calls) -> tuple[int, int, list[float]]:
    """When SIRI `Order` advances, does the newly reached stop lie between the two pings?"""
    by_sequence = {call.sequence: call.distance_m for call in calls}
    ordered = [points[at] for at in sorted(points)]
    agree = disagree = 0
    offsets = []
    for (before_m, before_order), (after_m, after_order) in zip(ordered, ordered[1:], strict=False):
        if after_order <= before_order:
            continue
        stop_m = by_sequence.get(after_order)
        if stop_m is None:
            continue
        if before_m - CONSISTENCY_TOLERANCE_M <= stop_m <= after_m + CONSISTENCY_TOLERANCE_M:
            agree += 1
        else:
            disagree += 1
            offsets.append(stop_m - (before_m + after_m) / 2)
    return agree, disagree, offsets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--service-date", type=date.fromisoformat, required=True)
    parser.add_argument("--siri-cache", type=Path, required=True)
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--tables-dir", type=Path, required=True)
    parser.add_argument("--decimation-sample", type=int, default=2000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print(f"refusing to overwrite {args.output}", file=sys.stderr)
        return 2
    day = args.service_date
    start = datetime.combine(day, datetime.min.time(), JERUSALEM)
    keys = list(minute_keys(start, start + timedelta(hours=30)))

    schedule = load_day(args.feed, day)
    rides, archive = load_rides(args.siri_cache, keys, day)

    reasons = Counter()
    call_reasons = Counter()
    track_totals = Counter()
    accumulator = Accumulator(day_type(day))
    delays_by_hour: dict[int, list[float]] = defaultdict(list)
    origin_delays, final_delays, duration_ratios = [], [], []
    by_agency: dict[str, dict] = defaultdict(lambda: {"rides": 0, "final": []})
    agree = disagree = 0
    offsets: list[float] = []
    matched_trip_ids = set()
    decimation_errors = []
    rng = random.Random(20261001)
    best: dict[str, tuple] = {}  # trip_id → (ride, trip); one observation per scheduled trip
    for ride in rides.values():
        trip, reason = match_ride(schedule, ride.line_ref, ride.origin_departure)
        if trip is None:
            reasons[reason] += 1
            if len(ride.points) < 3:
                reasons[reason + "FewerThan3Pings"] += 1
            continue
        reasons["matched"] += 1
        if trip.trip_id.split("_", 1)[0] == ride.trip_ref:
            reasons["matchedTripRefIsGtfsPrefix"] += 1
        if trip.trip_id in best:
            reasons["extraRideForSameTripDropped"] += 1
            if len(best[trip.trip_id][0].points) >= len(ride.points):
                continue
        best[trip.trip_id] = (ride, trip)
    for ride, trip in best.values():
        matched_trip_ids.add(trip.trip_id)
        track, stats = clean_track(ride.points)
        track_totals.update(
            pings=stats.pings,
            duplicates=ride.duplicates,
            backwards=stats.backwards,
            speedOutliers=stats.speed_outliers,
        )
        if len(ride.vehicles) > 1:
            track_totals["ridesWithSeveralVehicles"] += 1
        calls = observe_calls(track, trip.calls)
        call_reasons.update(call.reason or "observed" for call in calls)
        accumulator.add(trip.route_id, calls)
        a, d, o = consistency(ride.points, trip.calls)
        agree, disagree = agree + a, disagree + d
        offsets.extend(o)
        for call in calls[1:]:
            if call.observed is not None:
                delays_by_hour[local_hour(call.scheduled)].append(call.observed - call.scheduled)
        first, last = calls[0], calls[-1]
        if first.observed is not None:
            origin_delays.append(first.observed - first.scheduled)
        agency = schedule.routes.get(trip.route_id, {}).get("agency_id", "?")
        by_agency[agency]["rides"] += 1
        if last.observed is not None:
            final_delays.append(last.observed - last.scheduled)
            by_agency[agency]["final"].append(last.observed - last.scheduled)
            if first.observed is not None and last.scheduled > first.scheduled:
                duration_ratios.append(
                    (last.observed - first.observed) / (last.scheduled - first.scheduled)
                )
        if len(track) >= 20 and rng.random() < args.decimation_sample / max(len(rides), 1):
            sparse = observe_calls(track[::2], trip.calls)
            for full, thin in zip(calls, sparse, strict=True):
                if full.observed is not None and thin.observed is not None:
                    decimation_errors.append(abs(thin.observed - full.observed))

    scheduled_by_agency = Counter(
        schedule.routes.get(trip.route_id, {}).get("agency_id", "?")
        for trip in schedule.trips.values()
    )
    args.tables_dir.mkdir(parents=True, exist_ok=True)
    tables = {}
    for name, rows in (
        ("delays", accumulator.delay_rows()),
        ("segments", accumulator.segment_rows()),
    ):
        path = args.tables_dir / f"{name}.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        tables[name] = {"path": path.as_posix(), "rows": len(rows), "sha256": sha256(path)}

    short_names = {key: value["route_short_name"] for key, value in schedule.routes.items()}
    worst = sorted(
        (
            row
            for row in accumulator.segment_rows()
            if row["samples"] >= MIN_SEGMENT_SAMPLES and row["scheduledSecondsMedian"] >= 120
        ),
        key=lambda row: row["runP50Seconds"] / row["scheduledSecondsMedian"],
        reverse=True,
    )[:15]
    for row in worst:
        row["routeShortName"] = short_names.get(row["routeId"], "")
        row["ratioP50"] = round(row["runP50Seconds"] / row["scheduledSecondsMedian"], 2)

    def share(values, test):
        return round(sum(1 for value in values if test(value)) / len(values), 3) if values else None

    report = {
        "task": "OB-01 pilot (historical replay; not live, not approved for public display)",
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "serviceDate": day.isoformat(),
        "dayType": day_type(day),
        "inputs": {
            "siriArchive": "openbus-stride-public/stride-siri-requester (Hasadna Open Bus)",
            "siriMinutesRequested": len(keys),
            "siriMinutesRead": archive["files"],
            "siriMinutesMissing": archive["missingFiles"],
            "feed": args.feed.as_posix(),
            "feedSha256": sha256(args.feed),
            "feedArchiveKey": f"gtfs_archive/{day:%Y/%m/%d}/israel-public-transportation.zip",
        },
        "parameters": {
            "backwardToleranceM": BACKWARD_TOLERANCE_M,
            "maxSpeedMps": MAX_SPEED_MPS,
            "maxBracketS": MAX_BRACKET_S,
            "originEpsilonM": ORIGIN_EPSILON_M,
            "cruiseMpsFromRest": CRUISE_MPS,
            "earlyLateThresholdsS": [EARLY_S, LATE_S],
        },
        "pings": {
            "serviceDatePings": archive["pings"],
            "skippedVisits": archive["skippedVisits"],
            "otherServiceDatePings": archive["otherDatePings"],
            **dict(track_totals),
        },
        "matching": {
            "rides": len(rides),
            "outcomes": dict(reasons),
            "scheduledTrips": len(schedule.trips),
            "scheduledTripsObserved": len(matched_trip_ids),
            "scheduledTripCoverage": round(len(matched_trip_ids) / len(schedule.trips), 3),
            "note": "Unobserved trips may have run untracked; never label them cancelled.",
        },
        "calls": dict(call_reasons),
        "distanceConsistency": {
            "orderChangesAgreeing": agree,
            "orderChangesDisagreeing": disagree,
            "toleranceM": CONSISTENCY_TOLERANCE_M,
            "disagreeingOffsetM": summary(offsets) if offsets else None,
        },
        "interpolationCheck": {
            "method": "re-infer sampled rides from every second ping; compare with full track",
            "absErrorSeconds": summary(decimation_errors) if decimation_errors else None,
        },
        "originDepartureDelaySeconds": summary(origin_delays) if origin_delays else None,
        "originEarlyShare": share(origin_delays, lambda v: v < EARLY_S),
        "originLateShare": share(origin_delays, lambda v: v > LATE_S),
        "finalStopDelaySeconds": summary(final_delays) if final_delays else None,
        "durationRatio": (
            {
                "n": len(duration_ratios),
                "p10": round(percentile(duration_ratios, 0.1), 3),
                "p50": round(percentile(duration_ratios, 0.5), 3),
                "p90": round(percentile(duration_ratios, 0.9), 3),
            }
            if duration_ratios
            else None
        ),
        "stopDelayByScheduledHour": {
            str(hour): summary(values) for hour, values in sorted(delays_by_hour.items())
        },
        "byAgency": {
            agency: {
                "scheduledTrips": scheduled_by_agency.get(agency, 0),
                "matchedRides": value["rides"],
                "finalStopDelaySeconds": summary(value["final"]) if value["final"] else None,
            }
            for agency, value in sorted(by_agency.items(), key=lambda item: -item[1]["rides"])
        },
        "slowestSegmentsVsSchedule": worst,
        "tables": tables,
        "scope": (
            "One service day; historical replay from a third-party archive of MOT SIRI. Inferred "
            "times are about ±30 s at one-minute pings. Small per-key samples; distributions need "
            "a month and a held-out validation month (OB-01 done-when). Public display needs "
            "Phase 4 and data terms."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    brief = {
        k: report[k] for k in ("matching", "calls", "distanceConsistency", "interpolationCheck")
    }
    print(json.dumps(brief, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
