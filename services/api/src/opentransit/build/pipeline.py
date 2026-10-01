"""One command from a fetch snapshot to a complete, verified generation (M2).

``build_complete_generation`` runs, in order: the OSM context scan (one pyosmium pass over the
snapshot PBF: named streets and administrative level 8 localities; only when localities or
addresses are wanted), paired validation, the reference SQLite build (with the OSM localities
loaded from that context), the memory-capped geocoding-enabled MOTIS import and export (all
through ``build_generation``), then with ``addresses=True`` the Photon preparation (house export,
enrichment from the same context, address catalog), the memory-capped Photon import and seal, the
attestation and an in-place composite manifest, and finally a full artifact verification. Every
stage is recorded in ``<output>/pipeline/pipeline.json`` with timings and details; stage logs live
next to it (MOTIS logs stay in the output root where ``build_generation`` writes them).

Localities (``localities=None`` is automatic): on when an OSM reader path is given or addresses
are built, forced on by ``True`` (the build then fails if pyosmium cannot be loaded) and off for
``False``. Without them the reference has empty locality tables and search falls back to
feed-derived city names; the choice is recorded in ``pipeline.json`` (``request.localities``).

The output directory must not exist. A failure keeps everything written so far (nothing is
deleted or overwritten, and no input or earlier generation is touched), marks the failing stage in
the evidence and raises; an address build holds ``manifest.json`` back until the composite verifies
so an incomplete generation is never loadable. Only the Docker/subprocess and osmium boundaries
are external; unit tests replace them.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from opentransit.address_catalog import AddressCatalog
from opentransit.build import composite, generations, photon, photon_source
from opentransit.build.address_catalog import build_address_catalog
from opentransit.core.artifacts import (
    JAVA_21_IMAGE_DIGEST,
    PHOTON_130_JAR_SHA256,
    verify_artifacts,
)
from opentransit.localities import LocalityDataset, load_locality_context

SCHEMA_VERSION = 1
CONTEXT_STAGES = ("osm_context",)
SCHEDULE_STAGES = ("validate", "reference", "motis_import", "motis_export")
ADDRESS_STAGES = (
    "hold_component",
    "photon_houses",
    "photon_enrich",
    "address_catalog",
    "photon_import",
    "photon_seal",
    "attestation",
    "compose",
)
FINAL_STAGES = ("verify",)
RESERVED = frozenset({"pipeline"})
_ECHOED_LIMIT = re.compile(r"^\s*(street_routing_max_\w+):\s*(\d+)\s*$", re.MULTILINE)


def uses_localities(localities: bool | None, addresses: bool, osm_reader_path: Path | None) -> bool:
    """Whether OSM localities go into the reference (``None`` selects automatically)."""
    if localities is None:
        return addresses or osm_reader_path is not None
    return bool(localities)


def stage_order(addresses: bool, localities: bool = False) -> tuple[str, ...]:
    context = CONTEXT_STAGES if addresses or localities else ()
    return context + SCHEDULE_STAGES + (ADDRESS_STAGES if addresses else ()) + FINAL_STAGES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _import_tool(name: str) -> Any:
    """Import ``services/api/tools/<name>.py`` (a checkout-only script module)."""
    try:
        return importlib.import_module(f"tools.{name}")
    except ModuleNotFoundError:
        root = str(Path(__file__).resolve().parents[3])
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            return importlib.import_module(f"tools.{name}")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"tools.{name} is only available from a repository checkout of services/api"
            ) from exc


def _enrich(houses: Path, context: Path, output: Path, provenance: Path, pbf_sha256: str) -> dict:
    tool = _import_tool("enrich_photon_addresses")
    return tool.transform_dump(
        houses,
        context,
        output,
        provenance,
        expected_source_sha256=pbf_sha256,
        expected_house_dump_sha256=None,
        expected_house_count=None,
    )


@dataclass
class Boundaries:
    """Every external effect of the pipeline, replaceable in tests."""

    runner: Callable = subprocess.run
    sleep: Callable[[float], None] = time.sleep
    build_schedule: Callable[..., Path] = generations.build_generation
    load_osmium: Callable[[Path | None], Any] = photon_source.load_osmium
    export_houses: Callable[..., dict] = photon_source.export_house_dump
    extract_context: Callable[..., dict] = photon_source.extract_context
    load_localities: Callable[..., LocalityDataset] = load_locality_context
    enrich: Callable[..., dict] = _enrich
    import_photon: Callable[..., dict] = photon.import_photon
    seal_photon: Callable[..., dict] = photon.seal_photon


class _Evidence:
    """Atomic, attributable stage log (``pipeline/pipeline.json``)."""

    def __init__(self, path: Path, request: dict, order: tuple[str, ...]) -> None:
        self.path = path
        self.clock: dict[str, float] = {}
        self.data: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "state": "running",
            "startedAt": datetime.now(UTC).isoformat(),
            "finishedAt": None,
            "request": request,
            "plannedStages": list(order),
            "environment": {
                "python": sys.version,
                "platform": platform.platform(),
                "pipelineSha256": _sha256(Path(__file__)),
                "generationsSha256": _sha256(Path(generations.__file__)),
            },
            "stages": [],
            "failure": None,
        }
        self.flush()

    def flush(self) -> None:
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def _entry(self, name: str) -> dict | None:
        for entry in reversed(self.data["stages"]):
            if entry["name"] == name:
                return entry
        return None

    def begin(self, name: str, details: dict | None = None) -> None:
        self.clock[name] = time.perf_counter()
        self.data["stages"].append(
            {
                "name": name,
                "status": "running",
                "startedAt": datetime.now(UTC).isoformat(),
                "finishedAt": None,
                "elapsedSeconds": None,
                "details": details or {},
                "error": None,
            }
        )
        self.flush()

    def finish(self, name: str, details: dict | None = None) -> None:
        entry = self._entry(name)
        assert entry is not None and entry["status"] == "running", name
        entry.update(
            {
                "status": "passed",
                "finishedAt": datetime.now(UTC).isoformat(),
                "elapsedSeconds": round(time.perf_counter() - self.clock[name], 2),
            }
        )
        entry["details"].update(details or {})
        self.flush()

    def on_stage(self, name: str, event: str, details: dict) -> None:
        if event == "started":
            self.begin(name, details)
        else:
            self.finish(name, details)

    def fail(self, exc: BaseException) -> None:
        message = f"{type(exc).__name__}: {exc}"
        running = [e for e in self.data["stages"] if e["status"] == "running"]
        for entry in running:
            entry.update(
                {
                    "status": "failed",
                    "finishedAt": datetime.now(UTC).isoformat(),
                    "elapsedSeconds": round(time.perf_counter() - self.clock[entry["name"]], 2),
                    "error": message,
                }
            )
        self.data["state"] = "failed"
        self.data["finishedAt"] = datetime.now(UTC).isoformat()
        self.data["failure"] = {
            "stage": running[-1]["name"] if running else None,
            "error": message,
        }
        self.flush()

    def complete(self, summary: dict) -> None:
        self.data["state"] = "complete"
        self.data["finishedAt"] = datetime.now(UTC).isoformat()
        self.data["result"] = summary
        self.flush()


def check_engine_config(generation_dir: Path) -> dict:
    """Assert the generated MOTIS config is slot-free and carries the walking caps (G3).

    The effective-config echo in ``import.log`` is checked only when MOTIS printed one.
    """
    generation_dir = Path(generation_dir)
    config = (generation_dir / "config.yml").read_text(encoding="utf-8")
    if re.search(r"^\s*(server|host|port):", config, re.MULTILINE):
        raise ValueError("Generated MOTIS config bakes a host/port; builds must be slot-free")
    expected = generations.STREET_ROUTING_LIMITS
    block = "limits:\n" + "".join(f"  {key}: {value}\n" for key, value in expected.items())
    if block not in config:
        raise ValueError("Generated MOTIS config lacks the pinned street-routing limits")
    echoed: dict[str, int] = {}
    log_path = generation_dir / "import.log"
    if log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        echoed = {key: int(value) for key, value in _ECHOED_LIMIT.findall(text)}
        for key, value in echoed.items():
            if key in expected and value != expected[key]:
                raise ValueError(f"MOTIS echoed {key}={value}, expected {expected[key]}")
    return {
        "slotFree": True,
        "limits": dict(expected),
        "configSha256": _sha256(generation_dir / "config.yml"),
        "engineEchoedLimits": echoed or None,
    }


def _preflight(
    snapshot: Path,
    output: Path,
    first_day: date,
    days: int,
    addresses: bool,
    use_localities: bool,
    photon_jar: Path | None,
    photon_memory_gib: int,
    osm_reader_path: Path | None,
    boundaries: Boundaries,
) -> Path | None:
    if not isinstance(first_day, date) or isinstance(first_day, datetime):
        raise ValueError("first_day must be a calendar date")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 60:
        raise ValueError("days must be between 1 and 60")
    if output.exists():
        raise FileExistsError(f"Output directory already exists: {output}")
    if not snapshot.is_dir():
        raise FileNotFoundError(f"Snapshot directory does not exist: {snapshot}")
    for name in generations.CANONICAL_INPUTS.values():
        if not any(snapshot.rglob(name)):
            raise FileNotFoundError(f"Snapshot lacks {name}")
    jar = None
    if addresses:
        if photon_jar is None:
            raise ValueError("--photon-jar is required with --addresses")
        jar = photon.check_photon_jar(photon_jar)
        photon.photon_memory_args(photon_memory_gib)
    if addresses or use_localities:
        boundaries.load_osmium(osm_reader_path)
    return jar


def build_complete_generation(
    snapshot: Path,
    output: Path,
    first_day: date,
    days: int = 31,
    *,
    addresses: bool = False,
    memory_gib: int = generations.MAX_BUILD_MEMORY_GIB,
    photon_memory_gib: int = photon.MAX_PHOTON_MEMORY_GIB,
    photon_jar: Path | None = None,
    osm_reader_path: Path | None = None,
    localities: bool | None = None,
    import_timeout_seconds: int = 1800,
    photon_timeout_seconds: int = 1800,
    boundaries: Boundaries | None = None,
) -> Path:
    """Build, validate and verify a complete generation in a new ``output`` directory."""
    boundaries = boundaries or Boundaries()
    snapshot, output = Path(snapshot).resolve(), Path(output).resolve()
    use_localities = uses_localities(localities, addresses, osm_reader_path)
    need_context = addresses or use_localities
    jar = _preflight(
        snapshot,
        output,
        first_day,
        days,
        addresses,
        use_localities,
        photon_jar,
        photon_memory_gib,
        osm_reader_path,
        boundaries,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    work = output / "pipeline"
    logs, scratch = work / "logs", work / "work"
    logs.mkdir(parents=True)
    scratch.mkdir()
    provenance = snapshot / "provenance.json"
    request = {
        "snapshot": str(snapshot),
        "snapshotProvenanceSha256": _sha256(provenance) if provenance.is_file() else None,
        "output": str(output),
        "firstDay": first_day.isoformat(),
        "days": days,
        "addresses": addresses,
        "localities": use_localities,
        "localitiesRequested": localities,
        "osmReaderPath": str(osm_reader_path) if osm_reader_path else None,
        "geocoding": True,
        "motisImportMemoryGiB": memory_gib,
        "photonImportMemoryGiB": photon_memory_gib if addresses else None,
        "photonJar": str(jar) if jar else None,
        "engineDigest": generations.ENGINE_DIGEST,
        "javaImage": photon.JAVA_IMAGE if addresses else None,
        "engineLimits": dict(generations.STREET_ROUTING_LIMITS),
    }
    evidence = _Evidence(work / "pipeline.json", request, stage_order(addresses, use_localities))
    try:
        context = scratch / "osm-context.jsonl"
        dataset: LocalityDataset | None = None
        pbf = None
        if need_context:
            pbf = generations._find_input(snapshot, "osm", generations.CANONICAL_INPUTS["osm"])
            dataset = _context_stage(
                pbf, context, evidence, boundaries, osm_reader_path, use_localities
            )
        boundaries.build_schedule(
            snapshot,
            output,
            first_day,
            days,
            memory_gib,
            True,
            runner=boundaries.runner,
            timeout_seconds=import_timeout_seconds,
            on_stage=evidence.on_stage,
            reserved_entries=RESERVED,
            localities=dataset,
        )
        if addresses:
            assert jar is not None and pbf is not None
            _address_stages(
                pbf,
                context,
                output,
                jar,
                scratch,
                logs,
                evidence,
                boundaries,
                photon_memory_gib,
                photon_timeout_seconds,
                osm_reader_path,
            )
        evidence.begin("verify")
        verified = verify_artifacts(output)
        details = {"verified": verified, "engineConfig": check_engine_config(output)}
        if addresses:
            details["photonTree"] = _check_photon_tree(output)
        details["manifestSha256"] = _sha256(output / "manifest.json")
        evidence.finish("verify", details)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        evidence.complete(
            {
                "generationId": manifest["generationId"],
                "scheduleComponentGenerationId": manifest.get("scheduleComponentGenerationId"),
                "addresses": addresses,
                "manifestSha256": details["manifestSha256"],
            }
        )
        return output
    except BaseException as exc:
        evidence.fail(exc)
        raise


def _check_photon_tree(output: Path) -> dict:
    attestation = json.loads((output / composite.ATTESTATION_NAME).read_text(encoding="utf-8"))
    sealed = attestation["checkpoint"]
    actual = photon.tree_checkpoint(output / "photon")
    for key in ("treeSha256", "files", "bytes"):
        if actual[key] != sealed[key]:
            raise ValueError(f"Photon data tree differs from its sealed checkpoint ({key})")
    return actual


def _context_stage(
    pbf: generations.InputArtifact,
    context: Path,
    evidence: _Evidence,
    boundaries: Boundaries,
    osm_reader_path: Path | None,
    use_localities: bool,
) -> LocalityDataset | None:
    """Scan the snapshot PBF once; the context feeds the localities and the enrichment."""
    evidence.begin("osm_context")
    result = boundaries.extract_context(pbf.path, context, reader_path=osm_reader_path)
    if result["sourcePbfSha256"] != pbf.sha256:
        raise ValueError("OSM context was extracted from a different PBF than the snapshot input")
    dataset = None
    details = dict(result)
    if use_localities:
        dataset = boundaries.load_localities(context, expected_osm_sha256=pbf.sha256)
        details["localities"] = dataset.provenance
    else:
        details["localities"] = None  # context kept for the Photon enrichment only
    evidence.finish("osm_context", details)
    return dataset


def _address_stages(
    pbf: generations.InputArtifact,
    context: Path,
    output: Path,
    jar: Path,
    scratch: Path,
    logs: Path,
    evidence: _Evidence,
    boundaries: Boundaries,
    photon_memory_gib: int,
    photon_timeout_seconds: int,
    osm_reader_path: Path | None,
) -> None:
    manifest_path = output / "manifest.json"
    held = output / composite.COMPONENT_MANIFEST_NAME

    evidence.begin("hold_component")
    component = json.loads(manifest_path.read_text(encoding="utf-8"))
    if component.get("state") != "ready":
        raise RuntimeError("Schedule component is not ready")
    os.replace(manifest_path, held)  # no manifest.json until the composite verifies
    evidence.finish(
        "hold_component",
        {"scheduleComponentGenerationId": component["generationId"], "heldAs": held.name},
    )

    houses = scratch / "photon-houses.jsonl"
    enriched = scratch / "photon-enriched.jsonl"
    enrichment_provenance = scratch / "photon-enriched.provenance.json"

    evidence.begin("photon_houses")
    house_result = boundaries.export_houses(pbf.path, houses, reader_path=osm_reader_path)
    evidence.finish("photon_houses", house_result)

    evidence.begin("photon_enrich")
    enrichment = boundaries.enrich(houses, context, enriched, enrichment_provenance, pbf.sha256)
    counts = enrichment["counts"]
    expected_documents = int(counts["houseRecords"]) + int(counts["streetDocumentsAdded"])
    if expected_documents <= 0:
        raise ValueError("Enrichment produced no Photon documents")
    dump_sha256 = enrichment["outputs"]["photonDumpSha256"]
    evidence.finish(
        "photon_enrich",
        {
            "counts": counts,
            "photonDumpSha256": dump_sha256,
            "expectedDocuments": expected_documents,
            "provenanceSha256": _sha256(enrichment_provenance),
        },
    )

    evidence.begin("address_catalog")
    catalog_path = output / composite.CATALOG_NAME
    catalog = build_address_catalog(enriched, catalog_path)
    if int(catalog["record_count"]) != expected_documents:
        raise ValueError("Address catalog record count differs from the enriched dump")
    if catalog["source_dump_sha256"] != dump_sha256:
        raise ValueError("Address catalog was built from a different dump")
    evidence.finish(
        "address_catalog",
        {"catalogSha256": _sha256(catalog_path), "recordCount": int(catalog["record_count"])},
    )

    evidence.begin("photon_import")
    imported = boundaries.import_photon(
        enriched,
        jar,
        logs,
        expected_documents,
        memory_gib=photon_memory_gib,
        timeout_seconds=photon_timeout_seconds,
        runner=boundaries.runner,
    )
    evidence.finish("photon_import", imported)

    evidence.begin("photon_seal")
    probes = photon.pick_probe_documents(enriched)
    sealed = boundaries.seal_photon(
        imported["volumeName"],
        jar,
        probes,
        expected_documents,
        logs,
        output / "photon",
        runner=boundaries.runner,
        sleep=boundaries.sleep,
    )
    evidence.finish(
        "photon_seal",
        {key: sealed[key] for key in ("indexUuid", "clusterUuid", "documentCount", "checkpoint")},
    )

    evidence.begin("attestation")
    attestation_path = output / composite.ATTESTATION_NAME
    with AddressCatalog(catalog_path, dump_sha256) as address_catalog:
        for probe in sealed["probes"]:
            place = address_catalog.lookup(probe["osmType"], probe["osmId"])
            if place is None or place["centroid"] != [probe["lon"], probe["lat"]]:
                raise ValueError(f"Sealed probe is not in the address catalog: {probe}")
    attestation = {
        "schemaVersion": 1,
        "provider": "photon",
        "sourceDumpSha256": dump_sha256,
        "catalogSha256": _sha256(catalog_path),
        "indexName": photon.INDEX_NAME,
        "indexUuid": sealed["indexUuid"],
        "clusterUuid": sealed["clusterUuid"],
        "documentCount": sealed["documentCount"],
        "importedAt": imported["finishedAt"],
        "sealedAt": sealed["sealedAt"],
        "indexWriteBlocked": True,
        "probes": sealed["probes"],
        "checkpoint": sealed["checkpoint"],
        "import": {
            "memoryCapBytes": imported["memoryCapBytes"],
            "elapsedSeconds": imported["elapsedSeconds"],
            "logCheck": imported["logCheck"],
            "volumeName": imported["volumeName"],
        },
        "enrichmentProvenanceSha256": _sha256(enrichment_provenance),
        "photonJarSha256": PHOTON_130_JAR_SHA256,
        "javaImageDigest": JAVA_21_IMAGE_DIGEST,
    }
    with attestation_path.open("x", encoding="utf-8") as stream:
        json.dump(attestation, stream, sort_keys=True, ensure_ascii=False, indent=2)
        stream.write("\n")
    evidence.finish("attestation", {"attestationSha256": _sha256(attestation_path)})

    evidence.begin("compose")
    composite.compose_in_place(
        output,
        photon_jar_sha256=PHOTON_130_JAR_SHA256,
        java_image_digest=JAVA_21_IMAGE_DIGEST,
        extra_manifest_fields={
            "addressBuild": {
                "photonDataPath": "photon",
                "photonTreeSha256": sealed["checkpoint"]["treeSha256"],
                "pipelineEvidence": "pipeline/pipeline.json",
                "enrichmentProvenanceSha256": attestation["enrichmentProvenanceSha256"],
            }
        },
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence.finish(
        "compose",
        {
            "generationId": manifest["generationId"],
            "scheduleComponentGenerationId": manifest["scheduleComponentGenerationId"],
        },
    )
