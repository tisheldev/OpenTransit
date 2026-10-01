import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest
from test_reference_api import reference_client

from opentransit.api.lifecycle import _load_address_provider
from opentransit.build.address_catalog import build_address_catalog
from opentransit.config import Settings
from opentransit.runtime import AddressProviderBinding, RuntimeSnapshot


def test_address_provider_binding_pins_origin_and_artifact_identity():
    class Catalog:
        def lookup(self, osm_type, full_osm_id):
            return None

        def close(self):
            pass

    class Client:
        base_url = "http://127.0.0.1:2322"

        async def aclose(self):
            pass

    client = Client()
    binding = AddressProviderBinding(
        client, "http://127.0.0.1:2322", "a" * 64, "photon-index-uuid", Catalog()
    )
    assert binding.client is client
    with pytest.raises(ValueError, match="fixed loopback"):
        AddressProviderBinding(
            client, "http://example.com:2322", "a" * 64, "photon-index-uuid", Catalog()
        )
    with pytest.raises(ValueError, match="SHA-256"):
        AddressProviderBinding(
            client, "http://127.0.0.1:2322", "not-a-hash", "photon-index-uuid", Catalog()
        )


@pytest.mark.parametrize(
    ("mismatch", "message"),
    [
        ("uuid", "UUID or immutable write block"),
        ("write_block", "UUID or immutable write block"),
        ("count", "document count or shard status"),
    ],
)
def test_address_binding_rejects_live_index_mismatch(tmp_path, monkeypatch, mismatch, message):
    import opentransit.api.lifecycle as lifecycle_module

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"addressSearch": {"provider": "photon"}}))
    expected = {
        "addressArtifactIdentity": "a" * 64,
        "indexUuid": "index-uuid",
        "clusterUuid": "cluster-uuid",
        "documentCount": 1,
        "sourceDumpSha256": "b" * 64,
        "probes": [{"osmType": "N", "osmId": "7", "lat": 32.1, "lon": 34.8}],
    }
    monkeypatch.setattr(lifecycle_module, "verify_address_composite", lambda *_: expected)

    class Catalog:
        closed = False

        def __init__(self, path, expected_sha256):
            assert expected_sha256 == expected["sourceDumpSha256"]

        def lookup(self, osm_type, osm_id):
            assert (osm_type, osm_id) == ("N", "7")
            return {
                "object_type": "N",
                "object_id": 7,
                "address_type": "house",
                "centroid": [34.8, 32.1],
                "housenumber": "10",
            }

        def close(self):
            self.closed = True

    monkeypatch.setattr(lifecycle_module, "AddressCatalog", Catalog)

    def respond(request):
        if request.url.path == "/":
            return httpx.Response(200, json={"cluster_uuid": "cluster-uuid"})
        if request.url.path == "/photon/_settings":
            uuid = "other-uuid" if mismatch == "uuid" else "index-uuid"
            blocked = "false" if mismatch == "write_block" else "true"
            return httpx.Response(
                200,
                json={"photon": {"settings": {"index.uuid": uuid, "index.blocks.write": blocked}}},
            )
        if request.url.path == "/photon/_count":
            count = 2 if mismatch == "count" else 1
            return httpx.Response(
                200, json={"count": count, "_shards": {"failed": 0, "successful": 5}}
            )
        if request.url.path == "/photon/_doc/N7":
            return httpx.Response(
                200,
                json={
                    "found": True,
                    "_source": {
                        "osm_id": 7,
                        "osm_type": "N",
                        "type": "house",
                        "housenumber": "10",
                        "coordinate": {"lat": 32.1, "lon": 34.8},
                    },
                },
            )
        return httpx.Response(404)

    settings = Settings(
        manifest_path,
        photon_url="http://127.0.0.1:2322",
        photon_admin_url="http://127.0.0.1:9201",
    )
    with pytest.raises(ValueError, match=message):
        asyncio.run(_load_address_provider(manifest_path, settings, httpx.MockTransport(respond)))


