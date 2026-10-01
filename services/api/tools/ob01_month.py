"""OB-01 multi-day driver: pinned fetch → per-day observations → month tables → held-out check.

Historical replay from Hasadna's public archive of MOT SIRI; not live, not served by the API and
not approved for public display (Phase 4 and data terms). Subcommands, run from the repository
root with `uv run --project services/api --locked --group history python
services/api/tools/ob01_month.py <command> ...`:

    fetch     --start 2025-11-01 --end 2025-11-30 --raw-cache C:/ot-scratch/open-bus-archive
              --work D:/ot/open-bus-archive/ob01-month
    observe   --start ... --end ... --raw-cache ... --work ...        (one day at a time)
    aggregate --start ... --end ... --work ... --name 202511 --output results/<file>.json
    validate  --calibration 202511 --start ... --end ... --work ... --output results/<file>.json
    review    --calibration 202511 --raw-cache ... --work ... --output results/<file>.json

`fetch` copies SIRI minutes (MD5-checked against the listing) and each day's GTFS schedule
members (range requests, CRC-checked), and writes per-day manifests under <work>/manifests.
Raw caches are reproducible from the archive and may live on scratch disk; manifests, per-day
observations and tables are the durable outputs. Result JSON files are never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import gzip
import hashlib
import heapq
import io
import json
import os
import shutil
import sys
import threading
import time
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from opentransit.history.archive_fetch import (
    BUCKET_URL,
    GTFS_FEED,
    SCHEDULE_MEMBERS,
    SIRI_PREFIX,
    ArchiveObject,
    extract_members,
    fetch_object,
    list_prefix,
    manifest_digest,
    siri_window,
)
from opentransit.history.arrivals import (
    BACKWARD_TOLERANCE_M,
    CRUISE_MPS,
    MAX_BRACKET_S,
    MAX_SPEED_MPS,
    ORIGIN_EPSILON_M,
)
from opentransit.history.distributions import day_type, local_hour, percentile
from opentransit.history.distributions import summary as distribution_summary
from opentransit.history.month import (
    BUCKETS,
    MIN_COVERAGE,
    MIN_SAMPLES,
    MIN_SERVICE_DAYS,
    DayWriter,
    HeldOutCheck,
    MonthAggregate,
    histogram_summary,
    observe_day,
    read_bucket,
    trips_of,
)
from opentransit.history.review import (
    ARTEFACT_GPS_M,
    FROZEN_M,
    STATIONARY_SHARE,
    TracePing,
    classify,
    haversine_m,
    segment_trace,
)
from opentransit.history.schedule import load_day, match_ride
from opentransit.history.siri_archive import load_rides, parse_snapshot

PARAMETERS = {
    "backwardToleranceM": BACKWARD_TOLERANCE_M,
    "maxSpeedMps": MAX_SPEED_MPS,
    "maxBracketS": MAX_BRACKET_S,
    "originEpsilonM": ORIGIN_EPSILON_M,
    "cruiseMpsFromRest": CRUISE_MPS,
}


def days_between(start: date, end: date, exclude: set[date]) -> list[date]:
    days, day = [], start
    while day <= end:
        if day not in exclude:
            days.append(day)
        day += timedelta(days=1)
    return days


def expected_minutes(day: date) -> list[str]:
    start, end = siri_window(day)
    keys, moment = [], start
    while moment < end:
        keys.append(f"{SIRI_PREFIX}/{moment:%Y/%m/%d/%H/%M}.br")
        moment += timedelta(minutes=1)
    return keys


def siri_path(raw: Path, key: str) -> Path:
    return raw / "siri" / key.removeprefix(SIRI_PREFIX + "/")


def schedule_path(raw: Path, day: date) -> Path:
    return raw / "gtfs" / f"{day:%Y-%m-%d}" / "schedule-members.zip"


def manifest_path(work: Path, day: date) -> Path:
    return work / "manifests" / f"{day:%Y-%m-%d}.json"


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch(args) -> int:
    limits = httpx.Limits(max_connections=args.workers, max_keepalive_connections=args.workers)
    listings: dict[str, dict[str, ArchiveObject]] = {}
    lock = threading.Lock()
    with httpx.Client(base_url=BUCKET_URL, timeout=120, limits=limits) as client:

        def listed(utc_day: str) -> dict[str, ArchiveObject]:
            with lock:
                if utc_day not in listings:
                    objects = list_prefix(client, f"{SIRI_PREFIX}/{utc_day}/")
                    listings[utc_day] = {obj.key: obj for obj in objects}
                return listings[utc_day]

        for day in days_between(args.start, args.end, set(args.exclude)):
            target = manifest_path(args.work, day)
            if target.exists():
                print(f"{day}: manifest exists, skipping", flush=True)
                continue
            began = time.monotonic()
            expected = expected_minutes(day)
            present, missing = [], []
            for key in expected:
                obj = listed("/".join(key.split("/")[1:4])).get(key)
                (present if obj else missing).append(obj or key)
            with ThreadPoolExecutor(args.workers) as pool:
                records = list(
                    pool.map(
                        lambda obj: fetch_object(client, obj, siri_path(args.raw_cache, obj.key)),
                        present,
                    )
                )
            feed_key = f"gtfs_archive/{day:%Y/%m/%d}/{GTFS_FEED}"
            feeds = [obj for obj in list_prefix(client, feed_key) if obj.key == feed_key]
            if not feeds:
                print(f"{day}: no archived GTFS feed; skipping day", flush=True)
                continue
            schedule = extract_members(
                client, feeds[0], SCHEDULE_MEMBERS, schedule_path(args.raw_cache, day)
            )
            manifest = {
                "serviceDate": day.isoformat(),
                "bucket": BUCKET_URL,
                "siri": {
                    "window": [moment.isoformat() for moment in siri_window(day)],
                    "expectedMinutes": len(expected),
                    "presentMinutes": len(records),
                    "missingMinutes": missing,
                    "bytes": sum(record["size"] for record in records),
                    "manifestSha256": manifest_digest(records),
                    "objects": [
                        [
                            record["key"].removeprefix(SIRI_PREFIX + "/"),
                            record["size"],
                            record["md5"],
                            record["sha256"],
                        ]
                        for record in records
                    ],
                },
                "gtfs": schedule,
            }
            write_new(target, manifest)
            print(
                f"{day}: {len(records)}/{len(expected)} minutes, "
                f"{manifest['siri']['bytes'] / 1e6:.0f} MB SIRI, schedule members "
                f"{sum(m['bytes'] for m in schedule['members'].values()) / 1e6:.0f} MB raw, "
                f"{time.monotonic() - began:.0f} s",
                flush=True,
            )
    return 0


def peak_memory_mb() -> float | None:
    """Peak working set of this process (Windows); None elsewhere."""
    if sys.platform != "win32":
        return None

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    current = ctypes.windll.kernel32.GetCurrentProcess
    current.restype = ctypes.c_void_p
    info = ctypes.windll.psapi.GetProcessMemoryInfo
    info.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    info(current(), ctypes.byref(counters), counters.cb)
    return round(counters.PeakWorkingSetSize / 2**20)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def day_dir(work: Path, day: date) -> Path:
    return work / "days" / f"{day:%Y-%m-%d}"


def observe_one(args, day: date) -> dict:
    """Stage 1 for one service day: verify cached inputs, infer stop times, write buckets."""
    began = time.monotonic()
    manifest_file = manifest_path(args.work, day)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    mismatched = [
        key
        for key, _size, _md5, sha in manifest["siri"]["objects"]
        if file_sha256(args.raw_cache / "siri" / key) != sha
    ]
    if mismatched:
        raise SystemExit(f"{day}: {len(mismatched)} cached minutes differ from the manifest")
    schedule = load_day(schedule_path(args.raw_cache, day), day)
    rides, archive = load_rides(args.raw_cache / "siri", expected_minutes(day), day)
    final = day_dir(args.work, day)
    partial = final.with_name(final.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    writer = DayWriter(partial)
    try:
        result = observe_day(schedule, rides, writer.write, decimation_share=args.decimation)
    finally:
        writer.close()
    files = {
        f"calls-{index:02d}.csv.gz": file_sha256(partial / f"calls-{index:02d}.csv.gz")
        for index in range(BUCKETS)
    }
    summary = {
        "task": "OB-01 per-day observations (historical replay; not live, not for display)",
        "serviceDate": day.isoformat(),
        "dayType": day_type(day),
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "inputs": {
            "manifest": manifest_file.as_posix(),
            "manifestFileSha256": file_sha256(manifest_file),
            "siriManifestSha256": manifest["siri"]["manifestSha256"],
            "siriMinutesExpected": manifest["siri"]["expectedMinutes"],
            "siriMinutesRead": archive["files"],
            "siriMinutesMissing": len(archive["missingFiles"]),
            "gtfsKey": manifest["gtfs"]["key"],
            "gtfsEtag": manifest["gtfs"]["etag"],
            "gtfsMembersSha256": {
                name: member["sha256"] for name, member in manifest["gtfs"]["members"].items()
            },
        },
        "parameters": PARAMETERS,
        "pings": {
            "serviceDatePings": archive["pings"],
            "skippedVisits": archive["skippedVisits"],
            "otherServiceDatePings": archive["otherDatePings"],
        },
        **result,
        "files": files,
        "runtime": {
            "seconds": round(time.monotonic() - began),
            "peakWorkingSetMb": peak_memory_mb(),
        },
    }
    (partial / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    partial.replace(final)
    return summary


def observe(args) -> int:
    """Observe each fetched day once; a lock file lets several processes share a range."""
    days = days_between(args.start, args.end, set(args.exclude))
    for day in reversed(days) if args.reverse else days:
        if (day_dir(args.work, day) / "summary.json").exists():
            print(f"{day}: already observed", flush=True)
            continue
        if not manifest_path(args.work, day).exists():
            print(f"{day}: no manifest (fetch first); skipping", flush=True)
            continue
        lock = day_dir(args.work, day).with_name(f"{day:%Y-%m-%d}.lock")
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            print(f"{day}: locked by another process ({lock}); skipping", flush=True)
            continue
        try:
            if (day_dir(args.work, day) / "summary.json").exists():
                continue
            summary = observe_one(args, day)
        finally:
            lock.unlink()
        matching = summary["matching"]
        print(
            f"{day}: {matching['scheduledTripsObserved']}/{matching['scheduledTrips']} trips, "
            f"{summary['calls'].get('observed', 0)} calls observed, "
            f"{summary['runtime']['seconds']} s, peak {summary['runtime']['peakWorkingSetMb']} MB",
            flush=True,
        )
    return 0


PILOT_OUTLIER_STOP_PAIRS = (("8877", "11755"), ("9402", "51369"), ("11562", "9063"))
JERUSALEM_BOX = (31.70, 31.90, 35.10, 35.30)  # lat min/max, lon min/max (rough)
HOLIDAY_NOTE = (
    "Calibration November 2025 and held-out January 2026 were chosen as the most recent whole "
    "months with no Jewish public holiday or holiday eve (Sukkot/Simchat Torah ended 14 Oct "
    "2025; Hanukkah 14-22 Dec 2025 and its school break fall between them; Tu BiShvat 2 Feb), no "
    "Ramadan/Eid (Ramadan 2026 began about 18 Feb), school in session and the same UTC+2 clock "
    "(winter time 26 Oct 2025 - 27 Mar 2026). September 2026 (pilot) is Tishrei holiday season."
)


def observed_days(args) -> list[date]:
    days = [
        day
        for day in days_between(args.start, args.end, set(args.exclude))
        if (day_dir(args.work, day) / "summary.json").exists()
    ]
    if not days:
        raise SystemExit("no observed days in range")
    return days


def day_summaries(args, days: list[date]) -> list[dict]:
    return [
        json.loads((day_dir(args.work, day) / "summary.json").read_text(encoding="utf-8"))
        for day in days
    ]


def write_table(path: Path, rows: list[dict]) -> dict:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["empty"])
        writer.writeheader()
        writer.writerows(rows)
    return {"file": path.name, "rows": len(rows), "sha256": file_sha256(path)}


def context(raw: Path, day: date) -> tuple[dict, dict]:
    """Routes and stops of one day's archived GTFS, for labelling review rows."""
    path = schedule_path(raw, day)
    routes, stops = {}, {}
    if not path.exists():
        return routes, stops
    with zipfile.ZipFile(path) as archive:
        with archive.open("routes.txt") as raw_routes:
            for row in csv.DictReader(io.TextIOWrapper(raw_routes, encoding="utf-8-sig")):
                routes[row["route_id"]] = {
                    "agency": row.get("agency_id", ""),
                    "shortName": row.get("route_short_name", ""),
                    "longName": row.get("route_long_name", ""),
                }
        with archive.open("stops.txt") as raw_stops:
            for row in csv.DictReader(io.TextIOWrapper(raw_stops, encoding="utf-8-sig")):
                stops[row["stop_id"]] = {
                    "code": row.get("stop_code", ""),
                    "name": row.get("stop_name", ""),
                    "lat": float(row["stop_lat"]),
                    "lon": float(row["stop_lon"]),
                }
    return routes, stops


