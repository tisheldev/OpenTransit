#!/usr/bin/env python3
"""Does the graph still fit in 8 GB when the server is actually working?

The corpus run issues 25 queries one at a time. That measures memory with the
graph loaded and essentially nothing happening, which flatters the number:
MOTIS started with n_threads=16, and RAPTOR allocates per-query state. A serving
figure taken at idle would not be an answer to system-design.md 320's question,
which is whether an 8 GB production box holds this.

So this replays the corpus concurrently for a fixed wall time and samples the
capped container's RSS throughout. It is deliberately modest -- this is a
capacity smoke test, not a benchmark, and POC-2 is not a load-testing exercise.

Reported: peak RSS under load, whether the 8 GB cgroup OOM-killed the container,
and request latency percentiles (useful later against PRD 969's p95 < 350 ms
target, though that target is for the finished API, not a bare MOTIS).

Usage:
    python poc/routing/stress_serving.py [--workers 16] [--seconds 90]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from feed_context import verified_context, departure_iso

ROUTING = Path(__file__).resolve().parent
POC = ROUTING.parent
CORPUS = POC / "corpora" / "journeys.json"
OUT = ROUTING / "serving-stress.json"
SAMPLES = ROUTING / "serving-stress-samples.jsonl"
BASE = "http://localhost:58080/api/v6/plan"
CONTAINER = "poc-motis"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--seconds", type=int, default=90)
    args = ap.parse_args()

    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    rules = corpus["depart_rules"]
    feed_sha, resolved = verified_context()

    queries = []
    for c in corpus["cases"]:
        local = resolved.get(c.get("depart", "weekday_morning"))
        if not local:
            continue
        queries.append(BASE + "?" + urllib.parse.urlencode({
            "fromPlace": f"{c['from']['lat']},{c['from']['lon']}",
            "toPlace": f"{c['to']['lat']},{c['to']['lon']}",
            "time": departure_iso(local),
            "arriveBy": "false", "numItineraries": "5", "timetableView": "true",
        }))

    stop = threading.Event()
    lat: list[float] = []
    codes: dict[str, int] = {}
    lock = threading.Lock()
    counter = {"n": 0}

    def worker(i: int) -> None:
        k = i
        while not stop.is_set():
            url = queries[k % len(queries)]
            k += 1
            t0 = time.monotonic()
            try:
                with urllib.request.urlopen(url, timeout=180) as r:
                    r.read()
                    key = str(r.status)
            except Exception as e:
                key = type(e).__name__
            dt = (time.monotonic() - t0) * 1000
            with lock:
                lat.append(dt)
                codes[key] = codes.get(key, 0) + 1
                counter["n"] += 1

    samples: list[float] = []
    limit = [None]

    def sample() -> None:
        with SAMPLES.open("w", encoding="utf-8") as fh:
            while not stop.is_set():
                try:
                    out = subprocess.run(
                        ["docker", "stats", "--no-stream", "--format",
                         "{{.MemUsage}}|{{.MemPerc}}|{{.CPUPerc}}", CONTAINER],
                        capture_output=True, text=True, timeout=30)
                    line = out.stdout.strip()
                    if line:
                        usage, perc, cpu = line.split("|")
                        used_s, lim_s = [x.strip() for x in usage.split("/")]
                        used = parse_bytes(used_s)
                        limit[0] = parse_bytes(lim_s) or limit[0]
                        if used is not None:
                            samples.append(used)
                            fh.write(json.dumps({"t": now(), "mem_mb": round(used / 1024 ** 2, 1),
                                                 "mem_perc_of_cap": perc.strip(),
                                                 "cpu_perc": cpu.strip(),
                                                 "requests_so_far": counter["n"]}) + "\n")
                            fh.flush()
                except Exception:
                    pass
                stop.wait(2.0)

    print(f"stressing {CONTAINER} with {args.workers} workers for {args.seconds}s "
          f"over {len(queries)} distinct queries")
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i in range(args.workers):
            ex.submit(worker, i)
        time.sleep(args.seconds)
        stop.set()
    sampler.join(timeout=10)
    elapsed = time.monotonic() - t0

    lat.sort()

    def pct(p: float) -> float:
        return round(lat[min(int(len(lat) * p), len(lat) - 1)], 1) if lat else 0.0

    try:
        st = subprocess.run(["docker", "inspect", CONTAINER, "--format",
                             "{{.State.OOMKilled}}|{{.State.Status}}|{{.RestartCount}}"],
                            capture_output=True, text=True, timeout=30).stdout.strip().split("|")
        state = {"oom_killed": st[0] == "true", "status": st[1], "restart_count": int(st[2])}
    except Exception as e:
        state = {"error": str(e)}

    peak = max(samples) if samples else 0.0
    res = {
        "feed_sha256": feed_sha,
        "generated": now(),
        "workers": args.workers, "seconds": round(elapsed, 1),
        "requests": len(lat), "requests_per_second": round(len(lat) / elapsed, 1) if elapsed else 0,
        "http_status_counts": codes,
        "latency_ms": {"p50": pct(0.50), "p90": pct(0.90), "p95": pct(0.95),
                       "p99": pct(0.99), "max": round(lat[-1], 1) if lat else 0.0},
        "memory_cap_gb": 8,
        "cap_observed_bytes": limit[0],
        "peak_rss_bytes": int(peak), "peak_rss_mb": round(peak / 1024 ** 2, 1),
        "peak_rss_pct_of_cap": round(peak / (8 * 1024 ** 3) * 100, 1) if peak else 0.0,
        "samples": len(samples),
        "container_state_after": state,
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
