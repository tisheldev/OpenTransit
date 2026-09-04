#!/usr/bin/env python3
"""POC-1 — the single GTFS ingest entry point.

    python poc/gtfs/ingest.py                       # refresh, parse, load, check
    python poc/gtfs/ingest.py --offline             # use the bytes already on disk
    python poc/gtfs/ingest.py --data-dir <empty>    # cold run, downloads everything

One command, no manual steps, works from an empty data directory. That is the
PRD §6 PASS bar and corpus check E10.

Order of work:
  1. refresh   — GET each feed, sha256, validate the zip, replace on change
  2. parse     — all seven PRD §6 file groups, streamed (parse.py)
  3. pair      — refuse a TripIdToDate that does not belong (pairing.py, E05)
  4. load      — the five ADR-0003 tables into Postgres + PostGIS (db.py)
  5. verify    — PRD §6 validation examples and the ten E-checks (checks.py)
  6. record    — poc/results/poc-1.json, corpora/stops.json resolved ids
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

if __package__ in (None, ""):  # allow `python poc/gtfs/ingest.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "poc.gtfs"

from . import checks, corpus as corpus_mod, db, fetch, pairing, queries as Q  # noqa: E402
from .parse import parse_feed  # noqa: E402

POC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = POC_ROOT.parent
PRIMARY = "Gtfs_10_days.zip"
COMPARISON = "israel-public-transportation.zip"
T2D = "TripIdToDate.zip"


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def peak_rss_mb() -> float | None:
    """Peak resident set of this process, MB. None if it cannot be measured.

    ADR 0003 keeps stop_times out of Postgres precisely so that ingestion
    stays inside a modest memory envelope, so this number is evidence, not
    decoration. Never report a guess: None means not measured.
    """
    try:
        import os
        import psutil
        mi = psutil.Process(os.getpid()).memory_info()
        peak = getattr(mi, "peak_wset", None) or mi.rss
        return round(peak / (1 << 20), 1)
    except Exception:  # noqa: BLE001
        pass
    try:
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:  # noqa: BLE001
        return None


def sha_of(data_dir: Path, name: str) -> str | None:
    p = data_dir / name
    return fetch.sha256_file(p) if p.exists() else None


# ---------------------------------------------------------------------------

def run(args) -> dict:
    t_start = time.monotonic()
    data_dir = Path(args.data_dir).resolve()
    report: dict = {"data_dir": str(data_dir), "schema": args.schema}

    started_empty = not any(data_dir.glob("*.zip")) if data_dir.exists() else True
    report["started_empty"] = started_empty

    # -- 1. refresh ---------------------------------------------------
    refresh_results: dict[str, fetch.FetchResult] = {}
    downloaded_bytes = 0
    if args.offline:
        log("refresh SKIPPED (--offline): using the bytes already in the data dir")
        for n in (PRIMARY, COMPARISON, T2D):
            if not (data_dir / n).exists():
                raise SystemExit(f"--offline but {n} is not in {data_dir}")
    else:
        want = [PRIMARY, T2D] + ([] if args.skip_comparison else [COMPARISON])
        log(f"refresh: GET {len(want)} feeds into {data_dir}")
        refresh_results = fetch.refresh(data_dir, want, timeout=args.timeout)
        for name, r in refresh_results.items():
            log(f"  {name:38s} {r.status:9s} {(r.size_bytes or 0)/1e6:8.1f} MB "
                f"{r.seconds:6.1f}s sha {(r.sha256 or '')[:12]}")
            if r.status == "failed":
                raise SystemExit(f"refresh failed for {name}: {r.error}")
            downloaded_bytes += r.size_bytes or 0
        fetch.write_manifest(data_dir, refresh_results)
    report["refresh"] = {k: v.as_dict() for k, v in refresh_results.items()}
    report["downloaded_bytes"] = downloaded_bytes

    shas = {n: sha_of(data_dir, n) for n in (PRIMARY, COMPARISON, T2D)}
    report["sha256"] = shas
    log(f"primary feed sha256 {shas[PRIMARY]}")

    # -- 2. parse -----------------------------------------------------
    corpus_path = POC_ROOT / "corpora" / "stops.json"
    corpus_doc = checks.load_corpus(corpus_path)

    def selector(fp):
        """Detail is collected for every stop within 3 km of a corpus entry.

        Corpus resolution is mode-aware and therefore has to know which route
        types call at each *candidate*, not just at the eventual winner — and
        that is only known after the stop_times pass. Collecting the whole
        candidate pool in the one pass avoids a second read of a 1.77 GB file.
        City-wide totals come from departures_per_stop, a 30k-entry counter
        over every stop that costs nothing.
        """
        return corpus_mod.nearby_ids(fp, corpus_doc)

    log(f"parse: {PRIMARY} (all seven PRD §6 groups, streamed)")
    t = time.monotonic()
    primary = parse_feed(data_dir / PRIMARY, shas[PRIMARY],
                         detail_selector=selector, progress=log)
    log(f"  parsed in {time.monotonic() - t:.1f}s: " +
        ", ".join(f"{k}={v:,}" for k, v in sorted(primary.rows.items())))

    comparison = None
    if (data_dir / COMPARISON).exists() and not args.skip_comparison:
        log(f"parse: {COMPARISON} (row counts only, for E06 / ADR 0005)")
        t = time.monotonic()
        comparison = parse_feed(data_dir / COMPARISON, shas[COMPARISON])
        log(f"  parsed in {time.monotonic() - t:.1f}s: " +
            ", ".join(f"{k}={v:,}" for k, v in sorted(comparison.rows.items())))

    # -- 3. TripIdToDate pairing (E05) --------------------------------
    log(f"parse: {T2D}")
    t2d = pairing.parse_trip_id_to_date(data_dir / T2D)
    log(f"  {t2d.rows:,} rows, {t2d.distinct_trip_ids:,} distinct TripId, window "
        f"{t2d.min_from_date}..{t2d.max_to_date}")

    active = sorted({d for s in primary.services.services.values() for d in s.active_dates})
    window = (active[0], active[-1]) if active else (None, None)
    pair_primary = pairing.check_pairing(primary.trips.keys(), t2d, window)
    log(f"  pairing vs {PRIMARY}: {pair_primary['match_fraction']:.4%} "
        f"-> {pair_primary['verdict']}")

    pair_comparison = None
    if comparison is not None:
        cactive = sorted({d for s in comparison.services.services.values()
                          for d in s.active_dates})
        cwin = (cactive[0], cactive[-1]) if cactive else (None, None)
        pair_comparison = pairing.check_pairing(comparison.trips.keys(), t2d, cwin)
        log(f"  pairing vs {COMPARISON}: {pair_comparison['match_fraction']:.4%} "
            f"-> {pair_comparison['verdict']}")

    # Negative control: the default path must stop on a mismatch.
    negative = {}
    try:
        pairing.pair_or_raise(["definitely-not-a-real-trip-id"], t2d)
        negative = {"raised": False,
                    "note": "pair_or_raise accepted a synthetic non-matching trip id"}
    except pairing.FeedPairingError as e:
        negative = {"raised": True, "error": str(e)}

    paired = pair_primary["verdict"] == "ACCEPTED"
    if not paired:
        log("  WARNING: TripIdToDate does NOT pair with the primary feed. "
            "Loading it for row-count evidence only; it must not be used to "
            "resolve trips for this feed.")
        if not args.allow_unpaired_trip_id_to_date:
            pairing.pair_or_raise(primary.trips.keys(), t2d, window)

    # -- 4. load ------------------------------------------------------
    log(f"load: Postgres schema '{args.schema}'")
    conn = db.connect(args.dsn)
    db.create_schema(conn, args.schema)
    loaded = {}
    t = time.monotonic()
    loaded["routes"] = db.load_routes(conn, primary, args.schema)
    loaded["stops"] = db.load_stops(conn, primary, args.schema)
    loaded["calendars"] = db.load_calendars(conn, primary, args.schema)
    loaded["trips"] = db.load_trips(conn, primary, args.schema)
    conn.commit()
    loaded["trip_id_to_date"] = db.load_trip_id_to_date(conn, data_dir / T2D, args.schema)
    conn.commit()
    db.create_indexes(conn, args.schema)
    db.record_run(conn, args.schema, PRIMARY, shas[PRIMARY], shas[T2D], paired,
                  f"pairing {pair_primary['verdict']} at "
                  f"{pair_primary['match_fraction']:.6f} overlap")
    log(f"  loaded in {time.monotonic() - t:.1f}s: " +
        ", ".join(f"{k}={v:,}" for k, v in loaded.items()))
    report["rows_loaded"] = db.table_counts(conn, args.schema)

    # -- 5. verify ----------------------------------------------------
    log("verify: PRD §6 validation examples")
    dep = primary.departures_per_stop
    val = {
        "tel_aviv": Q.city_summary(conn, args.schema, Q.CITY_TEL_AVIV, dep),
        "jerusalem": Q.city_summary(conn, args.schema, Q.CITY_JERUSALEM, dep),
        "haifa": Q.city_summary(conn, args.schema, Q.CITY_HAIFA, dep),
        "israel_railways": Q.rail_summary(conn, args.schema),
        "multiple_bus_operators": Q.bus_operator_summary(conn, args.schema),
    }
    for k, v in val.items():
        log(f"  {k:24s} ok={v['ok']}")
    report["validation_detail"] = val
    report["modes"] = Q.mode_summary(conn, args.schema)

    # Corpus stops, resolved now that stop_times has told us which route
    # types actually call at each candidate.
    # Departures are recorded against platforms, not against the
    # location_type=1 station above them, so roll a station's children up —
    # otherwise every station looks like it has no service at all.
    route_types: dict[str, set] = {}
    for sid, rids in primary.detail_routes.items():
        t = {primary.routes[rid].get("route_type") for rid in rids
             if rid in primary.routes}
        route_types.setdefault(sid, set()).update(t)
        parent = (primary.stops.get(sid, {}).get("parent_station") or "").strip()
        if parent:
            route_types.setdefault(parent, set()).update(t)
    resolutions = corpus_mod.resolve(primary, corpus_doc, route_types)
    for r in resolutions:
        sid = r["resolved_stop_id"]
        ids = [sid] + r["platforms"]
        r["observed_departures"] = sum(dep.get(i, 0) for i in ids)
        per_hour: dict[tuple, int] = {}
        for (st_id, svc, hour), n in primary.detail_departures.items():
            if st_id in ids:
                per_hour[(svc, hour)] = per_hour.get((svc, hour), 0) + n
        r["peak_departures_per_hour"] = max(per_hour.values()) if per_hour else 0
        # The corpus states a floor per entry; report whether the feed clears
        # it. This is evidence for checkpoint H4, not a pass/fail of POC-1.
        floor = next((e.get("expect_min_services_per_hour")
                      for e in corpus_doc["stops"] if e["id"] == r["id"]), None)
        r["expect_min_services_per_hour"] = floor
        r["meets_expect_min_services_per_hour"] = (
            None if floor is None else r["peak_departures_per_hour"] >= floor)
        route_ids = {rt for i in ids for rt in primary.detail_routes.get(i, ())}
        r["observed_route_count"] = len(route_ids)
        r["feed_sha256"] = shas[PRIMARY]
        r["postgis_nearest"] = Q.snap_stop(
            conn, args.schema,
            next(e["lat"] for e in corpus_doc["stops"] if e["id"] == r["id"]),
            next(e["lon"] for e in corpus_doc["stops"] if e["id"] == r["id"]))[0]
        log(f"  {r['id']} {r['name'][:32]:32s} -> {sid:>7s} "
            f"{r['resolution_rule']:18s} {r['distance_m']:7.0f} m  "
            f"types={','.join(r['observed_route_types']) or '-':4s} "
            f"want={r['expected_route_type'] or '-'} "
            f"pf={r['platform_count']:<3d} dep={r['observed_departures']:>7,} "
            f"{'LOW-CONFIDENCE' if r['low_confidence'] else ''}")
    report["corpus_stops"] = resolutions
    if args.write_corpus:
        corpus_mod.write_back(corpus_path, resolutions)
        log(f"  wrote resolved_stop_id into {corpus_path}")

    # -- edge cases ---------------------------------------------------
    log("verify: edge-cases.json E01..E10")
    probe = change = None
    if not args.offline or args.head_probe:
        probe = checks.probe_head_vs_get(fetch.FEEDS[T2D]["url"], timeout=args.timeout)
        change = checks.change_detection_probe(T2D, timeout=args.timeout)
        log(f"  change detection: {change['first']['status']} -> "
            f"{change['second']['status']}")
    report["change_detection_probe"] = change
    per_date = Q.service_day_trip_counts(conn, args.schema)
    results = [
        checks.e01(probe, refresh_results, change),
        checks.e02(primary),
        checks.e03(conn, args.schema, primary),
        checks.e04(primary, comparison),
        checks.e05(pair_primary, pair_comparison, negative,
                   {"gtfs": shas[PRIMARY], "trip_id_to_date": shas[T2D]}),
        checks.e06(primary, comparison),
        checks.e07(primary, per_date),
        checks.e08(primary),
        checks.e09(conn, args.schema, resolutions, corpus_doc),
        checks.e10(args.cold_result),
    ]
    for r in results:
        log(f"  {r['id']} {r['result'].upper():13s} {r['detail'][:110]}")
    report["edge_case_results"] = results
    report["service_day_trip_counts"] = per_date

    # queryability proof: a real journey-shaped query against the loaded data
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT count(*) FROM {args.schema}.trips t "
            f"JOIN {args.schema}.routes r USING (route_id) "
            f"JOIN {args.schema}.calendars c USING (service_id) "
            f"WHERE r.route_type = 2 AND %s = ANY(c.active_dates)",
            (window[0],))
        report["queryable_probe"] = {
            "sql": "rail trips active on the first service day",
            "service_date": window[0].isoformat() if window[0] else None,
            "rows": cur.fetchone()[0],
        }
    conn.close()

    report["rows_parsed"] = primary.row_counts()
    report["comparison_rows_parsed"] = comparison.row_counts() if comparison else None
    report["feed_info"] = primary.feed_info
    report["service_window"] = [window[0].isoformat() if window[0] else None,
                                window[1].isoformat() if window[1] else None]
    report["trip_id_to_date"] = {
        "rows": t2d.rows, "distinct_trip_ids": t2d.distinct_trip_ids,
        "window": [t2d.min_from_date.isoformat() if t2d.min_from_date else None,
                   t2d.max_to_date.isoformat() if t2d.max_to_date else None],
        "paired_with_primary": paired,
        "read_stats": t2d.read_stats,
    }
    report["read_stats"] = primary.read_stats
    report["wall_seconds"] = round(time.monotonic() - t_start, 1)
    report["peak_rss_mb"] = peak_rss_mb()
    log(f"done in {report['wall_seconds']}s, peak RSS {report['peak_rss_mb']} MB")
    return report


# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser(description="POC-1 GTFS ingest")
    ap.add_argument("--data-dir", default=str(POC_ROOT / "data"))
    ap.add_argument("--dsn", default=db.DSN)
    ap.add_argument("--schema", default="public")
    ap.add_argument("--offline", action="store_true",
                    help="do not download; use the bytes already on disk")
    ap.add_argument("--skip-comparison", action="store_true",
                    help="skip the 60-day feed (E06 becomes not_observed)")
    ap.add_argument("--head-probe", action="store_true",
                    help="run the E01 HEAD-vs-GET diagnostic even when offline")
    ap.add_argument("--allow-unpaired-trip-id-to-date", action="store_true",
                    help="load TripIdToDate even when it does not pair with the feed; "
                         "without this an unpaired snapshot is a hard stop (E05)")
    ap.add_argument("--write-corpus", action="store_true",
                    help="write resolved_stop_id back into poc/corpora/stops.json")
    ap.add_argument("--report", default=None, help="write the raw run report here")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args(argv)
    args.cold_result = None

    report = run(args)
    if args.report:
        Path(args.report).write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8")
        log(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