def in_jerusalem(stop: dict | None) -> bool:
    if not stop:
        return False
    lat_min, lat_max, lon_min, lon_max = JERUSALEM_BOX
    return lat_min <= stop["lat"] <= lat_max and lon_min <= stop["lon"] <= lon_max


def summary_digest(files: dict) -> str:
    digest = hashlib.sha256()
    for name, sha in sorted(files.items()):
        digest.update(f"{name}\t{sha}\n".encode())
    return digest.hexdigest()


def pins(summaries: list[dict]) -> list[dict]:
    """Per-day archive pins: GTFS object and members, SIRI manifest digest and gaps."""
    pinned = []
    for summary in summaries:
        inputs = summary["inputs"]
        members = inputs["gtfsMembersSha256"]
        pinned.append(
            {
                "serviceDate": summary["serviceDate"],
                "dayType": summary["dayType"],
                "gtfsKey": inputs["gtfsKey"],
                "gtfsEtag": inputs["gtfsEtag"],
                "gtfsStopTimesSha256": members["stop_times.txt"],
                "gtfsTripsSha256": members["trips.txt"],
                "gtfsCalendarSha256": members["calendar.txt"],
                "gtfsRoutesSha256": members["routes.txt"],
                "siriManifestSha256": inputs["siriManifestSha256"],
                "siriManifestFileSha256": inputs["manifestFileSha256"],
                "siriMinutesReadOfExpected": [
                    inputs["siriMinutesRead"],
                    inputs["siriMinutesExpected"],
                ],
                "dayFilesSha256": summary_digest(summary["files"]),
            }
        )
    return pinned


