"""Check a RUNNING API's real MOTIS enforcement of the access/egress/direct walking caps.

M3.2 conformance: the adapter sends maxPreTransitTime / maxPostTransitTime / maxDirectTime
and the pinned MOTIS documents them as limited by unpinned server config. This script asks the
API for journeys at several cap values and checks every returned walk against the cap. It never
starts Docker or downloads data, and refuses to overwrite an existing --output file.

    uv run --project services/api --locked python services/api/tools/check_walk_caps.py
        --api-url http://127.0.0.1:8002 --depart-at 2026-10-02T08:00:00+03:00
        --output .runtime/walk-cap-conformance-1.json

(from the repository root; choose a departure inside the generation's coverage).

Exit 0: no violation found (the sample is not proof for other routes); 1: violation; 2: error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

# Approximate points. The short pair has a ~1 km walk so direct-walk alternatives can appear.
PAIRS = {
    "dizengoff-technion": (
        {"kind": "coordinate", "latitude": 32.0757, "longitude": 34.7748},
        {"kind": "coordinate", "latitude": 32.7775, "longitude": 35.0219},
    ),
    "dizengoff-rabin-square": (
        {"kind": "coordinate", "latitude": 32.0757, "longitude": 34.7748},
        {"kind": "coordinate", "latitude": 32.0807, "longitude": 34.7806},
    ),
}
CAP_MINUTES = (1, 5, 15, 30)
TOLERANCE_SECONDS = 60  # MOTIS reports walk legs at one-minute timetable resolution.


def walk_segments(journey: dict) -> tuple[int, int, bool]:
    """Return (leading walk seconds, trailing walk seconds, walk-only)."""
    legs = journey["legs"]
    if all(leg["kind"] == "walk" for leg in legs):
        return 0, 0, True
    lead = 0
    for leg in legs:
        if leg["kind"] != "walk":
            break
        lead += leg["durationSeconds"]
    tail = 0
    for leg in reversed(legs):
        if leg["kind"] != "walk":
            break
        tail += leg["durationSeconds"]
    return lead, tail, False


def violations(journey: dict, access: int, egress: int, direct: int) -> list[str]:
    """Walks longer than their cap (minutes) plus one-minute resolution tolerance."""
    lead, tail, walk_only = walk_segments(journey)
    found = []
    if walk_only:
        if journey["durationSeconds"] > direct * 60 + TOLERANCE_SECONDS:
            found.append(f"direct walk {journey['durationSeconds']}s > {direct} min")
        return found
    if lead > access * 60 + TOLERANCE_SECONDS:
        found.append(f"access walk {lead}s > {access} min")
    if tail > egress * 60 + TOLERANCE_SECONDS:
        found.append(f"egress walk {tail}s > {egress} min")
    return found


def run(api_url: str, depart_at: str, client: httpx.Client) -> dict:
    cases, failures = [], 0
    for name, (origin, destination) in PAIRS.items():
        for minutes in CAP_MINUTES:
            caps = {
                "maxAccessWalkMinutes": minutes,
                "maxEgressWalkMinutes": minutes,
                "maxDirectWalkMinutes": minutes,
            }
            body = {"from": origin, "to": destination, "departAt": depart_at, "results": 5}
            response = client.post(api_url.rstrip("/") + "/v1/journeys", json=body | caps)
            entry = {"pair": name, "capMinutes": minutes, "status": response.status_code}
            if response.status_code == 200:
                payload = response.json()
                found = [
                    f"{journey['id']}: {problem}"
                    for journey in payload["data"]["journeys"]
                    for problem in violations(journey, minutes, minutes, minutes)
                ]
                entry |= {
                    "outcome": payload["data"]["outcome"],
                    "journeys": len(payload["data"]["journeys"]),
                    "violations": found,
                    "generationId": payload["meta"]["generationId"],
                    "warnings": payload["meta"]["warnings"],
                }
                failures += len(found)
            else:
                entry["violations"] = []
                entry["error"] = response.json().get("code") if response.content else None
            cases.append(entry)
    return {
        "departAt": depart_at,
        "apiUrl": api_url,
        "toleranceSeconds": TOLERANCE_SECONDS,
        "violationCount": failures,
        "errors": sum(1 for case in cases if case["status"] != 200),
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--depart-at", required=True, help="ISO time with explicit offset")
    parser.add_argument("--output", type=Path, help="new JSON evidence file (never overwritten)")
    args = parser.parse_args(argv)
    try:
        with httpx.Client(timeout=15.0) as client:
            report = run(args.api_url, args.depart_at, client)
        text = json.dumps(report, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text)
    except (httpx.HTTPError, OSError, KeyError, ValueError) as exc:
        print(f"error: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(text)
    return 1 if report["violationCount"] else 2 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
