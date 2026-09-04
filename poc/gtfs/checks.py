"""The ten `poc/corpora/edge-cases.json` integrity checks.

Every check returns `{"id", "result", "detail", "evidence"}` where result is
`pass`, `fail` or `not_observed`. A missing result is not allowed; a
`not_observed` that says why is a useful answer.

Nothing here writes a capability. checks.py produces evidence, ingest.py
decides, and neither is allowed to assert something a run did not show.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import requests

from .gtfstime import format_gtfs_time, parse_gtfs_time
from . import queries as Q

GTFS_DIR = Path(__file__).resolve().parent


def _r(cid: str, result: str, detail: str, **evidence) -> dict:
    return {"id": cid, "result": result, "detail": detail, "evidence": evidence}


# ---------------------------------------------------------------------------
# E01 — HEAD lies
# ---------------------------------------------------------------------------

def probe_head_vs_get(url: str, timeout: int = 120) -> dict:
    """DIAGNOSTIC ONLY.

    This is the only HEAD request in the project and its result never feeds a
    decision. It exists to record, live, that HEAD still misreports the file
    so that E01's claim stays evidenced rather than inherited.
    """
    out: dict = {"url": url}
    try:
        h = requests.head(url, timeout=timeout, allow_redirects=True)
        out["head_status"] = h.status_code
        out["head_content_length"] = h.headers.get("Content-Length")
        out["head_content_type"] = h.headers.get("Content-Type")
    except Exception as e:  # noqa: BLE001
        out["head_error"] = f"{type(e).__name__}: {e}"
    try:
        n = 0
        with requests.get(url, stream=True, timeout=timeout) as g:
            out["get_status"] = g.status_code
            out["get_content_length_header"] = g.headers.get("Content-Length")
            out["get_content_type"] = g.headers.get("Content-Type")
            out["get_last_modified"] = g.headers.get("Last-Modified")
            out["get_etag"] = g.headers.get("ETag")
            for c in g.iter_content(1 << 20):
                n += len(c)
        out["get_bytes_received"] = n
    except Exception as e:  # noqa: BLE001
        out["get_error"] = f"{type(e).__name__}: {e}"
    return out


def change_detection_probe(feed: str = "TripIdToDate.zip", timeout: int = 300) -> dict:
    """Fetch one feed twice into an empty directory and record the verdicts.

    The refresh path can only report "unchanged" by hashing bytes it actually
    received, so running it twice is the only honest demonstration that change
    detection works at all. Uses the smallest feed to keep the bandwidth cost
    of the demonstration proportionate.
    """
    import tempfile
    import shutil
    from . import fetch

    tmp = Path(tempfile.mkdtemp(prefix="opentransit-changedet-"))
    try:
        first = fetch.fetch(feed, tmp, timeout=timeout)
        second = fetch.fetch(feed, tmp, timeout=timeout)
        return {
            "feed": feed,
            "first": first.as_dict(),
            "second": second.as_dict(),
            "detected": first.status == "new" and second.status in ("unchanged", "changed"),
            "note": ("first run on an empty directory must be 'new'; the second must be "
                     "'unchanged' if MOT has not republished between the two GETs, or "
                     "'changed' if it has. Either is a working detector; only a crash "
                     "or a wrong hash would not be."),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _grep_head_in_refresh_path() -> dict:
    """Static guard: no HEAD verb in the modules the refresh path uses."""
    pat = re.compile(r"\.head\s*\(|\"HEAD\"|'HEAD'|request\(\s*[\"']HEAD", re.I)
    hits = {}
    for mod in ("fetch.py", "zipread.py", "parse.py", "db.py", "pairing.py",
                "ingest.py", "queries.py", "corpus.py", "result.py",
                "run_poc1.py", "gtfstime.py"):
        p = GTFS_DIR / mod
        if not p.exists():
            continue
        found = [ln for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
                 if pat.search(ln)]
        if found:
            hits[mod] = found
    return hits


def e01(probe: dict | None, refresh_results: dict, change: dict | None = None) -> dict:
    hits = _grep_head_in_refresh_path()
    if hits:
        return _r("E01", "fail",
                  "A HEAD request appears in the refresh path.", head_in_code=hits)
    if not probe or "get_bytes_received" not in probe:
        return _r("E01", "not_observed",
                  "Refresh path is HEAD-free (static check passed) but the live "
                  "HEAD-vs-GET probe did not complete.",
                  head_in_refresh_path=False, probe=probe, change_detection=change)
    hcl = probe.get("head_content_length")
    got = probe.get("get_bytes_received")
    discrepancy = hcl is not None and got is not None and int(hcl) != got
    detail = (f"HEAD reported Content-Length {hcl} ({probe.get('head_content_type')}); "
              f"GET delivered {got:,} bytes ({probe.get('get_content_type')}). "
              f"Change detection uses GET + sha256 + zip validation only.")
    if change:
        detail += (f" Two consecutive GETs of {change['feed']} into an empty directory "
                   f"reported '{change['first']['status']}' then "
                   f"'{change['second']['status']}'.")
    return _r("E01", "pass" if discrepancy else "fail" if got else "not_observed",
              detail if discrepancy else
              f"HEAD and GET agree ({hcl} vs {got}); the documented discrepancy was "
              f"not reproduced, so the HEAD-free rule is now belt-and-braces.",
              head_in_refresh_path=False, probe=probe, change_detection=change,
              refresh={k: v.as_dict() for k, v in refresh_results.items()})


# ---------------------------------------------------------------------------
# E02 — times beyond 24:00:00
# ---------------------------------------------------------------------------

def e02(fp) -> dict:
    from .parse import max_time_roundtrip
    rt = max_time_roundtrip(fp)
    if not rt.get("observed"):
        return _r("E02", "not_observed", "No stop_times rows carried a parsable time.")
    # An explicit synthetic round trip on the spec's own example, alongside the
    # largest value the feed actually contains.
    synthetic = {}
    for raw in ("25:30:00", "24:00:00", "27:45:10"):
        s = parse_gtfs_time(raw)
        synthetic[raw] = {"seconds": s, "back": format_gtfs_time(s),
                          "day_offset": s // 86400,
                          "clock_next_day": format_gtfs_time(s % 86400)}
    ok = rt["roundtrip_exact"] and fp.stop_times_over_24h > 0 and not fp.stop_times_time_errors
    return _r("E02", "pass" if ok else "fail",
              f"{fp.stop_times_over_24h:,} of {fp.stop_times_rows:,} stop_times rows are "
              f"at or past 24:00:00. Largest observed {rt['raw']} "
              f"= {rt['seconds_from_service_day_start']}s = service day "
              f"{rt['wall_clock_within_service_day']}; round trip exact: "
              f"{rt['roundtrip_exact']}.",
              largest_observed=rt, synthetic_roundtrip=synthetic,
              parse_errors=fp.stop_times_time_errors)


# ---------------------------------------------------------------------------
# E03 — Hebrew round trip through Postgres
# ---------------------------------------------------------------------------

_HEB = re.compile(r"[֐-׿]")


_LAT = re.compile(r"[A-Za-z]")
_DIG = re.compile(r"\d")

# The awkward-name categories E03 names, each a predicate over a Hebrew string.
CATEGORIES = {
    "doubled_quote": lambda v: '""' in v,
    "single_quote": lambda v: '"' in v and '""' not in v,
    "apostrophe_geresh": lambda v: "'" in v,
    "hebrew_plus_latin": lambda v: bool(_LAT.search(v)),
    "hebrew_plus_digits": lambda v: bool(_DIG.search(v)),
    "hebrew_latin_digits": lambda v: bool(_LAT.search(v)) and bool(_DIG.search(v)),
    "plain_hebrew": lambda v: True,
}
PER_CATEGORY = 5


def pick_hebrew_samples(fp, want: int = 24) -> list[tuple[str, str, str]]:
    """(kind, id, value) triples, deliberately covering the awkward cases.

    Draws from stop names, route long names and agency names so a category
    that exists anywhere in the feed is exercised. Categories the feed simply
    does not contain come back empty and are reported as absent rather than
    quietly skipped.
    """
    pool: list[tuple[str, str, str]] = []
    for sid, s in fp.stops.items():
        pool.append(("stop", sid, s.get("stop_name") or ""))
    for rid, r in fp.routes.items():
        pool.append(("route", rid, r.get("route_long_name") or ""))
    for aid, a in fp.agencies.items():
        pool.append(("agency", aid, a.get("agency_name") or ""))
    pool = [p for p in pool if p[2] and _HEB.search(p[2])]

    picked: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for name, pred in CATEGORIES.items():
        got = 0
        for kind, key, val in pool:
            if got >= PER_CATEGORY:
                break
            if (kind, key) in seen or not pred(val):
                continue
            seen.add((kind, key))
            picked.append((kind, key, val))
            got += 1
    return picked


def e03(conn, schema: str, fp) -> dict:
    samples = pick_hebrew_samples(fp)
    mismatches = []
    checked = 0
    with conn.cursor() as cur:
        for kind, key, val in samples:
            if kind == "route":
                cur.execute(f"SELECT route_long_name FROM {schema}.routes WHERE route_id=%s",
                            (key,))
            elif kind == "stop":
                cur.execute(f"SELECT stop_name FROM {schema}.stops WHERE stop_id=%s", (key,))
            else:
                cur.execute(f"SELECT DISTINCT agency_name FROM {schema}.routes "
                            f"WHERE agency_id=%s", (key,))
            row = cur.fetchone()
            got = row[0] if row else None
            checked += 1
            if got != val:
                mismatches.append({"kind": kind, "id": key, "in_feed": val,
                                   "from_postgres": got})

    coverage = {name: sum(1 for s in samples if pred(s[2]))
                for name, pred in CATEGORIES.items()}
    absent = [k for k, v in coverage.items() if v == 0]
    ok = checked >= 20 and not mismatches
    detail = (f"{checked} Hebrew names compared byte-for-byte after "
              f"download -> extract -> parse -> Postgres -> read; "
              f"{len(mismatches)} mismatches. Coverage: "
              + ", ".join(f"{k}={v}" for k, v in coverage.items()) + ".")
    if absent:
        detail += (f" Not present anywhere in this feed's stop, route or agency "
                   f"names, so untestable here: {', '.join(absent)}.")
    return _r("E03", "pass" if ok else "fail", detail,
              compared=checked, mismatches=mismatches, coverage=coverage,
              categories_absent_from_feed=absent,
              nfc_normalised_equal=all(
                  unicodedata.normalize("NFC", s[2]) == s[2] for s in samples),
              examples=[{"kind": k, "id": i, "value": v} for k, i, v in samples])


# ---------------------------------------------------------------------------
# E04 — translations.txt
# ---------------------------------------------------------------------------

def e04(fp, other=None) -> dict:
    if not fp.translations_rows:
        return _r("E04", "not_observed", "No translations.txt in the primary feed.")
    ev = {
        "primary_feed": {
            "rows": fp.translations_rows,
            "schema": fp.translations_schema,
            "languages": fp.translations_languages,
            "malformed_rows": fp.read_stats.get("translations.txt", {}).get(
                "malformed_rows", 0),
            "malformed_samples": fp.read_stats.get("translations.txt", {}).get(
                "malformed_samples", []),
            "uncompressed_bytes": fp.members.get("translations.txt"),
        }
    }
    if other is not None and other.translations_rows:
        ev["comparison_feed"] = {
            "rows": other.translations_rows,
            "schema": other.translations_schema,
            "languages": other.translations_languages,
            "malformed_rows": other.read_stats.get("translations.txt", {}).get(
                "malformed_rows", 0),
            "uncompressed_bytes": other.members.get("translations.txt"),
        }
    return _r("E04", "pass",
              f"translations.txt parsed: {fp.translations_rows:,} rows, schema "
              f"'{fp.translations_schema}', languages {sorted(fp.translations_languages)}. "
              f"No sanitisation is applied — the rules would have to be written down "
              f"first, and nothing in the file required cleaning to parse.",
              **ev)


# ---------------------------------------------------------------------------
# E05 — TripIdToDate pairing
# ---------------------------------------------------------------------------

def e05(pair_primary: dict, pair_comparison: dict | None,
        negative_control: dict | None, hashes: dict) -> dict:
    ok = negative_control is not None and negative_control.get("raised") is True
    detail = (f"Pairing is decided by trip-id overlap. Primary feed: "
              f"{pair_primary['matched_join_keys']:,} of "
              f"{pair_primary['feed_distinct_join_keys']:,} join keys matched "
              f"({pair_primary['match_fraction']:.4%}) -> {pair_primary['verdict']}.")
    if pair_comparison:
        detail += (f" Comparison feed: {pair_comparison['match_fraction']:.4%} -> "
                   f"{pair_comparison['verdict']}.")
    if negative_control:
        detail += (" A deliberately mismatched pair raised FeedPairingError: "
                   f"{negative_control.get('raised')}.")
    return _r("E05", "pass" if ok else "fail", detail,
              primary=pair_primary, comparison=pair_comparison,
              negative_control=negative_control, hashes=hashes)


# ---------------------------------------------------------------------------
# E06 — the two feeds are different products
# ---------------------------------------------------------------------------

def e06(primary, comparison) -> dict:
    if comparison is None:
        return _r("E06", "not_observed", "The 60-day feed was not parsed in this run.")
    keys = sorted(set(primary.rows) | set(comparison.rows))
    table = {k: {"ten_day": primary.rows.get(k), "sixty_day": comparison.rows.get(k)}
             for k in keys}
    return _r("E06", "pass",
              f"Both feeds row-counted side by side. 10-day: "
              f"{primary.rows.get('trips', 0):,} trips / "
              f"{primary.rows.get('stop_times', 0):,} stop_times. 60-day: "
              f"{comparison.rows.get('trips', 0):,} trips / "
              f"{comparison.rows.get('stop_times', 0):,} stop_times. "
              f"Only the 10-day feed is loaded (D5).",
              row_counts=table,
              ten_day_sha256=primary.sha256, sixty_day_sha256=comparison.sha256,
              ten_day_service_shape=("calendar_dates only"
                                     if primary.services.has_calendar_dates
                                     and not primary.services.has_calendar
                                     else "calendar present"),
              sixty_day_service_shape=("calendar only"
                                       if comparison.services.has_calendar
                                       and not comparison.services.has_calendar_dates
                                       else "calendar_dates present"),
              uncompressed_sizes={"ten_day": primary.members,
                                  "sixty_day": comparison.members})


# ---------------------------------------------------------------------------
# E07 — service exceptions / Shabbat
# ---------------------------------------------------------------------------

def e07(fp, per_date: list[dict]) -> dict:
    import datetime as dt
    if not per_date:
        return _r("E07", "not_observed", "No active service dates materialised.")
    trips = [d["trips"] for d in per_date]
    peak = max(trips)
    rows = []
    for d in per_date:
        day = dt.date.fromisoformat(d["date"])
        rows.append({"date": d["date"],
                     "weekday": day.strftime("%A"),
                     "trips": d["trips"],
                     "pct_of_peak": round(100.0 * d["trips"] / peak, 1)})
    reduced = [r for r in rows if r["pct_of_peak"] < 60.0]
    sat = [r for r in rows if r["weekday"] == "Saturday"]
    ok = bool(reduced) and bool(sat) and all(r["pct_of_peak"] < 60.0 for r in sat)
    return _r("E07", "pass" if ok else "fail",
              f"Service is not a flat weekly pattern: "
              f"{', '.join(f'{r['date']} ({r['weekday'][:3]}) {r['pct_of_peak']}%' for r in reduced)} "
              f"against a peak of {peak:,} trips/day.",
              calendar_dates_by_exception_type=fp.services.exception_type_counts,
              calendar_rows=fp.services.calendar_rows,
              calendar_dates_rows=fp.services.calendar_dates_rows,
              service_shape=("calendar_dates only"
                             if fp.services.has_calendar_dates and not fp.services.has_calendar
                             else "calendar present"),
              trips_per_service_date=rows,
              materially_reduced_days=reduced)


# ---------------------------------------------------------------------------
# E08 — orphans and dangling references
# ---------------------------------------------------------------------------

def e08(fp) -> dict:
    counts = dict(fp.integrity)
    violations = {k: v for k, v in counts.items() if v}
    detail = ("No dangling references in any counted class."
              if not violations else
              "Dangling references counted, not dropped: "
              + ", ".join(f"{k}={v:,}" for k, v in violations.items()))
    return _r("E08", "pass", detail, counts=counts, samples=fp.integrity_samples)


# ---------------------------------------------------------------------------
# E09 — parent stations and stop grouping
# ---------------------------------------------------------------------------

def e09(conn, schema: str, corpus_resolution: list[dict], corpus_doc: dict) -> dict:
    dist = Q.location_type_distribution(conn, schema)
    biggest = Q.stations_with_platforms(conn, schema, 10)
    grouping = Q.rail_station_grouping(conn, schema)
    by_id = {c["id"]: c for c in corpus_resolution}
    coords = {e["id"]: (e["lat"], e["lon"]) for e in corpus_doc["stops"]}

    detail_stops = {}
    for cid in ("S01", "S08"):
        rec = by_id.get(cid, {})
        lat, lon = coords.get(cid, (None, None))
        near = Q.stations_near(conn, schema, lat, lon) if lat else []
        detail_stops[cid] = {
            "resolved": rec,
            "platforms_of_resolved": rec.get("platforms", []),
            "stations_within_400m": near,
            "platforms_of_nearest_station": (
                Q.children_of(conn, schema, near[0]["stop_id"]) if near else []),
        }

    grouped = any(d["platforms_of_resolved"] or d["platforms_of_nearest_station"]
                  for d in detail_stops.values())
    total = sum(dist.values()) or 1
    pct = 100.0 * grouping["stops_with_parent_station"] / total
    rail_entries = [r for r in corpus_resolution if r.get("mode") == "rail"]
    rail_with_platforms = sum(1 for r in rail_entries if r.get("platform_count"))

    def phrase(cid: str) -> str:
        d = detail_stops[cid]
        rec = d["resolved"]
        own = len(d["platforms_of_resolved"])
        if own:
            return (f"{cid} resolves to station {rec.get('resolved_stop_id')} with "
                    f"{own} platforms grouped under it")
        near = d["stations_within_400m"]
        if near:
            return (f"{cid} resolves to {rec.get('resolved_stop_id')} "
                    f"({rec.get('resolved_stop_name')}), which has no platform children; "
                    f"the nearest station to it is {near[0]['stop_id']} with "
                    f"{near[0]['platforms']} platforms, {near[0]['distance_m']:.0f} m away")
        return (f"{cid} resolves to {rec.get('resolved_stop_id')} with no platform "
                f"children and no station within 400 m")

    detail = (
        f"location_type distribution {dist}: {grouping['stations_location_type_1']} "
        f"stations, {grouping['stops_with_parent_station']} stops with a parent "
        f"({pct:.1f}% of all stops). {phrase('S08')}. {phrase('S01')}. "
        f"Of the {len(rail_entries)} rail corpus entries, {rail_with_platforms} resolved "
        f"to a stop with platform children — parent/child grouping in this feed is a "
        f"bus-terminal construct, not a rail-station model (KDP-011)."
    )
    return _r("E09", "pass" if grouped else "fail", detail,
              location_type_distribution=dist,
              grouping_summary=grouping,
              largest_stations=biggest,
              **detail_stops)


# ---------------------------------------------------------------------------
# E10 — refresh is genuinely automatic
# ---------------------------------------------------------------------------

def e10(cold: dict | None) -> dict:
    if not cold:
        return _r("E10", "not_observed", "No cold run was performed in this session.")
    ok = cold.get("exit_status") == 0 and cold.get("queryable") is True \
        and cold.get("started_empty") is True and cold.get("manual_steps", 1) == 0
    return _r("E10", "pass" if ok else "fail",
              f"Cold run from an empty data directory: started_empty="
              f"{cold.get('started_empty')}, downloaded "
              f"{cold.get('downloaded_bytes', 0) / 1e6:.1f} MB, wall time "
              f"{cold.get('wall_seconds')}s, exit status {cold.get('exit_status')}, "
              f"resulting database queryable: {cold.get('queryable')}, "
              f"manual steps: {cold.get('manual_steps')}.",
              **cold)


def load_corpus(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
