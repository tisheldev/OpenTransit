"""Compose an address generation from preserved schedule and sealed Photon artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from opentransit.core.artifacts import (
    JAVA_21_IMAGE_DIGEST,
    PHOTON_130_JAR_SHA256,
    verify_address_composite,
    verify_artifacts,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def compose_address_generation(
    schedule_generation: Path,
    catalog_path: Path,
    attestation_path: Path,
    output_dir: Path,
    *,
    photon_jar_sha256: str,
    java_image_digest: str,
    selection_policy_version: str = "primary-name-house-street-v1",
    normalization_policy_version: str = "source-catalog-v1",
) -> Path:
    """Create a new immutable generation without rebuilding or modifying schedule inputs."""
    source = Path(schedule_generation).resolve(strict=True)
    output = Path(output_dir).resolve()
    catalog = Path(catalog_path).resolve(strict=True)
    attestation = Path(attestation_path).resolve(strict=True)
    if output == source or source in output.parents or output in source.parents:
        raise ValueError("Composite output and schedule component directories must be disjoint")
    if photon_jar_sha256 != PHOTON_130_JAR_SHA256:
        raise ValueError("Photon JAR hash differs from the pinned Photon 1.3.0 artifact")
    if java_image_digest != JAVA_21_IMAGE_DIGEST:
        raise ValueError("Java image digest differs from the pinned Temurin 21 runtime")
    for version in (selection_policy_version, normalization_policy_version):
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Address policy versions must be non-empty strings")

    source_manifest_path = source / "manifest.json"
    component = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if component.get("state") != "ready":
        raise ValueError("Only a ready schedule generation can be composed")
    verify_artifacts(source, component)
    attestation_data = json.loads(attestation.read_text(encoding="utf-8"))
    catalog_hash = _sha256(catalog)
    attestation_hash = _sha256(attestation)
    if attestation_data.get("catalogSha256") != catalog_hash:
        raise ValueError("Sealed Photon attestation does not describe the selected catalog")

    # Exclusive creation and preserved partial output make failed attempts inspectable.
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(source_manifest_path, output / "schedule-component-manifest.json")
    shutil.copy2(source / "config.yml", output / "config.yml")
    shutil.copy2(source / "reference.sqlite", output / "reference.sqlite")
    shutil.copytree(source / "motis", output / "motis")
    shutil.copy2(catalog, output / "address-catalog.sqlite")
    shutil.copy2(attestation, output / "photon-import-attestation.json")

    component_id = component["generationId"]
    address_identity = _canonical_sha256(
        {
            "scheduleComponentGenerationId": component_id,
            "sourceDumpSha256": attestation_data["sourceDumpSha256"],
            "catalogSha256": catalog_hash,
            "attestationSha256": attestation_hash,
            "selectionPolicyVersion": selection_policy_version,
            "normalizationPolicyVersion": normalization_policy_version,
            "photonJarSha256": photon_jar_sha256,
            "javaImageDigest": java_image_digest,
        }
    )
    generation_id = _canonical_sha256(
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
        "path": "schedule-component-manifest.json",
        "sha256": _sha256(output / "schedule-component-manifest.json"),
    }
    artifacts["addressCatalog"] = {
        "path": "address-catalog.sqlite",
        "sha256": catalog_hash,
    }
    artifacts["addressAttestation"] = {
        "path": "photon-import-attestation.json",
        "sha256": attestation_hash,
    }
    manifest["artifacts"] = artifacts
    manifest_path = output / "manifest.json"
    with manifest_path.open("xb") as stream:
        stream.write(json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8") + b"\n")
    verify_artifacts(output, manifest)
    verify_address_composite(output, manifest)
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schedule_generation", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("attestation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--photon-jar-sha256", required=True)
    parser.add_argument("--java-image-digest", required=True)
    parser.add_argument("--selection-policy-version", default="primary-name-house-street-v1")
    parser.add_argument("--normalization-policy-version", default="source-catalog-v1")
    args = parser.parse_args()
    result = compose_address_generation(
        args.schedule_generation,
        args.catalog,
        args.attestation,
        args.output,
        photon_jar_sha256=args.photon_jar_sha256,
        java_image_digest=args.java_image_digest,
        selection_policy_version=args.selection_policy_version,
        normalization_policy_version=args.normalization_policy_version,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
