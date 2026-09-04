#!/usr/bin/env python3
"""poc:status — regenerate the Phase 0 status tables from recorded results.

Reads poc/results/poc-N.json and emits:
  - the PRD §13 dependency-status table
  - the PRD §12 Go/No-Go table

Nothing here is hand-edited. If a capability shows green it is because a test
run wrote it into a result file. An agent's claim that something works is not
an input to this script.

Usage:
    python poc/poc_status.py            # print to stdout
    python poc/poc_status.py --write    # also regenerate poc/README.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

POCS = {
    1: "Static Israeli transportation data",
    2: "Public transportation routing",
    3: "Realtime transit information",
    4: "Service alerts",
    5: "Address and place search",
    6: "End-to-end journey",
}

# PRD §12 Go/No-Go table: (capability, poc, capability-key in that result file)
GONOGO = [
    ("Download current nationwide GTFS", 1, "download_gtfs"),
    ("Parse GTFS", 1, "parse_gtfs"),
    ("Route using Israeli GTFS", 2, "route_gtfs"),
    ("Walking + transit + transfers", 2, "walk_transit_transfer"),
    ("Obtain realtime arrivals", 3, "obtain_realtime"),
    ("Match realtime <-> GTFS", 3, "match_realtime"),
    ("Obtain service alerts", 4, "obtain_alerts"),
    ("Resolve Israeli addresses/places", 5, "resolve_places"),
    ("Run full end-to-end query", 6, "end_to_end"),
    ("Confirm acceptable data usage terms", 1, "usage_terms_confirmed"),
]

MARK = {
    True: "PASS",
    False: "FAIL",
    None: "—",
}

STATUS_ORDER = ["PASS", "PARTIAL", "BLOCKED_ON_ACCESS", "FAIL", "NOT_STARTED"]


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT.parent, capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def load() -> dict[int, dict]:
    found: dict[int, dict] = {}
    for n in POCS:
        p = RESULTS / f"poc-{n}.json"
        if not p.exists():
            continue
        try:
            found[n] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            found[n] = {"status": "FAIL", "notes": [f"result file is not valid JSON: {e}"]}
    return found


def capability(results: dict[int, dict], poc: int, key: str) -> bool | None:
    r = results.get(poc)
    if not r:
        return None
    return r.get("capabilities", {}).get(key)


def render(results: dict[int, dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L: list[str] = []
    A = L.append

    A("# Phase 0 POC — status")
    A("")
    A(f"Generated {now} from `poc/results/` at commit `{git_commit()}`.")
    A("**Machine-generated. Do not hand-edit — run `python poc/poc_status.py --write`.**")
    A("")
    A("## Dependency status (PRD §13)")
    A("")
    A("| POC | Component | Status | Detail |")
    A("| --- | --- | --- | --- |")
    for n, name in POCS.items():
        r = results.get(n)
        status = (r or {}).get("status", "NOT_STARTED")
        detail = (r or {}).get("headline", "no result file yet")
        A(f"| POC-{n} | {name} | **{status}** | {detail} |")
    A("")

    A("## Go / No-Go (PRD §12)")
    A("")
    A("Phase 0 is PASS only when every row is PASS.")
    A("")
    A("| Capability | Required | Actual | Source |")
    A("| --- | --- | --- | --- |")
    green = 0
    for cap, poc, key in GONOGO:
        val = capability(results, poc, key)
        if val is True:
            green += 1
        A(f"| {cap} | yes | **{MARK[val]}** | POC-{poc} |")
    A("")
    verdict = "PASS" if green == len(GONOGO) else "NOT YET"
    A(f"**{green}/{len(GONOGO)} capabilities green — Phase 0 verdict: {verdict}**")
    A("")

    blocked = [n for n, r in results.items() if r.get("status") == "BLOCKED_ON_ACCESS"]
    if blocked:
        A("### Blocked on external access")
        A("")
        for n in blocked:
            notes = results[n].get("notes", [])
            A(f"- **POC-{n} ({POCS[n]})** — " + ("; ".join(notes) if notes else "no detail recorded"))
        A("")

    metrics = {n: r.get("metrics") for n, r in results.items() if r.get("metrics")}
    if metrics:
        A("## Recorded metrics")
        A("")
        for n, m in sorted(metrics.items()):
            A(f"**POC-{n}**")
            A("")
            for k, v in m.items():
                A(f"- `{k}`: {v}")
            A("")

    problems = ROOT / "docs" / "known-data-problems.md"
    if problems.exists():
        A("## Known data problems")
        A("")
        A("See [docs/known-data-problems.md](docs/known-data-problems.md).")
        A("")

    return "\n".join(L) + "\n"


def main() -> int:
    # Windows consoles default to cp1252 and mangle the em-dashes below.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="regenerate poc/README.md")
    args = ap.parse_args()

    results = load()
    out = render(results)
    print(out)
    if args.write:
        (ROOT / "README.md").write_text(out, encoding="utf-8")
        print(f"wrote {ROOT / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
