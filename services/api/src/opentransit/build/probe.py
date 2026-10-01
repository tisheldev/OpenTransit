"""Structural candidate-generation probes; results never imply human approval."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

from opentransit.build.generations import verify_artifacts
from opentransit.core.generation import Generation
from opentransit.reference import ReferenceStore

COUNT_DROP_LIMIT = 0.20
MAX_JOURNEYS = 10
JOURNEY_TIMEOUT_SECONDS = 1.5
_REQUIRED_PARAMS = {"fromPlace", "toPlace", "time"}


def _loopback_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or not parsed.hostname or parsed.path not in {"", "/"}:
        raise ValueError("Probe engine URL must be an HTTP loopback origin")
    try:
        loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        loopback = parsed.hostname.lower() == "localhost"
    if not loopback or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Probe engine URL must be an HTTP loopback origin")
    return value.rstrip("/")


def _journeys(source: Path | list[dict]) -> tuple[list[dict], str]:
    if isinstance(source, Path):
        source_bytes = source.read_bytes()
        corpus_sha256 = hashlib.sha256(source_bytes).hexdigest()
        data = json.loads(source_bytes)
        source = data.get("cases") if isinstance(data, dict) else data
    else:
        source_bytes = json.dumps(
            source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        corpus_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if not isinstance(source, list) or not source:
        raise ValueError("Probe requires at least one journey")
    if len(source) > MAX_JOURNEYS:
        raise ValueError(f"Probe accepts at most {MAX_JOURNEYS} explicitly selected journeys")
    result = []
    for item in source:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("Every probe journey needs a string id")
        params = item.get("params")
        if params is None:
            request = item.get("request")
            if not isinstance(request, dict) or not isinstance(request.get("url"), str):
                raise ValueError("Journey requires params or an H3 request URL")
            params = parse_qs(urlsplit(request["url"]).query, keep_blank_values=False)
            params = {key: values[-1] for key, values in params.items() if values}
        if not isinstance(params, dict) or not _REQUIRED_PARAMS <= params.keys():
            raise ValueError("Journey is missing required routing parameters")
        params = {str(key): str(value) for key, value in params.items()}
        when = datetime.fromisoformat(params["time"].replace("Z", "+00:00"))
        if when.utcoffset() is None:
            raise ValueError("Journey departure time requires an explicit offset")
        original_when = when
        probe_time = item.get("probeTime")
        if probe_time is not None:
            when = datetime.fromisoformat(str(probe_time).replace("Z", "+00:00"))
            if when.utcoffset() is None:
                raise ValueError("Probe departure override requires an explicit offset")
            params["time"] = when.isoformat()
        expected = item.get("expect", {}).get("outcome", "route")
        if expected not in {"route", "no_route", "either"}:
            raise ValueError("Journey expected outcome must be route, no_route, or either")
        result.append(
            {
                "id": item["id"],
                "params": params,
                "departAt": when,
                "sourceDepartAt": original_when,
                "expected": expected,
            }
        )
    if len({item["id"] for item in result}) != len(result):
        raise ValueError("Probe journey ids must be unique")
    return result, corpus_sha256


def _structural_summary(body: object, expected: str) -> dict:
    if not isinstance(body, dict):
        raise ValueError("Response body must be an object")
    itineraries, direct = body.get("itineraries"), body.get("direct")
    if not isinstance(itineraries, list) or not isinstance(direct, list):
        raise ValueError("Response is missing itinerary lists")
    selected = itineraries or direct
    if expected == "route" and not selected:
        raise ValueError("Expected a route but the engine returned no itinerary")
    if expected == "no_route" and selected:
        raise ValueError("Expected no route but the engine returned an itinerary")
    summary = {
        "outcome": "route" if selected else "no_route",
        "itineraryCount": len(itineraries),
        "directCount": len(direct),
        "itineraries": [],
    }
    for itinerary in selected:
        if not isinstance(itinerary, dict) or not isinstance(itinerary.get("legs"), list):
            raise ValueError("An itinerary has no ordered legs")
        legs = itinerary["legs"]
        if not legs:
            raise ValueError("An itinerary is empty")
        previous_end = None
        for leg in legs:
            if not isinstance(leg, dict):
                raise ValueError("An itinerary leg is malformed")
            for field in ("scheduledStartTime", "scheduledEndTime"):
                if not isinstance(leg.get(field), str):
                    raise ValueError("An itinerary leg has no scheduled time")
            start = datetime.fromisoformat(leg["scheduledStartTime"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(leg["scheduledEndTime"].replace("Z", "+00:00"))
            if start.utcoffset() is None or end.utcoffset() is None or end < start:
                raise ValueError("An itinerary leg has invalid scheduled ordering")
            if previous_end is not None and start < previous_end:
                raise ValueError("Itinerary legs overlap or are out of order")
            previous_end = end
        transfers = itinerary.get("transfers")
        if type(transfers) is not int or transfers < 0:
            raise ValueError("An itinerary has an invalid transfer count")
        summary["itineraries"].append(
            {
                "legCount": len(legs),
                "transfers": transfers,
                "scheduledStartTime": legs[0]["scheduledStartTime"],
                "scheduledEndTime": legs[-1]["scheduledEndTime"],
            }
        )
    return summary


def _count_guard(candidate: dict, active: dict, limit: float) -> dict:
    deltas = {}
    blocked = []
    for name in ("stops", "routes"):
        old, new = active.get(name), candidate.get(name)
        if not isinstance(old, int) or not isinstance(new, int) or old <= 0:
            raise ValueError(f"Reference count {name} is unavailable for comparison")
        drop = max(0.0, (old - new) / old)
        deltas[name] = {"active": old, "candidate": new, "dropFraction": round(drop, 6)}
        if drop > limit:
            blocked.append(name)
    return {
        "threshold": limit,
        "proposal": "blocks drops greater than 20 percent",
        "counts": deltas,
        "blockedCounts": blocked,
    }


async def probe_generation(
    generation_dir: Path,
    engine_url: str,
    queries: Path | list[dict],
    active_dir: Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    *,
    allow_count_drop: bool = False,
    count_drop_limit: float = COUNT_DROP_LIMIT,
    now: datetime | None = None,
    report_path: Path | None = None,
) -> dict:
    """Probe an already-running candidate engine and exclusively write its report."""
    generation_dir = Path(generation_dir).resolve()
    report_path = Path(report_path) if report_path else generation_dir / "probe.json"
    if report_path.exists():
        raise FileExistsError(report_path)
    checked_at = now or datetime.now(UTC)
    if checked_at.utcoffset() is None:
        raise ValueError("Probe clock must have an explicit timezone")
    checked_at = checked_at.astimezone(UTC)
    manifest = json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))
    identity = {"generationId": manifest.get("generationId")}
    report = {
        **identity,
        "engineOrigin": engine_url.rstrip("/"),
        "status": "failed",
        "checkedAt": checked_at.isoformat(),
        "journeys": [],
        "journeyIds": [],
        "caseCount": 0,
        "corpusSha256": None,
        "warnings": [],
        "structuralOnly": True,
        "humanH3Approval": False,
    }
    try:
        origin = _loopback_origin(engine_url)
        verified = verify_artifacts(generation_dir)
        generation = Generation.load(generation_dir / "manifest.json")
        if generation.freshness(checked_at) != "current":
            raise ValueError("Candidate source freshness is not current")
        if not generation.contains(checked_at):
            raise ValueError("Candidate schedule does not cover the current time")
        reference = ReferenceStore(generation_dir / "reference.sqlite", generation.id)
        if reference.metadata.counts != manifest["artifacts"]["reference"]["counts"]:
            raise ValueError("Reference counts differ from the manifest")
        report.update(verified)
        report["referenceCounts"] = reference.metadata.counts
        if not 0 <= count_drop_limit <= 1:
            raise ValueError("count_drop_limit must be between zero and one")
        if active_dir is not None:
            active_dir = Path(active_dir).resolve()
            active_manifest = json.loads((active_dir / "manifest.json").read_text(encoding="utf-8"))
            verify_artifacts(active_dir)
            active_counts = active_manifest["artifacts"]["reference"]["counts"]
            guard = _count_guard(reference.metadata.counts, active_counts, count_drop_limit)
            if allow_count_drop:
                guard["overrideApplied"] = True
                guard["override"] = "explicit reviewed override supplied by caller"
            report["countGuard"] = guard
            if guard["blockedCounts"] and not allow_count_drop:
                raise ValueError("Candidate reference count drop exceeds the configured threshold")

        cases, corpus_sha256 = _journeys(queries)
        report["journeyIds"] = [case["id"] for case in cases]
        report["caseCount"] = len(cases)
        report["corpusSha256"] = corpus_sha256
        report["probeClass"] = "synthetic-fixture" if generation.mode == "fixture" else "real"
        minimum_journeys = 1 if generation.mode == "fixture" else MAX_JOURNEYS
        if len(cases) < minimum_journeys:
            raise ValueError(f"Probe requires at least {minimum_journeys} selected journeys")
        if generation.mode == "fixture":
            report["warnings"].append("Synthetic fixture probe; not production candidate evidence")
        if len(cases) < MAX_JOURNEYS:
            report["warnings"].append("Probe uses fewer than ten journeys")
        for case in cases:
            entry = {"id": case["id"], "status": "failed"}
            try:
                params = case["params"]
                departure = datetime.fromisoformat(params["time"].replace("Z", "+00:00"))
                entry["departureTime"] = departure.isoformat()
                entry["sourceDepartureTime"] = case["sourceDepartAt"].isoformat()
                entry["expectedOutcome"] = case["expected"]
                if not generation.contains(departure):
                    raise ValueError("Journey departure lies outside candidate coverage")
                async with asyncio.timeout(JOURNEY_TIMEOUT_SECONDS):
                    async with httpx.AsyncClient(
                        base_url=origin,
                        transport=transport,
                        timeout=httpx.Timeout(JOURNEY_TIMEOUT_SECONDS),
                        trust_env=False,
                        follow_redirects=False,
                    ) as client:
                        response = await client.get("/api/v6/plan", params=params)
                    entry["httpStatus"] = response.status_code
                    entry["responseSha256"] = hashlib.sha256(response.content).hexdigest()
                    response.raise_for_status()
                    entry["structure"] = _structural_summary(response.json(), case["expected"])
                entry["status"] = "passed"
            except TimeoutError:
                entry["failure"] = "TimeoutError: journey exceeded the 1.5 second total deadline"
            except asyncio.CancelledError:
                entry["failure"] = "Probe cancelled while a journey was in progress"
                report["journeys"].append(entry)
                raise
            except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                entry["failure"] = f"{type(exc).__name__}: {exc}"
            report["journeys"].append(entry)
        report["status"] = (
            "passed"
            if report["journeys"] and all(x["status"] == "passed" for x in report["journeys"])
            else "failed"
        )
    except asyncio.CancelledError:
        report["failure"] = "Probe cancelled while a journey was in progress"
        report["status"] = "failed"
        _write_probe_report(report_path, report)
        raise
    except Exception as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
    _write_probe_report(report_path, report)
    return report


def _write_probe_report(report_path: Path, report: dict) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
