"""Build a new, provenance-pinned schedule generation from immutable inputs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from opentransit.build.prepare import ENGINE_DIGEST, IMAGE
from opentransit.build.validation import FeedValidationError, ValidationReport, validate_feed
from opentransit.core.artifacts import verify_artifacts as _verify_artifacts
from opentransit.core.trip_calls import PINNED_PROJECTION_POLICY, POLICY_ID
from opentransit.localities import LocalityDataset
from opentransit.reference import SCHEMA_VERSION as REFERENCE_SCHEMA_VERSION
from opentransit.reference import ReferenceStore, build_reference

PARSER_VERSION = 2
MAX_BUILD_MEMORY_GIB = 6
MAX_IMPORT_DAYS = 60
VOLUME_PREFLIGHT_TIMEOUT_SECONDS = 30
LOCAL_TIMEZONE = ZoneInfo("Asia/Jerusalem")
CANONICAL_INPUTS = {
    "gtfs": "israel-public-transportation.zip",
    "trip_id_to_date": "TripIdToDate.zip",
    "osm": "israel-and-palestine-latest.osm.pbf",
}
LOCAL_ENGINE_SLOTS = {"blue": 59081, "green": 59082}
# The API accepts access/egress/direct walking caps of at most 30 minutes
# (JourneyRequest maxAccessWalkMinutes/maxEgressWalkMinutes/maxDirectWalkMinutes, le=30).
# MOTIS clamps maxPreTransitTime/maxPostTransitTime and maxDirectTime to these server
# `limits` values, so a generated config pins them to exactly the advertised maxima instead
# of relying on engine defaults (3600/21600 in v2.11.2). They are part of the config hash.
API_MAX_WALK_SECONDS = 30 * 60
STREET_ROUTING_LIMITS = {
    "street_routing_max_prepost_transit_seconds": API_MAX_WALK_SECONDS,
    "street_routing_max_direct_seconds": API_MAX_WALK_SECONDS,
}
REQUIRED_VALIDATION_CHECKS = {f"E{i:02d}" for i in range(1, 11)} | {
    f"V{i:02d}" for i in range(1, 11)
}


@dataclass(frozen=True)
class InputArtifact:
    key: str
    name: str
    path: Path
    sha256: str
    size_bytes: int
    acquired_at: str | None
    checked_at: str | None
    status: str | None
    url: str | None
    last_modified: str | None
    reused_local_path: str | None
    note: str | None
    source_path: str

    def as_dict(self) -> dict:
        return {
            "sha256": self.sha256,
            "bytes": self.size_bytes,
            "acquiredAt": self.acquired_at,
            "checkedAt": self.checked_at,
            "status": self.status,
            "url": self.url,
            "lastModified": self.last_modified,
            "reusedLocalPath": self.reused_local_path,
            "note": self.note,
            "sourcePath": self.source_path,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_artifact(root: Path) -> dict:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("MOTIS output contains a symbolic link")
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size <= 0:
            continue
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": size,
                "sha256": _sha256(path),
            }
        )
    if not files:
        raise ValueError("MOTIS import succeeded without any non-empty graph artifacts")
    digest = hashlib.sha256()
    for item in files:
        digest.update(f"{item['path']}\0{item['bytes']}\0{item['sha256']}\n".encode())
    return {
        "path": root.name,
        "sha256": digest.hexdigest(),
        "files": files,
        "fileCount": len(files),
        "bytes": sum(item["bytes"] for item in files),
    }


def verify_artifacts(generation_dir: Path) -> dict:
    """Verify immutable config, reference DB and complete MOTIS tree."""
    return _verify_artifacts(Path(generation_dir))


def _load_input_metadata(inputs_dir: Path) -> tuple[dict, dict[str, dict]]:
    for manifest_path in (
        inputs_dir / "provenance.json",
        inputs_dir / "manifest.json",
        inputs_dir.parent / "provenance.json",
        inputs_dir.parent / "manifest.json",
    ):
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        if isinstance(manifest, dict):
            input_map = manifest.get("inputs", {})
            if not isinstance(input_map, dict) or not input_map:
                generation = manifest.get("generation", {})
                input_map = generation.get("inputs", {}) if isinstance(generation, dict) else {}
            if isinstance(input_map, dict):
                return manifest, input_map
            return manifest, {}
    return {}, {}


def _find_input(inputs_dir: Path, key: str, name: str) -> InputArtifact:
    manifest, manifest_inputs = _load_input_metadata(inputs_dir)
    candidates = []
    direct = inputs_dir / name
    if direct.is_file():
        candidates.append(direct)
    else:
        candidates.extend(
            path
            for path in inputs_dir.rglob("*")
            if path.is_file() and (path.name == name or path.name.endswith(f"-{name}"))
        )
    unique = sorted(set(path.resolve() for path in candidates))
    if not unique:
        raise FileNotFoundError(f"Input artifact missing: {name}")
    hashes = {_sha256(path) for path in unique}
    if len(hashes) != 1:
        raise ValueError(f"Multiple different input artifacts found for {name}")
    path = unique[0]
    metadata = manifest_inputs.get(name, {})
    if not metadata:
        metadata = manifest_inputs.get(key, {})
    if not metadata:
        for event in inputs_dir.glob("events/*.json"):
            try:
                item = json.loads(event.read_text(encoding="utf-8"))
            except OSError, json.JSONDecodeError:
                continue
            if item.get("key") == key and item.get("path") and Path(item["path"]).resolve() == path:
                metadata = item
                break
    digest = _sha256(path)
    expected = metadata.get("sha256")
    if expected and expected != digest:
        raise ValueError(f"Input hash differs from recorded provenance: {name}")
    try:
        source_path = path.relative_to(inputs_dir.resolve()).as_posix()
    except ValueError:
        source_path = str(path)
    return InputArtifact(
        key=key,
        name=name,
        path=path,
        sha256=digest,
        size_bytes=path.stat().st_size,
        acquired_at=metadata.get("acquiredAt"),
        checked_at=metadata.get("checkedAt"),
        status=metadata.get("status"),
        url=metadata.get("url"),
        last_modified=metadata.get("lastModified"),
        reused_local_path=metadata.get("reusedLocalPath"),
        note=metadata.get("note"),
        source_path=source_path,
    )


def _write_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _reuse_reference_artifact(
    source_generation: Path,
    destination: Path,
    generation_id: str,
    identity: dict,
    expected_source_sha256: str,
) -> dict:
    """Copy a reference only when its manifest and SQLite metadata prove identity."""
    source_generation = Path(source_generation).resolve()
    manifest_path = source_generation / "manifest.json"
    try:
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Reference reuse source has no readable generation manifest") from exc
    if source_manifest.get("identity") != identity:
        raise ValueError("Reference reuse identity differs from the candidate")
    if source_manifest.get("generationId") != generation_id:
        raise ValueError("Reference reuse generation ID differs from the candidate")
    source_entry = source_manifest.get("artifacts", {}).get("reference", {})
    if source_entry.get("path") != "reference.sqlite":
        raise ValueError("Reference reuse source has an unsupported artifact path")
    source_path = source_generation / "reference.sqlite"
    if source_path.is_symlink() or not source_path.is_file():
        raise ValueError("Reference reuse source database is missing or redirected")
    source_sha256 = _sha256(source_path)
    if source_sha256 != source_entry.get("sha256"):
        raise ValueError("Reference reuse file checksum differs from its manifest")
    store = ReferenceStore(source_path, generation_id)
    metadata = store.metadata
    if metadata.source_sha256 != expected_source_sha256:
        raise ValueError("Reference reuse source feed hash differs from candidate GTFS")
    if metadata.schema_version != REFERENCE_SCHEMA_VERSION:
        raise ValueError("Reference reuse schema version differs from the candidate")
    if source_manifest.get("referenceSchemaVersion") != metadata.schema_version:
        raise ValueError("Reference reuse manifest schema version differs from its database")
    if metadata.content_sha256 != source_entry.get("contentSha256"):
        raise ValueError("Reference reuse content hash differs from its manifest")
    if metadata.counts != source_entry.get("counts"):
        raise ValueError("Reference reuse counts differ from its manifest")
    if metadata.timing_policy != source_entry.get("timingPolicy"):
        raise ValueError("Reference reuse timing policy differs from its manifest")
    shutil.copyfile(source_path, destination)
    destination.chmod(0o444)
    if _sha256(destination) != source_sha256:
        raise ValueError("Copied reference checksum differs from verified source")
    return {
        **source_entry,
        "reusedFrom": str(source_generation),
        "sha256": source_sha256,
    }


def _source_provenance_time(artifacts: dict[str, InputArtifact]) -> str | None:
    pair = [artifacts[key] for key in ("gtfs", "trip_id_to_date")]
    successful = {"new", "changed", "unchanged"}
    now = datetime.now(UTC)

    def parsed(value: str | None, label: str) -> datetime | None:
        if value is None:
            return None
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid {label} provenance timestamp") from exc
        if result.utcoffset() is None:
            raise ValueError(f"{label} provenance timestamp requires an explicit offset")
        result = result.astimezone(UTC)
        if result > now:
            raise ValueError(f"{label} provenance timestamp is in the future")
        return result

    if all(item.checked_at and item.status in successful for item in pair):
        checked = [parsed(item.checked_at, "checkedAt") for item in pair]
        return min(value for value in checked if value is not None).isoformat()
    if all(item.acquired_at for item in pair):
        acquired = [parsed(item.acquired_at, "acquiredAt") for item in pair]
        return min(value for value in acquired if value is not None).isoformat()
    return None


def _config(
    first_day: date,
    days: int,
    geocoding: bool,
    local_engine_slot: str | None = None,
) -> str:
    server = ""
    if local_engine_slot is not None:
        server = f"server:\n  host: 127.0.0.1\n  port: {LOCAL_ENGINE_SLOTS[local_engine_slot]}\n"
    return server + (
        f"osm: /input/{CANONICAL_INPUTS['osm']}\n"
        "timetable:\n"
        f"  first_day: {first_day.isoformat()}\n"
        f"  num_days: {days}\n"
        "  with_shapes: true\n"
        "  railviz: true\n"
        "  adjust_footpaths: true\n"
        "  merge_dupes_intra_src: false\n"
        "  merge_dupes_inter_src: false\n"
        "  datasets:\n"
        "    mot60day:\n"
        f"      path: /input/{CANONICAL_INPUTS['gtfs']}\n"
        "      extend_calendar: false\n"
        "street_routing: true\n"
        "limits:\n"
        + "".join(f"  {key}: {value}\n" for key, value in STREET_ROUTING_LIMITS.items())
        + f"geocoding: {'true' if geocoding else 'false'}\n"
        "reverse_geocoding: false\n"
    )


def _read_validation_evidence(
    path: Path, artifacts: dict[str, InputArtifact]
) -> tuple[ValidationReport, dict, str]:
    """Load only an audit bound to these exact inputs and current validator code."""
    path = Path(path).resolve()
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Unable to read validation evidence") from exc
    if not isinstance(evidence, dict):
        raise ValueError("Validation evidence must be a JSON object")
    if evidence.get("error") is not None:
        raise ValueError("Validation evidence records an unsuccessful validator run")

    expected_inputs = {
        "gtfs": artifacts["gtfs"].sha256,
        "tripIdToDate": artifacts["trip_id_to_date"].sha256,
    }
    recorded_inputs = evidence.get("inputSha256")
    if not isinstance(recorded_inputs, dict) or any(
        recorded_inputs.get(key) != value for key, value in expected_inputs.items()
    ):
        raise ValueError("Validation evidence input hashes do not match the selected inputs")

    validator_path = Path(__file__).with_name("validation.py")
    policy_path = Path(__file__).parents[1] / "core" / "trip_calls.py"
    validator_hash = _sha256(validator_path)
    policy_hash = _sha256(policy_path)
    if evidence.get("validatorSha256") != validator_hash:
        raise ValueError("Validation evidence validator code hash is stale")
    if evidence.get("policyCodeSha256") != policy_hash:
        raise ValueError("Validation evidence projection policy code hash is stale")
    if evidence.get("policyId") != POLICY_ID:
        raise ValueError("Validation evidence policy identity is stale")
    if evidence.get("validatorVersion") != validator_hash[:16]:
        raise ValueError("Validation evidence validator version does not match its code hash")

    report_data = evidence.get("report")
    if not isinstance(report_data, dict) or report_data.get("valid") is not True:
        raise ValueError("Validation evidence does not contain a successful report")
    checks = report_data.get("checks")
    if not isinstance(checks, list):
        raise ValueError("Validation evidence report has no check results")
    check_ids = [item.get("id") for item in checks if isinstance(item, dict)]
    if (
        len(check_ids) != len(checks)
        or len(set(check_ids)) != len(check_ids)
        or not REQUIRED_VALIDATION_CHECKS.issubset(check_ids)
        or any(item.get("status") == "fail" for item in checks)
    ):
        raise ValueError("Validation evidence is missing required checks or contains a failure")

    created_at = evidence.get("createdAtUtc")
    if not isinstance(created_at, str):
        raise ValueError("Validation evidence has no validator completion time")
    try:
        parsed_created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Validation evidence completion time is invalid") from exc
    if parsed_created_at.utcoffset() is None or parsed_created_at > datetime.now(UTC):
        raise ValueError("Validation evidence completion time must be offset-aware and not future")

    required_report_fields = (
        "gtfsPath",
        "tripIdToDatePath",
        "integrity",
        "serviceDates",
        "coverage",
        "pairing",
    )
    if any(key not in report_data for key in required_report_fields):
        raise ValueError("Validation evidence report is incomplete")
    report = ValidationReport(
        Path(report_data["gtfsPath"]),
        Path(report_data["tripIdToDatePath"]),
        checks,
        report_data["integrity"],
        report_data["serviceDates"],
        report_data["coverage"],
        report_data["pairing"],
    )
    if not report.valid:
        raise ValueError("Validation evidence report contains a failed check")

    provenance = {
        "path": str(path),
        "sha256": _sha256(path),
        "validatorSha256": validator_hash,
        "policyCodeSha256": policy_hash,
        "policyId": POLICY_ID,
        "createdAtUtc": created_at,
    }
    return report, provenance, created_at


def build_generation(
    inputs_dir: Path,
    output_dir: Path,
    first_day: date,
    days: int = 31,
    memory_gib: int = 6,
    geocoding: bool = False,
    runner: Callable = subprocess.run,
    timeout_seconds: int = 600,
    local_engine_slot: str | None = None,
    validation_evidence_path: Path | None = None,
    reference_reuse_generation_path: Path | None = None,
    on_stage: Callable[[str, str, dict], None] | None = None,
    reserved_entries: frozenset[str] = frozenset(),
    localities: LocalityDataset | None = None,
) -> Path:
    """Validate inputs, build reference SQLite and import MOTIS into a new directory.

    ``localities`` (``opentransit.localities.load_locality_context``) adds the OSM locality
    tables to the reference. Its context hash joins the generation identity and its provenance
    is recorded in the reference artifact entry; it must have been extracted from this build's
    OSM input.

    ``runner`` is injectable so tests can exercise success/failure handling without
    launching Docker. The candidate directory is created with exclusive semantics;
    failures leave their manifest and logs behind and are never overwritten.

    ``on_stage(name, "started"|"finished", details)`` reports the validate, reference,
    motis_import and motis_export boundaries to an orchestrator. A failure raises without a
    "finished" event for the open stage. ``reserved_entries`` names entries an orchestrator
    created before the call; the directory may then pre-exist but must hold nothing else.
    """

    def stage(name: str, event: str, details: dict | None = None) -> None:
        if on_stage is not None:
            on_stage(name, event, details or {})

    inputs_dir = Path(inputs_dir).resolve()
    output_dir = Path(output_dir).resolve()
    if not isinstance(first_day, date) or isinstance(first_day, datetime):
        raise ValueError("first_day must be a calendar date")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_IMPORT_DAYS:
        raise ValueError("days must be between 1 and 60")
    if (
        isinstance(memory_gib, bool)
        or not isinstance(memory_gib, int)
        or not 1 <= memory_gib <= MAX_BUILD_MEMORY_GIB
    ):
        raise ValueError("memory_gib must be between 1 and 6")
    if not isinstance(geocoding, bool):
        raise ValueError("geocoding must be a boolean")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int)
        or not 1 <= timeout_seconds <= 7200
    ):
        raise ValueError("timeout_seconds must be between 1 and 7200")
    if local_engine_slot is not None and (
        not isinstance(local_engine_slot, str) or local_engine_slot not in LOCAL_ENGINE_SLOTS
    ):
        raise ValueError("local_engine_slot must be 'blue', 'green', or None")
    if validation_evidence_path is not None and not isinstance(
        validation_evidence_path, (str, os.PathLike)
    ):
        raise ValueError("validation_evidence_path must be a path or None")
    if reference_reuse_generation_path is not None and not isinstance(
        reference_reuse_generation_path, (str, os.PathLike)
    ):
        raise ValueError("reference_reuse_generation_path must be a path or None")
    if localities is not None and not isinstance(localities, LocalityDataset):
        raise ValueError("localities must be a loaded locality dataset or None")
    if reserved_entries and output_dir.is_dir():
        unexpected = sorted(
            entry.name for entry in output_dir.iterdir() if entry.name not in reserved_entries
        )
        if unexpected:
            raise FileExistsError(f"Generation directory already contains {unexpected}")
    else:
        output_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = output_dir / "manifest.json"
    manifest = {
        "schemaVersion": 1,
        "state": "preparing",
        "mode": "real",
        "engineDigest": ENGINE_DIGEST,
        "parserVersion": PARSER_VERSION,
        "referenceSchemaVersion": REFERENCE_SCHEMA_VERSION,
        "timingPolicy": asdict(PINNED_PROJECTION_POLICY),
        "engineLimits": dict(STREET_ROUTING_LIMITS),
        "localEngineSlot": local_engine_slot,
        "engineOrigin": (
            f"http://127.0.0.1:{LOCAL_ENGINE_SLOTS[local_engine_slot]}"
            if local_engine_slot is not None
            else None
        ),
        "inputs": {},
        "artifacts": {},
    }
    _write_json(manifest_path, manifest)
    build = {
        "importMemoryCapBytes": memory_gib * 1024**3,
        "resourceScope": (
            "Volume preflight and MOTIS import containers only; "
            "validation and reference build are uncapped"
        ),
        "timeoutSeconds": timeout_seconds,
        "containerName": None,
        "volumeName": None,
        "volumePreflightContainerName": None,
        "volumePreflightExitCode": None,
        "volumeWritableAsImageUser": None,
        "startedAt": None,
        "elapsedSeconds": None,
        "exitCode": None,
        "finishedAt": None,
        "exportElapsedSeconds": None,
        "exportExitCode": None,
    }
    manifest["build"] = build
    import_started_clock = None

    try:
        if not inputs_dir.is_dir():
            raise FileNotFoundError(f"Input directory does not exist: {inputs_dir}")
        artifacts = {
            key: _find_input(inputs_dir, key, name) for key, name in CANONICAL_INPUTS.items()
        }
        manifest["inputs"] = {artifact.name: artifact.as_dict() for artifact in artifacts.values()}
        if localities is not None and (
            localities.provenance.get("osmPbfSha256") != artifacts["osm"].sha256
        ):
            raise ValueError("Locality context was extracted from a different OSM input")
        input_manifest, _ = _load_input_metadata(inputs_dir)
        if input_manifest.get("mode") == "fixture":
            manifest["mode"] = "fixture"

        evidence_provenance = None
        stage("validate", "started")
        if validation_evidence_path is None:
            validation = validate_feed(
                artifacts["gtfs"].path,
                artifacts["trip_id_to_date"].path,
            )
            validation_run_at = datetime.now(UTC).isoformat()
            validation_artifact = validation.as_dict()
        else:
            validation, evidence_provenance, validation_run_at = _read_validation_evidence(
                Path(validation_evidence_path), artifacts
            )
            validation_artifact = validation.as_dict()
            validation_artifact["evidenceProvenance"] = evidence_provenance
            manifest["validationEvidence"] = evidence_provenance
        _write_json(output_dir / "validation.json", validation_artifact)
        stage("validate", "finished", {"serviceDates": len(validation.service_dates)})
        available_dates = [date.fromisoformat(day) for day in validation.service_dates]
        if first_day not in available_dates:
            raise ValueError("first_day must be an active validated GTFS service date")
        effective_days = min(days, (max(available_dates) - first_day).days + 1)
        if effective_days < 1:
            raise ValueError("Import window has no active service date coverage")
        coverage_end = first_day + timedelta(days=effective_days)
        import_service_dates = [
            day.isoformat() for day in available_dates if first_day <= day < coverage_end
        ]
        coverage = {
            "from": datetime.combine(first_day, datetime.min.time(), LOCAL_TIMEZONE).isoformat(),
            "until": datetime.combine(
                coverage_end, datetime.min.time(), LOCAL_TIMEZONE
            ).isoformat(),
        }
        source_checked_at = _source_provenance_time(artifacts)
        manifest.update(
            {
                "coverage": coverage,
                "serviceDates": {
                    "from": validation.coverage["from"],
                    "through": validation.coverage["through"],
                },
                "preflight": {
                    "integrity": validation.integrity,
                    "pairing": validation.pairing,
                    "importDays": effective_days,
                    "importServiceDates": import_service_dates,
                    "tripCount": validation.pairing.get("feedTripCount"),
                    "stopTimeCount": validation.integrity.get("time_integrity", {}).get(
                        "stopTimeRows"
                    ),
                },
                "validatedAt": validation_run_at,
                "validationRunAt": validation_run_at,
                "sourceCheckedAt": source_checked_at,
            }
        )
        config_text = _config(first_day, effective_days, geocoding, local_engine_slot)
        config_path = output_dir / "config.yml"
        config_path.write_text(config_text, encoding="utf-8")
        config_hash = _sha256(config_path)
        identity = {
            "inputs": {artifact.name: artifact.sha256 for artifact in artifacts.values()},
            "configSha256": config_hash,
            "engineDigest": ENGINE_DIGEST,
            "parserVersion": PARSER_VERSION,
            "referenceSchemaVersion": REFERENCE_SCHEMA_VERSION,
            "timingPolicy": asdict(PINNED_PROJECTION_POLICY),
            "mode": manifest["mode"],
            "window": {"firstDay": first_day.isoformat(), "days": effective_days},
            "importMemoryCapBytes": build["importMemoryCapBytes"],
            "engineLimits": dict(STREET_ROUTING_LIMITS),
        }
        if local_engine_slot is not None:
            identity["localEngineSlot"] = local_engine_slot
        if localities is not None:
            identity["localityContextSha256"] = localities.provenance["contextSha256"]
        if evidence_provenance is not None:
            identity["validationEvidenceSha256"] = evidence_provenance["sha256"]
        generation_id = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        manifest.update(
            {
                "generationId": generation_id,
                "configSha256": config_hash,
                "identity": identity,
            }
        )
        manifest["state"] = "building"
        _write_json(manifest_path, manifest)

        reference_path = output_dir / "reference.sqlite"
        stage("reference", "started")
        if reference_reuse_generation_path is None:
            reference_metadata = build_reference(
                artifacts["gtfs"].path, reference_path, generation_id, localities=localities
            )
            manifest["artifacts"]["reference"] = {
                "path": reference_path.name,
                "sha256": _sha256(reference_path),
                "contentSha256": reference_metadata.content_sha256,
                "counts": reference_metadata.counts,
                "timingPolicy": reference_metadata.timing_policy,
            }
            if localities is not None:
                manifest["artifacts"]["reference"]["localityProvenance"] = localities.provenance
        else:
            reference_artifact = _reuse_reference_artifact(
                Path(reference_reuse_generation_path),
                reference_path,
                generation_id,
                identity,
                artifacts["gtfs"].sha256,
            )
            manifest["artifacts"]["reference"] = reference_artifact
            manifest["referenceReuse"] = {
                "generationId": generation_id,
                "sourceGeneration": reference_artifact["reusedFrom"],
                "sha256": reference_artifact["sha256"],
                "contentSha256": reference_artifact["contentSha256"],
            }
        stage("reference", "finished", {"sha256": manifest["artifacts"]["reference"]["sha256"]})
        motis_dir = output_dir / "motis"
        motis_dir.mkdir()
        builder_name = f"opentransit-builder-{uuid.uuid4().hex}"
        volume_name = f"opentransit-graph-{uuid.uuid4().hex}"
        build["containerName"] = builder_name
        build["volumeName"] = volume_name
        command = ["docker", "run", "--name", builder_name, "--memory", f"{memory_gib}g"]
        for artifact in artifacts.values():
            target = f"/input/{artifact.name}"
            if "," in str(artifact.path):
                raise ValueError("Docker input paths containing commas are unsupported")
            command.extend(
                ["--mount", f"type=bind,src={artifact.path.as_posix()},dst={target},readonly"]
            )
        if "," in str(config_path) or "," in str(motis_dir):
            raise ValueError("Docker generation paths containing commas are unsupported")
        command.extend(
            [
                "--mount",
                f"type=bind,src={config_path.as_posix()},dst=/config.yml,readonly",
                "--mount",
                f"type=volume,src={volume_name},dst=/data",
            ]
        )
        preflight_name = f"opentransit-volume-check-{uuid.uuid4().hex}"
        build["volumePreflightContainerName"] = preflight_name
        preflight_command = [
            "docker",
            "run",
            "--rm",
            "--name",
            preflight_name,
            "--memory",
            f"{memory_gib}g",
            "--mount",
            f"type=volume,src={volume_name},dst=/data",
            "--entrypoint",
            "/bin/sh",
            IMAGE,
            "-c",
            'test "$(id -u)" = 100 && test "$(id -g)" = 101 && '
            "test -w /data && touch /data/.opentransit-write-check && "
            "rm /data/.opentransit-write-check",
        ]
        preflight_path = output_dir / "volume-preflight.log"
        stage("motis_import", "started", {"memoryCapBytes": build["importMemoryCapBytes"]})
        with preflight_path.open("w", encoding="utf-8") as preflight_log:
            preflight = runner(
                preflight_command,
                stdout=preflight_log,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=VOLUME_PREFLIGHT_TIMEOUT_SECONDS,
            )
        build["volumePreflightExitCode"] = preflight.returncode
        if preflight.returncode != 0:
            manifest["state"] = "failed"
            manifest["failure"] = "Builder image user cannot write to its graph volume"
            _write_json(manifest_path, manifest)
            raise RuntimeError(
                f"MOTIS image user cannot write to the new graph volume; inspect {preflight_path}"
            )
        build["volumeWritableAsImageUser"] = True
        _write_json(manifest_path, manifest)
        command.extend(
            [
                IMAGE,
                "/motis",
                "import",
                "-c",
                "/config.yml",
                "-d",
                "/data",
            ]
        )
        log_path = output_dir / "import.log"
        import_started_clock = time.perf_counter()
        build["startedAt"] = datetime.now(UTC).isoformat()
        _write_json(manifest_path, manifest)
        with log_path.open("w", encoding="utf-8") as log:
            try:
                result = runner(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired, KeyboardInterrupt:
                try:
                    runner(
                        ["docker", "stop", "--time", "5", builder_name],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        check=False,
                        timeout=15,
                    )
                except Exception as stop_error:
                    manifest["cleanupFailure"] = f"{type(stop_error).__name__}: {stop_error}"
                    _write_json(manifest_path, manifest)
                raise
        build.update(
            {
                "elapsedSeconds": round(time.perf_counter() - import_started_clock, 2),
                "exitCode": result.returncode,
                "finishedAt": datetime.now(UTC).isoformat(),
            }
        )
        manifest["artifacts"]["motis"] = {"path": motis_dir.name}
        manifest["artifacts"]["config"] = {"path": config_path.name, "sha256": config_hash}
        if result.returncode != 0:
            manifest["state"] = "failed"
            manifest["failure"] = "MOTIS import returned a non-zero exit code"
            _write_json(manifest_path, manifest)
            raise RuntimeError(
                f"MOTIS import failed with exit code {result.returncode}; inspect {log_path}"
            )

        stage("motis_import", "finished", {"elapsedSeconds": build["elapsedSeconds"]})
        stage("motis_export", "started")
        export_path = output_dir / "export.log"
        export_started_clock = time.perf_counter()
        with export_path.open("w", encoding="utf-8") as export_log:
            export_result = runner(
                ["docker", "cp", f"{builder_name}:/data/.", str(motis_dir)],
                stdout=export_log,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout_seconds,
            )
        build["exportElapsedSeconds"] = round(time.perf_counter() - export_started_clock, 2)
        build["exportExitCode"] = export_result.returncode
        if export_result.returncode != 0:
            manifest["state"] = "failed"
            manifest["failure"] = "Graph export from the builder volume failed"
            _write_json(manifest_path, manifest)
            raise RuntimeError(
                f"MOTIS graph export failed with exit code {export_result.returncode}; "
                f"inspect {export_path}"
            )

        manifest["artifacts"]["motis"] = _tree_artifact(motis_dir)
        manifest["state"] = "ready"
        manifest["builtAt"] = datetime.now(UTC).isoformat()
        _write_json(manifest_path, manifest)
        stage(
            "motis_export",
            "finished",
            {
                "exportElapsedSeconds": build["exportElapsedSeconds"],
                "graphTreeSha256": manifest["artifacts"]["motis"]["sha256"],
                "graphBytes": manifest["artifacts"]["motis"]["bytes"],
            },
        )
        return output_dir
    except FeedValidationError as exc:
        if hasattr(exc, "report"):
            _write_json(output_dir / "validation.json", exc.report.as_dict())
        manifest["state"] = "failed"
        manifest["failure"] = str(exc)
        if import_started_clock is not None and build["finishedAt"] is None:
            build["elapsedSeconds"] = round(time.perf_counter() - import_started_clock, 2)
            build["finishedAt"] = datetime.now(UTC).isoformat()
        _write_json(manifest_path, manifest)
        raise
    except KeyboardInterrupt:
        manifest["state"] = "failed"
        manifest["failure"] = "Build interrupted by operator"
        if import_started_clock is not None and build["finishedAt"] is None:
            build["elapsedSeconds"] = round(time.perf_counter() - import_started_clock, 2)
            build["finishedAt"] = datetime.now(UTC).isoformat()
        _write_json(manifest_path, manifest)
        raise
    except Exception as exc:
        if manifest.get("state") != "failed":
            manifest["state"] = "failed"
            manifest["failure"] = f"{type(exc).__name__}: {exc}"
        if import_started_clock is not None and build["finishedAt"] is None:
            build["elapsedSeconds"] = round(time.perf_counter() - import_started_clock, 2)
            build["finishedAt"] = datetime.now(UTC).isoformat()
        _write_json(manifest_path, manifest)
        raise
