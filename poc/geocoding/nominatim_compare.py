#!/usr/bin/env python3
"""Bounded Nominatim comparison — ADR 0006 and PRD §10 allow this and nothing more.

    python poc/geocoding/nominatim_compare.py

Constraints, enforced here rather than assumed:
  - at most one request per second (this script sleeps 1.2 s between calls)
  - no autocomplete, no bulk run: only the `address` category, 15 queries
  - a descriptive User-Agent, as the Nominatim usage policy requires

This is **evidence about relative quality, never ground truth**. Nominatim is a
different OSM extract on a different date; where it disagrees with MOTIS that says
the two engines differ, not that either is right. Its only job here is to answer one
question POC-5 raised: is "Latin-script Israeli street addresses do not resolve" a
property of OSM data, or a property of MOTIS's index?

Writes poc/results/poc-5-nominatim.json.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from poc.geocoding.score import haversine_m  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpora" / "places.json"
OUT = ROOT / "results" / "poc-5-nominatim.json"

ENDPOINT = "https://nominatim.openstreetmap.org/search"
UA = "OpenTransit-POC5/0.1 (Phase 0 evaluation; bounded comparison, <=1 req/s)"
MIN_INTERVAL_S = 1.2

CATEGORY = "address"   # the only category we spend requests on


def query(text: str) -> list[dict]:
    url = ENDPOINT + "?" + urllib.parse.urlencode(
        {"q": text, "format": "json", "limit": "3", "countrycodes": "il"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return [{"_error": repr(e)}]


def main() -> int:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases = [c for c in corpus["cases"] if c["category"] == CATEGORY]

    rows, last = [], 0.0
    for c in cases:
        wait = MIN_INTERVAL_S - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        last = time.monotonic()
        res = query(c["query"])
        e = c["expect"]
        top = res[0] if res and "_error" not in res[0] else None
        d = haversine_m(float(top["lat"]), float(top["lon"]), e["lat"], e["lon"]) if top else None
        rows.append({
            "id": c["id"], "query": c["query"], "lang": c["lang"],
            "returned": (top or {}).get("display_name"),
            "osm_type": (top or {}).get("type"),
            "lat": float(top["lat"]) if top else None,
            "lon": float(top["lon"]) if top else None,
            "distance_m": round(d, 1) if d is not None else None,
            "tol_m": e["tol_m"],
            "scored": "pass" if (d is not None and d <= e["tol_m"]) else "fail",
            "n_results": 0 if (res and "_error" in res[0]) else len(res),
            "error": res[0].get("_error") if res and "_error" in res[0] else None,
        })
        print(f"  {rows[-1]['id']} {rows[-1]['scored']:4} "
              f"{rows[-1]['distance_m']} m  {c['query']}")

    ok = sum(1 for r in rows if r["scored"] == "pass")
    en = [r for r in rows if r["lang"] == "en"]
    he = [r for r in rows if r["lang"] == "he"]
    doc = {
        "poc": 5,
        "artifact": "bounded Nominatim comparison (PRD §10, ADR 0006)",
        "generated": date.today().isoformat(),
        "status": "COMPARISON ONLY — not ground truth, not a POC-5 result",
        "endpoint": ENDPOINT,
        "rate_limit": f"{MIN_INTERVAL_S}s between requests, {len(rows)} requests total, "
                      "no autocomplete",
        "scope": f"the {len(rows)} `{CATEGORY}` cases only",
        "summary": {
            "correct": ok, "total": len(rows),
            "en": {"correct": sum(1 for r in en if r["scored"] == "pass"), "total": len(en)},
            "he": {"correct": sum(1 for r in he if r["scored"] == "pass"), "total": len(he)},
        },
        "cases": rows,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nNominatim on the address category: {ok}/{len(rows)} "
          f"(en {doc['summary']['en']['correct']}/{doc['summary']['en']['total']}, "
          f"he {doc['summary']['he']['correct']}/{doc['summary']['he']['total']})")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