def daily_rows(summaries: list[dict]) -> list[dict]:
    return [
        {
            "serviceDate": s["serviceDate"],
            "dayType": s["dayType"],
            "siriMinutesMissing": s["inputs"]["siriMinutesMissing"],
            "scheduledTrips": s["matching"]["scheduledTrips"],
            "observedTrips": s["matching"]["scheduledTripsObserved"],
            "tripCoverage": s["matching"]["scheduledTripCoverage"],
            "callsObserved": s["calls"].get("observed", 0),
            "interpolationP50Seconds": (s["interpolationCheckAbsErrorSeconds"] or {}).get("p50"),
        }
        for s in summaries
    ]


def agency_totals(summaries: list[dict]) -> dict:
    totals: dict[str, Counter] = {}
    for summary in summaries:
        for agency, counts in summary["byAgency"].items():
            totals.setdefault(agency, Counter()).update(counts)
    ordered = sorted(totals.items(), key=lambda item: -item[1]["scheduledTrips"])
    return {
        agency: dict(counts)
        | {
            "tripCoverage": round(counts["observedTrips"] / counts["scheduledTrips"], 3)
            if counts["scheduledTrips"]
            else None
        }
        for agency, counts in ordered
    }


def trip_totals(summaries: list[dict]) -> dict:
    scheduled = sum(s["matching"]["scheduledTrips"] for s in summaries)
    observed = sum(s["matching"]["scheduledTripsObserved"] for s in summaries)
    return {
        "scheduledTrips": scheduled,
        "observedTrips": observed,
        "tripCoverage": round(observed / scheduled, 4) if scheduled else None,
    }


