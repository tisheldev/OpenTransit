"""Compose a schedule component and sealed Photon address artifacts into one generation.

``composite_manifest`` is the single place that derives the public composite generation ID and
the address artifact identity; ``tools/compose_address_generation.py`` (copying) and the
single-command pipeline (in place, no multi-gigabyte copies) both use it, and
``opentransit.core.artifacts.verify_address_composite`` independently re-derives the same IDs.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from opentransit.core.artifacts import (
    JAVA_21_IMAGE_DIGEST,
    PHOTON_130_JAR_SHA256,
    canonical_sha256,
    file_sha256,
    verify_address_composite,
    verify_artifacts,
)

DEFAULT_SELECTION_POLICY = "primary-name-house-street-v1"
DEFAULT_NORMALIZATION_POLICY = "source-catalog-v1"
COMPONENT_MANIFEST_NAME = "schedule-component-manifest.json"
CATALOG_NAME = "address-catalog.sqlite"
ATTESTATION_NAME = "photon-import-attestation.json"


def check_pins(
    photon_jar_sha256: str,
    java_image_digest: str,
    selection_policy_version: str,
    normalization_policy_version: str,
) -> None:
    if photon_jar_sha256 != PHOTON_130_JAR_SHA256:
        raise ValueError("Photon JAR hash differs from the pinned Photon 1.3.0 artifact")
    if java_image_digest != JAVA_21_IMAGE_DIGEST:
        raise ValueError("Java image digest differs from the pinned Temurin 21 runtime")
    for version in (selection_policy_version, normalization_policy_version):
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Address policy versions must be non-empty strings")


def composite_manifest(
    component: dict,
    *,
    component_manifest_sha256: str,
    catalog_sha256: str,
    attestation: dict,
    attestation_sha256: str,
    photon_jar_sha256: str,
    java_image_digest: str,
    selection_policy_version: str = DEFAULT_SELECTION_POLICY,
    normalization_policy_version: str = DEFAULT_NORMALIZATION_POLICY,
) -> dict:
    """Return the composite manifest for a ready schedule component and sealed addresses."""
    check_pins(
        photon_jar_sha256, java_image_digest, selection_policy_version, normalization_policy_version
    )
    if component.get("state") != "ready":
        raise ValueError("Only a ready schedule generation can be composed")
    if attestation.get("catalogSha256") != catalog_sha256:
        raise ValueError("Sealed Photon attestation does not describe the selected catalog")
    component_id = component["generationId"]
    address_identity = canonical_sha256(
        {
            "scheduleComponentGenerationId": component_id,
            "sourceDumpSha256": attestation["sourceDumpSha256"],
            "catalogSha256": catalog_sha256,
            "attestationSha256": attestation_sha256,
            "selectionPolicyVersion": selection_policy_version,
            "normalizationPolicyVersion": normalization_policy_version,
            "photonJarSha256": photon_jar_sha256,
            "javaImageDigest": java_image_digest,
        }
    )
    generation_id = canonical_sha256(
        {
            "scheduleComponentGenerationId": component_id,
            "addressArtifactIdentity": address_identity,
        }
    )
    manifest = dict(component)
    manifest["scheduleComponentGenerationId"] = component_id
    manifest["generationId"] = generation_id
    manifest["scheduleComponentIdentity"] = component.get("identity")
    manifest["identity"] = {
        "scheduleComponentGenerationId": component_id,
        "addressArtifactIdentity": address_identity,
    }
    manifest["addressSearch"] = {
        "schemaVersion": 1,
        "provider": "photon",
        "artifactIdentity": address_identity,
        "catalogArtifact": "addressCatalog",
        "attestationArtifact": "addressAttestation",
        "selectionPolicyVersion": selection_policy_version,
        "normalizationPolicyVersion": normalization_policy_version,
        "photonJarSha256": photon_jar_sha256,
        "javaImageDigest": java_image_digest,
    }
    artifacts = dict(component["artifacts"])
    artifacts["scheduleComponentManifest"] = {
        "path": COMPONENT_MANIFEST_NAME,
        "sha256": component_manifest_sha256,
    }
    artifacts["addressCatalog"] = {"path": CATALOG_NAME, "sha256": catalog_sha256}
    artifacts["addressAttestation"] = {"path": ATTESTATION_NAME, "sha256": attestation_sha256}
    manifest["artifacts"] = artifacts
    return manifest


def write_manifest_exclusive(path: Path, manifest: dict) -> None:
    with path.open("xb") as stream:
        stream.write(json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8") + b"\n")


def compose_in_place(
    generation_dir: Path,
    *,
    photon_jar_sha256: str,
    java_image_digest: str,
    selection_policy_version: str = DEFAULT_SELECTION_POLICY,
    normalization_policy_version: str = DEFAULT_NORMALIZATION_POLICY,
    extra_manifest_fields: dict | None = None,
) -> Path:
    """Turn a ready schedule generation directory into a composite one without copying it.

    The directory must already contain ``address-catalog.sqlite`` and
    ``photon-import-attestation.json``. The schedule component manifest is either still
    ``manifest.json`` (copied to ``schedule-component-manifest.json``) or was already moved
    there by the orchestrator so that an incomplete generation has no ``manifest.json``. The
    composite ``manifest.json`` is verified in memory and only then written, so a failure never
    leaves an unverified composite.
    """
    generation = Path(generation_dir).resolve(strict=True)
    manifest_path = generation / "manifest.json"
    preserved = generation / COMPONENT_MANIFEST_NAME
    if manifest_path.exists() == preserved.exists():
        raise FileExistsError(
            "Expected exactly one of manifest.json (plain schedule generation) or "
            f"{COMPONENT_MANIFEST_NAME} (schedule component awaiting composition)"
        )
    source = manifest_path if manifest_path.exists() else preserved
    component = json.loads(source.read_text(encoding="utf-8"))
    if "addressSearch" in component:
        raise ValueError("Generation is already an address composite")
    verify_artifacts(generation, component)
    catalog, attestation_path = generation / CATALOG_NAME, generation / ATTESTATION_NAME
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    if source is manifest_path:
        shutil.copy2(manifest_path, preserved)
    manifest = composite_manifest(
        component,
        component_manifest_sha256=file_sha256(preserved),
        catalog_sha256=file_sha256(catalog),
        attestation=attestation,
        attestation_sha256=file_sha256(attestation_path),
        photon_jar_sha256=photon_jar_sha256,
        java_image_digest=java_image_digest,
        selection_policy_version=selection_policy_version,
        normalization_policy_version=normalization_policy_version,
    )
    for key, value in (extra_manifest_fields or {}).items():
        if key in manifest:
            raise ValueError(f"Extra manifest field {key!r} would replace a composite field")
        manifest[key] = value
    verify_artifacts(generation, manifest)
    verify_address_composite(generation, manifest)
    candidate = generation / "manifest.composite.tmp"
    write_manifest_exclusive(candidate, manifest)
    os.replace(candidate, manifest_path)  # replaces only the superseded component manifest
    return manifest_path
