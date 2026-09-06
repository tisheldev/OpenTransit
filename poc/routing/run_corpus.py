#!/usr/bin/env python3
"""POC-2, measurement 2 of 2: run all 25 journey cases against the CAPPED server.

This talks to the `motis` service from poc/docker-compose.yml, which is capped
at mem_limit 8g because system-design.md 320 puts the production box at 8 GB.
It does not start that container and it must not: the cap is the experiment.

WHAT THIS CHECKS, AND WHAT IT DELIBERATELY DOES NOT
---------------------------------------------------
Structure only. PRD 7's bar is "at least 9/10 representative journeys produce
reasonable usable routes", and "reasonable" is a human comparison against
Moovit, Google Maps and BetterRail. That is checkpoint H3, not this file. So
this script answers questions with objectively checkable answers:

  - did a route come back, or was it correctly refused (`no-route` cases)
  - are the legs well-formed: chained end-to-start, times monotonic,
    no leg ending before it starts, no two legs overlapping
  - does every transit stop id in the response exist in the static feed
  - is the total duration inside min_duration_min .. max_duration_min
  - are modes_any_of / modes_all_of / min_transfers / max_transfers /
    max_walk_m honoured

It never decides whether a route is *good*. A structurally perfect itinerary
that no Tel Aviv resident would ever take passes here and may still fail H3.

WHICH ITINERARY IS JUDGED
-------------------------
MOTIS returns several itineraries. Two numbers are recorded for every case,
because they answer different questions and collapsing them would hide things:

  structural_any    - does ANY returned itinerary satisfy the expectations?
                      This is the honest reading of a constraint like J15's
                      modes_all_of [bus, rail]: it asks whether a bus-then-rail
                      journey is available, not whether MOTIS ranked it first.
  structural_first  - does itineraries[0], the one a user would actually be
                      shown, satisfy them?

`structural_any` is the headline number. `structural_first` is reported
alongside it, and any case where the two disagree is flagged for H3, because a
gap between them is exactly a ranking question and ranking is a human call.

Usage:
    python poc/routing/run_corpus.py

Outputs, all under poc/routing/:
    responses/J01.json ...    the full response for every case, unedited
    corpus-result.json        per-case structural verdicts and serving metrics
    serving-samples.jsonl     RSS of the capped container, sampled throughout
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from feed_context import verified_context, departure_iso

ROUTING = Path(__file__).resolve().parent
POC = ROUTING.parent
CORPUS = POC / "corpora" / "journeys.json"
FEED = POC / "data" / "israel-public-transportation.zip"
MANIFEST = POC / "data" / "manifest.json"
STOPIDS = ROUTING / "feed-stop-ids.json"

# Two labelled runs, both recorded, neither hidden.
#
#   default        MOTIS's own defaults, unchanged. This is the primary result:
#                  what an operator gets by deploying MOTIS as shipped.
#   generous-walk  maxPreTransitTime / maxPostTransitTime raised from 900 s to
#                  1800 s. MOTIS defaults to allowing 15 minutes of walking to
#                  the first stop and from the last. On Haifa's Carmel slope
#                  that is not enough to reach a stop 600 m away as the crow
#                  flies, which is why J09 returns nothing under `default`. The
#                  variant exists to separate "the engine cannot route this"
#                  from "the engine was told not to walk that far".
#
# The `default` numbers are the ones reported as POC-2's result. The variant is
# evidence for checkpoint H3, not a second chance at a better score.
PROFILES = {
    "default": {},
    "generous-walk": {"maxPreTransitTime": "1800", "maxPostTransitTime": "1800"},
}

BASE = "http://localhost:58080"
CONTAINER = "poc-motis"

# MOTIS mode enum -> the vocabulary poc/corpora/journeys.json uses.
# MOTIS renamed METRO to SUBURBAN in 2.5.0; both are mapped so this survives a
# version bump either way.
MODE_MAP = {
    "BUS": "bus",
    "COACH": "bus",
    "RAIL": "rail",
    "SUBURBAN": "rail",
    "METRO": "rail",
    "HIGHSPEED_RAIL": "rail",
    "LONG_DISTANCE": "rail",
    "NIGHT_RAIL": "rail",
    "REGIONAL_RAIL": "rail",
    "REGIONAL_FAST_RAIL": "rail",
    "TRAM": "light_rail",
    "SUBWAY": "light_rail",
    "CABLE_CAR": "cable_car",
    "AERIAL_LIFT": "cable_car",
    "GONDOLA": "cable_car",
    "FUNICULAR": "funicular",
    "FERRY": "ferry",
    "AIRPLANE": "air",
    "OTHER": "other",
}
NON_TRANSIT = {"WALK", "BIKE", "CAR", "ODM", "RENTAL", "FLEX", "HGV", "CAR_PARKING"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# The static feed, for stop-id resolution
# --------------------------------------------------------------------------

def feed_stop_ids() -> set[str]:
    """Every stop_id in israel-public-transportation.zip. Cached, because unzipping a 4.7 MB
    member out of a 252 MB archive is not free and this is called per leg."""
    ids: set[str] = set()
    with zipfile.ZipFile(FEED) as z:
        with z.open("stops.txt") as fh:
            header = fh.readline().decode("utf-8-sig").strip().split(",")
            col = header.index("stop_id")
            for raw in fh:
                parts = raw.decode("utf-8", "replace").rstrip("\r\n").split(",")
                if len(parts) > col:
                    ids.add(parts[col].strip().strip('"'))
    STOPIDS.write_text(json.dumps(sorted(ids)), encoding="utf-8")
    return ids


def strip_prefix(stop_id: str) -> str:
    """MOTIS namespaces stop ids with the dataset tag from config.yml
    (`mot60day`). Strip it so ids can be compared against the raw feed."""
    for sep in ("_", ":", "-"):
        pre = "mot60day" + sep
        if stop_id.startswith(pre):
            return stop_id[len(pre):]
    return stop_id


# --------------------------------------------------------------------------
# Talking to MOTIS
# --------------------------------------------------------------------------

def discover_plan_path() -> str:
    """The plan endpoint is versioned and the version has moved (v1 .. v6+
    across MOTIS releases). Ask the running server rather than assuming."""
    try:
        with urllib.request.urlopen(BASE + "/openapi.yaml", timeout=30) as r:
            spec = r.read().decode("utf-8", "replace")
        found = sorted(set(re.findall(r"(/api/v\d+/plan)\s*:", spec)))
        if found:
            return found[-1]
    except Exception:
        pass
    for v in range(9, 0, -1):
        path = f"/api/v{v}/plan"
        try:
            req = BASE + path + "?fromPlace=32.0836,34.7981&toPlace=32.0838,34.8044"
            with urllib.request.urlopen(req, timeout=60) as r:
                if r.status == 200:
                    return path
        except urllib.error.HTTPError as e:
            # 400 means the route exists and disliked the query; 404 means it
            # is not mounted at this version.
            if e.code != 404:
                return path
        except Exception:
            pass
    raise SystemExit("could not find a /api/vN/plan endpoint on " + BASE)


def plan(path: str, case: dict, depart_local: str, extra: dict) -> tuple[dict | None, dict]:
    q = {
        "fromPlace": f"{case['from']['lat']},{case['from']['lon']}",
        "toPlace": f"{case['to']['lat']},{case['to']['lon']}",
        "time": depart_local,
        "arriveBy": "false",
        "numItineraries": "5",
        "timetableView": "true",
    }
    q.update(extra)
    url = BASE + path + "?" + urllib.parse.urlencode(q)
    t0 = time.monotonic()
    meta = {"url": url, "requested_time_local": depart_local}
    try:
        with urllib.request.urlopen(url, timeout=180) as r:
            body = json.loads(r.read().decode("utf-8"))
        meta.update(http_status=200, latency_ms=round((time.monotonic() - t0) * 1000, 1))
        return body, meta
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:2000]
        except Exception:
            pass
        meta.update(http_status=e.code, latency_ms=round((time.monotonic() - t0) * 1000, 1),
                    error=f"HTTP {e.code}", error_body=detail)
        return None, meta
    except Exception as e:
        meta.update(http_status=None, latency_ms=round((time.monotonic() - t0) * 1000, 1),
                    error=f"{type(e).__name__}: {e}")
        return None, meta


# --------------------------------------------------------------------------
# Structural checks
# --------------------------------------------------------------------------

def haversine_m(a: dict, b: dict) -> float | None:
    """Straight-line metres between two Places."""
    try:
        lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    except (KeyError, TypeError):
        return None
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def summarise(it: dict) -> dict:
    """Flatten one itinerary into the handful of facts the checks need, and the
    H3 review sheet renders."""
    legs = it.get("legs") or []
    modes_raw, modes, walk_m, transit_legs = [], [], 0.0, 0
    stop_ids = []
    walk_estimated = False
    cancelled = 0
    for lg in legs:
        m = (lg.get("mode") or "").upper()
        modes_raw.append(m)
        if any((lg.get(e) or {}).get("cancelled") for e in ("from", "to")):
            cancelled += 1
        if m in NON_TRANSIT:
            if m == "WALK":
                # MOTIS reports `distance` on access and egress walk legs but
                # omits it on stop-to-stop transfer walks. Falling back to
                # straight-line distance UNDER-states those, so max_walk_m is
                # checked against a lower bound; the flag says when that
                # happened so a max_walk_m pass is never silently optimistic.
                d = lg.get("distance")
                if d is None:
                    d = haversine_m(lg.get("from") or {}, lg.get("to") or {})
                    if d is not None:
                        walk_estimated = True
                walk_m += float(d or 0)
        else:
            transit_legs += 1
            modes.append(MODE_MAP.get(m, m.lower()))
            for endp in ("from", "to"):
                sid = (lg.get(endp) or {}).get("stopId")
                if sid:
                    stop_ids.append(sid)
            for s in (lg.get("intermediateStops") or []):
                if s.get("stopId"):
                    stop_ids.append(s["stopId"])
    dur_s = it.get("duration")
    return {
        "duration_s": dur_s,
        "duration_min": round(dur_s / 60.0, 1) if isinstance(dur_s, (int, float)) else None,
        "start": it.get("startTime"),
        "end": it.get("endTime"),
        "transfers": it.get("transfers"),
        "n_legs": len(legs),
        "n_transit_legs": transit_legs,
        "modes_raw": modes_raw,
        "modes": sorted(set(modes)),
        "walk_m": round(walk_m),
        "walk_m_partly_estimated": walk_estimated,
        "cancelled_endpoints": cancelled,
        "stop_ids": stop_ids,
    }


def check_wellformed(it: dict) -> list[str]:
    """Leg sequence sanity. These are failures of the response itself, not of
    the expectations, so they are reported separately."""
    problems = []
    legs = it.get("legs") or []
    if not legs:
        return ["itinerary has no legs"]
    prev_end = None
    for i, lg in enumerate(legs):
        s, e = parse_ts(lg.get("startTime")), parse_ts(lg.get("endTime"))
        if s is None or e is None:
            problems.append(f"leg {i} ({lg.get('mode')}) missing start/end time")
            continue
        if e < s:
            problems.append(f"leg {i} ({lg.get('mode')}) ends {(s - e).total_seconds():.0f}s before it starts")
        if prev_end is not None and s < prev_end:
            problems.append(
                f"leg {i} ({lg.get('mode')}) starts {(prev_end - s).total_seconds():.0f}s "
                f"before leg {i - 1} ends -- overlapping legs")
        prev_end = e
        if i + 1 < len(legs):
            a = (lg.get("to") or {})
            b = (legs[i + 1].get("from") or {})
            aid, bid = a.get("stopId"), b.get("stopId")
            if aid and bid and aid != bid:
                problems.append(f"leg {i} ends at {aid} but leg {i + 1} starts at {bid} -- broken chain")
    st, en = parse_ts(it.get("startTime")), parse_ts(it.get("endTime"))
    if st and en:
        if en < st:
            problems.append("itinerary ends before it starts")
        d = it.get("duration")
        if isinstance(d, (int, float)):
            actual = (en - st).total_seconds()
            if abs(actual - d) > 120:
                problems.append(f"duration field {d}s disagrees with endTime-startTime {actual:.0f}s")
    return problems


def check_expectations(s: dict, exp: dict, known_stops: set[str]) -> list[str]:
    fails = []
    dmin, dmax = exp.get("min_duration_min"), exp.get("max_duration_min")
    if dmin is not None and (s["duration_min"] is None or s["duration_min"] < dmin):
        fails.append(f"duration {s['duration_min']} min < min_duration_min {dmin}")
    if dmax is not None and (s["duration_min"] is None or s["duration_min"] > dmax):
        fails.append(f"duration {s['duration_min']} min > max_duration_min {dmax}")

    tmin, tmax = exp.get("min_transfers"), exp.get("max_transfers")
    tr = s["transfers"]
    if tmin is not None and (tr is None or tr < tmin):
        fails.append(f"transfers {tr} < min_transfers {tmin}")
    if tmax is not None and (tr is None or tr > tmax):
        fails.append(f"transfers {tr} > max_transfers {tmax}")

    any_of = exp.get("modes_any_of")
    if any_of and not (set(s["modes"]) & set(any_of)):
        fails.append(f"modes {s['modes']} share nothing with modes_any_of {any_of}")
    all_of = exp.get("modes_all_of")
    if all_of and not set(all_of).issubset(set(s["modes"])):
        missing = sorted(set(all_of) - set(s["modes"]))
        fails.append(f"modes {s['modes']} missing modes_all_of entries {missing}")

    mw = exp.get("max_walk_m")
    if mw is not None and s["walk_m"] > mw:
        note = " (partly straight-line estimated, so the real figure is higher)" if s["walk_m_partly_estimated"] else ""
        fails.append(f"walking {s['walk_m']} m > max_walk_m {mw}{note}")

    unknown = sorted({strip_prefix(i) for i in s["stop_ids"]} - known_stops)
    if unknown:
        fails.append(f"{len(unknown)} stop id(s) not in the static feed, e.g. {unknown[:5]}")
    return fails


def has_wttw_shape(it: dict) -> bool:
    """PRD 7 asks specifically for walk -> transit -> transfer -> transit ->
    walk. Structurally: a walk leg first, a walk leg last, and at least two
    transit legs in between. The `walk_transit_transfer` capability in
    poc/results/poc-2.json is written true only if some case actually produced
    this, never because routing worked in general."""
    legs = it.get("legs") or []
    if len(legs) < 3:
        return False
    modes = [(lg.get("mode") or "").upper() for lg in legs]
    transit = [m for m in modes if m not in NON_TRANSIT]
    return modes[0] == "WALK" and modes[-1] == "WALK" and len(transit) >= 2


# --------------------------------------------------------------------------
# Serving-container RSS sampling
# --------------------------------------------------------------------------

class ServingSampler(threading.Thread):
    def __init__(self, path: Path) -> None:
        super().__init__(daemon=True)
        self.path = path
        self.stop_flag = threading.Event()
        self.samples: list[float] = []
        self.limit_bytes = None

    def run(self) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            while not self.stop_flag.is_set():
                try:
                    out = subprocess.run(
                        ["docker", "stats", "--no-stream", "--format",
                         "{{.MemUsage}}|{{.MemPerc}}|{{.CPUPerc}}", CONTAINER],
                        capture_output=True, text=True, timeout=30)
                    line = out.stdout.strip()
                    if line:
                        usage, perc, cpu = line.split("|")
                        used_s, limit_s = [x.strip() for x in usage.split("/")]
                        used = parse_bytes(used_s)
                        self.limit_bytes = parse_bytes(limit_s) or self.limit_bytes
                        if used is not None:
                            self.samples.append(used)
                            fh.write(json.dumps({
                                "t": now(), "mem_bytes": used,
                                "mem_mb": round(used / 1024 ** 2, 1),
                                "mem_perc_of_cap": perc.strip(), "cpu_perc": cpu.strip(),
                            }) + "\n")
                            fh.flush()
                except Exception:
                    pass
                self.stop_flag.wait(3.0)


def parse_bytes(s: str):
    s = s.strip()
    units = {"B": 1, "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3, "TiB": 1024 ** 4,
             "kB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4}
    for u in sorted(units, key=len, reverse=True):
        if s.endswith(u):
            try:
                return float(s[: -len(u)]) * units[u]
            except ValueError:
                return None
    return None


def container_ooms() -> dict:
    """Did the 8 GB cgroup actually kill it? This is the difference between
    'fits in 8 GB' and 'appeared to fit because nothing asked much of it'."""
    try:
        out = subprocess.run(["docker", "inspect", CONTAINER, "--format",
                              "{{.State.OOMKilled}}|{{.State.Status}}|{{.State.ExitCode}}|{{.RestartCount}}"],
                             capture_output=True, text=True, timeout=30)
        oom, status, code, restarts = out.stdout.strip().split("|")
        return {"oom_killed": oom == "true", "status": status,
                "exit_code": int(code), "restart_count": int(restarts)}
    except Exception as e:
        return {"error": str(e)}


# --------------------------------------------------------------------------

def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=sorted(PROFILES), default="default",
                    help="query profile; see PROFILES in this file")
    args = ap.parse_args()
    profile, extra = args.profile, PROFILES[args.profile]
    suffix = "" if profile == "default" else f"-{profile}"
    responses = ROUTING / f"responses{suffix}"
    result_path = ROUTING / f"corpus-result{suffix}.json"
    samples_path = ROUTING / f"serving-samples{suffix}.jsonl"
    print(f"profile={profile} extra params={extra or '(none)'}")

    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    feed_sha, resolved = verified_context()
    print(f"feed sha256 {feed_sha[:16]}.. window {resolved['feed_window']}")

    known_stops = feed_stop_ids()
    print(f"{len(known_stops)} stop ids loaded from the static feed")

    responses.mkdir(exist_ok=True)
    plan_path = discover_plan_path()
    print(f"plan endpoint: {plan_path}")

    sampler = ServingSampler(samples_path)
    sampler.start()

    cases_out = []
    wttw_cases = []
    for case in corpus["cases"]:
        cid = case["id"]
        rule = case.get("depart", "weekday_morning")
        local = resolved.get(rule)
        if not local:
            print(f"{cid}: no resolved departure for rule {rule!r}", file=sys.stderr)
            continue
        depart_iso = departure_iso(local)

        body, meta = plan(plan_path, case, depart_iso, extra)
        (responses / f"{cid}.json").write_text(
            json.dumps({"case": case, "request": meta, "response": body},
                       indent=2, ensure_ascii=False), encoding="utf-8")

        rec = {
            "id": cid, "category": case.get("category"), "prd_ref": case.get("prd_ref"),
            "depart_rule": rule, "depart_local": depart_iso,
            "from": case["from"]["name"], "to": case["to"]["name"],
            "expect": case["expect"], "human_review": case.get("human_review"),
            "request": meta, "response_file": f"poc/routing/responses{suffix}/{cid}.json",
        }

        exp_outcome = case["expect"].get("outcome", "route")

        if body is None:
            rec.update(outcome="error", structural="fail", answered=False,
                       notes=[f"request failed: {meta.get('error')}"])
            cases_out.append(rec)
            print(f"{cid}: ERROR {meta.get('error')}")
            continue

        its = body.get("itineraries") or []
        directs = body.get("direct") or []
        rec["n_itineraries"] = len(its)
        rec["n_direct"] = len(directs)
        rec["answered"] = True

        if not its:
            rec["outcome"] = "no-route"
            rec["itineraries"] = []
            if exp_outcome in ("no-route", "either"):
                rec["structural"] = "pass"
                rec["structural_first"] = "pass"
                rec["notes"] = ["no itineraries returned, which the case allows"]
            else:
                rec["structural"] = "fail"
                rec["structural_first"] = "fail"
                rec["notes"] = [f"no itineraries returned but the case expects outcome={exp_outcome}"]
            cases_out.append(rec)
            print(f"{cid}: no-route ({rec['structural']})")
            continue

        rec["outcome"] = "route"
        if exp_outcome == "no-route":
            rec["structural"] = "fail"
            rec["structural_first"] = "fail"
            rec["notes"] = [f"{len(its)} itinerary/itineraries returned but the case "
                            f"requires no route -- the engine may be inventing service"]
            rec["itineraries"] = [summarise(i) for i in its]
            cases_out.append(rec)
            print(f"{cid}: route returned but no-route expected -> FAIL")
            continue

        sums, verdicts = [], []
        for idx, it in enumerate(its):
            s = summarise(it)
            wf = check_wellformed(it)
            ex = check_expectations(s, case["expect"], known_stops)
            s["wellformed_problems"] = wf
            s["expectation_failures"] = ex
            s["ok"] = not wf and not ex
            s["wttw_shape"] = has_wttw_shape(it)
            sums.append(s)
            verdicts.append(s["ok"])
        rec["itineraries"] = sums
        matching = [i for i, v in enumerate(verdicts) if v]
        rec["matching_itinerary_indexes"] = matching
        rec["structural"] = "pass" if matching else "fail"
        rec["structural_first"] = "pass" if verdicts[0] else "fail"
        if rec["structural"] == "pass" and rec["structural_first"] == "fail":
            rec.setdefault("notes", []).append(
                f"itinerary 0 (the one a user sees) does not satisfy the case; "
                f"itinerary {matching[0]} does. This is a ranking question -- flag for H3.")
        if not matching:
            rec.setdefault("notes", []).append(
                "no returned itinerary satisfied the case: " + "; ".join(sums[0]["expectation_failures"]
                                                                        + sums[0]["wellformed_problems"]))
        if any(s["wttw_shape"] for s in sums):
            wttw_cases.append(cid)
        cases_out.append(rec)
        print(f"{cid}: route  n={len(its)}  any={rec['structural']}  first={rec['structural_first']}  "
              f"dur={sums[0]['duration_min']}min tr={sums[0]['transfers']} modes={sums[0]['modes']}")

    sampler.stop_flag.set()
    sampler.join(timeout=15)

    peak = max(sampler.samples) if sampler.samples else 0.0
    # Steady state = median of the second half of the run, once the graph is
    # loaded and the queries have stopped churning.
    tail_samples = sorted(sampler.samples[len(sampler.samples) // 2:]) or [0.0]
    steady = tail_samples[len(tail_samples) // 2]

    answered = sum(1 for c in cases_out if c.get("answered"))
    passed = sum(1 for c in cases_out if c.get("structural") == "pass")
    passed_first = sum(1 for c in cases_out if c.get("structural_first") == "pass")

    out = {
        "generated": now(),
        "profile": profile,
        "profile_extra_params": extra,
        "feed_sha256": feed_sha,
        "feed_window": resolved["feed_window"],
        "plan_endpoint": plan_path,
        "serving": {
            "memory_cap_gb": 8,
            "cap_observed_bytes": sampler.limit_bytes,
            "peak_rss_bytes": int(peak), "peak_rss_mb": round(peak / 1024 ** 2, 1),
            "steady_rss_bytes": int(steady), "steady_rss_mb": round(steady / 1024 ** 2, 1),
            "samples": len(sampler.samples),
            "container_state": container_ooms(),
        },
        "journeys": {"total": len(corpus["cases"]), "answered": answered,
                     "structural_pass_any": passed, "structural_pass_first": passed_first},
        "wttw_shape_cases": wttw_cases,
        "cases": cases_out,
    }
    result_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"answered {answered}/{len(corpus['cases'])}  "
          f"structural pass (any itinerary) {passed}  (itinerary 0) {passed_first}")
    print(f"serving peak {out['serving']['peak_rss_mb']} MB, steady {out['serving']['steady_rss_mb']} MB, "
          f"cap 8192 MB, oom_killed={out['serving']['container_state'].get('oom_killed')}")
    print(f"walk->transit->transfer->transit->walk shape seen in: {wttw_cases or 'NONE'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
