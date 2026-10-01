"""Bounded API-backed M4 search evaluation; does not edit historical PoC evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

EARTH_M = 6_371_008.8
VENUE_EARTH_M = 6_371_000.0
CORPUS_EARTH_RADII_M = {
    "venues-48": VENUE_EARTH_M,
    "venues-language-variants": VENUE_EARTH_M,
}
MAX_VARIANTS = 250
MAX_REQUESTS = 1000
REPEATS = 3
API_LIMIT = 10
EXACT_STOP_SOURCE_IDS = {
    "GTFS-TRANS-13583-en": "13583",
    "GTFS-TRANS-42658-en": "42658",
}
SUPPORTED_TYPES = {"stop", "station", "poi", "address"}
CATEGORY_TYPES = {
    "station": ("stop", "station"),
    "address": ("address",),
    "all": ("stop", "station", "poi", "address"),
}
DURATION_LOG = re.compile(
    r"request_id=(?P<id>[0-9a-fA-F]+) route=/v1/places "
    r"status=(?P<status>[0-9]{3}) duration_ms=(?P<duration>[0-9]+(?:\.[0-9]+)?)"
)


@dataclass(frozen=True)
class SearchCase:
    id: str
    source_case_id: str | None
    variant: str
    query: str
    language: str
    language_assignment: str
    query_script: str
    category: str
    api_types: tuple[str, ...]
    expected_place: str
    latitude: float
    longitude: float
    tolerance_m: float | None
    near: tuple[float, float] | None
    corpus: str
    expected_stop_id: str | None = None
    earth_radius_m: float = EARTH_M
    source_reference: dict[str, Any] | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def haversine_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    earth_m: float = EARTH_M,
) -> float:
    """Places-corpus Earth radius and unrounded haversine calculation."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * earth_m * math.asin(math.sqrt(a))


def api_types_for(category: str) -> tuple[str, ...]:
    if category.startswith("poi_") or category in {"neighborhood", "venue"}:
        return ("poi",)
    if category == "station":
        return CATEGORY_TYPES["station"]
    if category == "address":
        return CATEGORY_TYPES["address"]
    if category in {"misspelling", "translit", "near_dependent"}:
        return CATEGORY_TYPES["all"]
    if category == "translated_stop":
        return ("stop",)
    raise ValueError(f"Unsupported corpus category: {category}")


def _script(text: str) -> str:
    return "hebrew" if any("\u0590" <= char <= "\u05ff" for char in text) else "latin"


def _case(
    case_id: str,
    source_case_id: str | None,
    variant: str,
    query: str,
    language: str,
    language_assignment: str,
    query_script: str,
    category: str,
    api_types: tuple[str, ...],
    expected: dict[str, Any],
    near: dict[str, float] | None,
    corpus: str,
    expected_stop_id: str | None = None,
    source_reference: dict[str, Any] | None = None,
) -> SearchCase:
    if not isinstance(query, str) or not query.strip() or language not in {"he", "en"}:
        raise ValueError(f"Invalid query or language for {case_id}")
    if not api_types or any(kind not in SUPPORTED_TYPES for kind in api_types):
        raise ValueError(f"Invalid API type for {case_id}")
    lat, lon = float(expected["lat"]), float(expected["lon"])
    tolerance_raw = expected.get("tol_m")
    tolerance = float(tolerance_raw) if tolerance_raw is not None else None
    if not all(math.isfinite(number) for number in (lat, lon)):
        raise ValueError(f"Invalid target coordinate for {case_id}")
    if expected_stop_id is None:
        if tolerance is None or not math.isfinite(tolerance) or tolerance <= 0:
            raise ValueError(f"Invalid target tolerance for {case_id}")
    elif tolerance is not None or not expected_stop_id:
        raise ValueError(f"Stop-identity cases must not set a distance tolerance: {case_id}")
    near_pair = None if near is None else (float(near["lat"]), float(near["lon"]))
    if near_pair is not None and not all(math.isfinite(number) for number in near_pair):
        raise ValueError(f"Invalid near coordinate for {case_id}")
    return SearchCase(
        case_id,
        source_case_id,
        variant,
        query,
        language,
        language_assignment,
        query_script,
        category,
        tuple(api_types),
        str(expected.get("place", "")),
        lat,
        lon,
        tolerance,
        near_pair,
        corpus,
        expected_stop_id,
        CORPUS_EARTH_RADII_M.get(corpus, EARTH_M),
        source_reference,
    )