def aggregate(args) -> int:
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    days = observed_days(args)
    summaries = day_summaries(args, days)
    tables = args.work / "tables" / args.name
    if tables.exists():
        raise SystemExit(f"refusing to overwrite {tables}")
    partial = tables.with_name(tables.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    began = time.monotonic()
    routes, stops = context(args.raw_cache, days[-1])
    files, counts = [], Counter()
    hourly: dict[str, dict[str, Counter]] = {}
    slowest: list[tuple] = []
    pilot_rows: list[dict] = []
    ratio_outliers: Counter = Counter()
    for bucket in range(BUCKETS):
        month = MonthAggregate()
        for index, day in enumerate(days):
            month.add(index, day_type(day), read_bucket(day_dir(args.work, day), bucket))
        delay_rows, segment_rows = month.delay_rows(), month.segment_rows()
        files.append(write_table(partial / f"delays-{bucket:02d}.csv.gz", delay_rows))
        files.append(write_table(partial / f"segments-{bucket:02d}.csv.gz", segment_rows))
        for (kind, hour), histogram in month.hourly.items():
            hourly.setdefault(kind, {}).setdefault(str(hour), Counter()).update(histogram)
        for kind, rows in (("delay", delay_rows), ("segment", segment_rows)):
            for row in rows:
                counts[f"{kind}Keys"] += 1
                counts[f"{kind}ScheduledCalls"] += row["scheduledCalls"]
                counts[f"{kind}Samples"] += row["samples"]
                if row["samples"]:
                    counts[f"{kind}KeysWithSamples"] += 1
                if row["publishable"]:
                    counts[f"{kind}KeysPublishable"] += 1
                    counts[f"{kind}SamplesInPublishableKeys"] += row["samples"]
        for row in segment_rows:
            if (row["fromStopId"], row["toStopId"]) in PILOT_OUTLIER_STOP_PAIRS:
                pilot_rows.append(row)
            planned = row["scheduledSecondsMedian"]
            if not row["publishable"] or not planned or planned < 120:
                continue
            ratio = row["runP50Seconds"] / planned
            if ratio >= 3:
                ratio_outliers["publishableSegmentsRatioAtLeast3"] += 1
                if in_jerusalem(stops.get(row["fromStopId"])):
                    ratio_outliers["ofWhichInJerusalemBox"] += 1
            entry = (ratio, row["routeId"], row["fromStopId"], row["toStopId"], row["hour"])
            heapq.heappush(slowest, (*entry, row["dayType"], row))
            if len(slowest) > 20:
                heapq.heappop(slowest)
        del month, delay_rows, segment_rows
        print(f"bucket {bucket:02d} done, {time.monotonic() - began:.0f} s", flush=True)

    def label(row: dict) -> dict:
        origin, destination = stops.get(row["fromStopId"]), stops.get(row["toStopId"])
        ratio = None
        if row["runP50Seconds"] is not None and row["scheduledSecondsMedian"]:
            ratio = round(row["runP50Seconds"] / row["scheduledSecondsMedian"], 2)
        return row | {
            "route": routes.get(row["routeId"]),
            "fromStop": origin,
            "toStop": destination,
            "inJerusalemBox": in_jerusalem(origin),
            "ratioP50": ratio,
        }

    partial.replace(tables)
    daily = daily_rows(summaries)
    interpolation = [r["interpolationP50Seconds"] for r in daily if r["interpolationP50Seconds"]]
    report = {
        "task": "OB-01 month batch (historical replay; not live, not approved for public display)",
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "name": args.name,
        "period": {"start": days[0].isoformat(), "end": days[-1].isoformat()},
        "serviceDays": len(days),
        "dayTypes": dict(Counter(day_type(day) for day in days)),
        "excludedDates": [day.isoformat() for day in args.exclude],
        "daySelection": HOLIDAY_NOTE,
        "source": {
            "siri": f"{BUCKET_URL}/{SIRI_PREFIX}/YYYY/MM/DD/HH/MM.br (Hasadna Open Bus)",
            "gtfs": f"{BUCKET_URL}/gtfs_archive/YYYY/MM/DD/{GTFS_FEED}",
            "pinning": (
                "Per day: the GTFS object key and ETag plus SHA-256 of the members read, and "
                "siriManifestSha256 = SHA-256 over sorted 'key<TAB>size<TAB>sha256' lines of "
                "every SIRI minute read (each MD5-checked against the S3 listing ETag). Full "
                "per-minute manifests: <work>/manifests/<date>.json (siriManifestFileSha256)."
            ),
            "work": args.work.as_posix(),
        },
        "parameters": PARAMETERS
        | {
            "minSamples": MIN_SAMPLES,
            "minServiceDays": MIN_SERVICE_DAYS,
            "minCoverage": MIN_COVERAGE,
            "keys": "delay: route x stop x local hour x day type; segment: route x stop pair x "
            "hour of the first stop x day type",
        },
        "archivePins": pins(summaries),
        "daily": daily,
        "totals": trip_totals(summaries)
        | {
            "serviceDatePings": sum(s["pings"]["serviceDatePings"] for s in summaries),
            "calls": dict(sum((Counter(s["calls"]) for s in summaries), Counter())),
            "interpolationCheckMedianOfDailyP50Seconds": percentile(interpolation, 0.5)
            if interpolation
            else None,
            "note": "Unobserved trips may have run untracked; never label them cancelled.",
        },
        "byAgency": agency_totals(summaries),
        "keys": dict(counts),
        "enRouteDelayByScheduledHour": {
            kind: {
                hour: histogram_summary(hist)
                for hour, hist in sorted(hours.items(), key=lambda item: int(item[0]))
            }
            for kind, hours in sorted(hourly.items())
        },
        "segmentRatioOutliers": dict(ratio_outliers),
        "slowestPublishableSegmentsVsSchedule": [
            label(item[-1]) for item in sorted(slowest, key=lambda item: -item[0])
        ],
        "pilotOutlierStopPairs": [label(row) for row in pilot_rows],
        "tables": {"directory": tables.as_posix(), "files": files},
        "runtimeSeconds": round(time.monotonic() - began),
        "scope": (
            "Historical replay from a third-party archive of MOT SIRI. Inferred times are about "
            "±30 s at one-minute pings. Figures below the publication rule must not be shown. "
            "Public display needs Phase 4 and data terms."
        ),
    }
    write_new(args.output, report)
    print(json.dumps(report["totals"], indent=2))
    print(json.dumps(report["keys"], indent=2))
    return 0


def load_calibration(tables: Path, bucket: int) -> tuple[dict, dict]:
    def read(name: str, prefix: str, key_of) -> dict:
        result = {}
        with gzip.open(tables / f"{name}-{bucket:02d}.csv.gz", "rt", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                if row["samples"] == "0":
                    continue
                result[key_of(row)] = {
                    "p10": float(row[f"{prefix}P10Seconds"]),
                    "p50": float(row[f"{prefix}P50Seconds"]),
                    "p90": float(row[f"{prefix}P90Seconds"]),
                    "samples": int(row["samples"]),
                    "publishable": row["publishable"] == "True",
                }
        return result

    delays = read(
        "delays", "delay", lambda r: (r["routeId"], r["stopId"], int(r["hour"]), r["dayType"])
    )
    segments = read(
        "segments",
        "run",
        lambda r: (r["routeId"], r["fromStopId"], r["toStopId"], int(r["hour"]), r["dayType"]),
    )
    return delays, segments


def zero_baseline(key: tuple, scheduled: int) -> float:
    return 0


def run_baseline(key: tuple, scheduled: int) -> float:
    return scheduled


def validate(args) -> int:
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    days = observed_days(args)
    summaries = day_summaries(args, days)
    tables = args.work / "tables" / args.calibration
    calibration_report = json.loads(args.calibration_report.read_text(encoding="utf-8"))
    began = time.monotonic()
    total_delays = HeldOutCheck({}, baseline=zero_baseline)
    total_segments = HeldOutCheck({}, baseline=run_baseline)
    hours: dict[int, int] = {}

    def hour_of(epoch_seconds: int) -> int:
        slot = epoch_seconds // 3600
        if slot not in hours:
            hours[slot] = local_hour(slot * 3600)
        return hours[slot]

    for bucket in range(BUCKETS):
        cal_delays, cal_segments = load_calibration(tables, bucket)
        delays = HeldOutCheck(cal_delays, baseline=zero_baseline)
        segments = HeldOutCheck(cal_segments, baseline=run_baseline)
        for day in days:
            kind = day_type(day)
            for trip in trips_of(read_bucket(day_dir(args.work, day), bucket)):
                trip.sort(key=lambda row: row[2])
                for row in trip:
                    if row[5] is not None:
                        delays.add((row[1], row[3], hour_of(row[4]), kind), row[5], scheduled=0)
                for first, second in zip(trip, trip[1:], strict=False):
                    if first[5] is None or second[5] is None:
                        continue
                    planned = second[4] - first[4]
                    segments.add(
                        (first[1], first[3], second[3], hour_of(first[4]), kind),
                        planned + second[5] - first[5],
                        scheduled=planned,
                    )
        delays.merge_into(total_delays)
        segments.merge_into(total_segments)
        del cal_delays, cal_segments, delays, segments
        print(f"bucket {bucket:02d} done, {time.monotonic() - began:.0f} s", flush=True)
    report = {
        "task": "OB-01 held-out validation (historical replay; not live, not for public display)",
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "calibration": {
            "name": args.calibration,
            "report": args.calibration_report.as_posix(),
            "reportSha256": file_sha256(args.calibration_report),
            "period": calibration_report["period"],
            "tablesDirectory": tables.as_posix(),
            "tableFiles": calibration_report["tables"]["files"],
        },
        "heldOut": {
            "period": {"start": days[0].isoformat(), "end": days[-1].isoformat()},
            "serviceDays": len(days),
            "dayTypes": dict(Counter(day_type(day) for day in days)),
            "daySelection": HOLIDAY_NOTE,
            "archivePins": pins(summaries),
            "daily": daily_rows(summaries),
            "totals": trip_totals(summaries),
            "byAgency": agency_totals(summaries),
        },
        "method": (
            "Every held-out observation is placed against the calibration p10/p50/p90 of the "
            "same key. If distributions transfer, about 10% fall below p10, 50% below p50 and "
            "10% above p90. medianAbsErrorSeconds compares the calibration p50 with the "
            "schedule-only prediction (0 s delay; scheduled run time for segments) in 10 s bins. "
            "publishableKeyMedianShiftSeconds compares held-out and calibration medians for keys "
            f"with at least {MIN_SAMPLES} held-out samples."
        ),
        "stopDelay": total_delays.report(),
        "segmentRunTime": total_segments.report(),
        "runtimeSeconds": round(time.monotonic() - began),
    }
    write_new(args.output, report)
    for kind in ("stopDelay", "segmentRunTime"):
        print(kind, json.dumps(report[kind]["byStratum"], indent=1))
    return 0


def review_targets(report: dict, top: int) -> list[dict]:
    targets: dict[tuple, dict] = {}
    rows = report["pilotOutlierStopPairs"] + report["slowestPublishableSegmentsVsSchedule"][:top]
    for row in rows:
        key = (row["routeId"], row["fromStopId"], row["toStopId"])
        target = targets.setdefault(
            key,
            {
                "routeId": row["routeId"],
                "fromStopId": row["fromStopId"],
                "toStopId": row["toStopId"],
                "route": row.get("route"),
                "fromStop": row.get("fromStop"),
                "toStop": row.get("toStop"),
                "monthRows": [],
            },
        )
        target["monthRows"].append(
            {
                field: row[field]
                for field in (
                    "hour",
                    "dayType",
                    "samples",
                    "coverage",
                    "serviceDays",
                    "scheduledSecondsMedian",
                    "runP10Seconds",
                    "runP50Seconds",
                    "runP90Seconds",
                    "publishable",
                    "ratioP50",
                )
            }
        )
    return list(targets.values())


def nearest_stop(stops: dict, point: tuple[float, float] | None) -> dict | None:
    if point is None or not stops:
        return None
    stop_id, stop = min(
        stops.items(),
        key=lambda item: haversine_m(point[0], point[1], item[1]["lat"], item[1]["lon"]),
    )
    distance = haversine_m(point[0], point[1], stop["lat"], stop["lon"])
    return {"stopId": stop_id, "name": stop["name"], "metres": round(distance)}


def review(args) -> int:
    """Trace the slowest and the pilot's Jerusalem segments on raw pings for a few days."""
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    targets = review_targets(report, args.top)
    routes_wanted = {target["routeId"] for target in targets}
    began = time.monotonic()
    traces: dict[tuple, list[dict]] = {}
    stops: dict = {}
    for day in args.day:
        schedule = load_day(schedule_path(args.raw_cache, day), day)
        _, stops = context(args.raw_cache, day)
        pings: dict[tuple, list[TracePing]] = {}
        for key in expected_minutes(day):
            path = siri_path(args.raw_cache, key)
            if not path.exists():
                continue
            for ping in parse_snapshot(path.read_bytes())[0]:
                if ping.line_ref in routes_wanted and ping.service_date == day:
                    identity = (ping.line_ref, ping.origin_departure, ping.trip_ref)
                    pings.setdefault(identity, []).append(
                        TracePing(
                            ping.recorded_at, ping.distance_m, ping.lat, ping.lon, ping.velocity
                        )
                    )
        for (line_ref, origin, _trip_ref), ride_pings in pings.items():
            trip, _reason = match_ride(schedule, line_ref, origin)
            if trip is None:
                continue
            calls = trip.calls
            for target in targets:
                if target["routeId"] != line_ref:
                    continue
                for first, second in zip(calls, calls[1:], strict=False):
                    if (first.stop_id, second.stop_id) != (
                        target["fromStopId"],
                        target["toStopId"],
                    ):
                        continue
                    if first.distance_m is None or second.distance_m is None:
                        continue
                    trace = segment_trace(ride_pings, first.distance_m, second.distance_m)
                    if trace is None:
                        continue
                    trace |= {
                        "serviceDate": day.isoformat(),
                        "hour": local_hour(first.departure),
                        "scheduledSeconds": second.arrival - first.departure,
                        "segmentMetres": round(second.distance_m - first.distance_m),
                        "class": classify(trace),
                    }
                    key = (target["routeId"], target["fromStopId"], target["toStopId"])
                    traces.setdefault(key, []).append(trace)
        print(f"{day}: traced, {time.monotonic() - began:.0f} s", flush=True)
    findings = []
    for target in targets:
        key = (target["routeId"], target["fromStopId"], target["toStopId"])
        found = traces.get(key, [])
        slow = [t for t in found if t["runSeconds"] >= 3 * max(t["scheduledSeconds"], 60)]
        places = Counter(
            (round(t["longestFrozenAt"][0], 3), round(t["longestFrozenAt"][1], 3))
            for t in slow
            if t["longestFrozenAt"]
        )
        common = places.most_common(1)[0] if places else None
        findings.append(
            target
            | {
                "tracedTrips": len(found),
                "segmentMetres": found[0]["segmentMetres"] if found else None,
                "runSecondsAll": distribution_summary([t["runSeconds"] for t in found])
                if found
                else None,
                "slowTrips": len(slow),
                "slowTripClasses": dict(Counter(t["class"] for t in slow)),
                "slowTripFrozenShareMedian": percentile(
                    [t["frozenSeconds"] / t["runSeconds"] for t in slow if t["runSeconds"]], 0.5
                )
                if slow
                else None,
                "slowTripGpsNetMetresWhileFrozenMedian": percentile(
                    [t["gpsNetMetresWhileFrozen"] for t in slow], 0.5
                )
                if slow
                else None,
                "commonStandstillPlace": {
                    "latLon": list(common[0]),
                    "slowTrips": common[1],
                    "nearestStop": nearest_stop(stops, common[0]),
                }
                if common
                else None,
                "slowHours": dict(sorted(Counter(t["hour"] for t in slow).items())),
            }
        )
    result = {
        "task": "OB-01 outlier-segment review (historical replay; not live, not for display)",
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "monthReport": args.report.as_posix(),
        "monthReportSha256": file_sha256(args.report),
        "days": [day.isoformat() for day in args.day],
        "method": (
            "For each target route x stop pair, every matched trip on the review days is traced "
            "on raw pings. A slow trip takes at least 3x its scheduled time (minimum 60 s). "
            "'Frozen' stretches are consecutive pings whose SIRI distance advances by at most "
            f"{FROZEN_M} m; net GPS movement over them separates a standstill ('stationary', "
            f"frozen for at least {STATIONARY_SHARE:.0%} of the run) from a frozen-distance "
            f"artefact (at least {ARTEFACT_GPS_M} m of GPS movement). Heuristic, unreviewed by "
            "a human."
        ),
        "targets": findings,
        "runtimeSeconds": round(time.monotonic() - began),
    }
    write_new(args.output, result)
    for finding in findings:
        print(
            finding["routeId"],
            finding["fromStopId"],
            finding["toStopId"],
            finding["tracedTrips"],
            finding["slowTrips"],
            finding["slowTripClasses"],
            (finding["commonStandstillPlace"] or {}).get("nearestStop"),
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("fetch", "observe"):
        command = sub.add_parser(name)
        command.add_argument("--start", type=date.fromisoformat, required=True)
        command.add_argument("--end", type=date.fromisoformat, required=True)
        command.add_argument("--exclude", type=date.fromisoformat, action="append", default=[])
        command.add_argument("--raw-cache", type=Path, required=True)
        command.add_argument("--work", type=Path, required=True)
        command.add_argument("--workers", type=int, default=16)
        command.add_argument("--decimation", type=float, default=0.02)
        command.add_argument("--reverse", action="store_true")
    for name in ("aggregate", "validate"):
        command = sub.add_parser(name)
        command.add_argument("--start", type=date.fromisoformat, required=True)
        command.add_argument("--end", type=date.fromisoformat, required=True)
        command.add_argument("--exclude", type=date.fromisoformat, action="append", default=[])
        command.add_argument("--raw-cache", type=Path, required=True)
        command.add_argument("--work", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name == "aggregate":
            command.add_argument("--name", required=True)
        else:
            command.add_argument("--calibration", required=True)
            command.add_argument("--calibration-report", type=Path, required=True)
    command = sub.add_parser("review")
    command.add_argument("--report", type=Path, required=True)
    command.add_argument("--day", type=date.fromisoformat, action="append", required=True)
    command.add_argument("--raw-cache", type=Path, required=True)
    command.add_argument("--top", type=int, default=10)
    command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    commands = {
        "fetch": fetch,
        "observe": observe,
        "aggregate": aggregate,
        "validate": validate,
        "review": review,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
