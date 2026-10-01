"""Offline replay of M4 stop-search ranking against a saved API search run.

For every case in a saved ``evaluate_search`` result whose request types include
``stop`` or ``station`` the tool recomputes the stop candidates in-process against a
real reference file, reuses the geocoder candidates recorded in the saved run (in
their recorded order), merges them with the production merge and scores the
merged list with the production evaluator. It needs no HTTP, Docker or network.

Limits (record them with any result): geocoder candidates come from the saved
merged top-10 only, so candidates that the original merge truncated cannot
reappear; timings are in-process ``search_stops`` durations on the host, not API
durations; a replay is a projection, never a fresh API run and never an H4 verdict.

With ``--locality-probe`` the result also carries a before/after probe of city-name
queries: each query is run once with the reference's OSM localities and once with only
the feed-derived locality fallback, and every top-5 stop is judged by polygon
containment in the expected OSM locality (a structural check, not an H4 verdict).

Usage:
    python tools/replay_search.py --reference REF.sqlite --saved-run RUN.json \
        --output OUT.json [--compare NAME=PREVIOUS_REPLAY.json ...] [--locality-probe]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:  # imported as tools.replay_search (tests) or run as a script
    from tools.evaluate_search import SearchCase, load_cases, score_response
except ImportError:  # pragma: no cover - script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from evaluate_search import SearchCase, load_cases, score_response

from opentransit.api.routes.places import _merge_candidates
from opentransit.reference import ReferenceStore
from opentransit.stop_search import _distance_m, _search_index, search_stops

SCHEMA_VERSION = 1
STOP_TYPES = ("stop", "station")
GEOCODER_KINDS = ("poi", "address")
API_LIMIT = 10


# (query, language, OSM locality id it names). Relation ids are the pinned OSM extract's;
# the list mixes Hebrew names, English names and common Latin spellings.
LOCALITY_PROBE = (
    ("Tel Aviv", "en", "osm:relation:1382494"),
    ("תל אביב", "he", "osm:relation:1382494"),
    ("Tel-Aviv", "en", "osm:relation:1382494"),
    ("Jerusalem", "en", "osm:relation:1381350"),
    ("ירושלים", "he", "osm:relation:1381350"),
    ("Haifa", "en", "osm:relation:1387888"),
    ("חיפה", "he", "osm:relation:1387888"),
    ("Be'er Sheva", "en", "osm:relation:1377264"),
    ("Beer Sheva", "en", "osm:relation:1377264"),
    ("Beersheba", "en", "osm:relation:1377264"),
    ("באר שבע", "he", "osm:relation:1377264"),
    ("Ashdod", "en", "osm:relation:1380013"),
    ("אשדוד", "he", "osm:relation:1380013"),
    ("Holon", "en", "osm:relation:1382460"),
    ("חולון", "he", "osm:relation:1382460"),
    ("Ramat Gan", "en", "osm:relation:1382493"),
    ("רמת גן", "he", "osm:relation:1382493"),
    ("Petah Tikva", "en", "osm:relation:1382816"),
    ("Petach Tikvah", "en", "osm:relation:1382816"),
    ("פתח תקווה", "he", "osm:relation:1382816"),
    ("Rishon LeZion", "en", "osm:relation:1382177"),
    ("ראשון לציון", "he", "osm:relation:1382177"),
    ("Netanya", "en", "osm:relation:1383391"),
    ("נתניה", "he", "osm:relation:1383391"),
    ("Herzliya", "en", "osm:relation:1382820"),
    ("הרצליה", "he", "osm:relation:1382820"),
    ("Ashkelon", "en", "osm:relation:1376782"),
    ("אשקלון", "he", "osm:relation:1376782"),
    ("Eilat", "en", "osm:relation:1377284"),
    ("אילת", "he", "osm:relation:1377284"),
    ("Kfar Saba", "en", "osm:relation:1383631"),
    ("Hadera", "en", "osm:relation:1392860"),
    ("Bat Yam", "en", "osm:relation:1382458"),
    ("Bnei Brak", "en", "osm:relation:1382817"),
    ("בני ברק", "he", "osm:relation:1382817"),
    ("Rehovot", "en", "osm:relation:1246791"),
    ("Nazareth", "en", "osm:relation:1386836"),
    ("Tiberias", "en", "osm:relation:1387273"),
    ("Acre", "en", "osm:relation:1387962"),
    ("עכו", "he", "osm:relation:1387962"),
    ("Modiin", "en", "osm:relation:1381425"),
    ("Lod", "en", "osm:relation:1381532"),
    ("Ramla", "en", "osm:relation:1381458"),
    ("Raanana", "en", "osm:relation:1383630"),
    ("Nahariya", "en", "osm:relation:1932164"),
    ("Afula", "en", "osm:relation:1380226"),
    ("Kiryat Shmona", "en", "osm:relation:1378947"),
    ("Beit Shemesh", "en", "osm:relation:1379449"),
    ("Givatayim", "en", "osm:relation:1382923"),
    ("Dimona", "en", "osm:relation:1376826"),
)


class _FeedOnly:
    """The same stop corpus without OSM localities: the feed-derived fallback alone."""

    def __init__(self, reference: ReferenceStore) -> None:
        self._reference = reference

    def stop_search_candidates(self) -> list[dict[str, Any]]:
        return self._reference.stop_search_candidates()


def locality_probe(
    reference: ReferenceStore, queries: tuple[tuple[str, str, str], ...] = LOCALITY_PROBE
) -> dict[str, Any]:
    """Before/after city-name queries judged by containment in the expected OSM locality."""
    localities = {item["locality_id"]: item for item in reference.search_localities()}
    if not localities:
        return {"available": False, "reason": "reference has no OSM localities"}
    rows = {row["stop_id"]: row for row in _search_index(reference).rows}
    feed_only = _FeedOnly(reference)

    def run(source: Any, query: str, language: str, expected: str) -> dict[str, Any]:
        items = search_stops(source, query, language=language, types=STOP_TYPES, limit=API_LIMIT)[
            "items"
        ]
        center = localities[expected]["center"]
        top = []
        for item in items[:5]:
            row = rows[item["id"]]
            coordinates = item["coordinates"]
            top.append(
                {
                    "displayName": item["displayName"],
                    "kind": item["kind"],
                    "inside": expected in row["locality_ids"],
                    "centerDistanceMeters": (
                        round(
                            _distance_m(
                                center[0],
                                center[1],
                                coordinates["latitude"],
                                coordinates["longitude"],
                            )
                        )
                        if coordinates
                        else None
                    ),
                    "routeCount": row["route_count"],
                }
            )
        return {
            "top1Inside": bool(top and top[0]["inside"]),
            "top5Inside": sum(entry["inside"] for entry in top),
            "top": top,
        }

    cases = []
    for query, language, expected in queries:
        if expected not in localities:
            raise ValueError(f"Probe names a locality the reference lacks: {expected}")
        cases.append(
            {
                "query": query,
                "language": language,
                "expectedLocality": expected,
                "expectedName": localities[expected]["name_en"] or localities[expected]["name"],
                "before": run(feed_only, query, language, expected),
                "after": run(reference, query, language, expected),
            }
        )

    def totals(side: str) -> dict[str, int]:
        return {
            "queries": len(cases),
            "top1Inside": sum(case[side]["top1Inside"] for case in cases),
            "top5AllInside": sum(
                case[side]["top5Inside"] == len(case[side]["top"]) > 0 for case in cases
            ),
        }

    return {
        "available": True,
        "note": (
            "before = same reference and code with only the feed-derived locality fallback; "
            "after = OSM localities. Judged by polygon containment of the stop in the expected "
            "OSM locality. A structural check, not an H4 verdict."
        ),
        "totals": {"before": totals("before"), "after": totals("after")},
        "top1Lost": [
            c["query"] for c in cases if c["before"]["top1Inside"] and not c["after"]["top1Inside"]
        ],
        "cases": cases,
    }


def stop_related(case: SearchCase) -> bool:
    return any(kind in STOP_TYPES for kind in case.api_types)


def saved_geocoder_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Recorded poi/address candidates in their recorded merged order."""
    return [
        {
            "kind": candidate["kind"],
            "displayName": candidate.get("displayName"),
            "coordinates": candidate.get("coordinates"),
            "addressLevel": candidate.get("addressLevel"),
            "precision": candidate.get("precision"),
            "languageUsed": candidate.get("languageUsed"),
            "locationRef": candidate.get("locationRef"),
        }
        for candidate in record["firstPass"].get("candidates", [])
        if candidate.get("kind") in GEOCODER_KINDS
    ]