def load_cases(
    places_path: Path, venues_path: Path, supplemental_path: Path
) -> tuple[list[SearchCase], dict[str, str], dict[str, Any]]:
    places_bytes, venues_bytes, extra_bytes = (
        places_path.read_bytes(),
        venues_path.read_bytes(),
        supplemental_path.read_bytes(),
    )
    places = json.loads(places_bytes)
    venues = json.loads(venues_bytes)
    extra = json.loads(extra_bytes)
    actual = {
        "places": hashlib.sha256(places_bytes).hexdigest(),
        "venues": hashlib.sha256(venues_bytes).hexdigest(),
    }
    declared = extra.get("sourceCorpora", {})
    if any(declared.get(name, {}).get("sha256") != digest for name, digest in actual.items()):
        raise ValueError("Supplemental corpus source hash is stale")

    cases: list[SearchCase] = []
    for item in places["cases"]:
        category = item["category"]
        cases.append(
            _case(
                item["id"],
                item["id"],
                "primary",
                item["query"],
                item["lang"],
                "explicit original corpus language",
                _script(item["query"]),
                category,
                api_types_for(category),
                item["expect"],
                item.get("near"),
                "places-100",
            )
        )
    for item in venues["cases"]:
        script = "hebrew" if item.get("script") == "he" else "latin"
        assignment = (
            "native Hebrew query"
            if script == "hebrew"
            else "API default he; corpus has no explicit language"
        )
        cases.append(
            _case(
                item["id"],
                item["id"],
                "native",
                item["query"],
                "he",
                assignment,
                script,
                "venue",
                ("poi",),
                item["expect"],
                None,
                "venues-48",
                source_reference=item.get("osm"),
            )
        )
    for item in extra.get("venueVariants", []):
        cases.append(
            _case(
                item["id"],
                item["sourceCaseId"],
                item["sourceField"],
                item["query"],
                item["lang"],
                item["languageAssignment"],
                item["queryScript"],
                item["category"],
                api_types_for(item["category"]),
                item["expect"],
                None,
                "venues-language-variants",
                source_reference=item.get("osm"),
            )
        )
    for item in extra.get("acceptedGtfsStopVariants", []):
        cases.append(
            _case(
                item["id"],
                None,
                "accepted-gtfs-translation",
                item["query"],
                item["lang"],
                item["languageAssignment"],
                item["queryScript"],
                item["category"],
                tuple(item["apiTypes"]),
                item["expect"],
                None,
                "accepted-gtfs-translations",
                item["expectedStopId"],
            )
        )
    for item in extra.get("acceptedOsmAddressVariants", []):
        api_types = tuple(item.get("apiTypes", ["address"]))
        if item.get("category", "address") != "address" or api_types != ("address",):
            raise ValueError("Accepted OSM address variants must route only to address")
        cases.append(
            _case(
                item["id"],
                item.get("sourceCaseId"),
                item.get("variant", "accepted-osm-address"),
                item["query"],
                item["lang"],
                item["languageAssignment"],
                item["queryScript"],
                item.get("category", "address"),
                api_types,
                item["expect"],
                item.get("near"),
                "accepted-osm-addresses",
                source_reference=item.get("source"),
            )
        )
    if len(cases) > MAX_VARIANTS or len(cases) * (REPEATS + 1) > MAX_REQUESTS:
        raise ValueError("Corpus exceeds bounded request limits")
    hashes = {
        str(places_path): actual["places"],
        str(venues_path): actual["venues"],
        str(supplemental_path): hashlib.sha256(extra_bytes).hexdigest(),
    }
    return cases, hashes, extra


def request_params(case: SearchCase) -> list[tuple[str, str]]:
    params = [("q", case.query), ("lang", case.language)]
    params.extend(("type", kind) for kind in case.api_types)
    params.append(("limit", str(API_LIMIT)))
    if case.near is not None:
        params.append(("near", f"{case.near[0]},{case.near[1]}"))
    return params


def _coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
    coords = item.get("coordinates")
    if not isinstance(coords, dict):
        return None
    lat, lon = coords.get("latitude"), coords.get("longitude")
    if (
        isinstance(lat, bool)
        or isinstance(lon, bool)
        or not isinstance(lat, (int, float))
        or not isinstance(lon, (int, float))
        or not math.isfinite(float(lat))
        or not math.isfinite(float(lon))
    ):
        return None
    return float(lat), float(lon)


