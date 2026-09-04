#!/usr/bin/env python3
"""POC-5 supplement — can the geocoder find bars, restaurants and cafes?

The main places.json corpus covers stations, campuses, hospitals, malls,
landmarks, addresses and neighborhoods. It does not cover the venue category
people actually search for on a night out. This fills that gap.

GROUND TRUTH IS NOT HAND-ENTERED. Every case is sampled from
israel-and-palestine-latest.osm.pbf — the exact file MOTIS's geocoder was
built from. So the venue is provably present in the source data, and a miss
is unambiguously an indexing or ranking failure rather than a bad coordinate.
That matters: three separate hand-entered coordinates in this project have
already turned out to be wrong.

    python poc/geocoding/venues.py --build    # sample the corpus from OSM
    python poc/geocoding/venues.py --run      # query MOTIS and score
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geocoding.client import geocode  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "corpora" / "_osm_venues_raw.json"
CORPUS = ROOT / "corpora" / "places-venues.json"
RESULT = ROOT / "results" / "poc-5-venues.json"
REVIEW = ROOT / "results" / "venues-h4-review.md"

HEBREW = re.compile(r"[֐-׿]")
TOL_M = 300.0
SEED = 20260904

# Rough centres used only to spread the sample geographically and to label it.
CITIES = {
    "Tel Aviv": (32.0750, 34.7750), "Jerusalem": (31.7850, 35.2100),
    "Haifa": (32.8150, 34.9900), "Beersheba": (31.2520, 34.7910),
    "Netanya": (32.3300, 34.8550), "Eilat": (29.5570, 34.9520),
    "Rishon LeZion": (31.9640, 34.8040), "Nazareth": (32.7010, 35.3030),
}


def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def city_of(lat, lon) -> str | None:
    best, bd = None, 1e18
    for name, (cl, co) in CITIES.items():
        d = haversine(lat, lon, cl, co)
        if d < bd:
            best, bd = name, d
    return best if bd < 12000 else None


def build() -> None:
    venues = json.loads(RAW.read_text(encoding="utf-8"))
    rng = random.Random(SEED)

    # Stratify by amenity x script, and spread across cities so the sample is
    # not 48 Tel Aviv cafes.
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for v in venues:
        c = city_of(v["lat"], v["lon"])
        if not c:
            continue
        v["city"] = c
        script = "he" if HEBREW.search(v["name"]) else "latin"
        buckets[(v["amenity"], script)].append(v)

    quota = {
        "restaurant": 12, "cafe": 10, "fast_food": 8,
        "bar": 8, "pub": 5, "ice_cream": 3, "nightclub": 2,
    }

    picked: list[dict] = []
    for amenity, n in quota.items():
        half = max(1, n // 2)
        for script, want in (("he", n - half), ("latin", half)):
            pool = buckets.get((amenity, script), [])
            rng.shuffle(pool)
            seen_city: Counter = Counter()
            for v in pool:
                if len(([p for p in picked if p["amenity"] == amenity and p["script"] == script])) >= want:
                    break
                if seen_city[v["city"]] >= 2:
                    continue
                seen_city[v["city"]] += 1
                picked.append({**v, "script": script})

    cases = []
    for i, v in enumerate(sorted(picked, key=lambda x: (x["amenity"], x["script"], x["name"])), 1):
        case = {
            "id": f"V{i:03d}",
            "query": v["name"],
            "script": v["script"],
            "amenity": v["amenity"],
            "city": v["city"],
            "cuisine": v.get("cuisine"),
            "expect": {"lat": v["lat"], "lon": v["lon"], "tol_m": TOL_M},
            "osm": {"type": "node", "id": v["osm_id"]},
        }
        if v.get("name_en") and v["name_en"] != v["name"]:
            case["alt_query_en"] = v["name_en"]
        if v.get("name_he") and v["name_he"] != v["name"]:
            case["alt_query_he"] = v["name_he"]
        cases.append(case)

    doc = {
        "schema_version": 1,
        "generated": "2026-09-04",
        "generator": "poc/geocoding/venues.py --build",
        "purpose": "POC-5 supplement: bars, restaurants, cafes and other food-and-drink venues.",
        "provenance": {
            "ground_truth": (
                "Sampled from israel-and-palestine-latest.osm.pbf sha256 8a34b30f91a63ef9 — the same "
                "extract MOTIS's graph was built from. Coordinates are the OSM node's own, so they are "
                "exact by construction. NOT hand-entered."
            ),
            "why_this_matters": (
                "Because the venue is provably in the geocoder's source data, a miss cannot be blamed on "
                "a wrong corpus coordinate. It is an indexing or ranking failure."
            ),
            "sampling": f"seeded ({SEED}), stratified by amenity x script, capped at 2 per city per stratum",
            "tolerance": f"{TOL_M:.0f} m — a venue is a point, not an area",
        },
        "counts": {
            "by_amenity": dict(Counter(c["amenity"] for c in cases)),
            "by_script": dict(Counter(c["script"] for c in cases)),
            "by_city": dict(Counter(c["city"] for c in cases)),
            "with_english_name": sum(1 for c in cases if "alt_query_en" in c),
        },
        "total": len(cases),
        "cases": cases,
    }
    CORPUS.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {CORPUS} — {len(cases)} cases")
    for k, v in doc["counts"].items():
        print(f"  {k}: {v}")


def score_query(q: str, lat: float, lon: float) -> dict:
    resp = geocode(q)
    hits = resp.hits
    out = {"query": q, "n_hits": len(hits), "top1": None, "top5_rank": None,
           "top1_distance_m": None, "hits": []}
    for h in hits[:5]:
        d = haversine(lat, lon, h.lat, h.lon)
        out["hits"].append({"rank": h.rank, "name": h.name, "type": h.type,
                            "source": h.source, "distance_m": round(d, 1)})
        if out["top5_rank"] is None and d <= TOL_M:
            out["top5_rank"] = h.rank
    if hits:
        d0 = haversine(lat, lon, hits[0].lat, hits[0].lon)
        out["top1_distance_m"] = round(d0, 1)
        out["top1"] = d0 <= TOL_M
        out["top1_name"] = hits[0].name
        out["top1_source"] = hits[0].source
    else:
        out["top1"] = False
    return out


def run() -> None:
    doc = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases = doc["cases"]
    results, en_results = [], []

    for c in cases:
        lat, lon = c["expect"]["lat"], c["expect"]["lon"]
        r = score_query(c["query"], lat, lon)
        r.update(id=c["id"], amenity=c["amenity"], script=c["script"], city=c["city"])
        results.append(r)
        if "alt_query_en" in c:
            e = score_query(c["alt_query_en"], lat, lon)
            e.update(id=c["id"], amenity=c["amenity"], script=c["script"], city=c["city"])
            en_results.append(e)

    top1 = sum(1 for r in results if r["top1"])
    top5 = sum(1 for r in results if r["top5_rank"] is not None)
    zero = sum(1 for r in results if r["n_hits"] == 0)

    def bucket(key):
        d = defaultdict(lambda: {"top1": 0, "top5": 0, "total": 0, "zero_hits": 0})
        for r in results:
            b = d[r[key]]
            b["total"] += 1
            b["top1"] += bool(r["top1"])
            b["top5"] += r["top5_rank"] is not None
            b["zero_hits"] += r["n_hits"] == 0
        return dict(d)

    out = {
        "poc": 5,
        "supplement": "food-and-drink venues",
        "generated": "2026-09-04",
        "osm_sha256": "8a34b30f91a63ef9",
        "headline": f"{top1}/{len(results)} top-1, {top5}/{len(results)} in top-5, {zero} returned no candidate at all",
        "metrics": {
            "overall": {"top1": top1, "top5": top5, "total": len(results), "zero_hits": zero},
            "by_amenity": bucket("amenity"),
            "by_script": bucket("script"),
            "by_city": bucket("city"),
            "english_name_variant": {
                "top1": sum(1 for r in en_results if r["top1"]),
                "top5": sum(1 for r in en_results if r["top5_rank"] is not None),
                "total": len(en_results),
                "zero_hits": sum(1 for r in en_results if r["n_hits"] == 0),
            },
        },
        "cases": results,
        "english_variant_cases": en_results,
    }
    RESULT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    L = [f"# POC-5 supplement — food-and-drink venues\n",
         f"{out['headline']}\n",
         "Ground truth is the OSM node itself, from the extract MOTIS indexed. "
         "A miss here is an indexing or ranking failure, not a bad coordinate.\n"]
    for r in results:
        mark = "HIT " if r["top1"] else ("top5" if r["top5_rank"] else "MISS")
        L.append(f"## {r['id']} [{mark}] {r['query']}")
        L.append(f"- {r['amenity']} in {r['city']}, name script {r['script']}, {r['n_hits']} candidates")
        if r["hits"]:
            for h in r["hits"]:
                L.append(f"  - {h['rank']}. {h['name']} ({h['type']}, {h['source']}) — {h['distance_m']} m")
        else:
            L.append("  - no candidates returned")
        L.append("")
    REVIEW.write_text("\n".join(L), encoding="utf-8")

    print(out["headline"])
    print("\nby amenity:")
    for k, v in sorted(out["metrics"]["by_amenity"].items()):
        print(f"  {k:<12} top1 {v['top1']:>2}/{v['total']:<2}  top5 {v['top5']:>2}  zero-hits {v['zero_hits']}")
    print("\nby script:")
    for k, v in sorted(out["metrics"]["by_script"].items()):
        print(f"  {k:<12} top1 {v['top1']:>2}/{v['total']:<2}  top5 {v['top5']:>2}  zero-hits {v['zero_hits']}")
    e = out["metrics"]["english_name_variant"]
    print(f"\nname:en variant: top1 {e['top1']}/{e['total']}, top5 {e['top5']}, zero-hits {e['zero_hits']}")
    print(f"\nwrote {RESULT}\nwrote {REVIEW}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.build:
        build()
    if a.run:
        run()
    if not (a.build or a.run):
        ap.error("pass --build or --run")
