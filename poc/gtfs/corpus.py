"""Resolve `poc/corpora/stops.json` against the real feed.

The corpus ships approximate coordinates and a Hebrew name, and says so:
"APPROXIMATE. Agent A snaps each to the nearest real stop and records
resolved_stop_id." `expect_routes` stays null — the corpus's own provenance
note reserves that for a human, and filling it with guesses would create fake
ground truth.

Snapping on distance alone gets several entries wrong, and snapping on name
gets a different several wrong, because of how MOT names Israeli stops:

* `S03 Yitzhak Navon` (rail) sits 24 m from the Jerusalem *bus* station and
  85 m from the rail stop, so pure nearest makes S03 and S07 the same id.
* A stop *named after* a railway station is usually the bus stop outside it.
  Israel Railways' own stops carry plain names — `תל אביב מרכז`, `השלום`,
  `חיפה מרכז`, `נתב"ג` — while the bus stops beside them are the ones called
  `ת. רכבת תל אביב - סבידור/הורדה` and `תחנת רכבת חיפה מרכז השמונה`. Name
  matching alone therefore snaps every rail entry onto a bus stop.

So resolution is mode-aware and runs after `stop_times`, when the route types
actually calling at each candidate are known. Rules, in order, each tried at
300 m, then 1 km, then 3 km:

  1. `name+mode`  — shares a name token *and* is served by the mode the
     corpus asked for. `+station` when the winner is a `location_type = 1`
     station, which is what E09 wants for sprawling sites.
  2. `mode`       — nearest stop served by the right mode, no name evidence.
  3. `name`       — best name-token match, mode unknown or absent.
  4. `nearest`    — geometrically nearest stop, nothing else known.

`low_confidence` is set when the winner is over 500 m away, resolved by
distance alone, or is not served by the expected mode — so checkpoint H4 knows
exactly which entries to look at. Nothing is invented: every candidate comes
from `stops.txt`, and `expect_routes` is never filled.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

RADIUS_M = 3000.0
RADIUS_STAGES_M = [300.0, 1000.0, 3000.0]
LOW_CONFIDENCE_M = 500.0

# corpus `mode` -> GTFS route_type (spec values: 0 tram/light rail, 2 rail, 3 bus)
MODE_TO_ROUTE_TYPE = {"rail": "2", "bus": "3", "light_rail": "0", "tram": "0"}

_TOKEN = re.compile(r"[^\s/,\-–]+")
# Words in almost every Israeli stop name; they would match anything.
_STOPWORDS = {"תחנת", "תחנה", "ת.", "ת", "רכבת", "מרכזית", "של"}


def tokens(name: str) -> set[str]:
    out = set()
    for t in _TOKEN.findall(name or ""):
        t = t.strip(".\"'()")
        if len(t) >= 2 and t not in _STOPWORDS:
            out.add(t)
    return out


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _positioned_stops(fp):
    out = []
    for sid, s in fp.stops.items():
        try:
            out.append((sid, s, float(s["stop_lat"]), float(s["stop_lon"])))
        except (TypeError, ValueError, KeyError):
            continue
    return out


def nearby_ids(fp, corpus: dict, radius_m: float = RADIUS_M) -> set[str]:
    """Every stop within `radius_m` of any corpus entry.

    This is the candidate pool. `parse_feed` collects per-hour departures and
    calling routes for exactly these stops during its single `stop_times`
    pass, which is what makes the mode-aware second phase possible without a
    second read of a 1.77 GB file.
    """
    stops = _positioned_stops(fp)
    ids: set[str] = set()
    for entry in corpus["stops"]:
        for sid, s, la, lo in stops:
            if haversine_m(entry["lat"], entry["lon"], la, lo) <= radius_m:
                ids.add(sid)
    return ids


def resolve(fp, corpus: dict, route_types: dict[str, set] | None = None,
            radius_m: float = RADIUS_M) -> list[dict]:
    """One resolution record per corpus entry, in corpus order.

    `route_types` maps stop_id -> set of GTFS route_type strings observed
    calling there. Pass None for a first, mode-blind pass (used only to build
    the candidate pool); pass the real map for the resolution of record.
    """
    stops = _positioned_stops(fp)
    children_of: dict[str, list[str]] = {}
    for cid, cs in fp.stops.items():
        p = (cs.get("parent_station") or "").strip()
        if p:
            children_of.setdefault(p, []).append(cid)

    types = route_types or {}
    out: list[dict] = []

    for entry in corpus["stops"]:
        want = tokens(entry.get("name_he") or "")
        expected = MODE_TO_ROUTE_TYPE.get(entry.get("mode") or "")

        scored = sorted(
            ((haversine_m(entry["lat"], entry["lon"], la, lo), sid, s)
             for sid, s, la, lo in stops),
            key=lambda t: t[0])
        nearest_d, nearest_id, nearest_s = scored[0]
        cands = [t for t in scored if t[0] <= radius_m]

        def score_of(s):
            hit = want & tokens(s.get("stop_name") or "")
            return (len(hit) / len(want)) if want else 0.0, sorted(hit)

        def is_station(s):
            return 1 if (s.get("location_type") or "") == "1" else 0

        def has_mode(sid):
            return expected is not None and expected in types.get(sid, set())

        chosen = None
        rule = None

        # 1. name token match AND the right mode
        for stage in RADIUS_STAGES_M:
            best = None
            for d, sid, s in cands:
                if d > stage:
                    break
                sc, hit = score_of(s)
                if sc > 0 and has_mode(sid):
                    key = (sc, is_station(s), -d)
                    if best is None or key > best[0]:
                        best = (key, d, sid, s, sc, hit)
            if best:
                _, d, sid, s, sc, hit = best
                chosen = (d, sid, s, sc, hit)
                rule = "name+mode+station" if is_station(s) else "name+mode"
                break

        # 2. nearest stop of the right mode, name unknown
        if chosen is None and expected is not None:
            for stage in RADIUS_STAGES_M:
                for d, sid, s in cands:
                    if d > stage:
                        break
                    if has_mode(sid):
                        sc, hit = score_of(s)
                        chosen, rule = (d, sid, s, sc, hit), "mode"
                        break
                if chosen:
                    break

        # 3. best name token match, mode unknown or not represented
        if chosen is None:
            for stage in RADIUS_STAGES_M:
                best = None
                for d, sid, s in cands:
                    if d > stage:
                        break
                    sc, hit = score_of(s)
                    if sc > 0:
                        key = (sc, is_station(s), -d)
                        if best is None or key > best[0]:
                            best = (key, d, sid, s, sc, hit)
                if best:
                    _, d, sid, s, sc, hit = best
                    chosen = (d, sid, s, sc, hit)
                    rule = "name+station" if is_station(s) else "name"
                    break

        # 4. nothing but geometry
        if chosen is None:
            chosen, rule = (nearest_d, nearest_id, nearest_s, 0.0, []), "nearest"

        d, sid, s, sc, hit = chosen
        observed = sorted(types.get(sid, set()))
        mode_ok = (expected in observed) if (expected and observed) else None
        kids = sorted(children_of.get(sid, []))

        out.append({
            "id": entry["id"],
            "name": entry["name"],
            "name_he": entry.get("name_he"),
            "mode": entry.get("mode"),
            "resolved_stop_id": sid,
            "resolved_stop_name": s.get("stop_name"),
            "resolution_rule": rule,
            "name_token_score": round(sc, 3),
            "matched_tokens": hit,
            "distance_m": round(d, 1),
            "location_type": s.get("location_type") or None,
            "parent_station": s.get("parent_station") or None,
            "platforms": kids,
            "platform_count": len(kids),
            "candidates_within_radius": len(cands),
            "expected_route_type": expected,
            "observed_route_types": observed,
            "mode_matches_feed": mode_ok,
            "geometric_nearest": {"stop_id": nearest_id,
                                  "stop_name": nearest_s.get("stop_name"),
                                  "distance_m": round(nearest_d, 1)},
            "low_confidence": bool(d > LOW_CONFIDENCE_M or rule == "nearest"
                                   or mode_ok is False),
        })
    return out


def write_back(corpus_path: Path, resolutions: list[dict]) -> None:
    """Write resolved_stop_id back into the corpus. expect_routes stays null."""
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in resolutions}
    for entry in corpus["stops"]:
        r = by_id.get(entry["id"])
        if not r:
            continue
        entry["resolved_stop_id"] = r["resolved_stop_id"]
        entry["resolution"] = {
            "rule": r["resolution_rule"],
            "resolved_stop_name": r["resolved_stop_name"],
            "distance_m": r["distance_m"],
            "name_token_score": r["name_token_score"],
            "location_type": r["location_type"],
            "platform_count": r["platform_count"],
            "expected_route_type": r["expected_route_type"],
            "observed_route_types": r["observed_route_types"],
            "mode_matches_feed": r["mode_matches_feed"],
            "observed_route_count": r.get("observed_route_count"),
            "observed_departures_in_feed_window": r.get("observed_departures"),
            "observed_peak_departures_per_hour": r.get("peak_departures_per_hour"),
            "meets_expect_min_services_per_hour": r.get(
                "meets_expect_min_services_per_hour"),
            "geometric_nearest": r["geometric_nearest"],
            "low_confidence": r["low_confidence"],
            "feed_sha256": r.get("feed_sha256"),
        }
        # expect_routes is a human's job (corpus provenance note); never guessed.
        entry.setdefault("expect_routes", None)
    corpus["resolution_note"] = (
        "resolved_stop_id and resolution written by poc/gtfs/ingest.py from the feed "
        "recorded in poc/data/manifest.json. Resolution is mode-aware: see the module "
        "docstring of poc/gtfs/corpus.py. expect_routes remains null by design — the "
        "corpus reserves it for human confirmation (checkpoint H4), and entries with "
        "low_confidence true are the ones to check first."
    )
    corpus_path.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
