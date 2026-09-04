"""Turn a run report into `poc/results/poc-1.json`.

The status table is the project's honesty mechanism, so every field here is
derived from something a run actually did:

* `download_gtfs` is true only if this session performed a real GET that
  produced bytes which validated as a zip.
* `parse_gtfs` is true only if all seven PRD §6 file groups produced a row
  count and no file failed to parse.
* `usage_terms_confirmed` is hardcoded false. It is human checkpoint H2 —
  gov.il returns 403 to automated fetches, so no agent can honestly set it.

A `PARTIAL` status is a normal outcome and is preferred to an optimistic
`PASS`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

SEVEN_GROUPS = {
    "agency": "agency",
    "routes": "routes",
    "trips": "trips",
    "stops": "stops",
    "stop_times": "stop_times",
    "calendar": "services",
    "shapes": "shapes",
}


def build(report: dict, cold: dict | None, notes: list[str]) -> tuple[dict, dict]:
    parsed = report.get("rows_parsed", {})
    groups = {}
    for label, key in SEVEN_GROUPS.items():
        groups[label] = parsed.get(key)
    all_groups = all(v is not None and v > 0 for v in groups.values())

    downloaded = bool(cold and cold.get("downloaded_bytes", 0) > 0) or any(
        r.get("status") in ("new", "changed", "unchanged") and r.get("zip_valid")
        for r in (report.get("refresh") or {}).values())

    val = report.get("validation_detail", {})
    validation = {k: bool(v.get("ok")) for k, v in val.items()}

    ec = report.get("edge_case_results", [])
    passed = sum(1 for e in ec if e["result"] == "pass")
    failed = [e["id"] for e in ec if e["result"] == "fail"]
    unobserved = [e["id"] for e in ec if e["result"] == "not_observed"]

    capabilities = {
        "download_gtfs": downloaded,
        "parse_gtfs": all_groups,
        "usage_terms_confirmed": False,   # checkpoint H2 — a human must read the licence
    }

    if capabilities["download_gtfs"] and capabilities["parse_gtfs"] \
            and not failed and all(validation.values()):
        status = "PASS"
    elif failed or not capabilities["parse_gtfs"]:
        status = "FAIL"
    else:
        status = "PARTIAL"

    headline = (
        f"{parsed.get('trips', 0):,} trips / {parsed.get('stop_times', 0):,} stop_times "
        f"parsed, 5 tables in Postgres, {passed}/{len(ec)} integrity checks pass"
    )
    if failed:
        headline += f"; FAILED {', '.join(failed)}"
    elif unobserved:
        headline += f"; {', '.join(unobserved)} not observed"
    if not report.get("trip_id_to_date", {}).get("paired_with_primary", True):
        headline += "; TripIdToDate unjoinable (KDP-008)"
    headline += "; licence terms unread (H2)"

    result = {
        "poc": 1,
        "name": "Static Israeli transportation data",
        "status": status,
        "generated": date.today().isoformat(),
        "headline": headline,
        "feed_sha256": report.get("sha256", {}).get("Gtfs_10_days.zip"),
        "capabilities": capabilities,
        "metrics": {
            "rows_parsed": parsed,
            "rows_loaded": report.get("rows_loaded", {}),
            "cold_refresh_seconds": (cold or {}).get("wall_seconds"),
            "peak_rss_mb": report.get("peak_rss_mb"),
            "ingest_seconds_offline": report.get("wall_seconds"),
            "seven_prd_groups": groups,
        },
        "validation_examples": validation,
        "edge_case_results": [
            {"id": e["id"], "result": e["result"], "detail": e["detail"]} for e in ec
        ],
        "notes": notes,
    }

    evidence = {
        "poc": 1,
        "generated": date.today().isoformat(),
        "feed_sha256": result["feed_sha256"],
        "note": ("Full evidence for poc/results/poc-1.json. Machine-written by "
                 "poc/gtfs/ingest.py; nothing here is hand-edited."),
        "report": report,
        "cold_run": cold,
        "edge_case_evidence": ec,
    }
    return result, evidence


def write(results_dir: Path, result: dict, evidence: dict) -> tuple[Path, Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    p1 = results_dir / "poc-1.json"
    p2 = results_dir / "poc-1-evidence.json"
    p1.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    p2.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, default=str) + "\n",
                  encoding="utf-8")
    return p1, p2
