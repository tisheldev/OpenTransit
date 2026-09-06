#!/usr/bin/env python3
"""Steady-state RSS of the capped serving container.

The corpus run finishes in about fifteen seconds, which is not long enough to
sample a steady state -- it yields one or two readings and calling their median
"steady RSS" would be overstating what was measured. The stress run measures the
opposite end, RSS under load.

This measures the number the POC-2 brief actually asks for: what the container
holds at rest, with the graph loaded, after it has served traffic. That is the
figure a production box has to accommodate all day.

Usage:
    python poc/routing/measure_steady.py [--seconds 120] [--interval 3]
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from feed_context import verified_context

ROUTING = Path(__file__).resolve().parent
OUT = ROUTING / "serving-steady.json"
SAMPLES = ROUTING / "serving-steady-samples.jsonl"
CONTAINER = "poc-motis"


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
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--interval", type=float, default=3.0)
    args = ap.parse_args()

    feed_sha, _ = verified_context()
    vals: list[float] = []
    limit = None
    print(f"sampling {CONTAINER} at rest for {args.seconds}s every {args.interval}s")
    end = time.monotonic() + args.seconds
    with SAMPLES.open("w", encoding="utf-8") as fh:
        while time.monotonic() < end:
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
                    limit = parse_bytes(lim_s) or limit
                    if used is not None:
                        vals.append(used)
                        fh.write(json.dumps({
                            "t": datetime.now(timezone.utc).isoformat(),
                            "mem_mb": round(used / 1024 ** 2, 1),
                            "mem_perc_of_cap": perc.strip(), "cpu_perc": cpu.strip(),
                        }) + "\n")
                        fh.flush()
            except Exception:
                pass
            time.sleep(args.interval)

    if not vals:
        print("no samples collected -- is poc-motis running?")
        return 1

    res = {
        "feed_sha256": feed_sha,
        "generated": datetime.now(timezone.utc).isoformat(),
        "condition": "at rest, graph loaded, after serving the corpus and a 16-worker load test",
        "seconds": args.seconds, "interval_s": args.interval, "samples": len(vals),
        "memory_cap_gb": 8, "cap_observed_bytes": limit,
        "steady_rss_bytes": int(statistics.median(vals)),
        "steady_rss_mb": round(statistics.median(vals) / 1024 ** 2, 1),
        "min_rss_mb": round(min(vals) / 1024 ** 2, 1),
        "max_rss_mb": round(max(vals) / 1024 ** 2, 1),
        "steady_pct_of_cap": round(statistics.median(vals) / (8 * 1024 ** 3) * 100, 1),
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