def score_response(
    case: SearchCase,
    status: int,
    payload: Any,
    expected_generation_id: str | None = None,
) -> dict[str, Any]:
    result = {
        "httpStatus": status,
        "responseValid": False,
        "generationCurrent": None if expected_generation_id is None else False,
        "categoriesComplete": False,
        "serviceSuccess": False,
        "matchedTypes": [],
        "unavailableTypes": [],
        "partial": None,
        "outcome": "http_error",
        "scoreEligible": False,
        "candidateCount": 0,
        "top1DistanceMeters": None,
        "top1Hit": False,
        "top5Hit": False,
        "top5HitRank": None,
        "top5DistinctRank": None,
        "scoreRule": None,
        "candidates": [],
    }
    if status != 200 or not isinstance(payload, dict):
        return result
    if expected_generation_id is not None:
        meta = payload.get("meta")
        result["generationCurrent"] = (
            isinstance(meta, dict) and meta.get("generationId") == expected_generation_id
        )
    items, matched, unavailable, partial = (
        payload.get("data"),
        payload.get("matchedTypes"),
        payload.get("unavailableTypes"),
        payload.get("partial"),
    )
    if (
        not isinstance(items, list)
        or len(items) > API_LIMIT
        or any(not isinstance(item, dict) for item in items)
        or not isinstance(matched, list)
        or any(not isinstance(kind, str) or kind not in SUPPORTED_TYPES for kind in matched)
        or not isinstance(unavailable, list)
        or any(not isinstance(kind, str) or kind not in SUPPORTED_TYPES for kind in unavailable)
        or type(partial) is not bool
    ):
        result["outcome"] = "invalid_response"
        return result
    matched_set, unavailable_set = set(matched), set(unavailable)
    if (
        len(matched_set) != len(matched)
        or len(unavailable_set) != len(unavailable)
        or matched_set & unavailable_set
        or matched_set | unavailable_set != set(case.api_types)
        or partial != bool(unavailable_set)
    ):
        result["outcome"] = "invalid_response"
        return result
    if any(
        not isinstance(item.get("kind"), str) or item["kind"] not in matched_set for item in items
    ):
        result["outcome"] = "invalid_response"
        return result
    categories_complete = matched_set == set(case.api_types) and not unavailable_set and not partial
    result.update(
        responseValid=True,
        categoriesComplete=categories_complete,
        serviceSuccess=categories_complete and result["generationCurrent"] is True,
        matchedTypes=matched,
        unavailableTypes=unavailable,
        partial=partial,
        candidateCount=len(items),
    )
    if result["generationCurrent"] is False:
        result["outcome"] = "generation_mismatch"
        return result
    result["scoreEligible"] = bool(matched_set)
    result["outcome"] = (
        "unavailable"
        if not matched_set
        else "partial"
        if unavailable_set
        else "valid_empty"
        if not items
        else "success"
    )
    seen_candidates: dict[str, int] = {}
    distinct_rank = 0
    for rank, item in enumerate(items, 1):
        point = _coordinates(item)
        location_ref = item.get("locationRef")
        if isinstance(location_ref, dict) and location_ref:
            ref_kind = location_ref.get("kind")
            ref_id = location_ref.get("stopId", location_ref.get("placeRef"))
            identity_value = [ref_kind, ref_id] if ref_kind and ref_id else location_ref
        else:
            identity_value = [item.get("kind"), point, item.get("displayName", item.get("name"))]
        identity = json.dumps(
            identity_value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        duplicate_of = seen_candidates.get(identity)
        is_distinct = duplicate_of is None
        if is_distinct:
            distinct_rank += 1
            seen_candidates[identity] = distinct_rank
        candidate = {
            "rank": rank,
            "distinctRank": distinct_rank if is_distinct else None,
            "duplicateOfDistinctRank": duplicate_of,
            "kind": item.get("kind"),
            "displayName": item.get("displayName", item.get("name")),
            "coordinates": item.get("coordinates"),
            "addressLevel": item.get("addressLevel"),
            "precision": item.get("precision"),
            "languageUsed": item.get("languageUsed"),
            "locationRef": item.get("locationRef"),
            "distanceMeters": None,
        }
        exact_stop_match = (
            case.expected_stop_id is not None
            and isinstance(location_ref, dict)
            and location_ref.get("kind") == "stop"
            # Frozen corpus IDs are raw GTFS source IDs; API refs are mot:stop: qualified.
            and location_ref.get("stopId") == _canonical_expected_stop_ref(case.expected_stop_id)
        )
        if case.expected_stop_id is not None and exact_stop_match:
            if rank == 1:
                result["top1Hit"] = True
            if is_distinct and rank <= 5 and result["top5HitRank"] is None:
                result["top5Hit"] = True
                result["top5HitRank"] = rank
                result["top5DistinctRank"] = distinct_rank
        if point is not None:
            distance = haversine_m(
                point[0], point[1], case.latitude, case.longitude, case.earth_radius_m
            )
            candidate["distanceMeters"] = distance
            if rank == 1:
                result["top1DistanceMeters"] = distance
                if case.expected_stop_id is None:
                    result["top1Hit"] = distance <= case.tolerance_m
            if (
                case.expected_stop_id is None
                and is_distinct
                and rank <= 5
                and result["top5HitRank"] is None
                and distance <= case.tolerance_m
            ):
                result["top5Hit"] = True
                result["top5HitRank"] = rank
                result["top5DistinctRank"] = distinct_rank
        result["candidates"].append(candidate)
    result["scoreRule"] = (
        "exact_stop_reference"
        if case.expected_stop_id is not None
        else "haversine_within_original_tolerance"
    )
    return result


def _capture(
    case: SearchCase,
    send: Callable,
    pass_name: str,
    order: int,
    expected_generation_id: str | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = send(request_params(case))
        rtt = (time.perf_counter() - started) * 1000
        try:
            payload = response.json()
        except ValueError, TypeError:
            payload = None
        return {
            **score_response(case, response.status_code, payload, expected_generation_id),
            "requestId": response.headers.get("X-Request-ID"),
            "clientRoundTripMs": rtt,
            "passName": pass_name,
            "requestOrder": order,
            "processDurationMs": None,
            "logCorrelationStatus": "pending",
        }
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        return {
            **score_response(case, 0, None),
            "requestId": None,
            "clientRoundTripMs": (time.perf_counter() - started) * 1000,
            "passName": pass_name,
            "requestOrder": order,
            "processDurationMs": None,
            "logCorrelationStatus": "request_failed",
            "requestErrorType": type(exc).__name__,
        }


def _duration_logs(text: str | None) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in (text or "").splitlines():
        match = DURATION_LOG.search(line)
        if match:
            result[match.group("id")].append(
                {"status": int(match.group("status")), "durationMs": float(match.group("duration"))}
            )
    return result


def correlate_process_timings(records: list[dict], log_text: str | None) -> dict[str, Any]:
    logs = _duration_logs(log_text)
    response_ids = Counter(
        request_id for record in records if (request_id := record.get("requestId"))
    )
    matched = 0
    for record in records:
        record["processDurationMs"] = None
        request_id = record.get("requestId")
        candidates = logs.get(request_id, []) if request_id else []
        if not request_id:
            status = "missing_request_id"
        elif response_ids[request_id] > 1:
            status = "ambiguous_duplicate_response_ids"
        elif not candidates:
            status = "missing_log_entry"
        elif len(candidates) > 1:
            status = "ambiguous_duplicate_log_entries"
        elif candidates[0]["status"] != record["httpStatus"]:
            status = "log_status_mismatch"
        else:
            status = "matched"
            record["processDurationMs"] = candidates[0]["durationMs"]
            matched += 1
        record["logCorrelationStatus"] = status
    return {
        "verified": bool(records) and matched == len(records),
        "requestCount": len(records),
        "matchedCount": matched,
        "unmatchedCount": len(records) - matched,
    }


def finalize_process_timings(
    result: dict[str, Any],
    log_text: str,
    *,
    log_sha256: str,
    source_result_sha256: str,
) -> dict[str, Any]:
    """Return a derived result with process timings correlated from a later log capture."""
    finalized = copy.deepcopy(result)
    records = finalized.get("records")
    if not isinstance(records, list):
        raise ValueError("Saved evaluation has no records list")
    requests = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("firstPass"), dict):
            raise ValueError("Saved evaluation contains a malformed record")
        requests.append(record["firstPass"])
        warm = record.get("warmRepeats")
        if not isinstance(warm, list) or any(not isinstance(item, dict) for item in warm):
            raise ValueError("Saved evaluation contains malformed warm repeats")
        requests.extend(warm)
    correlation = correlate_process_timings(requests, log_text)
    finalized.setdefault("timing", {})["correlation"] = correlation
    finalized["timing"]["allRequests"] = _latency_summary(requests, len(requests))
    finalized["timing"]["firstPass"] = {
        "apiProcess": _metric(
            [record["firstPass"] for record in records],
            "processDurationMs",
        ),
        "clientRoundTrip": _metric(
            [record["firstPass"] for record in records], "clientRoundTripMs"
        ),
        "processVerified": bool(records)
        and all(record["firstPass"]["logCorrelationStatus"] == "matched" for record in records),
        "latencyAcceptance": _latency_summary(
            [record["firstPass"] for record in records], len(records)
        ),
    }
    finalized["timing"]["warm"] = _warm_groups(records)
    finalized["timing"]["source"] = "sanitized API process log correlated by X-Request-ID"
    finalized["provenance"] = finalized.get("provenance") or {}
    finalized["provenance"]["containerLogSha256"] = log_sha256
    finalized["timingFinalization"] = {
        "sourceResultSha256": source_result_sha256,
        "containerLogSha256": log_sha256,
        "correlatedAt": datetime.now(UTC).isoformat(),
    }
    return finalized


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1))
    return ordered[index]