def replay_case(
    reference: ReferenceStore, case: SearchCase, geocoder_items: list[dict[str, Any]]
) -> tuple[dict[str, Any], float]:
    """Run stop search and the production merge for one case; return score and ms."""
    requested = tuple(kind for kind in case.api_types if kind in STOP_TYPES)
    started = time.perf_counter()
    result = search_stops(
        reference,
        case.query,
        language=case.language,
        near=case.near,
        types=requested,
        limit=API_LIMIT,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    stop_items = result["items"]
    for item in stop_items:
        item["locationRef"] = {"kind": "stop", "stopId": item["id"]}
    payload = {
        "data": _merge_candidates(stop_items, geocoder_items, API_LIMIT),
        "matchedTypes": sorted(case.api_types),
        "unavailableTypes": [],
        "partial": False,
    }
    return score_response(case, 200, payload), elapsed_ms


def _compact(score: dict[str, Any]) -> dict[str, Any]:
    return {
        "top1Hit": bool(score["top1Hit"]),
        "top5Hit": bool(score["top5Hit"]),
        "top5HitRank": score["top5HitRank"],
        "top5": [
            {
                "kind": candidate["kind"],
                "displayName": candidate["displayName"],
                "distanceMeters": (
                    None
                    if candidate["distanceMeters"] is None
                    else round(candidate["distanceMeters"])
                ),
            }
            for candidate in score["candidates"][:5]
        ],
    }


def replay(
    reference: ReferenceStore, saved_run: dict[str, Any], cases: dict[str, SearchCase]
) -> dict[str, Any]:
    per_case: list[dict[str, Any]] = []
    timings: list[float] = []
    # Build the per-generation index outside the per-case timings.
    build_started = time.perf_counter()
    _search_index(reference)
    index_build_seconds = time.perf_counter() - build_started
    for record in saved_run["records"]:
        case = cases[record["case"]["id"]]
        if not stop_related(case):
            continue
        recorded = record["firstPass"]
        # Exact-stop cases are re-scored with the current evaluator so the frozen raw
        # GTFS ID is compared with mot:stop: references consistently on both sides.
        replayed, elapsed_ms = replay_case(reference, case, saved_geocoder_items(record))
        timings.append(elapsed_ms)
        per_case.append(
            {
                "caseId": case.id,
                "category": case.category,
                "language": case.language,
                "query": case.query,
                "apiTypes": list(case.api_types),
                "near": list(case.near) if case.near else None,
                "recorded": {
                    "top1Hit": bool(recorded["top1Hit"]),
                    "top5Hit": bool(recorded["top5Hit"]),
                    "top5HitRank": recorded["top5HitRank"],
                },
                "replayed": _compact(replayed),
                "stopSearchMs": round(elapsed_ms, 2),
            }
        )
    return {"cases": per_case, "timings": timings, "indexBuildSeconds": index_build_seconds}


def cell_counts(per_case: list[dict[str, Any]], side: str) -> dict[str, list[int]]:
    """[top1, top5, total] per corpus category for ``recorded`` or ``replayed``."""
    cells: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for item in per_case:
        cell = cells[item["category"]]
        cell[0] += item[side]["top1Hit"]
        cell[1] += item[side]["top5Hit"]
        cell[2] += 1
    return {name: cells[name] for name in sorted(cells)}


def diff_cases(before: dict[str, dict], after: dict[str, dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {
        "top1Gained": [],
        "top1Lost": [],
        "top5Gained": [],
        "top5Lost": [],
    }
    for case_id in sorted(after):
        if case_id not in before:
            continue
        for field, gained, lost in (
            ("top1Hit", "top1Gained", "top1Lost"),
            ("top5Hit", "top5Gained", "top5Lost"),
        ):
            if after[case_id][field] and not before[case_id][field]:
                out[gained].append(case_id)
            elif before[case_id][field] and not after[case_id][field]:
                out[lost].append(case_id)
    return out


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        return None


def build_result(
    outcome: dict[str, Any],
    *,
    saved_run: dict[str, Any],
    saved_run_path: Path,
    reference: ReferenceStore,
    compares: list[tuple[str, Path, dict[str, Any]]],
    label: str,
    root: Path,
) -> dict[str, Any]:
    per_case = outcome["cases"]
    timings = outcome["timings"]
    by_id = {item["caseId"]: item for item in per_case}
    recorded = {key: item["recorded"] for key, item in by_id.items()}
    replayed = {key: item["replayed"] for key, item in by_id.items()}
    result: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "recordedAt": datetime.now(UTC).isoformat(),
        "label": label,
        "scope": (
            "Offline replay of stop-related cases: in-process search_stops on a real "
            "reference file, saved geocoder candidates in recorded order, production "
            "merge, production evaluator scoring. Not a fresh API run, not H4."
        ),
        "limitations": [
            "Geocoder candidates are replayed from the saved merged top-10 only.",
            "Timings are host in-process search_stops durations, not API durations.",
            "Projected overall counts assume no non-stop case changes.",
        ],
        "provenance": {
            "gitHead": _git_head(root),
            "savedRunPath": saved_run_path.as_posix(),
            "savedRunSha256": _sha256(saved_run_path),
            "referencePath": reference.path.as_posix(),
            # ReferenceStore verified this content hash against the file on open.
            "referenceContentSha256": reference.metadata.content_sha256,
            "referenceComponentGenerationId": reference.component_generation_id,
            "pythonVersion": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "caseCount": len(per_case),
        "recordedByCell": cell_counts(per_case, "recorded"),
        "replayedByCell": cell_counts(per_case, "replayed"),
        "diffVsRecorded": diff_cases(recorded, replayed),
        "indexBuildSeconds": round(outcome["indexBuildSeconds"], 2),
        "stopSearchInProcessMs": {
            "samples": len(timings),
            "p50": round(statistics.median(timings), 2) if timings else None,
            "p95": (
                round(statistics.quantiles(timings, n=20)[18], 2) if len(timings) >= 20 else None
            ),
            "max": round(max(timings), 2) if timings else None,
        },
        "cases": per_case,
    }
    summary = saved_run.get("summary", {}).get("overall", {})
    if summary:
        recorded_top1 = sum(item["top1Hit"] for item in recorded.values())
        replayed_top1 = sum(item["top1Hit"] for item in replayed.values())
        recorded_top5 = sum(item["top5Hit"] for item in recorded.values())
        replayed_top5 = sum(item["top5Hit"] for item in replayed.values())
        result["projectedOverall"] = {
            "denominator": summary["denominator"],
            "recordedTop1": summary["top1"],
            "recordedTop5": summary["top5"],
            "projectedTop1": summary["top1"] - recorded_top1 + replayed_top1,
            "projectedTop5": summary["top5"] - recorded_top5 + replayed_top5,
            "note": "recorded overall with the stop-related subset swapped for replayed values",
        }
    if compares:
        result["compare"] = []
        for name, path, earlier in compares:
            previous = {item["caseId"]: item["replayed"] for item in earlier["cases"]}
            result["compare"].append(
                {
                    "name": name,
                    "path": path.as_posix(),
                    "sha256": _sha256(path),
                    "label": earlier.get("label"),
                    "previousByCell": earlier["replayedByCell"],
                    "diff": diff_cases(previous, replayed),
                }
            )
    return result


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--saved-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--compare",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="earlier replay result to diff against (repeatable)",
    )
    parser.add_argument("--label", default="replay")
    parser.add_argument(
        "--locality-probe",
        action="store_true",
        help="add the before/after city-name probe (needs a reference with OSM localities)",
    )
    parser.add_argument("--places-corpus", type=Path, default=root / "poc/corpora/places.json")
    parser.add_argument(
        "--venues-corpus", type=Path, default=root / "poc/corpora/places-venues.json"
    )
    parser.add_argument(
        "--supplemental-corpus",
        type=Path,
        default=root / "services/api/tests/fixtures/m4-api-search-language-variants-20260930.json",
    )
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Output path must be new; historical evidence is never overwritten")
    saved_run = json.loads(args.saved_run.read_text(encoding="utf-8"))
    compares = []
    for spec in args.compare:
        name, separator, raw_path = spec.partition("=")
        if not separator or not name or not raw_path:
            parser.error("--compare expects NAME=PATH")
        path = Path(raw_path)
        compares.append((name, path, json.loads(path.read_text(encoding="utf-8"))))
    cases_list, _, _ = load_cases(args.places_corpus, args.venues_corpus, args.supplemental_corpus)
    cases = {case.id: case for case in cases_list}
    reference = ReferenceStore(args.reference)
    outcome = replay(reference, saved_run, cases)
    result = build_result(
        outcome,
        saved_run=saved_run,
        saved_run_path=args.saved_run,
        reference=reference,
        compares=compares,
        label=args.label,
        root=root,
    )
    if args.locality_probe:
        result["localityProbe"] = locality_probe(reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"replayed {result['caseCount']} stop-related cases")
    for name, (top1, top5, total) in result["replayedByCell"].items():
        before = result["recordedByCell"][name]
        print(f"  {name}: top1 {before[0]}->{top1}, top5 {before[1]}->{top5}, of {total}")
    if "localityProbe" in result and result["localityProbe"]["available"]:
        totals = result["localityProbe"]["totals"]
        print(f"  locality probe: {totals['before']} -> {totals['after']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
