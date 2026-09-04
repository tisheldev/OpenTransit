#!/usr/bin/env python3
"""Record a content manifest for the downloaded feeds.

Every result file in this POC must be traceable to the exact bytes it was
produced from. MOT rewrites the GTFS feeds nightly, so "the 10-day feed"
is not a stable identifier — the hash is.

Usage:
    python poc/manifest.py            # write poc/data/manifest.json
    python poc/manifest.py --check    # verify files still match the manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

EXPECTED = {
    "Gtfs_10_days.zip": "MOT 10-day GTFS — primary input (ADR 0005)",
    "israel-public-transportation.zip": "MOT 60-day GTFS — comparison only (ADR 0005)",
    "TripIdToDate.zip": "MOT trip-id to date mapping — required for realtime matching",
    "israel-and-palestine-latest.osm.pbf": "Geofabrik OSM extract — walking legs for MOTIS",
}

SOURCES = {
    "Gtfs_10_days.zip": "https://gtfs.mot.gov.il/gtfsfiles/Gtfs_10_days.zip",
    "israel-public-transportation.zip": "https://gtfs.mot.gov.il/gtfsfiles/israel-public-transportation.zip",
    "TripIdToDate.zip": "https://gtfs.mot.gov.il/gtfsfiles/TripIdToDate.zip",
    "israel-and-palestine-latest.osm.pbf": "https://download.geofabrik.de/asia/israel-and-palestine-latest.osm.pbf",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def zip_contents(p: Path) -> list[dict] | None:
    """Validate the zip and list members. A truncated download fails here, not later."""
    if p.suffix != ".zip":
        return None
    try:
        with zipfile.ZipFile(p) as z:
            bad = z.testzip()
            if bad is not None:
                return [{"error": f"corrupt member: {bad}"}]
            return [{"name": i.filename, "size": i.file_size} for i in z.infolist()]
    except zipfile.BadZipFile as e:
        return [{"error": f"not a valid zip: {e}"}]


def build() -> dict:
    files = {}
    for name, desc in EXPECTED.items():
        p = DATA / name
        if not p.exists():
            files[name] = {"present": False, "description": desc}
            continue
        st = p.stat()
        entry = {
            "present": True,
            "description": desc,
            "source": SOURCES[name],
            "size_bytes": st.st_size,
            "sha256": sha256(p),
            "retrieved_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
        }
        members = zip_contents(p)
        if members is not None:
            entry["zip_valid"] = not any("error" in m for m in members)
            entry["members"] = members
        files[name] = entry

    return {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "note": (
            "MOT rewrites these feeds nightly. Any result produced from this data must cite "
            "the sha256 recorded here, not the filename."
        ),
        "files": files,
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify against the existing manifest")
    args = ap.parse_args()

    out = DATA / "manifest.json"

    if args.check:
        if not out.exists():
            print("no manifest to check against")
            return 1
        old = json.loads(out.read_text(encoding="utf-8"))
        new = build()
        drift = []
        for name, entry in new["files"].items():
            prev = old["files"].get(name, {})
            if prev.get("sha256") != entry.get("sha256"):
                drift.append(f"{name}: {prev.get('sha256', 'absent')[:12]} -> {entry.get('sha256', 'absent')[:12]}")
        if drift:
            print("DRIFT — the feeds changed since the manifest was written:")
            for d in drift:
                print(f"  {d}")
            return 2
        print("manifest matches on disk")
        return 0

    m = build()
    DATA.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}\n")
    for name, e in m["files"].items():
        if not e["present"]:
            print(f"  MISSING  {name}")
            continue
        mb = e["size_bytes"] / 1_000_000
        zv = "" if "zip_valid" not in e else (" zip:ok" if e["zip_valid"] else " zip:CORRUPT")
        n = len(e.get("members", []))
        members = f" {n} members" if n else ""
        print(f"  {mb:9.1f} MB  {e['sha256'][:16]}  {name}{zv}{members}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