def _metric(values: list[dict], field: str, require_all: bool = False) -> dict[str, float | None]:
    numbers = [float(item[field]) for item in values if item.get(field) is not None]
    if require_all and len(numbers) != len(values):
        numbers = []
    return {
        "p50Ms": _percentile(numbers, 50),
        "p95Ms": _percentile(numbers, 95),
        "maxMs": max(numbers) if numbers else None,
    }


def _latency_summary(requests: list[dict], required_count: int) -> dict[str, Any]:
    correlated = [item for item in requests if item.get("processDurationMs") is not None]
    service_successes = [item for item in requests if item.get("serviceSuccess") is True]
    service_timings = [
        item for item in service_successes if item.get("processDurationMs") is not None
    ]
    blockers = []
    if not required_count:
        blockers.append("no_required_requests")
    if len(requests) != required_count:
        blockers.append("request_count_mismatch")
    if sum(item.get("responseValid") is True for item in requests) != required_count:
        blockers.append("invalid_or_missing_response")
    if sum(item.get("httpStatus") == 200 for item in requests) != required_count:
        blockers.append("unsuccessful_http_response")
    if sum(item.get("generationCurrent") is True for item in requests) != required_count:
        blockers.append("stale_or_unverified_generation")
    if sum(item.get("categoriesComplete") is True for item in requests) != required_count:
        blockers.append("incomplete_category_execution")
    if len(service_successes) != required_count:
        blockers.append("service_not_successful")
    if sum(item.get("logCorrelationStatus") == "matched" for item in requests) != required_count:
        blockers.append("missing_or_ambiguous_log_correlation")

    def sampled(items: list[dict], field: str) -> dict[str, Any]:
        measured = [item for item in items if item.get(field) is not None]
        return {**_metric(measured, field), "sampleCount": len(measured)}

    return {
        "requiredRequestCount": required_count,
        "requestCount": len(requests),
        "validResponseCount": sum(item.get("responseValid") is True for item in requests),
        "successfulHttpResponseCount": sum(item.get("httpStatus") == 200 for item in requests),
        "currentGenerationCount": sum(item.get("generationCurrent") is True for item in requests),
        "fullRequestedCategoriesCount": sum(
            item.get("categoriesComplete") is True for item in requests
        ),
        "successfulServiceCount": len(service_successes),
        "logCorrelatedCount": len(correlated),
        "allRequestApiProcess": sampled(requests, "processDurationMs"),
        "successfulServiceApiProcess": sampled(service_timings, "processDurationMs"),
        "allRequestClientRoundTrip": sampled(requests, "clientRoundTripMs"),
        "latencyAcceptanceEligible": not blockers,
        "latencyAcceptanceBlockers": blockers,
    }


