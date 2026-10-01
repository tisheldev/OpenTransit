"""Verify complete managed generation artifacts before candidate serving."""

import hashlib
import json
import re
from pathlib import Path

PHOTON_130_JAR_SHA256 = "a89707c0045e4807b2a1180e132e68e108d998709f48b6c94b98a6e281f571a5"
JAVA_21_IMAGE_DIGEST = "sha256:628467024d428251da635661936d6180717b1ac1119d41c76d28a03b7293c43c"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifacts(directory: Path, manifest: dict | None = None) -> dict:
    directory = directory.resolve()
    manifest = manifest or json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest["artifacts"]
    for key, name in (("reference", "reference.sqlite"), ("config", "config.yml")):
        if artifacts[key].get("path", name) != name:
            raise ValueError("Unsupported artifact path")
        path = directory / name
        if path.is_symlink() or file_sha256(path) != artifacts[key]["sha256"]:
            raise ValueError("Artifact checksum differs from the manifest")
    graph = artifacts["motis"]
    if graph.get("path") != "motis":
        raise ValueError("Unsupported graph artifact path")
    graph_dir = directory / "motis"
    if graph_dir.is_symlink():
        raise ValueError("Graph directory may not redirect to another generation")
    entries = []
    for path in sorted(graph_dir.rglob("*")):
        if path.is_symlink():
            raise ValueError("Graph artifact may not redirect to another generation")
        if path.is_file() and path.stat().st_size:
            entries.append(
                {
                    "path": path.relative_to(graph_dir).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
    if not entries or entries != graph["files"]:
        raise ValueError("Graph artifact set differs from the manifest")
    digest = hashlib.sha256()
    for item in entries:
        digest.update(f"{item['path']}\0{item['bytes']}\0{item['sha256']}\n".encode())
    if digest.hexdigest() != graph["sha256"]:
        raise ValueError("Graph tree checksum differs from the manifest")
    verified = {
        "generationId": manifest.get("generationId"),
        "engineDigest": manifest.get("engineDigest"),
        "graphTreeSha256": graph["sha256"],
        "configSha256": artifacts["config"]["sha256"],
        "referenceSha256": artifacts["reference"]["sha256"],
    }
    if manifest.get("addressSearch") is not None:
        verified.update(verify_address_composite(directory, manifest))
    return verified


def _canonical_sha256(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def verify_address_composite(directory: Path, manifest: dict) -> dict:
    """Verify a composite generation's preserved schedule and sealed address inputs."""
    directory = Path(directory).resolve()
    component_id = manifest.get("scheduleComponentGenerationId")
    if not isinstance(component_id, str) or not re.fullmatch(r"[a-f0-9]{64}", component_id):
        raise ValueError("Composite generation schedule component ID is invalid")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("Composite generation artifacts are missing")

    component = artifacts.get("scheduleComponentManifest")
    if (
        not isinstance(component, dict)
        or component.get("path") != "schedule-component-manifest.json"
    ):
        raise ValueError("Composite generation must preserve its schedule component manifest")
    component_path = directory / "schedule-component-manifest.json"
    if component_path.is_symlink() or file_sha256(component_path) != component.get("sha256"):
        raise ValueError("Schedule component manifest checksum differs")
    original = json.loads(component_path.read_text(encoding="utf-8"))
    if original.get("generationId") != component_id:
        raise ValueError("Copied schedule component manifest has a different component ID")
    for key in ("engineDigest", "inputs", "coverage", "configSha256"):
        if original.get(key) != manifest.get(key):
            raise ValueError(f"Composite generation changed its schedule component {key}")
    for key in ("motis", "config", "reference"):
        if original.get("artifacts", {}).get(key) != artifacts.get(key):
            raise ValueError(f"Composite generation changed its schedule component {key} artifact")

    address = manifest.get("addressSearch")
    if (
        not isinstance(address, dict)
        or address.get("schemaVersion") != 1
        or address.get("provider") != "photon"
    ):
        raise ValueError("Composite address provider declaration is invalid")
    fixed_artifacts = (
        (address.get("catalogArtifact"), "addressCatalog", "address-catalog.sqlite"),
        (
            address.get("attestationArtifact"),
            "addressAttestation",
            "photon-import-attestation.json",
        ),
    )
    verified = {}
    for declared_key, artifact_key, expected_path in fixed_artifacts:
        if declared_key != artifact_key:
            raise ValueError("Composite address artifact key is invalid")
        artifact = artifacts.get(artifact_key)
        if not isinstance(artifact, dict) or artifact.get("path") != expected_path:
            raise ValueError("Composite address artifact path is invalid")
        path = directory / expected_path
        if path.is_symlink() or file_sha256(path) != artifact.get("sha256"):
            raise ValueError(f"Composite address artifact checksum differs: {artifact_key}")
        verified[artifact_key] = (path, artifact["sha256"])

    attestation = json.loads(verified["addressAttestation"][0].read_text(encoding="utf-8"))
    catalog_sha = verified["addressCatalog"][1]
    if (
        attestation.get("schemaVersion") != 1
        or attestation.get("provider") != "photon"
        or attestation.get("catalogSha256") != catalog_sha
        or not re.fullmatch(r"[a-f0-9]{64}", str(attestation.get("sourceDumpSha256", "")))
        or not isinstance(attestation.get("indexUuid"), str)
        or not isinstance(attestation.get("clusterUuid"), str)
        or not attestation.get("indexUuid")
        or not attestation.get("clusterUuid")
        or attestation.get("indexName") != "photon"
        or isinstance(attestation.get("documentCount"), bool)
        or not isinstance(attestation.get("documentCount"), int)
        or attestation["documentCount"] <= 0
        or attestation.get("indexWriteBlocked") is not True
        or not attestation.get("sealedAt")
        or not attestation.get("importedAt")
        or not isinstance(attestation.get("probes"), list)
        or not attestation["probes"]
    ):
        raise ValueError("Photon import attestation is incomplete or not sealed")
    if address.get("photonJarSha256") != PHOTON_130_JAR_SHA256:
        raise ValueError("Photon JAR hash differs from the pinned Photon 1.3.0 artifact")
    java_digest = address.get("javaImageDigest")
    if java_digest != JAVA_21_IMAGE_DIGEST:
        raise ValueError("Java image digest differs from the pinned Temurin 21 runtime")
    for key in ("selectionPolicyVersion", "normalizationPolicyVersion"):
        if not isinstance(address.get(key), str) or not address[key]:
            raise ValueError(f"Address search {key} is required")

    semantic_identity = _canonical_sha256(
        {
            "scheduleComponentGenerationId": component_id,
            "sourceDumpSha256": attestation["sourceDumpSha256"],
            "catalogSha256": catalog_sha,
            "attestationSha256": verified["addressAttestation"][1],
            "selectionPolicyVersion": address["selectionPolicyVersion"],
            "normalizationPolicyVersion": address["normalizationPolicyVersion"],
            "photonJarSha256": address["photonJarSha256"],
            "javaImageDigest": java_digest,
        }
    )
    if address.get("artifactIdentity") != semantic_identity:
        raise ValueError("Address artifact identity does not bind the sealed input set")
    public_generation_id = _canonical_sha256(
        {
            "scheduleComponentGenerationId": component_id,
            "addressArtifactIdentity": semantic_identity,
        }
    )
    if manifest.get("generationId") != public_generation_id:
        raise ValueError("Composite generation ID does not bind its schedule and address artifacts")
    return {
        "scheduleComponentGenerationId": component_id,
        "generationId": public_generation_id,
        "addressArtifactIdentity": semantic_identity,
        "sourceDumpSha256": attestation["sourceDumpSha256"],
        "catalogSha256": catalog_sha,
        "attestationSha256": verified["addressAttestation"][1],
        "indexUuid": attestation["indexUuid"],
        "clusterUuid": attestation["clusterUuid"],
        "documentCount": attestation["documentCount"],
        "probes": attestation["probes"],
    }


canonical_sha256 = _canonical_sha256