def test_address_binding_accepts_real_catalog_payload_and_source_document_ids(
    tmp_path, monkeypatch
):
    import opentransit.api.lifecycle as lifecycle_module

    dump = tmp_path / "source-dump.jsonl"
    source_pbf_sha = "c" * 64
    dump.write_text(
        json.dumps(
            {
                "type": "NominatimDumpFile",
                "content": {
                    "version": "0.1.0",
                    "generator": "OpenTransit source-context enrichment",
                    "database_version": (
                        f"source OSM PBF SHA-256 {source_pbf_sha}; context hash pinned"
                    ),
                },
            }
        )
        + "\n"
        + json.dumps(
            {
                "type": "Place",
                "content": [
                    {
                        "place_id": "N300",
                        "object_type": "N",
                        "object_id": 300,
                        "osm_key": "addr:housenumber",
                        "osm_value": "24",
                        "address_type": "house",
                        "name": {"name": "Example"},
                        "extra": {"addr:housenumber": "24"},
                        "address": {"street": "Example Street"},
                        "centroid": [34.78, 32.08],
                        "housenumber": "24",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    source_dump_sha = __import__("hashlib").sha256(dump.read_bytes()).hexdigest()
    catalog_path = tmp_path / "address-catalog.sqlite"
    build_address_catalog(dump, catalog_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"addressSearch": {"provider": "photon"}}))
    expected = {
        "addressArtifactIdentity": "a" * 64,
        "indexUuid": "index-uuid",
        "clusterUuid": "cluster-uuid",
        "documentCount": 1,
        "sourceDumpSha256": source_dump_sha,
        "probes": [{"osmType": "N", "osmId": "300", "lat": 32.08, "lon": 34.78}],
    }
    monkeypatch.setattr(lifecycle_module, "verify_address_composite", lambda *_: expected)

    def respond(request):
        if request.url.path == "/":
            return httpx.Response(200, json={"cluster_uuid": "cluster-uuid"})
        if request.url.path == "/photon/_settings":
            return httpx.Response(
                200,
                json={
                    "photon": {
                        "settings": {"index.uuid": "index-uuid", "index.blocks.write": "true"}
                    }
                },
            )
        if request.url.path == "/photon/_count":
            return httpx.Response(200, json={"count": 1, "_shards": {"failed": 0, "successful": 5}})
        if request.url.path == "/photon/_doc/N300":
            return httpx.Response(
                200,
                json={
                    "found": True,
                    "_source": {
                        "osm_id": 300,
                        "osm_type": "N",
                        "type": "house",
                        "housenumber": "24",
                        "coordinate": {"lat": 32.08, "lon": 34.78},
                    },
                },
            )
        return httpx.Response(404)

    settings = Settings(
        manifest_path,
        photon_url="http://127.0.0.1:2322",
        photon_admin_url="http://127.0.0.1:9201",
    )
    provider = asyncio.run(
        _load_address_provider(manifest_path, settings, httpx.MockTransport(respond))
    )
    assert isinstance(provider, AddressProviderBinding)
    assert provider.catalog.lookup("N", "300")["object_id"] == 300
    asyncio.run(provider.client.aclose())
    provider.catalog.close()


def test_managed_generation_requires_matching_probe_and_all_artifacts(manifest, engine_route):
    with reference_client(manifest, engine_route) as client:
        adapter = client.app.state.snapshot.motis
        assert not RuntimeSnapshot.load(manifest, adapter).routing_verified
        probe = manifest.parent / "probe.json"
        assert RuntimeSnapshot.load(manifest, adapter, probe_path=probe).routing_verified
        info = json.loads(probe.read_text())
        info["engineOrigin"] = "http://127.0.0.1:58082"
        probe.write_text(json.dumps(info))
        assert not RuntimeSnapshot.load(manifest, adapter, probe_path=probe).routing_verified
        (manifest.parent / "config.yml").write_text("corrupted config")
        with pytest.raises(ValueError):
            RuntimeSnapshot.load(manifest, adapter, probe_path=probe)


def test_composite_generation_refuses_to_start_without_address_provider(manifest, engine_route):
    with reference_client(manifest, engine_route) as client:
        snapshot = client.app.state.snapshot
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["addressSearch"] = {"schemaVersion": 1, "provider": "photon"}
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="requires a verified address provider"):
            RuntimeSnapshot.load(manifest, snapshot.motis)


def test_same_input_pair_check_renews_source_age_without_mutating_manifest(manifest, engine_route):
    with reference_client(manifest, engine_route) as client:
        adapter = client.app.state.snapshot.motis
        original = manifest.read_bytes()
        info = json.loads(original)
        digest = info["inputs"]["israel-public-transportation.zip"]["sha256"]
        info["inputs"]["TripIdToDate.zip"] = {"sha256": "b" * 64}
        manifest.write_text(json.dumps(info))
        before = manifest.read_bytes()
        evidence = {
            "pairedValidation": "passed",
            "validation": {"valid": True},
            "validatedAt": "2026-10-02T09:02:00+00:00",
            "sources": {
                "gtfs": {
                    "status": "unchanged",
                    "sha256": digest,
                    "checkedAt": "2026-10-02T09:00:00+00:00",
                },
                "trip_id_to_date": {
                    "status": "unchanged",
                    "sha256": "b" * 64,
                    "checkedAt": "2026-10-02T09:01:00+00:00",
                },
            },
        }
        check = manifest.parent / "check.json"
        check.write_text(json.dumps(evidence))
        snapshot = RuntimeSnapshot.load(manifest, adapter, source_check_path=check)
        assert snapshot.generation.id == info["generationId"]
        now = datetime(2026, 10, 2, 10, tzinfo=UTC)
        assert snapshot.generation.freshness(now) == "current"
        assert manifest.read_bytes() == before
        for mutation in ("failed", "wrong_hash"):
            if mutation == "failed":
                evidence["pairedValidation"] = "failed"
            else:
                evidence["pairedValidation"] = "passed"
                evidence["sources"]["gtfs"]["sha256"] = "c" * 64
            check.write_text(json.dumps(evidence))
            with pytest.raises(ValueError):
                RuntimeSnapshot.load(manifest, adapter, source_check_path=check)


def test_captured_snapshot_is_used_even_if_current_changes_during_engine_await(
    client_factory,
    query,
    engine_route,
):
    seen = []

    def engine(request):
        snapshot = client.app.state.snapshot
        seen.append(snapshot.generation.id)
        if len(seen) == 1:
            # Simulate publication while the engine request is in progress.
            client.app.state.snapshot = replace(
                snapshot,
                generation=replace(snapshot.generation, id="next-generation"),
            )
        return httpx.Response(200, json=engine_route)

    with client_factory(engine) as client:
        first = client.post("/v1/journeys", json=query).json()
        second = client.post("/v1/journeys", json=query).json()
    assert first["meta"]["generationId"] == "synthetic-test"
    assert second["meta"]["generationId"] == "next-generation"
    assert seen == ["synthetic-test", "next-generation"]