def _warm_groups(records: list[dict]) -> dict[str, Any]:
    categories: dict[str, list[dict]] = defaultdict(list)
    languages: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        for request in record["warmRepeats"]:
            categories[record["case"]["category"]].append(request)
            languages[record["case"]["language"]].append(request)

    def groups(source):
        return {
            name: {
                "requests": len(items),
                "apiProcess": _metric(items, "processDurationMs"),
                "clientRoundTrip": _metric(items, "clientRoundTripMs"),
                "processVerified": all(item["logCorrelationStatus"] == "matched" for item in items),
                "latencyAcceptance": _latency_summary(items, len(items)),
            }
            for name, items in sorted(source.items())
        }

    return {"byCategory": groups(categories), "byLanguage": groups(languages)}


def summarize(records: list[dict]) -> dict[str, Any]:
    total = len(records)

    def bucket(key):
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in records:
            grouped[row["case"][key]].append(row)
        return {
            name: {
                "top1": sum(bool(row["firstPass"]["top1Hit"]) for row in rows),
                "top5": sum(bool(row["firstPass"]["top5Hit"]) for row in rows),
                "total": len(rows),
                "unavailable": sum(
                    row["firstPass"]["outcome"]
                    in {"unavailable", "http_error", "invalid_response", "generation_mismatch"}
                    for row in rows
                ),
            }
            for name, rows in sorted(grouped.items())
        }

    top1 = sum(bool(row["firstPass"]["top1Hit"]) for row in records)
    top5 = sum(bool(row["firstPass"]["top5Hit"]) for row in records)
    return {
        "overall": {
            "top1": top1,
            "top5": top5,
            "denominator": total,
            "top1Rate": top1 / total if total else None,
            "top5Rate": top5 / total if total else None,
        },
        "byCategory": bucket("category"),
        "byLanguage": bucket("language"),
        "byCorpus": bucket("corpus"),
        "firstPassOutcomes": dict(
            sorted(Counter(r["firstPass"]["outcome"] for r in records).items())
        ),
    }


def summarize_saved_osm_address_near_groups(records: list[dict]) -> dict[str, Any]:
    """Describe saved OSM-address scores by recorded near-field presence only."""
    address_records = [
        row for row in records if row.get("case", {}).get("corpus") == "accepted-osm-addresses"
    ]
    groups: dict[str, list[dict]] = {"near_supplied": [], "near_not_supplied": [], "unknown": []}
    for row in address_records:
        group = "near_supplied" if row["case"].get("near") is not None else "near_not_supplied"
        groups[group].append(row)
    return {
        "basis": "Recorded case.near presence only; no inference from query wording.",
        "groups": {
            name: {
                "cases": len(rows),
                "caseIds": [row["case"]["id"] for row in rows],
                "top1": sum(bool(row["firstPass"].get("top1Hit")) for row in rows),
                "top5": sum(bool(row["firstPass"].get("top5Hit")) for row in rows),
            }
            for name, rows in groups.items()
            if rows or name != "unknown"
        },
    }


def _canonical_expected_stop_ref(value: str) -> str:
    """Qualify a preserved numeric GTFS source ID without normalizing its digits."""
    prefix = "mot:stop:"
    source_id = value[len(prefix) :] if value.startswith(prefix) else value
    if not source_id or not source_id.isascii() or not source_id.isdigit():
        raise ValueError("Expected exact-stop ID must be a numeric source ID or mot:stop reference")
    return prefix + source_id


def correct_saved_exact_stop_scores(
    saved_result: dict[str, Any], *, source_result_sha256: str
) -> dict[str, Any]:
    """Correct only the two whitelisted GTFS stop-reference namespaces in saved results."""
    result = copy.deepcopy(saved_result)
    records = result.get("records")
    if not isinstance(records, list):
        raise ValueError("Saved result has no records array")
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        case_data = row.get("case") if isinstance(row, dict) else None
        if isinstance(case_data, dict) and case_data.get("id") in EXACT_STOP_SOURCE_IDS:
            by_id[case_data["id"]].append(row)
    if set(by_id) != set(EXACT_STOP_SOURCE_IDS) or any(len(rows) != 1 for rows in by_id.values()):
        raise ValueError("Saved result must contain exactly one record for each frozen GTFS case")

    corrections = {}
    for case_id, expected_source_id in EXACT_STOP_SOURCE_IDS.items():
        row = by_id[case_id][0]
        case_data = row["case"]
        expected = case_data.get("expected")
        if not isinstance(expected, dict) or expected.get("expectedStopId") != expected_source_id:
            raise ValueError(f"Saved source ID mismatch for {case_id}")
        expected_ref = _canonical_expected_stop_ref(expected_source_id)
        corrections[case_id] = {
            "sourceStopId": expected_source_id,
            "expectedPublicReference": expected_ref,
        }
        passes = [row.get("firstPass"), *row.get("warmRepeats", [])]
        if any(not isinstance(item, dict) for item in passes):
            raise ValueError(f"Saved request passes are malformed for {case_id}")
        for scored in passes:
            candidates = scored.get("candidates")
            if not isinstance(candidates, list):
                raise ValueError(f"Saved candidate list is malformed for {case_id}")
            matches = []
            for candidate in candidates:
                ref = candidate.get("locationRef") if isinstance(candidate, dict) else None
                if (
                    isinstance(ref, dict)
                    and ref.get("kind") == "stop"
                    and ref.get("stopId") == expected_ref
                ):
                    rank = candidate.get("rank")
                    distinct_rank = candidate.get("distinctRank")
                    if type(rank) is not int or type(distinct_rank) is not int:
                        raise ValueError(
                            f"Saved matching candidate rank is malformed for {case_id}"
                        )
                    matches.append((rank, distinct_rank))
            top1 = any(rank == 1 for rank, _ in matches)
            top5 = next(((rank, distinct) for rank, distinct in matches if rank <= 5), None)
            previous = {
                key: scored.get(key)
                for key in ("top1Hit", "top5Hit", "top5HitRank", "top5DistinctRank", "scoreRule")
            }
            scored.update(
                top1Hit=top1,
                top5Hit=top5 is not None,
                top5HitRank=top5[0] if top5 else None,
                top5DistinctRank=top5[1] if top5 else None,
                scoreRule="exact_stop_public_reference",
                scoreCorrection={"previousScore": previous},
            )

    result["summary"] = summarize(records)
    result["summary"]["acceptedOsmAddressNearBias"] = summarize_saved_osm_address_near_groups(
        records
    )
    result["exactStopScoringCorrection"] = {
        "scope": "Two frozen GTFS exact-stop cases only; candidates replayed from saved responses.",
        "sourceResultSha256": source_result_sha256,
        "helperSha256": sha256_file(Path(__file__).resolve()),
        "correctedAt": datetime.now(UTC).isoformat(),
        "originalSummary": copy.deepcopy(saved_result.get("summary")),
        "cases": corrections,
    }
    return result


