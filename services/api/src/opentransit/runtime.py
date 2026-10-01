"""A request captures one complete immutable generation and its engine adapter."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

from opentransit.build.prepare import sha256
from opentransit.core.artifacts import verify_artifacts
from opentransit.core.generation import Generation, instant
from opentransit.motis import MotisClient
from opentransit.reference import ReferenceStore


@dataclass(frozen=True)
class AddressProviderBinding:
    """One fixed Photon client bound to verified immutable address evidence."""

    client: object
    origin: str
    artifact_identity: str
    index_uuid: str
    catalog: object

    def __post_init__(self) -> None:
        if not isinstance(self.origin, str) or not re.fullmatch(
            r"http://(?:127\.0\.0\.1|localhost|\[::1\]):[1-9][0-9]{0,4}", self.origin
        ):
            raise ValueError("Address provider origin must be a fixed loopback HTTP origin")
        if not re.fullmatch(r"[a-f0-9]{64}", self.artifact_identity):
            raise ValueError("Address provider artifact identity must be a SHA-256 hex digest")
        if not isinstance(self.index_uuid, str) or not self.index_uuid:
            raise ValueError("Address provider index UUID is required")
        if not callable(getattr(self.client, "aclose", None)):
            raise TypeError("Address provider client must provide async aclose()")
        client_origin = getattr(self.client, "base_url", None)
        if client_origin is not None and str(client_origin).rstrip("/") != self.origin:
            raise ValueError("Address provider client origin differs from its binding")
        if not callable(getattr(self.catalog, "lookup", None)):
            raise TypeError("Address provider catalog must provide lookup()")
        if not callable(getattr(self.catalog, "close", None)):
            raise TypeError("Address provider catalog must provide close()")


def apply_source_check(
    generation: Generation, manifest: dict, source_check_path: Path
) -> Generation:
    """Apply a successful same-hash paired upstream check to a generation's provenance."""
    source_check_path = Path(source_check_path)
    evidence = json.loads(source_check_path.read_text(encoding="utf-8"))
    if evidence.get("pairedValidation") != "passed" or evidence["validation"]["valid"] is not True:
        raise ValueError("Only a successful paired check can renew freshness")
    checked_dates = []
    for key, name in (
        ("gtfs", "israel-public-transportation.zip"),
        ("trip_id_to_date", "TripIdToDate.zip"),
    ):
        source = evidence["sources"][key]
        if (
            source["status"] not in {"new", "changed", "unchanged"}
            or source["sha256"] != manifest["inputs"][name]["sha256"]
        ):
            raise ValueError("Source check does not describe this generation's input pair")
        checked_dates.append(instant(source["checkedAt"]))
    validated = instant(evidence["validatedAt"])
    if validated < max(checked_dates):
        raise ValueError("Pair validation precedes acquisition")
    previous = (
        generation.source_checked_at
        if generation.source_check_recorded
        else generation.validated_at
    )
    source_checked = min(checked_dates)
    if previous is not None and source_checked < previous:
        raise ValueError("Source check is older than existing provenance")
    return replace(generation, source_checked_at=source_checked, source_check_recorded=True)


def capture_snapshot(app_state) -> RuntimeSnapshot | None:
    """Capture one complete runtime generation for a request before its first await."""
    manager = getattr(app_state, "snapshot_manager", None)
    if manager is not None:
        return manager.current_snapshot
    return getattr(app_state, "snapshot", None)


@dataclass(frozen=True)
class RuntimeSnapshot:
    generation: Generation
    motis: MotisClient
    reference: ReferenceStore | None
    routing_verified: bool = True
    address_provider: AddressProviderBinding | None = None
    address_provider_required: bool = False

    @classmethod
    def load(
        cls,
        manifest_path: Path,
        motis: MotisClient,
        *,
        source_check_path: Path | None = None,
        probe_path: Path | None = None,
        address_provider: AddressProviderBinding | None = None,
        address_provider_required: bool = False,
    ) -> RuntimeSnapshot:
        generation = Generation.load(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        component_generation_id = manifest.get("scheduleComponentGenerationId", generation.id)
        if not isinstance(component_generation_id, str) or not component_generation_id:
            raise ValueError("A composed generation must identify its schedule component")
        if manifest.get("addressSearch") is not None and address_provider is None:
            raise ValueError("This generation requires a verified address provider")
        address_metadata = None
        managed = (
            "parserVersion" in manifest
            or bool(manifest.get("artifacts"))
            or manifest.get("addressSearch") is not None
        )
        if managed:
            verified_artifacts = verify_artifacts(manifest_path.parent, manifest)
            if manifest.get("addressSearch") is not None:
                address_metadata = verified_artifacts
        if source_check_path is not None:
            generation = apply_source_check(generation, manifest, source_check_path)
        reference_info = manifest.get("artifacts", {}).get("reference")
        reference = None
        if reference_info is not None:
            path = manifest_path.parent / "reference.sqlite"
            if sha256(path) != reference_info["sha256"]:
                raise ValueError("Reference artifact checksum differs from the manifest")
            reference = ReferenceStore(
                path,
                component_generation_id,
                cursor_generation_id=generation.id,
            )
            if (
                reference.metadata.source_sha256
                != manifest["inputs"]["israel-public-transportation.zip"]["sha256"]
            ):
                raise ValueError("Graph and reference feed identities differ")
        routing_verified = not managed
        if managed and probe_path is not None:
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            artifacts = manifest["artifacts"]
            routing_verified = (
                probe.get("status") == "passed"
                # Composite generations reuse the original graph and probe.
                # Preserve the component identity instead of relabeling evidence.
                and probe.get("generationId") == component_generation_id
                and probe.get("engineDigest") == generation.engine_digest
                and probe.get("engineOrigin", "").rstrip("/")
                == str(motis.client.base_url).rstrip("/")
                and probe.get("graphTreeSha256") == artifacts["motis"]["sha256"]
                and probe.get("configSha256") == artifacts["config"]["sha256"]
                and probe.get("referenceSha256") == artifacts["reference"]["sha256"]
            )
        address_provider_required = address_provider_required or address_metadata is not None
        if address_provider_required and address_provider is None:
            raise ValueError("This generation requires a verified address provider")
        if address_metadata is not None and address_provider is not None:
            if (
                address_provider.artifact_identity != address_metadata["addressArtifactIdentity"]
                or address_provider.index_uuid != address_metadata["indexUuid"]
            ):
                raise ValueError("Address provider identity differs from the sealed generation")
            catalog = address_provider.catalog
            if (
                getattr(catalog, "source_dump_sha256", None) != address_metadata["sourceDumpSha256"]
                or getattr(catalog, "source_pbf_sha256", None)
                != manifest["inputs"].get("israel-and-palestine-latest.osm.pbf", {}).get("sha256")
                or getattr(catalog, "record_count", None) != address_metadata["documentCount"]
            ):
                raise ValueError("Address source catalog differs from the sealed generation")
        return cls(
            generation,
            motis,
            reference,
            routing_verified,
            address_provider,
            address_provider_required,
        )
