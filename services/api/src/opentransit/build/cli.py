"""Schedule-only build tools. New artifacts never modify active serving data."""

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import uuid
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

from opentransit.build.fetch import DEFAULT_SOURCES, fetch_sources
from opentransit.build.identity import compare_ids
from opentransit.build.prepare import prepare
from opentransit.build.validation import FeedValidationError, validate_feed


def write_evidence(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def fetch_snapshot(output: Path, *, force_osm=False) -> Path:
    report = fetch_sources(output, force_osm=force_osm)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    evidence = output / "checks" / (stamp + ".json")
    payload = {"sources": {key: value.as_dict() for key, value in report.results.items()}}
    if not report.successful:
        payload["pairedValidation"] = "not_run"
        write_evidence(evidence, payload)
        raise ValueError("Source acquisition failed; previous generations are unchanged")
    try:
        validation = validate_feed(
            report.results["gtfs"].path, report.results["trip_id_to_date"].path
        )
    except FeedValidationError as exc:
        payload["validation"] = exc.report.as_dict()
        payload["pairedValidation"] = "failed"
        write_evidence(evidence, payload)
        raise
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        payload["pairedValidation"] = "failed"
        payload["validationError"] = type(exc).__name__
        write_evidence(evidence, payload)
        raise
    payload["validation"] = validation.as_dict()
    payload["pairedValidation"] = "passed"
    payload["validatedAt"] = datetime.now(UTC).isoformat()
    write_evidence(evidence, payload)
    snapshot = output / "snapshots" / stamp
    snapshot.mkdir(parents=True, exist_ok=False)
    sources = {}
    for key, item in report.results.items():
        shutil.copyfile(item.path, snapshot / item.name)
        sources[item.name] = {
            "sha256": item.sha256,
            "bytes": item.size_bytes,
            "acquiredAt": item.acquired_at,
            "checkedAt": item.checked_at,
            "status": item.status,
            "url": DEFAULT_SOURCES[key].url,
            "lastModified": item.last_modified,
        }
    write_evidence(
        snapshot / "provenance.json",
        {
            "inputs": sources,
            "validatedAt": payload["validatedAt"],
            "validationEvidence": str(evidence.resolve()),
        },
    )
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    m1 = commands.add_parser("prepare-m1", help="Preserved M1 isolated-volume workflow")
    m1.add_argument("--output", type=Path, required=True)
    m1.add_argument("--osm-path", type=Path)
    fetch = commands.add_parser("fetch", help="Acquire and validate immutable inputs")
    fetch.add_argument("--output", type=Path, required=True)
    fetch.add_argument("--force-osm", action="store_true")
    validate = commands.add_parser("validate", help="Validate a local GTFS/mapping pair")
    validate.add_argument("--gtfs", type=Path, required=True)
    validate.add_argument("--mapping", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    build = commands.add_parser("build", help="Build a new graph/reference generation")
    build.add_argument("--inputs", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--first-day", type=date.fromisoformat, required=True)
    build.add_argument("--days", type=int, default=31)
    build.add_argument("--memory-gib", type=int, default=6)
    build.add_argument("--geocoding", action="store_true")
    build.add_argument("--local-engine-slot", choices=("blue", "green"))
    build.add_argument("--validation-evidence", type=Path)
    build.add_argument("--reference-reuse-generation", type=Path)
    complete = commands.add_parser(
        "build-generation",
        help="One command: validate, reference, MOTIS import (+ Photon addresses), verify",
    )
    complete.add_argument("--snapshot", type=Path, required=True, help="fetch snapshot directory")
    complete.add_argument("--output", type=Path, required=True, help="new generation directory")
    complete.add_argument("--first-day", type=date.fromisoformat, required=True)
    complete.add_argument("--days", type=int, default=31)
    complete.add_argument("--memory-gib", type=int, default=6, help="MOTIS import cap (max 6)")
    complete.add_argument("--addresses", action="store_true", help="also build Photon addresses")
    complete.add_argument("--photon-jar", type=Path, help="pinned photon-1.3.0.jar (--addresses)")
    complete.add_argument("--photon-memory-gib", type=int, default=2, help="Photon import cap")
    complete.add_argument("--osm-reader-path", type=Path, help="directory providing pyosmium")
    complete.add_argument("--import-timeout-seconds", type=int, default=1800)
    complete.add_argument("--photon-timeout-seconds", type=int, default=1800)
    activate = commands.add_parser(
        "activate", help="Select a verified, probed generation as current (Linux)"
    )
    activate.add_argument("--generation", type=Path, required=True)
    activate.add_argument("--generations-root", type=Path, required=True)
    activate.add_argument("--engine-origin", required=True, help="loopback origin of its engine")
    activate.add_argument("--probe", type=Path, help="default: <generation>/probe.json")
    activate.add_argument("--source-check", type=Path)
    repair = commands.add_parser(
        "repair-reference",
        help="Clone a sealed generation and repair exact legacy translation keys",
    )
    repair.add_argument("--parent-generation", type=Path, required=True)
    repair.add_argument("--gtfs", type=Path, required=True)
    repair.add_argument("--output", type=Path, required=True)
    probe = commands.add_parser(
        "probe", help="Check an already-running candidate, preserving evidence"
    )
    probe.add_argument("--generation", type=Path, required=True)
    probe.add_argument("--engine-url", required=True)
    probe.add_argument("--queries", type=Path, required=True)
    probe.add_argument("--active", type=Path)
    probe.add_argument("--output", type=Path)
    prune = commands.add_parser("prune", help="List retention candidates; never delete")
    prune.add_argument("--generations-root", type=Path, required=True)
    prune.add_argument("--active", required=True)
    prune.add_argument("--previous", required=True)
    prune.add_argument("--pin", action="append", default=[])
    prune.add_argument("--draining", action="append", default=[])
    prune.add_argument("--dry-run", action="store_true", required=True)
    prune.add_argument("--output", type=Path, required=True)
    ids = commands.add_parser("compare-ids", help="Full source identifiers and dated hashes")
    ids.add_argument("--previous", type=Path, required=True)
    ids.add_argument("--candidate", type=Path, required=True)
    ids.add_argument("--previous-date", type=date.fromisoformat, required=True)
    ids.add_argument("--candidate-date", type=date.fromisoformat, required=True)
    ids.add_argument("--output", type=Path, required=True)
    demo = commands.add_parser(
        "demo", help="Plan Dizengoff Center -> Technion against a running API (scheduled)"
    )
    demo.add_argument("--api-url", default="http://127.0.0.1:8000")
    demo.add_argument("--depart-at", help="ISO time with offset; default tomorrow 08:00 Israel")
    demo.add_argument("--results", type=int, choices=range(1, 6), default=3)
    demo.add_argument("--lang", choices=("he", "en"), default="en")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            from opentransit.demo import run_demo

            for stream in (sys.stdout, sys.stderr):
                if hasattr(stream, "reconfigure"):
                    stream.reconfigure(errors="replace")
            return run_demo(args.api_url, args.depart_at, results=args.results, lang=args.lang)
        if args.command == "prepare-m1":
            prepare(args.output, args.osm_path)
        elif args.command == "fetch":
            print(fetch_snapshot(args.output, force_osm=args.force_osm))
        elif args.command == "validate":
            try:
                result = validate_feed(args.gtfs, args.mapping)
            except FeedValidationError as exc:
                write_evidence(args.output, exc.report.as_dict())
                raise
            write_evidence(args.output, result.as_dict())
            print(args.output)
        elif args.command == "compare-ids":
            write_evidence(
                args.output,
                compare_ids(
                    args.previous,
                    args.candidate,
                    args.previous_date,
                    args.candidate_date,
                ),
            )
            print(args.output)
        elif args.command == "build":
            from opentransit.build.generations import build_generation

            print(
                build_generation(
                    args.inputs,
                    args.output,
                    args.first_day,
                    args.days,
                    args.memory_gib,
                    args.geocoding,
                    local_engine_slot=args.local_engine_slot,
                    validation_evidence_path=args.validation_evidence,
                    reference_reuse_generation_path=args.reference_reuse_generation,
                )
            )
        elif args.command == "build-generation":
            from opentransit.build.pipeline import build_complete_generation

            print(
                build_complete_generation(
                    args.snapshot,
                    args.output,
                    args.first_day,
                    args.days,
                    addresses=args.addresses,
                    memory_gib=args.memory_gib,
                    photon_memory_gib=args.photon_memory_gib,
                    photon_jar=args.photon_jar,
                    osm_reader_path=args.osm_reader_path,
                    import_timeout_seconds=args.import_timeout_seconds,
                    photon_timeout_seconds=args.photon_timeout_seconds,
                )
            )
        elif args.command == "activate":
            from opentransit.build.select_generation import select_generation

            print(
                json.dumps(
                    select_generation(
                        args.generation,
                        args.generations_root,
                        args.engine_origin,
                        probe_path=args.probe,
                        source_check_path=args.source_check,
                    ),
                    indent=2,
                )
            )
        elif args.command == "repair-reference":
            from opentransit.build.reference_repair import repair_reference_generation

            print(
                repair_reference_generation(
                    args.parent_generation,
                    args.gtfs,
                    args.output,
                )
            )
        elif args.command == "probe":
            from opentransit.build.probe import probe_generation

            result = asyncio.run(
                probe_generation(
                    args.generation,
                    args.engine_url,
                    args.queries,
                    args.active,
                    report_path=args.output,
                )
            )
            print(result["status"])
            return 0 if result["status"] == "passed" else 1
        elif args.command == "prune":
            from opentransit.build.retention import plan_prune

            plan = plan_prune(
                args.generations_root,
                args.active,
                args.previous,
                set(args.pin),
                set(args.draining),
            )
            write_evidence(args.output, plan.as_dict())
            print(args.output)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