def run_evaluation(
    cases: list[SearchCase],
    send: Callable[[list[tuple[str, str]]], Any],
    *,
    log_text: str | None,
    seed: int = 20260930,
    captured_at: str | None = None,
    expected_generation_id: str | None = None,
) -> dict[str, Any]:
    if len(cases) > MAX_VARIANTS or len(cases) * (REPEATS + 1) > MAX_REQUESTS:
        raise ValueError("Evaluation exceeds bounded request limit")
    records = []
    for case in cases:
        records.append(
            {
                "case": {
                    "id": case.id,
                    "sourceCaseId": case.source_case_id,
                    "variant": case.variant,
                    "query": case.query,
                    "language": case.language,
                    "languageAssignment": case.language_assignment,
                    "queryScript": case.query_script,
                    "category": case.category,
                    "apiTypes": list(case.api_types),
                    "expected": {
                        "place": case.expected_place,
                        "latitude": case.latitude,
                        "longitude": case.longitude,
                        "toleranceMeters": case.tolerance_m,
                        "expectedStopId": case.expected_stop_id,
                    },
                    "near": (
                        {"latitude": case.near[0], "longitude": case.near[1]} if case.near else None
                    ),
                    "corpus": case.corpus,
                    "scoringEarthRadiusMeters": case.earth_radius_m,
                    "sourceReference": case.source_reference,
                },
                "firstPass": None,
                "warmRepeats": [],
            }
        )
    all_requests = []
    for index, record in enumerate(records):
        request = _capture(cases[index], send, "first_pass", index + 1, expected_generation_id)
        record["firstPass"] = request
        all_requests.append(request)
    warm_order = list(range(len(cases)))
    random.Random(seed).shuffle(warm_order)
    for repetition in range(REPEATS):
        for order, index in enumerate(warm_order, 1):
            request = _capture(
                cases[index], send, f"warm_{repetition + 1}", order, expected_generation_id
            )
            records[index]["warmRepeats"].append(request)
            all_requests.append(request)
    correlation = correlate_process_timings(all_requests, log_text)
    return {
        "schemaVersion": 1,
        "capturedAt": captured_at or datetime.now(UTC).isoformat(),
        "scope": "API first pass; three fixed-seed warm repetitions; H4 verdict remains open",
        "parameters": {
            "endpoint": "/v1/places",
            "limit": API_LIMIT,
            "firstPassState": "not claimed cold; cache state unverified",
            "warmRepeatCount": REPEATS,
            "warmOrderSeed": seed,
            "warmOrder": warm_order,
            "retryCount": 0,
            "requestCount": len(all_requests),
            "requestCap": MAX_REQUESTS,
            "maxVariantCount": MAX_VARIANTS,
        },
        "summary": summarize(records),
        "timing": {
            "source": "sanitized API process log correlated by X-Request-ID",
            "correlation": correlation,
            "firstPass": {
                "apiProcess": _metric(
                    [record["firstPass"] for record in records],
                    "processDurationMs",
                ),
                "clientRoundTrip": _metric(
                    [record["firstPass"] for record in records], "clientRoundTripMs"
                ),
                "processVerified": bool(records)
                and all(
                    record["firstPass"]["logCorrelationStatus"] == "matched" for record in records
                ),
                "latencyAcceptance": _latency_summary(
                    [record["firstPass"] for record in records], len(records)
                ),
            },
            "allRequests": _latency_summary(all_requests, len(all_requests)),
            "warm": _warm_groups(records),
            "note": "Client round-trip and API process durations are reported separately.",
        },
        "records": records,
    }


