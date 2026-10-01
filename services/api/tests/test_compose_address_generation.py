import hashlib
import json
from pathlib import Path

from opentransit.core.artifacts import JAVA_21_IMAGE_DIGEST, PHOTON_130_JAR_SHA256
from tools.compose_address_generation import compose_address_generation


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree(root: Path) -> dict:
    entries = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.stat().st_size
    ]
    digest = hashlib.sha256()
    for item in entries:
        digest.update(f"{item['path']}\0{item['bytes']}\0{item['sha256']}\n".encode())
    return {"path": "motis", "sha256": digest.hexdigest(), "files": entries}


def test_composition_reuses_schedule_artifacts_and_derives_new_public_identity(tmp_path):
    component_dir = tmp_path / "schedule"
    (component_dir / "motis").mkdir(parents=True)
    (component_dir / "motis" / "graph.bin").write_bytes(b"preserved graph")
    (component_dir / "config.yml").write_text("schedule: preserved\n", encoding="utf-8")
    (component_dir / "reference.sqlite").write_bytes(b"preserved reference bytes")
    (component_dir / "inputs").mkdir()
    component_id = "1" * 64
    source_hash = "2" * 64
    osm_hash = "3" * 64
    component_manifest = {
        "schemaVersion": 1,
        "state": "ready",
        "generationId": component_id,
        "mode": "real",
        "engineDigest": "sha256:" + "4" * 64,
        "inputs": {
            "israel-public-transportation.zip": {"sha256": source_hash},
            "israel-and-palestine-latest.osm.pbf": {"sha256": osm_hash},
        },
        "coverage": {"from": "2026-01-01T00:00:00Z", "until": "2026-02-01T00:00:00Z"},
        "configSha256": _sha(component_dir / "config.yml"),
        "identity": {"schedule": component_id},
        "artifacts": {
            "reference": {
                "path": "reference.sqlite",
                "sha256": _sha(component_dir / "reference.sqlite"),
            },
            "config": {
                "path": "config.yml",
                "sha256": _sha(component_dir / "config.yml"),
            },
            "motis": _tree(component_dir / "motis"),
        },
    }
    (component_dir / "manifest.json").write_text(
        json.dumps(component_manifest, sort_keys=True), encoding="utf-8"
    )

    catalog = tmp_path / "address-catalog.sqlite"
    catalog.write_bytes(b"synthetic catalog payload")
    attestation = tmp_path / "attestation.json"
    attestation_data = {
        "schemaVersion": 1,
        "provider": "photon",
        "sourceDumpSha256": "5" * 64,
        "catalogSha256": _sha(catalog),
        "indexName": "photon",
        "indexUuid": "index-uuid",
        "clusterUuid": "cluster-uuid",
        "documentCount": 1,
        "importedAt": "2026-10-01T00:00:00Z",
        "sealedAt": "2026-10-01T00:01:00Z",
        "indexWriteBlocked": True,
        "probes": [{"osmType": "N", "osmId": "7", "lat": 32.1, "lon": 34.8}],
    }
    attestation.write_text(json.dumps(attestation_data, sort_keys=True), encoding="utf-8")
    output = tmp_path / "composite"
    manifest_path = compose_address_generation(
        component_dir,
        catalog,
        attestation,
        output,
        photon_jar_sha256=PHOTON_130_JAR_SHA256,
        java_image_digest=JAVA_21_IMAGE_DIGEST,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["generationId"] != component_id
    assert manifest["scheduleComponentGenerationId"] == component_id
    assert (output / "schedule-component-manifest.json").read_bytes() == (
        component_dir / "manifest.json"
    ).read_bytes()
    assert (output / "reference.sqlite").read_bytes() == (
        component_dir / "reference.sqlite"
    ).read_bytes()
    assert (output / "motis" / "graph.bin").read_bytes() == b"preserved graph"
