"""Compose an address generation from preserved schedule and sealed Photon artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from opentransit.build.composite import (
    DEFAULT_NORMALIZATION_POLICY,
    DEFAULT_SELECTION_POLICY,
    check_pins,
    composite_manifest,
    write_manifest_exclusive,
)
from opentransit.core.artifacts import verify_address_composite, verify_artifacts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compose_address_generation(
    schedule_generation: Path,
    catalog_path: Path,
    attestation_path: Path,
    output_dir: Path,
    *,
    photon_jar_sha256: str,
    java_image_digest: str,
    selection_policy_version: str = DEFAULT_SELECTION_POLICY,
    normalization_policy_version: str = DEFAULT_NORMALIZATION_POLICY,
) -> Path:
    """Create a new immutable generation without rebuilding or modifying schedule inputs."""
    source = Path(schedule_generation).resolve(strict=True)
    output = Path(output_dir).resolve()
    catalog = Path(catalog_path).resolve(strict=True)
    attestation = Path(attestation_path).resolve(strict=True)
    if output == source or source in output.parents or output in source.parents:
        raise ValueError("Composite output and schedule component directories must be disjoint")
    check_pins(
        photon_jar_sha256, java_image_digest, selection_policy_version, normalization_policy_version
    )

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

    manifest = composite_manifest(
        component,
        component_manifest_sha256=_sha256(output / "schedule-component-manifest.json"),
        catalog_sha256=catalog_hash,
        attestation=attestation_data,
        attestation_sha256=attestation_hash,
        photon_jar_sha256=photon_jar_sha256,
        java_image_digest=java_image_digest,
        selection_policy_version=selection_policy_version,
        normalization_policy_version=normalization_policy_version,
    )
    manifest_path = output / "manifest.json"
    write_manifest_exclusive(manifest_path, manifest)
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
    parser.add_argument("--selection-policy-version", default=DEFAULT_SELECTION_POLICY)
    parser.add_argument("--normalization-policy-version", default=DEFAULT_NORMALIZATION_POLICY)
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