def _load_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def build_provenance_snapshot(
    *,
    api_url: str,
    manifest_path: Path,
    source_hashes_path: Path | None,
    runtime_evidence_path: Path | None,
    container_log_path: Path | None,
    corpus_hashes: dict[str, str],
    supplemental: dict[str, Any],
) -> dict[str, Any]:
    manifest = _load_object(manifest_path)
    return {
        "apiBaseUrl": api_url.rstrip("/"),
        "generationId": manifest.get("generationId"),
        "generationManifestSha256": sha256_file(manifest_path),
        "generationInputs": {
            name: record.get("sha256")
            for name, record in manifest.get("inputs", {}).items()
            if isinstance(record, dict)
        },
        "engineDigest": manifest.get("engineDigest"),
        "artifacts": {
            name: record.get("sha256")
            for name, record in manifest.get("artifacts", {}).items()
            if name in {"motis", "config", "reference"}
        },
        "corporaSha256": corpus_hashes,
        "supplementalGtfsProvenance": supplemental.get("acceptedGtfsProvenance"),
        "supplementalOsmAddressProvenance": supplemental.get("acceptedOsmAddressProvenance"),
        "apiSourceHashes": _load_object(source_hashes_path),
        "apiSourceHashFileSha256": (
            sha256_file(source_hashes_path) if source_hashes_path is not None else None
        ),
        "runtimeEvidence": _load_object(runtime_evidence_path),
        "runtimeEvidenceSha256": (
            sha256_file(runtime_evidence_path) if runtime_evidence_path is not None else None
        ),
        "containerLogSha256": (
            sha256_file(container_log_path) if container_log_path is not None else None
        ),
        "evaluatorSha256": sha256_file(Path(__file__).resolve()),
        "scoringReferenceSha256": sha256_file(
            Path(__file__).resolve().parents[3] / "poc/geocoding/score.py"
        ),
        "venueScoringReferenceSha256": sha256_file(
            Path(__file__).resolve().parents[3] / "poc/geocoding/venues.py"
        ),
    }


def add_provenance(
    result: dict[str, Any],
    *,
    api_url: str,
    manifest_path: Path,
    source_hashes_path: Path | None,
    runtime_evidence_path: Path | None,
    container_log_path: Path | None,
    corpus_hashes: dict[str, str],
    supplemental: dict[str, Any],
) -> None:
    result["provenance"] = build_provenance_snapshot(
        api_url=api_url,
        manifest_path=manifest_path,
        source_hashes_path=source_hashes_path,
        runtime_evidence_path=runtime_evidence_path,
        container_log_path=container_log_path,
        corpus_hashes=corpus_hashes,
        supplemental=supplemental,
    )


