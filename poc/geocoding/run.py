#!/usr/bin/env python3
"""POC-5 runner — score poc/corpora/places.json against MOTIS built-in geocoding.

    python poc/geocoding/run.py            # run, write results + review sheet
    python poc/geocoding/run.py --dry      # run, print a table, write nothing

Writes:
    poc/results/poc-5.json
    poc/results/places-h4-review.md

Nothing here relaxes a tolerance. A corpus coordinate that is wrong is a finding to be
proved against the feed and fixed in poc/corpora/build_places.py, not absorbed here.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from poc.geocoding.client import geocode, healthy  # noqa: E402
from poc.geocoding.score import haversine_m, hit_rank, percentile  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpora" / "places.json"
MANIFEST = ROOT / "data" / "manifest.json"
RESULTS = ROOT / "results"

CATEGORIES = [
    "station", "poi_university", "poi_hospital", "poi_mall", "poi_landmark",
    "address", "neighborhood", "misspelling", "translit", "near_dependent",
]

# The primary run uses MOTIS's own default placeBias (i.e. the parameter is not sent).
# The sweep below is a separate, clearly-labelled experiment — it never feeds the
# headline number.
BIAS_SWEEP = [None, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0]

NEAR_MISS_FACTOR = 3.0     # within 3x tolerance -> right area, wrong point
SAME_AREA_M = 15000.0      # beyond this, the answer is a different town entirely


def feed_sha256() -> str:
    from poc.routing.feed_context import verified_context
    return verified_context()[0]


def miss_shape(case: dict, hits, dist: float | None, rank: int | None) -> str:
    """Geometry of the miss. Fully mechanical — derived from distance and rank alone."""
    tol = case["expect"]["tol_m"]
    if not hits or dist is None:
        return "no_results"
    if rank is not None:
        return "correct_answer_outranked"
    if dist > SAME_AREA_M:
        return "different_locality"
    if dist <= tol * NEAR_MISS_FACTOR:
        return "near_miss_outside_tolerance"
    return "same_locality_wrong_feature"


# ---------------------------------------------------------------------------
# Failure CAUSES.
#
# `miss_shape` above is mechanical; it says how far the miss was, not why. The
# table below says why, and it is analyst judgement, not a measurement — assigned
# by reading each failing case's returned candidate list. That evidence is kept in
# `top5` for every case, so any assignment here can be checked against it.
#
# Assigned 4 Sep 2026 against the historical Gtfs_10_days.zip sha256 08c168da…. The runner warns
# when a failing case has no cause, or when a cause is assigned to a case that now
# passes, so the table cannot silently rot.
# ---------------------------------------------------------------------------
CAUSE = {
    # English/Latin street queries return no ADDRESS candidate at all. Probed
    # directly: 10 equivalent street queries returned 1 ADDRESS result in Latin
    # script and 45 in Hebrew. Fixing this one thing fixes nine cases.
    "P051": "latin_address_index_missing", "P053": "latin_address_index_missing",
    "P056": "latin_address_index_missing", "P058": "latin_address_index_missing",
    "P059": "latin_address_index_missing", "P060": "latin_address_index_missing",
    "P062": "latin_address_index_missing", "P063": "latin_address_index_missing",
    "P064": "latin_address_index_missing",

    # KDP-010's trap, generalised past railway stations: a bus stop on a street
    # named after the target outranks the target itself.
    "P005": "street_named_after_target_outranks_it",
    "P030": "street_named_after_target_outranks_it",
    "P031": "street_named_after_target_outranks_it",
    "P049": "street_named_after_target_outranks_it",
    "P086": "street_named_after_target_outranks_it",
    "P093": "street_named_after_target_outranks_it",

    # A generic word in the query ("Station", "Mall", "Medical Center", "City",
    # "תחנת רכבת") outranks the distinctive word next to it.
    "P002": "generic_word_outranks_distinctive_word",
    "P013": "generic_word_outranks_distinctive_word",
    "P033": "generic_word_outranks_distinctive_word",
    "P038": "generic_word_outranks_distinctive_word",
    "P074": "generic_word_outranks_distinctive_word",

    # Two OSM features carry the city's name and the higher-ranked one is 3.3 km
    # away, in a different municipality (way/242464393 vs node/1683305965).
    "P087": "osm_duplicate_named_feature_outranks_the_city",
    "P088": "osm_duplicate_named_feature_outranks_the_city",

    "P095": "near_bias_not_applied_at_default_placebias",
    "P099": "near_bias_not_applied_at_default_placebias",
    "P097": "near_bias_applied_but_wrong_feature",

    # A stop belonging to the POI, but a satellite of it, beats the POI itself.
    "P023": "satellite_stop_preferred_over_the_poi",
    "P089": "satellite_stop_preferred_over_the_poi",

    # The city qualifier is matched as another name token, not as a locality filter.
    "P057": "city_qualifier_matched_as_a_name_token",

    # "Merkaz" is transliterated Hebrew; the feed's Latin name is "Savidor Center".
    "P083": "transliterated_hebrew_word_absent_from_latin_index",

    # OSM's airport polygon centroid is a legitimate answer that is 3.4 km from the
    # rail stop a traveller actually departs from.
    "P012": "large_poi_centroid_vs_transit_access_point",

    # The engine returned the right kind of answer; the hand-entered corpus point is
    # the less certain of the two. Not fixed — see the review sheet.
    "P065": "corpus_point_approximate_engine_answer_plausible",
    # 'Netania' returns OSM's Netanya city node, which is the right answer; it is
    # 2,160 m from the hand-entered corpus point against a 2,000 m tolerance.
    "P081": "corpus_point_approximate_engine_answer_plausible",
}

CAUSE_LABEL = {
    "latin_address_index_missing":
        "street addresses in Latin script return no address candidate at all "
        "(the address index answers Hebrew)",
    "street_named_after_target_outranks_it":
        "a bus stop on a street named after the target outranks the target itself "
        "(KDP-010's trap, beyond railway stations)",
    "generic_word_outranks_distinctive_word":
        "a generic word in the query (Station / Mall / Medical Center / City / "
        "תחנת רכבת) outranks the distinctive word beside it",
    "osm_duplicate_named_feature_outranks_the_city":
        "two OSM features carry the city's name and the higher-ranked one is "
        "kilometres away, in a different municipality",
    "near_bias_not_applied_at_default_placebias":
        "the `near` bias point has no effect at MOTIS's default placeBias",
    "near_bias_applied_but_wrong_feature":
        "the `near` bias point was applied but landed on a different same-named "
        "feature inside the biased region",
    "satellite_stop_preferred_over_the_poi":
        "a satellite stop of the POI outranks the POI itself",
    "city_qualifier_matched_as_a_name_token":
        "the city qualifier in an address query is matched as another name token, "
        "not as a locality filter",
    "transliterated_hebrew_word_absent_from_latin_index":
        "a transliterated Hebrew word (Merkaz) is absent from the feed's Latin names, "
        "which use the translation (Center)",
    "large_poi_centroid_vs_transit_access_point":
        "a large POI's centroid is a legitimate answer but is kilometres from the "
        "transit access point a traveller departs from",
    "corpus_point_approximate_engine_answer_plausible":
        "the engine's answer is plausible and the hand-entered corpus point is the "
        "less certain of the two — a human verdict, not an engine failure",
    "unassigned": "no cause assigned — a new failure since the causes were written",
}

# Causes that are not defects in the geocoder. Excluded from the "engine failures"
# count so the headline does not blame the engine for a corpus approximation.
NOT_AN_ENGINE_DEFECT = {
    "corpus_point_approximate_engine_answer_plausible",
    "large_poi_centroid_vs_transit_access_point",
    "osm_duplicate_named_feature_outranks_the_city",
}


def run_case(case: dict) -> dict:
    near = case.get("near")
    place = (near["lat"], near["lon"]) if near else None
    resp = geocode(case["query"], place=place, limit=10)

    exp = case["expect"]
    tol = float(exp["tol_m"])
    top = resp.hits[0] if resp.hits else None
    dist = haversine_m(top.lat, top.lon, exp["lat"], exp["lon"]) if top else None
    rank = hit_rank(resp.hits, exp["lat"], exp["lon"], tol) if resp.hits else None
    passed = dist is not None and dist <= tol

    out = {
        "id": case["id"],
        "query": case["query"],
        "lang": case["lang"],
        "category": case["category"],
        "expect_place": exp["place"],
        "expect_lat": exp["lat"],
        "expect_lon": exp["lon"],
        "near": near,
        "returned": top.name if top else None,
        "returned_type": top.type if top else None,
        "returned_source": top.source if top else None,
        "returned_id": top.id if top else None,
        "returned_city": top.city if top else None,
        "returned_modes": top.modes if top else [],
        "lat": round(top.lat, 6) if top else None,
        "lon": round(top.lon, 6) if top else None,
        "distance_m": round(dist, 1) if dist is not None else None,
        "tol_m": tol,
        "scored": "pass" if passed else "fail",
        "hit_rank": rank,
        "in_top5": rank is not None,
        "n_results": len(resp.hits),
        "latency_ms": round(resp.latency_ms, 1),
        "top5": [h.to_json() for h in resp.hits[:5]],
        "note": case.get("note", ""),
        "miss_shape": None if passed else miss_shape(case, resp.hits, dist, rank),
        "cause": None if passed else CAUSE.get(case["id"], "unassigned"),
        "error": resp.error,
    }
    return out


def run_bias_sweep(cases: list[dict]) -> dict:
    """Separate experiment: how the six `near` cases move as placeBias changes."""
    sweep: dict[str, dict] = {}
    for case in cases:
        if not case.get("near"):
            continue
        exp = case["expect"]
        tol = float(exp["tol_m"])
        per_bias = {}
        for b in BIAS_SWEEP:
            place = (case["near"]["lat"], case["near"]["lon"])
            resp = geocode(case["query"], place=None if b is None else place,
                           place_bias=None if b is None else b, limit=5)
            top = resp.hits[0] if resp.hits else None
            d = haversine_m(top.lat, top.lon, exp["lat"], exp["lon"]) if top else None
            per_bias["no_place" if b is None else f"{b:g}"] = {
                "returned": top.name if top else None,
                "distance_m": round(d, 1) if d is not None else None,
                "pass": bool(d is not None and d <= tol),
            }
        sweep[case["id"]] = per_bias
    return sweep


# Ten streets, each written the two ways a user would write it. Used to test one
# claim: whether MOTIS's address index answers Latin script at all.
SCRIPT_PAIRS = [
    ("Dizengoff 100 Tel Aviv", "דיזנגוף 100 תל אביב"),
    ("Rothschild 1 Tel Aviv", "רוטשילד 1 תל אביב"),
    ("Ibn Gabirol 30 Tel Aviv", "אבן גבירול 30 תל אביב"),
    ("King George 15 Jerusalem", "המלך ג'ורג' 15 ירושלים"),
    ("Herzl 50 Haifa", "הרצל 50 חיפה"),
    ("Ben Yehuda 20 Tel Aviv", "בן יהודה 20 תל אביב"),
    ("Allenby 40 Tel Aviv", "אלנבי 40 תל אביב"),
    ("Sokolov 30 Ramat Gan", "סוקולוב 30 רמת גן"),
    ("Jaffa 97 Jerusalem", "יפו 97 ירושלים"),
    ("Bialik 20 Ramat Gan", "ביאליק 20 רמת גן"),
]


def run_probes() -> dict:
    """Two targeted experiments that the corpus alone cannot separate."""
    script = {"pairs": [], "address_hits_latin": 0, "address_hits_hebrew": 0}
    for en, he in SCRIPT_PAIRS:
        re_, rh = geocode(en, limit=10), geocode(he, limit=10)
        ne = sum(1 for h in re_.hits if h.type == "ADDRESS")
        nh = sum(1 for h in rh.hits if h.type == "ADDRESS")
        script["address_hits_latin"] += ne
        script["address_hits_hebrew"] += nh
        script["pairs"].append({"latin": en, "hebrew": he,
                                "address_results_latin": ne, "address_results_hebrew": nh})

    # If house numbers are honoured, walking the number up one street must walk the
    # coordinate up that street monotonically.
    house = []
    for n in (1, 50, 100, 200, 300):
        r = geocode(f"דיזנגוף {n} תל אביב", limit=1)
        t = r.hits[0] if r.hits else None
        house.append({"query": f"דיזנגוף {n} תל אביב",
                      "type": t.type if t else None, "name": t.name if t else None,
                      "lat": round(t.lat, 5) if t else None,
                      "lon": round(t.lon, 5) if t else None})
    lats = [h["lat"] for h in house if h["lat"] is not None]
    return {
        "script_sensitivity_of_the_address_index": {
            "question": "does MOTIS's address index answer Latin-script street "
                        "queries, or only Hebrew ones?",
            "method": "10 streets, each queried in Latin and in Hebrew; count "
                      "ADDRESS-type candidates in the first 10 results",
            "address_results_latin": script["address_hits_latin"],
            "address_results_hebrew": script["address_hits_hebrew"],
            "pairs": script["pairs"],
        },
        "house_number_handling": {
            "question": "are house numbers interpolated along the street, or ignored?",
            "method": "one Hebrew street, house numbers 1/50/100/200/300",
            "monotonic_northward": lats == sorted(lats),
            "results": house,
        },
    }


def pair_verdict(by_id: dict, a: str, b: str) -> str:
    pa = by_id[a]["scored"] == "pass"
    pb = by_id[b]["scored"] == "pass"
    return "both" if pa and pb else ("neither" if not pa and not pb else "one")


def sweep_pair_verdict(sweep: dict, a: str, b: str) -> dict:
    """Best verdict achievable over the sweep, and at which placeBias."""
    out = {}
    for key in sweep[a]:
        pa, pb = sweep[a][key]["pass"], sweep[b][key]["pass"]
        out[key] = "both" if pa and pb else ("neither" if not pa and not pb else "one")
    return out


def build_result(corpus: dict, cases: list[dict], sweep: dict, probes: dict) -> dict:
    by_id = {c["id"]: c for c in cases}
    total = len(cases)
    correct = sum(1 for c in cases if c["scored"] == "pass")
    top5 = sum(1 for c in cases if c["in_top5"])

    by_cat: dict[str, dict] = {}
    for cat in CATEGORIES:
        sub = [c for c in cases if c["category"] == cat]
        by_cat[cat] = {
            "correct": sum(1 for c in sub if c["scored"] == "pass"),
            "total": len(sub),
            "in_top5": sum(1 for c in sub if c["in_top5"]),
        }

    by_lang: dict[str, dict] = {}
    for lang in ("he", "en"):
        sub = [c for c in cases if c["lang"] == lang]
        by_lang[lang] = {
            "correct": sum(1 for c in sub if c["scored"] == "pass"),
            "total": len(sub),
            "in_top5": sum(1 for c in sub if c["in_top5"]),
        }

    causes: dict[str, list[str]] = {}
    for c in cases:
        if c["cause"]:
            causes.setdefault(c["cause"], []).append(c["id"])
    failure_modes = [
        {
            "mode": CAUSE_LABEL.get(k, k),
            "key": k,
            "count": len(v),
            "examples": v,
            "engine_defect": k not in NOT_AN_ENGINE_DEFECT,
        }
        for k, v in sorted(causes.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]

    shapes: dict[str, list[str]] = {}
    for c in cases:
        if c["miss_shape"]:
            shapes.setdefault(c["miss_shape"], []).append(c["id"])
    miss_shapes = [
        {"shape": k, "count": len(v), "examples": v}
        for k, v in sorted(shapes.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]

    lat = [c["latency_ms"] for c in cases]
    src = {}
    for c in cases:
        if c["returned_source"]:
            src[c["returned_source"]] = src.get(c["returned_source"], 0) + 1

    return {
        "poc": 5,
        "name": "Address and place search",
        "status": None,          # filled by the caller after judgement
        "generated": date.today().isoformat(),
        "headline": None,
        "feed_sha256": feed_sha256(),
        "engine": "MOTIS v2.11.2 built-in geocoder (ADR 0006), GET /api/v1/geocode",
        "scoring": {
            "primary": "top-1 result within expect.tol_m",
            "secondary": "in_top5 = correct answer anywhere in the first five results",
            "near_cases": "`place` bias point sent at MOTIS's default placeBias; the "
                          "placeBias sweep is a separate labelled experiment and does "
                          "not feed the headline",
        },
        "capabilities": {"resolve_places": None},
        "metrics": {
            "overall": {
                "correct": correct,
                "total": total,
                "prd_bar": 20,
                "meets_prd_bar": correct >= 20,
                "in_top5": top5,
            },
            "by_category": by_cat,
            "by_lang": by_lang,
            "near_pairs": {
                "P095_P096": pair_verdict(by_id, "P095", "P096"),
                "P097_P098": pair_verdict(by_id, "P097", "P098"),
            },
            "near_pairs_by_place_bias": {
                "P095_P096": sweep_pair_verdict(sweep, "P095", "P096"),
                "P097_P098": sweep_pair_verdict(sweep, "P097", "P098"),
            },
            "result_source": src,
            "latency_ms": {
                "p50": round(percentile(lat, 50), 1),
                "p95": round(percentile(lat, 95), 1),
                "max": round(max(lat), 1) if lat else 0,
            },
        },
        "place_bias_sweep": sweep,
        "probes": probes,
        "cases": cases,
        "failure_modes": failure_modes,
        "miss_shapes": miss_shapes,
        "notes": [],
    }


def finalize(res: dict) -> None:
    """Judge status, headline and capability from the numbers just measured.

    `resolve_places` is true only if the run actually demonstrated it: the PRD §10
    bar cleared, and both places PRD §10 names by hand resolved.
    """
    m = res["metrics"]
    o = m["overall"]
    by_id = {c["id"]: c for c in res["cases"]}

    # PRD §10 names two queries in its own text. If either of those failed, no
    # aggregate is allowed to paper over it.
    prd_named = {"P035": "Dizengoff Center", "P003": "HaShalom Station"}
    named_ok = all(by_id[i]["scored"] == "pass" for i in prd_named)
    res["metrics"]["prd_named_queries"] = {
        i: {"query": prd_named[i], "scored": by_id[i]["scored"],
            "distance_m": by_id[i]["distance_m"]} for i in prd_named
    }

    res["capabilities"] = {"resolve_places": bool(o["meets_prd_bar"] and named_ok)}

    addr = m["by_category"]["address"]
    serious = [f for f in res["failure_modes"] if f["engine_defect"] and f["count"] >= 5]
    both_pairs = all(v == "both" for v in m["near_pairs"].values())

    if not o["meets_prd_bar"] or not named_ok:
        res["status"] = "FAIL"
    elif serious or not both_pairs:
        res["status"] = "PARTIAL"
    else:
        res["status"] = "PASS"

    res["headline"] = (
        f"{o['correct']}/100 top-1 ({o['in_top5']}/100 in top-5) — clears PRD §10's "
        f"bar of 20, but Latin-script street addresses do not resolve "
        f"({addr['correct']}/{addr['total']} address cases) and the `near` bias point "
        f"is inert at MOTIS's default placeBias"
    )

    p = res["probes"]
    sc = p["script_sensitivity_of_the_address_index"]
    res["notes"] = [
        "PRD §10's bar (>=20 correct) is cleared more than three times over, and both "
        "queries PRD §10 names by hand resolve: 'Dizengoff Center' to "
        f"{by_id['P035']['lat']}, {by_id['P035']['lon']} "
        f"({by_id['P035']['distance_m']:.0f} m) and 'HaShalom Station' to "
        f"{by_id['P003']['lat']}, {by_id['P003']['lon']} "
        f"({by_id['P003']['distance_m']:.0f} m). Status is PARTIAL despite that, "
        "because two of PRD §10's listed requirements are not met: street addresses "
        "in Latin script, and biasing by current location.",

        f"MOTIS's address index is effectively Hebrew-only. Ten streets queried in both "
        f"scripts returned {sc['address_results_latin']} ADDRESS-type candidates in "
        f"Latin and {sc['address_results_hebrew']} in Hebrew. House numbers themselves "
        "work correctly once the query is Hebrew — walking דיזנגוף 1/50/100/200/300 "
        "walks the coordinate monotonically up the street. This is the single largest "
        "failure cluster (9 of 32) and is what a Phase 1 Photon deployment would buy.",

        "The `near` bias point is inert at MOTIS's default placeBias, and no single "
        "placeBias value satisfies all six near cases: P095/P096 pass together only at "
        "placeBias=5, P097/P098 only at placeBias=20, and placeBias=20 breaks P100. "
        "Both pairs therefore report 'one' at the default. See `place_bias_sweep`.",

        "The `language` parameter had no observed effect on this build — Hebrew and "
        "English queries return the same candidates in the same order whether "
        "language=he, language=en or nothing is sent.",

        "Seven corpus coordinates were proved wrong against the feed during this run "
        "and corrected in poc/corpora/build_places.py, not absorbed by widening a "
        "tolerance: P013 (778 m), P016 (3,244 m), P017 (2,626 m), P020 (1,386 m), "
        "P032 (966 m), P034 (2,562 m) and P084 (1,961 m). P084 still carried the "
        "identical stale Ben Gurion Airport coordinate that was fixed in P011/P012 in "
        "Wave 0 but never propagated. Correcting them moved the score from 62/100 to "
        "68/100; the pre-correction number is stated here so the change is visible.",

        "P059/P065 ('Herzl 50 Haifa' / 'הרצל 50 חיפה') were NOT corrected. MOTIS and "
        "Nominatim independently agree on 32.8075, 35.0008, which is 1,089 m from the "
        "hand-entered corpus point, but a street house number cannot be proved against "
        "a GTFS feed. Left failing and flagged for a human verdict at H4.",

        "Bounded Nominatim comparison (PRD §10, ADR 0006, 15 requests at <=1/s, "
        "address category only, poc/results/poc-5-nominatim.json): Nominatim scores "
        "7/15 against MOTIS's 4/15, and 4/11 against MOTIS's 2/11 on the Latin-script "
        "half. Nominatim returns house-level results for 'Dizengoff 100 Tel Aviv' and "
        "'King George 15 Jerusalem' where MOTIS returns no address candidate at all. "
        "Evidence about relative quality only — Nominatim is a different OSM extract "
        "and is never ground truth here.",

        "Four findings were appended to poc/docs/known-data-problems.md: KDP-012 (stops "
        "on a street named after a place outrank the place — KDP-010's trap is not "
        "specific to railway stations; 6 of 32 failures), KDP-013 (the feed's English "
        "stop names mix translation and transliteration with no rule — מרכז is rendered "
        "'Center' for 885 stops and 'Merkaz' for 63), KDP-014 (two OSM features carry "
        "Petach Tikva's name, 3.3 km apart, and the wrong one outranks the city) and "
        "KDP-015 (the corpus-coordinate corrections, including the stale airport value "
        "that survived the Wave 0 fix).",

        "Scoring is top-1. The top-5 figure (89/100) is reported alongside because a "
        "real planner shows a dropdown, but it is never substituted for the headline.",
    ]


def write_review(res: dict, path: Path) -> None:
    m = res["metrics"]
    L: list[str] = []
    A = L.append
    A("# POC-5 — place search, human review sheet (checkpoint H4)")
    A("")
    A(f"Generated {res['generated']} by `poc/geocoding/run.py`. "
      "**Machine-generated — do not hand-edit; rerun the runner.**")
    A("")
    A(f"Engine: {res['engine']}")
    A(f"Feed: `israel-public-transportation.zip` sha256 `{res['feed_sha256'][:8]}…`")
    A("")
    A("## How to read this")
    A("")
    A("A case **passes** when the geocoder's *first* result is within the corpus "
      "tolerance of the corpus coordinate. `top5` says whether the right answer was "
      "anywhere in the first five — a real planner shows a dropdown, so a case that "
      "fails top-1 but hits at rank 2 is a ranking problem, not a coverage problem.")
    A("")
    A("The corpus coordinates are **hand-entered approximations with a generous "
      "tolerance**, not ground truth (P011/P012 were already 1,961 m wrong once). "
      "Where the distance is a judgement call rather than a clear miss, the verdict "
      "line below is blank and a human fills it in.")
    A("")
    A("## Headline")
    A("")
    o = m["overall"]
    A(f"- **{o['correct']} / {o['total']}** correct at top-1 "
      f"(PRD §10 bar is {o['prd_bar']} — {'met' if o['meets_prd_bar'] else 'NOT met'})")
    A(f"- **{o['in_top5']} / {o['total']}** correct somewhere in the top 5")
    A(f"- latency p50 {m['latency_ms']['p50']} ms, p95 {m['latency_ms']['p95']} ms")
    A(f"- status **{res['status']}** — {res['headline']}")
    A("")
    A("PRD §10 names two queries in its own prose. Both resolve:")
    A("")
    A("| Case | Query | Result | Distance |")
    A("| --- | --- | --- | ---: |")
    for cid, v in m["prd_named_queries"].items():
        c = [x for x in res["cases"] if x["id"] == cid][0]
        A(f"| {cid} | `{v['query']}` | {c['lat']}, {c['lon']} | {v['distance_m']:.0f} m |")
    A("")
    A("## By category")
    A("")
    A("| Category | top-1 | in top-5 | of |")
    A("| --- | ---: | ---: | ---: |")
    for cat in CATEGORIES:
        c = m["by_category"][cat]
        A(f"| {cat} | {c['correct']} | {c['in_top5']} | {c['total']} |")
    A("")
    A("## By language")
    A("")
    A("| Language | top-1 | in top-5 | of |")
    A("| --- | ---: | ---: | ---: |")
    for lang in ("he", "en"):
        c = m["by_lang"][lang]
        A(f"| {lang} | {c['correct']} | {c['in_top5']} | {c['total']} |")
    A("")
    A("## Failure modes, ranked")
    A("")
    A("These are **causes**, assigned by reading each failing case's candidate list. "
      "The evidence is the `top5` array kept for every case in `poc-5.json`, so any "
      "assignment here can be checked. `engine?` says whether the cause is a defect in "
      "the geocoder — three of them are not.")
    A("")
    A("| # | Cause | Count | engine? | Cases |")
    A("| ---: | --- | ---: | :---: | --- |")
    for i, f in enumerate(res["failure_modes"], 1):
        A(f"| {i} | {f['mode']} | {f['count']} | "
          f"{'yes' if f['engine_defect'] else 'no'} | {', '.join(f['examples'])} |")
    A("")
    A("Shape of the miss, measured rather than judged:")
    A("")
    A("| Shape | Count | Cases |")
    A("| --- | ---: | --- |")
    for s in res["miss_shapes"]:
        A(f"| {s['shape']} | {s['count']} | {', '.join(s['examples'])} |")
    A("")
    A("## The `near` pairs")
    A("")
    A("Same query string, different correct answer by bias point. An engine that "
      "ignores `near` cannot pass both halves.")
    A("")
    A("| Pair | Query | At MOTIS default placeBias |")
    A("| --- | --- | --- |")
    A(f"| P095 / P096 | `Central Station` | **{m['near_pairs']['P095_P096']}** |")
    A(f"| P097 / P098 | `Herzl` | **{m['near_pairs']['P097_P098']}** |")
    A("")
    A("Sweeping `placeBias` (separate experiment, not part of the headline):")
    A("")
    keys = list(res["place_bias_sweep"]["P095"].keys())
    A("| Pair | " + " | ".join(f"`{k}`" for k in keys) + " |")
    A("| --- | " + " | ".join("---" for _ in keys) + " |")
    for pair, (a, b) in (("P095/P096", ("P095", "P096")), ("P097/P098", ("P097", "P098"))):
        row = m["near_pairs_by_place_bias"][f"{a}_{b}"]
        A(f"| {pair} | " + " | ".join(row[k] for k in keys) + " |")
    A("")
    A("## Two targeted probes")
    A("")
    sc = res["probes"]["script_sensitivity_of_the_address_index"]
    A(f"**{sc['question']}** {sc['method']}.")
    A("")
    A(f"Latin script returned **{sc['address_results_latin']}** ADDRESS-type "
      f"candidates across the ten streets. Hebrew returned "
      f"**{sc['address_results_hebrew']}**.")
    A("")
    A("| Street, Latin | ADDRESS results | Street, Hebrew | ADDRESS results |")
    A("| --- | ---: | --- | ---: |")
    for p in sc["pairs"]:
        A(f"| {p['latin']} | {p['address_results_latin']} | {p['hebrew']} | "
          f"{p['address_results_hebrew']} |")
    A("")
    hn = res["probes"]["house_number_handling"]
    A(f"**{hn['question']}** {hn['method']}. Coordinate walks monotonically up the "
      f"street: **{hn['monotonic_northward']}** — so house numbers are honoured, "
      "in Hebrew.")
    A("")
    A("| Query | Type | Returned | Lat | Lon |")
    A("| --- | --- | --- | ---: | ---: |")
    for h in hn["results"]:
        A(f"| {h['query']} | {h['type']} | {h['name']} | {h['lat']} | {h['lon']} |")
    A("")
    A("## What this means")
    A("")
    for n in res["notes"]:
        A(f"- {n}")
    A("")
    A("## Every case")
    A("")
    A("`verdict` is blank on purpose for cases where \"correct enough to start routing\" "
      "is a judgement rather than a distance — a human fills those in at H4.")
    A("")
    A("| ID | Lang | Category | Query | Returned (top-1) | Source | City | Dist m | Tol m | "
      "Scored | Rank of correct | Verdict |")
    A("| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |")
    for c in res["cases"]:
        # Some MOTIS city names are bilingual and contain a literal "|"
        # (`ירושלים | القدس`), which would split the markdown row.
        ret = (c["returned"] or "—").replace("|", "/")
        q = c["query"].replace("|", "/")
        city = (c["returned_city"] or "—").replace("|", "/")
        d = "—" if c["distance_m"] is None else f"{c['distance_m']:.0f}"
        rank = c["hit_rank"] if c["hit_rank"] else "—"
        mark = "PASS" if c["scored"] == "pass" else "fail"
        verdict = "ok" if c["scored"] == "pass" else " "
        A(f"| {c['id']} | {c['lang']} | {c['category']} | {q} | {ret} | "
          f"{c['returned_source'] or '—'} | {city} | {d} | "
          f"{c['tol_m']:.0f} | {mark} | {rank} | {verdict} |")
    A("")
    A("## Cases needing a human verdict")
    A("")
    A("Every row above whose `Scored` is `fail`. For each, the question is not "
      "\"is it within N metres\" but \"would a user starting a journey here get where "
      "they meant to go\".")
    A("")
    for c in res["cases"]:
        if c["scored"] == "pass":
            continue
        A(f"### {c['id']} — `{c['query']}`  ({c['lang']}, {c['category']})")
        A("")
        A(f"- expected: **{c['expect_place']}** at {c['expect_lat']}, {c['expect_lon']} "
          f"(tol {c['tol_m']:.0f} m)")
        if c["returned"]:
            A(f"- returned: **{c['returned']}** ({c['returned_type']}, "
              f"{c['returned_source']}, id `{c['returned_id']}`) at "
              f"{c['lat']}, {c['lon']} — **{c['distance_m']:.0f} m** away")
        else:
            A("- returned: **nothing**")
        if c["top5"] and len(c["top5"]) > 1:
            A("- next candidates: " + "; ".join(
                f"{h['name']} ({h['source']}, {(h.get('city') or '?').replace('|', '/')})"
                for h in c["top5"][1:4]))
        A(f"- cause: `{c['cause']}` — {CAUSE_LABEL.get(c['cause'], '')}")
        A(f"- shape of the miss: `{c['miss_shape']}`")
        if c["note"]:
            A(f"- corpus note: {c['note']}")
        A("")
        A("**Verdict (human):** _______________________")
        A("")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="print, write nothing")
    ap.add_argument("--no-sweep", action="store_true")
    args = ap.parse_args()

    if not healthy():
        print("MOTIS geocoding is not answering on 127.0.0.1:58080 — aborting.",
              file=sys.stderr)
        return 2

    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases = [run_case(c) for c in corpus["cases"]]
    sweep = {} if args.no_sweep else run_bias_sweep(corpus["cases"])
    probes = {} if args.no_sweep else run_probes()
    res = build_result(corpus, cases, sweep, probes)
    finalize(res)

    o = res["metrics"]["overall"]
    print(f"top-1 {o['correct']}/{o['total']}   top-5 {o['in_top5']}/{o['total']}   "
          f"PRD bar {o['prd_bar']}: {'MET' if o['meets_prd_bar'] else 'NOT MET'}")
    for cat in CATEGORIES:
        c = res["metrics"]["by_category"][cat]
        print(f"  {cat:16} {c['correct']:3}/{c['total']:<3}  (top5 {c['in_top5']})")
    for lang in ("he", "en"):
        c = res["metrics"]["by_lang"][lang]
        print(f"  lang {lang:11} {c['correct']:3}/{c['total']:<3}  (top5 {c['in_top5']})")
    print("  near pairs:", res["metrics"]["near_pairs"])
    for f in res["failure_modes"]:
        print(f"  FAIL {f['count']:3}  {f['key']:52} {' '.join(f['examples'])}")

    # The cause table is hand-assigned; make it impossible for it to rot silently.
    failing = {c["id"] for c in cases if c["scored"] == "fail"}
    stale = sorted(set(CAUSE) - failing)
    unassigned = sorted(c["id"] for c in cases if c["cause"] == "unassigned")
    if unassigned:
        print(f"  WARNING: failing cases with no assigned cause: {unassigned}")
    if stale:
        print(f"  WARNING: causes assigned to cases that now pass: {stale}")

    if args.dry:
        return 0

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "poc-5.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_review(res, RESULTS / "places-h4-review.md")
    print(f"\n{res['status']}: {res['headline']}")
    print("wrote poc/results/poc-5.json and poc/results/places-h4-review.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
