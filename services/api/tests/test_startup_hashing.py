"""API startup reads each generation artifact's bytes once and still refuses tampered ones.

The reference database is about 3 GB; every extra full read cost minutes on the Windows bind
mount. A synthetic composite (schedule + sealed address) generation is used; nothing is live.
"""

import asyncio
import json
from collections import Counter
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from test_probe_composite_freshness import ENGINE, PINNED_NOW, _pinned_probe

import opentransit.api.lifecycle as lifecycle_module
from opentransit.api.app import create_app
from opentransit.api.lifecycle import _load_address_provider
from opentransit.build.activation import read_binding, write_binding
from opentransit.build.generations import CANONICAL_INPUTS
from opentransit.config import Settings
from opentransit.core.generation import Generation
from opentransit.motis import MotisClient
from opentransit.runtime import RuntimeSnapshot

pytest_plugins = ["test_probe_composite_freshness"]

PHOTON = "http://127.0.0.1:2322"
PHOTON_ADMIN = "http://127.0.0.1:9201"


def _artifact_paths(directory: Path) -> list[Path]:
    fixed = (
        "reference.sqlite",
        "config.yml",
        "schedule-component-manifest.json",
        "address-catalog.sqlite",
        "photon-import-attestation.json",
    )
    graph = [path for path in sorted((directory / "motis").rglob("*")) if path.is_file()]
    return [(directory / name).resolve() for name in fixed] + [path.resolve() for path in graph]


def _count_binary_reads(monkeypatch) -> Counter:
    reads = Counter()
    original = Path.open

    def spy(self, mode="r", *args, **kwargs):
        if "r" in mode and "b" in mode:
            reads[Path(self).resolve()] += 1
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spy)
    return reads


def _stub_catalog(monkeypatch, directory: Path) -> None:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    attestation = json.loads(
        (directory / "photon-import-attestation.json").read_text(encoding="utf-8")
    )

    class Catalog:
        source_dump_sha256 = attestation["sourceDumpSha256"]
        source_pbf_sha256 = manifest["inputs"][CANONICAL_INPUTS["osm"]]["sha256"]
        record_count = attestation["documentCount"]

        def __init__(self, path, expected_dump_sha256):
            assert expected_dump_sha256 == self.source_dump_sha256

        def lookup(self, osm_type, osm_id):
            return {
                "object_type": osm_type,
                "object_id": int(osm_id),
                "address_type": "house",
                "centroid": [34.8, 32.1],
            }

        def close(self):
            pass

    # The fixture's catalog bytes are opaque; its hash is still verified like a real one.
    monkeypatch.setattr(lifecycle_module, "AddressCatalog", Catalog)


def _respond(request):
    path = request.url.path
    if request.url.port == 9201:
        if path == "/":
            return httpx.Response(200, json={"cluster_uuid": "cluster-uuid"})
        if path == "/photon/_settings":
            settings = {"index.uuid": "index-uuid", "index.blocks.write": "true"}
            return httpx.Response(200, json={"photon": {"settings": settings}})
        if path == "/photon/_count":
            return httpx.Response(200, json={"count": 1, "_shards": {"failed": 0, "successful": 1}})
        if path == "/photon/_doc/N7":
            source = {
                "osm_id": 7,
                "osm_type": "N",
                "type": "house",
                "coordinate": {"lat": 32.1, "lon": 34.8},
            }
            return httpx.Response(200, json={"found": True, "_source": source})
    if request.url.port == 2322:
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})
    return httpx.Response(404)


def _client(directory: Path) -> TestClient:
    settings = Settings(
        directory / "manifest.json",
        motis_url=ENGINE,
        probe_path=directory / "probe.json",
        photon_url=PHOTON,
        photon_admin_url=PHOTON_ADMIN,
        warmup_attempts=1,
        warmup_retry_seconds=0,
    )
    return TestClient(
        create_app(settings, transport=httpx.MockTransport(_respond), clock=lambda: PINNED_NOW)
    )


def test_startup_reads_each_generation_artifact_once(composite_generation, monkeypatch):
    directory, _ = composite_generation
    _pinned_probe(directory)
    _stub_catalog(monkeypatch, directory)
    reads = _count_binary_reads(monkeypatch)

    with _client(directory) as client:
        snapshot = client.app.state.snapshot
        assert snapshot is not None
        assert snapshot.generation.id == Generation.load(directory / "manifest.json").id
        assert snapshot.routing_verified

    counts = {path.name: reads[path] for path in _artifact_paths(directory)}
    assert counts == {path.name: 1 for path in _artifact_paths(directory)}


@pytest.mark.parametrize(
    "artifact",
    [
        "reference.sqlite",
        "config.yml",
        "schedule-component-manifest.json",
        "address-catalog.sqlite",
        "photon-import-attestation.json",
        "motis/graph.bin",
    ],
)
def test_tampered_artifact_still_fails_startup_and_readiness(
    composite_generation, monkeypatch, artifact
):
    directory, _ = composite_generation
    _pinned_probe(directory)
    _stub_catalog(monkeypatch, directory)
    target = directory / artifact
    target.chmod(0o644)  # the built reference is read-only
    with target.open("ab") as stream:
        stream.write(b"\0")

    with _client(directory) as client:
        assert client.app.state.snapshot is None
        response = client.get("/readyz")
    assert response.status_code == 503
    assert {"condition": "generation", "reason": "UNAVAILABLE"} in response.json()["errors"]


def test_verified_binding_digests_are_reused_by_the_candidate_snapshot(
    composite_generation, monkeypatch, tmp_path
):
    """A managed reload verifies the binding, then builds the candidate from the same bytes."""
    directory, _ = composite_generation
    _pinned_probe(directory)
    _stub_catalog(monkeypatch, directory)
    source_check = directory / "source-check.json"
    source_check.write_text("{}\n", encoding="utf-8")
    binding_path = tmp_path / "binding.json"
    write_binding(
        binding_path,
        {
            "generationDir": str(directory.resolve()),
            "engineOrigin": ENGINE,
            "probePath": str((directory / "probe.json").resolve()),
            "sourceCheckPath": str(source_check.resolve()),
            "activationToken": "token-one",
            "generationId": Generation.load(directory / "manifest.json").id,
            "photonOrigin": PHOTON,
            "photonAdminOrigin": PHOTON_ADMIN,
        },
    )
    reads = _count_binary_reads(monkeypatch)

    binding = read_binding(binding_path, tmp_path)
    manifest_path = binding.generation_dir / "manifest.json"
    settings = Settings(manifest_path)
    transport = httpx.MockTransport(_respond)
    digests = binding.artifact_digests
    provider = asyncio.run(
        _load_address_provider(
            manifest_path,
            settings,
            transport,
            photon_url=binding.photon_origin,
            photon_admin_url=binding.photon_admin_origin,
            digests=digests,
        )
    )
    engine = httpx.AsyncClient(base_url=ENGINE, transport=transport)
    try:
        snapshot = RuntimeSnapshot.load(
            manifest_path,
            MotisClient(engine),
            probe_path=binding.probe_path,
            address_provider=provider,
            digests=digests,
        )
        assert snapshot.routing_verified
    finally:
        asyncio.run(engine.aclose())
        asyncio.run(provider.client.aclose())

    counts = {path.name: reads[path] for path in _artifact_paths(directory)}
    assert counts == {path.name: 1 for path in _artifact_paths(directory)}