def run_and_write_evaluation(
    *,
    cases: list[dict[str, Any]],
    send: Callable[[dict[str, Any]], Any],
    seed: int,
    expected_generation_id: str,
    api_url: str,
    manifest_path: Path,
    source_hashes_path: Path | None,
    runtime_evidence_path: Path | None,
    corpus_hashes: dict[str, str],
    supplemental: dict[str, Any],
    output_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    provenance = build_provenance_snapshot(
        api_url=api_url,
        manifest_path=manifest_path,
        source_hashes_path=source_hashes_path,
        runtime_evidence_path=runtime_evidence_path,
        container_log_path=None,
        corpus_hashes=corpus_hashes,
        supplemental=supplemental,
    )
    result = run_evaluation(
        cases,
        send,
        log_text=None,
        seed=seed,
        expected_generation_id=expected_generation_id,
    )
    result["provenance"] = provenance
    write_exclusive(output_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    write_exclusive(review_path, review_markdown(result))
    return result


def review_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]["overall"]

    def cell(value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).replace("|", "\\|").split())

    lines = [
        "# API-backed M4 search review",
        "",
        f"- Captured: {result['capturedAt']}",
        f"- Generation: {result.get('provenance', {}).get('generationId')}",
        f"- First-pass top-1: {summary['top1']}/{summary['denominator']}",
        f"- First-pass top-5: {summary['top5']}/{summary['denominator']}",
        "- Human H4 verdict: ",
        "",
        "Mechanical outcomes only; no human verdict or failure cause is assigned.",
        "",
        "| Case | Variant | Query | Expected place | Lang | Script | Category | Outcome | "
        "Score rule | Top 1 mechanical | Top 5 mechanical | Top result | Kind | Address level | "
        "Precision | "
        "Result language | Distance m | H4 usability | H4 verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|---|---|---|",
    ]
    for row in result["records"]:
        case, scored = row["case"], row["firstPass"]
        top1 = "hit" if scored["top1Hit"] else "miss"
        top5 = "hit" if scored["top5Hit"] else "miss"
        candidate = scored["candidates"][0] if scored["candidates"] else {}
        expected = case["expected"]
        values = [
            case["id"],
            case["variant"],
            case["query"],
            expected["place"],
            case["language"],
            case["queryScript"],
            case["category"],
            scored["outcome"],
            scored["scoreRule"],
            top1,
            top5,
            candidate.get("displayName"),
            candidate.get("kind"),
            candidate.get("addressLevel"),
            candidate.get("precision"),
            candidate.get("languageUsed"),
            candidate.get("distanceMeters"),
            "",
            "",
        ]
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    correction = result.get("exactStopScoringCorrection")
    if correction:
        lines.extend(
            [
                "",
                "## Offline exact-stop scoring correction",
                "",
                f"- Source result SHA-256: `{correction['sourceResultSha256']}`",
                f"- Correction helper SHA-256: `{correction['helperSha256']}`",
                "- Scope: two frozen GTFS stop cases; original source IDs and saved candidates "
                "retained.",
            ]
        )
    near_bias = result.get("summary", {}).get("acceptedOsmAddressNearBias")
    if near_bias:
        lines.extend(
            [
                "",
                "## Accepted OSM address results by supplied near coordinate",
                "",
                near_bias["basis"],
                "",
                "| Recorded near state | Cases | Top 1 mechanical | Top 5 mechanical | Case IDs |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for name, group in near_bias["groups"].items():
            lines.append(
                "| "
                + " | ".join(
                    cell(value)
                    for value in (
                        name.replace("_", " "),
                        group["cases"],
                        group["top1"],
                        group["top5"],
                        ", ".join(group["caseIds"]),
                    )
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def write_exclusive(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
        output.write(text)


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--review-output", type=Path)
    parser.add_argument("--finalize-input", type=Path)
    parser.add_argument("--correct-exact-stops-input", type=Path)
    parser.add_argument("--places-corpus", type=Path, default=root / "poc/corpora/places.json")
    parser.add_argument(
        "--venues-corpus", type=Path, default=root / "poc/corpora/places-venues.json"
    )
    parser.add_argument(
        "--supplemental-corpus",
        type=Path,
        default=root / "services/api/tests/fixtures/m4-api-search-language-variants-20260930.json",
    )
    parser.add_argument("--source-hashes", type=Path)
    parser.add_argument("--runtime-evidence", type=Path)
    parser.add_argument("--container-log-file", type=Path)
    parser.add_argument("--seed", type=int, default=20260930)
    args = parser.parse_args()
    if args.correct_exact_stops_input is not None:
        if args.output is None or args.review_output is None:
            parser.error("--correct-exact-stops-input requires --output and --review-output")
        if args.finalize_input is not None or args.container_log_file is not None:
            parser.error(
                "Exact-stop correction accepts saved results only, without log finalization"
            )
        if (
            args.correct_exact_stops_input.resolve()
            in {args.output.resolve(), args.review_output.resolve()}
            or args.output.resolve() == args.review_output.resolve()
        ):
            parser.error("Correction input and the two output paths must be distinct")
        if args.output.exists() or args.review_output.exists():
            parser.error(
                "Corrected output paths must be new; historical evidence is never overwritten"
            )
        try:
            source_bytes = args.correct_exact_stops_input.read_bytes()
            source_result = json.loads(source_bytes)
            if not isinstance(source_result, dict):
                raise ValueError("Saved evaluation must be a JSON object")
            result = correct_saved_exact_stop_scores(
                source_result,
                source_result_sha256=hashlib.sha256(source_bytes).hexdigest(),
            )
            write_exclusive(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            write_exclusive(args.review_output, review_markdown(result))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"exact-stop correction failed: {type(exc).__name__}", file=sys.stderr)
            return 2
        print("corrected two frozen GTFS exact-stop scores from saved candidates")
        return 0
    if args.finalize_input is not None and args.correct_exact_stops_input is not None:
        parser.error("Choose one offline input mode")
    if args.finalize_input is not None:
        if args.output is None or args.container_log_file is None:
            parser.error("--finalize-input requires --output and --container-log-file")
        if args.review_output is not None:
            parser.error("--review-output applies only to a new network evaluation")
        if args.finalize_input.resolve() == args.output.resolve():
            parser.error("Finalized output must be a new file, separate from the raw result")
        if args.output.exists():
            parser.error(
                "Finalized output path must be new; historical evidence is never overwritten"
            )
        try:
            source_bytes = args.finalize_input.read_bytes()
            source_result = json.loads(source_bytes)
            if not isinstance(source_result, dict):
                raise ValueError("Saved evaluation must be a JSON object")
            log_bytes = args.container_log_file.read_bytes()
            result = finalize_process_timings(
                source_result,
                log_bytes.decode("utf-8", errors="replace"),
                log_sha256=hashlib.sha256(log_bytes).hexdigest(),
                source_result_sha256=hashlib.sha256(source_bytes).hexdigest(),
            )
            write_exclusive(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"timing finalization failed: {type(exc).__name__}", file=sys.stderr)
            return 2
        print(f"finalized timing for {result['parameters']['requestCount']} saved requests")
        return 0

    if (
        not args.api_url
        or args.manifest is None
        or args.output is None
        or args.review_output is None
    ):
        parser.error("New evaluation requires --api-url, --manifest, --output, and --review-output")
    if args.container_log_file is not None:
        parser.error("Use --container-log-file only with --finalize-input after capturing the log")
    if args.output.resolve() == args.review_output.resolve():
        parser.error("JSON result and review sheet need separate output paths")
    if args.output.exists() or args.review_output.exists():
        parser.error("Output paths must be new; historical evidence is never overwritten")
    try:
        manifest = _load_object(args.manifest)
        generation_id = manifest.get("generationId")
        if not isinstance(generation_id, str) or not generation_id:
            raise ValueError("Generation manifest has no generationId")
        cases, hashes, supplemental = load_cases(
            args.places_corpus, args.venues_corpus, args.supplemental_corpus
        )
        with httpx.Client(
            base_url=args.api_url.rstrip("/"),
            timeout=httpx.Timeout(3.0, connect=1.0),
            trust_env=False,
            follow_redirects=False,
        ) as client:
            result = run_and_write_evaluation(
                cases=cases,
                send=lambda params: client.get("/v1/places", params=params),
                seed=args.seed,
                expected_generation_id=generation_id,
                api_url=args.api_url,
                manifest_path=args.manifest,
                source_hashes_path=args.source_hashes,
                runtime_evidence_path=args.runtime_evidence,
                corpus_hashes=hashes,
                supplemental=supplemental,
                output_path=args.output,
                review_path=args.review_output,
            )
    except (OSError, ValueError, json.JSONDecodeError, httpx.HTTPError) as exc:
        print(f"evaluation failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(f"captured {len(cases)} variants / {result['parameters']['requestCount']} requests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
