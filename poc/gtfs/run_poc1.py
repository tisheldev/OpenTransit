#!/usr/bin/env python3
"""Produce `poc/results/poc-1.json` from two real runs.

    python poc/gtfs/run_poc1.py

Run 1 — **cold**. A brand new empty directory, a full download of every feed
over HTTP, parse, load into its own Postgres schema, and a query against the
result. This is the PRD §6 PASS bar and corpus check E10: zero manual steps
between "nothing on disk" and "queryable database". Its wall time is
`cold_refresh_seconds`.

Run 2 — **of record**. The same entry point against `poc/data/`, whose exact
bytes are pinned in `poc/data/manifest.json`. Every row count, every edge-case
result and the `feed_sha256` in poc-1.json come from this run, so the numbers
stay attached to a hash a human can check rather than to whatever MOT
published in the last few minutes.

`--skip-cold` reuses a previously recorded cold run instead of downloading
again; without one, E10 is honestly recorded as `not_observed`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "poc.gtfs"

from . import db, ingest, result as result_mod  # noqa: E402

POC_ROOT = Path(__file__).resolve().parents[1]
COLD_SCHEMA = "coldrun"


class Args:
    """ingest.run() takes an argparse namespace; this is one, explicitly."""

    def __init__(self, **kw):
        self.data_dir = str(POC_ROOT / "data")
        self.dsn = db.DSN
        self.schema = "public"
        self.offline = False
        self.skip_comparison = False
        self.head_probe = False
        self.write_corpus = False
        self.report = None
        self.timeout = 1800
        self.cold_result = None
        self.__dict__.update(kw)


def cold_run(dsn: str, keep: bool) -> dict:
    """Empty directory -> downloaded -> parsed -> loaded -> queried."""
    tmp = Path(tempfile.mkdtemp(prefix="opentransit-cold-"))
    ingest.log(f"COLD RUN: empty data directory {tmp}")
    t0 = time.monotonic()
    status = 0
    report = None
    try:
        report = ingest.run(Args(data_dir=str(tmp), schema=COLD_SCHEMA, dsn=dsn,
                                 offline=False, skip_comparison=True))
    except SystemExit as e:
        status = int(e.code or 1)
    except Exception as e:  # noqa: BLE001
        ingest.log(f"COLD RUN FAILED: {type(e).__name__}: {e}")
        status = 1
    wall = round(time.monotonic() - t0, 1)

    queryable = False
    probe = None
    if status == 0:
        try:
            conn = db.connect(dsn)
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT (SELECT count(*) FROM {COLD_SCHEMA}.stops), "
                    f"       (SELECT count(*) FROM {COLD_SCHEMA}.trips), "
                    f"       (SELECT count(*) FROM {COLD_SCHEMA}.routes)")
                stops, trips, routes = cur.fetchone()
            conn.close()
            probe = {"stops": stops, "trips": trips, "routes": routes}
            queryable = stops > 0 and trips > 0 and routes > 0
        except Exception as e:  # noqa: BLE001
            probe = {"error": f"{type(e).__name__}: {e}"}

    out = {
        "started_empty": True,
        "data_dir": str(tmp),
        "schema": COLD_SCHEMA,
        "manual_steps": 0,
        "command": "python poc/gtfs/ingest.py --data-dir <empty dir>",
        "wall_seconds": wall,
        "exit_status": status,
        "queryable": queryable,
        "query_probe": probe,
        "downloaded_bytes": (report or {}).get("downloaded_bytes", 0),
        "downloaded_sha256": (report or {}).get("sha256"),
        "refresh": (report or {}).get("refresh"),
        "peak_rss_mb": (report or {}).get("peak_rss_mb"),
        "note": ("The cold run downloads whatever MOT is publishing at that moment, "
                 "so its hashes may differ from poc/data/manifest.json. The recorded "
                 "row counts and edge-case results come from the manifest bytes, not "
                 "from this run."),
    }
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
        out["data_dir_removed"] = True
    return out


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=db.DSN)
    ap.add_argument("--skip-cold", action="store_true")
    ap.add_argument("--cold-json", default=str(POC_ROOT / "results" / "poc-1-cold-run.json"))
    ap.add_argument("--keep-cold-dir", action="store_true")
    args = ap.parse_args(argv)

    cold_path = Path(args.cold_json)
    if args.skip_cold:
        cold = json.loads(cold_path.read_text(encoding="utf-8")) if cold_path.exists() else None
        if cold and not (cold.get("downloaded_sha256") or {}).get(ingest.PRIMARY):
            cold = None
        if cold is None:
            ingest.log("no recorded cold run and --skip-cold given: E10 will be not_observed")
    else:
        cold = cold_run(args.dsn, args.keep_cold_dir)
        cold_path.parent.mkdir(parents=True, exist_ok=True)
        cold_path.write_text(json.dumps(cold, indent=2, default=str) + "\n", encoding="utf-8")
        ingest.log(f"cold run recorded in {cold_path}")

    ingest.log("RUN OF RECORD: poc/data (bytes pinned in manifest.json)")
    report = ingest.run(Args(offline=True, head_probe=True, write_corpus=True,
                             schema="public", dsn=args.dsn, cold_result=cold))

    notes = build_notes(report, cold)
    res, evidence = result_mod.build(report, cold, notes)
    p1, p2 = result_mod.write(POC_ROOT / "results", res, evidence)
    ingest.log(f"wrote {p1}")
    ingest.log(f"wrote {p2}")
    print(json.dumps({k: res[k] for k in
                      ("status", "headline", "feed_sha256", "capabilities")},
                     indent=2, ensure_ascii=False))
    return 0


def build_notes(report: dict, cold: dict | None) -> list[str]:
    notes: list[str] = []
    notes.append(f"Primary: {ingest.PRIMARY}; TripIdToDate compatibility enforced before load. "
                 f"Service window: {report.get('service_window')}. 10-day feed is comparison only.")
    notes.append(
        "stop_times and shapes are parsed, counted and integrity-checked but "
        "deliberately not loaded into Postgres (ADR 0003 / system-design §173)."
    )
    notes.append(
        "agency.txt is parsed but not given its own table; agency_name is "
        "denormalised onto routes so operator queries work without widening the "
        "load set beyond the five tables ADR 0003 names."
    )
    notes.append(
        "usage_terms_confirmed is false and cannot be set by an agent: gov.il "
        "returns 403 to automated fetches, so checkpoint H2 needs a human to read "
        "and record the licence text."
    )
    if cold and cold.get("exit_status") == 0:
        notes.append(
            f"Cold run: {cold['wall_seconds']}s from an empty directory to a "
            f"queryable database, {cold.get('downloaded_bytes', 0) / 1e6:.0f} MB "
            "downloaded, zero manual steps."
        )
    return notes


if __name__ == "__main__":
    raise SystemExit(main())
