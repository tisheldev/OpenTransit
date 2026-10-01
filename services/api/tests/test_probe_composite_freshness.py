"""Probe identity for composite (schedule + address) generations and freshness boundaries.

The startup verifier (`opentransit probe`) must accept exactly the source-freshness
states `/readyz` serves (current, aging, stale) and reject what it rejects (expired), and it
must verify a composite generation's reference with the schedule component ID while recording
both the public composite ID and the component ID. A fixed clock is used throughout.
"""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_generation_probe import (
    _probe,
    journey,
    response_payload,
)

from opentransit.build.generations import CANONICAL_INPUTS
from opentransit.core.artifacts import JAVA_21_IMAGE_DIGEST, PHOTON_130_JAR_SHA256
from opentransit.core.generation import Generation
from opentransit.motis import MotisClient
from opentransit.runtime import AddressProviderBinding, RuntimeSnapshot

pytest_plugins = ["test_generation_probe"]

PINNED_NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
ENGINE = "http://127.0.0.1:58082"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def _pin_clock(generation_dir, age):
    """Make the source check exactly ``age`` old at PINNED_NOW, with coverage around it."""
    path = generation_dir / "manifest.json"
    data = _read(path)
    data["validatedAt"] = data["sourceCheckedAt"] = (PINNED_NOW - age).isoformat()
    data["coverage"] = {
        "from": (PINNED_NOW - timedelta(days=30)).isoformat(),
        "until": (PINNED_NOW + timedelta(days=30)).isoformat(),
    }
    _write(path, data)


def _pinned_probe(generation_dir):
    ok = httpx.MockTransport(lambda request: httpx.Response(200, json=response_payload()))
    return _probe(
        generation_dir,
        ENGINE,
        [journey(departure=PINNED_NOW + timedelta(minutes=1))],
        transport=ok,
        now=PINNED_NOW,
    )


# (age of the recorded source check at the fixed clock, state, serviceable per /readyz)
FRESHNESS_BOUNDARIES = [
    pytest.param(timedelta(minutes=-4, seconds=-59), "current", True, id="future-inside"),
    pytest.param(timedelta(minutes=-5, seconds=-1), "expired", False, id="future-outside"),
    pytest.param(timedelta(hours=29, minutes=59, seconds=59), "current", True, id="current-edge"),
    pytest.param(timedelta(hours=30), "aging", True, id="aging-start"),
    pytest.param(timedelta(hours=47, minutes=59, seconds=59), "aging", True, id="aging-edge"),
    pytest.param(timedelta(hours=48), "stale", True, id="stale-start"),
    pytest.param(
        timedelta(days=6, hours=23, minutes=59, seconds=59), "stale", True, id="stale-edge"
    ),
    pytest.param(timedelta(days=7), "expired", False, id="expired-start"),
    pytest.param(timedelta(days=9), "expired", False, id="expired-well-past"),
]


@pytest.mark.parametrize(("age", "state", "serviceable"), FRESHNESS_BOUNDARIES)
def test_probe_accepts_exactly_the_freshness_states_readyz_serves(
    current_generation, age, state, serviceable
):
    _pin_clock(current_generation, age)
    result = _pinned_probe(current_generation)
    assert result["sourceFreshness"]["state"] == state
    assert result["sourceFreshness"]["basis"] == "sourceCheckedAt"
    assert result["sourceFreshness"]["checkedAt"] == (PINNED_NOW - age).isoformat()
    if serviceable:
        assert result["status"] == "passed", result.get("failure")
        warned = any("Source freshness is" in warning for warning in result["warnings"])
        assert warned is (state != "current")
    else:
        assert result["status"] == "failed"
        assert "not serviceable" in result["failure"]
        assert result["journeys"] == []


@pytest.mark.parametrize(("age", "state", "serviceable"), FRESHNESS_BOUNDARIES)
def test_readyz_decision_matches_the_probe_boundaries(
    manifest, engine_route, age, state, serviceable
):
    from test_reference_api import reference_client

    checked = Generation.load(manifest).validated_at
    assert Generation.load(manifest).freshness(checked + age) == state
    with reference_client(manifest, engine_route, now=checked + age) as client:
        readyz = client.get("/readyz")
    assert (readyz.status_code == 200) is serviceable
    if not serviceable:
        assert {"condition": "freshness", "reason": "SOURCE_CHECK_EXPIRED"} in readyz.json()[
            "errors"
        ]


def test_probe_falls_back_to_validated_at_without_a_recorded_source_check(current_generation):
    _pin_clock(current_generation, timedelta(hours=40))
    path = current_generation / "manifest.json"
    data = _read(path)
    del data["sourceCheckedAt"]
    _write(path, data)
    result = _pinned_probe(current_generation)
    assert result["status"] == "passed"
    assert result["sourceFreshness"]["state"] == "aging"
    assert result["sourceFreshness"]["basis"] == "validatedAt"


def test_plain_generation_probe_records_one_identity_and_binds_runtime(current_generation):
    _pin_clock(current_generation, timedelta(hours=1))
    result = _pinned_probe(current_generation)
    manifest = _read(current_generation / "manifest.json")
    assert result["status"] == "passed", result.get("failure")
    assert result["generationId"] == manifest["generationId"]
    assert "scheduleComponentGenerationId" not in result
    assert "addressArtifactIdentity" not in result

    clients = [httpx.AsyncClient(base_url=ENGINE), httpx.AsyncClient(base_url="http://127.0.0.1:1")]
    try:
        paths = (current_generation / "manifest.json", current_generation / "probe.json")
        good = RuntimeSnapshot.load(paths[0], MotisClient(clients[0]), probe_path=paths[1])
        other = RuntimeSnapshot.load(paths[0], MotisClient(clients[1]), probe_path=paths[1])
        assert good.routing_verified
        assert not other.routing_verified
    finally:
        for client in clients:
            asyncio.run(client.aclose())


class _Catalog:
    def __init__(self, dump, pbf, count):
        self.source_dump_sha256, self.source_pbf_sha256, self.record_count = dump, pbf, count

    def lookup(self, osm_type, full_osm_id):
        return None

    def close(self):
        pass


class _PhotonClient:
    base_url = "http://127.0.0.1:2322"

    async def aclose(self):
        pass


@pytest.fixture
def composite_generation(current_generation, tmp_path):
    from tools.compose_address_generation import compose_address_generation

    _pin_clock(current_generation, timedelta(hours=1))
    catalog = tmp_path / "address-catalog.sqlite"
    catalog.write_bytes(b"synthetic catalog payload")
    attestation = tmp_path / "attestation.json"
    _write(
        attestation,
        {
            "schemaVersion": 1,
            "provider": "photon",
            "sourceDumpSha256": "5" * 64,
            "catalogSha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
            "indexName": "photon",
            "indexUuid": "index-uuid",
            "clusterUuid": "cluster-uuid",
            "documentCount": 1,
            "importedAt": "2026-10-01T00:00:00Z",
            "sealedAt": "2026-10-01T00:01:00Z",
            "indexWriteBlocked": True,
            "probes": [{"osmType": "N", "osmId": "7", "lat": 32.1, "lon": 34.8}],
        },
    )
    component_id = _read(current_generation / "manifest.json")["generationId"]
    manifest_path = compose_address_generation(
        current_generation,
        catalog,
        attestation,
        tmp_path / "composite",
        photon_jar_sha256=PHOTON_130_JAR_SHA256,
        java_image_digest=JAVA_21_IMAGE_DIGEST,
    )
    return manifest_path.parent, component_id


def _composite_snapshot(directory, probe_path):
    manifest = _read(directory / "manifest.json")
    attestation = _read(directory / "photon-import-attestation.json")
    binding = AddressProviderBinding(
        _PhotonClient(),
        "http://127.0.0.1:2322",
        manifest["addressSearch"]["artifactIdentity"],
        attestation["indexUuid"],
        _Catalog(
            attestation["sourceDumpSha256"],
            manifest["inputs"][CANONICAL_INPUTS["osm"]]["sha256"],
            attestation["documentCount"],
        ),
    )
    return RuntimeSnapshot.load(
        directory / "manifest.json",
        MotisClient(httpx.AsyncClient(base_url=ENGINE)),
        probe_path=probe_path,
        address_provider=binding,
    )


def test_composite_probe_verifies_reference_by_component_id_and_records_both_identities(
    composite_generation,
):
    directory, component_id = composite_generation
    manifest = _read(directory / "manifest.json")
    assert manifest["generationId"] != component_id

    result = _pinned_probe(directory)

    assert result["status"] == "passed", result.get("failure")
    assert result["generationId"] == manifest["generationId"]
    assert result["scheduleComponentGenerationId"] == component_id
    assert result["addressArtifactIdentity"] == manifest["addressSearch"]["artifactIdentity"]
    assert result["engineOrigin"] == ENGINE
    assert result["referenceSha256"] == manifest["artifacts"]["reference"]["sha256"]
    assert _read(directory / "probe.json") == result

    snapshot = _composite_snapshot(directory, directory / "probe.json")
    assert snapshot.generation.id == manifest["generationId"]
    assert snapshot.routing_verified


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda p, component: p.update(generationId=component), id="component-as-id"),
        pytest.param(
            lambda p, component: p.pop("scheduleComponentGenerationId"), id="no-component"
        ),
        pytest.param(
            lambda p, component: p.update(scheduleComponentGenerationId="f" * 64),
            id="wrong-component",
        ),
        pytest.param(lambda p, component: p.update(engineOrigin="http://127.0.0.1:1"), id="origin"),
        pytest.param(lambda p, component: p.update(graphTreeSha256="0" * 64), id="graph"),
        pytest.param(lambda p, component: p.update(configSha256="0" * 64), id="config"),
        pytest.param(lambda p, component: p.update(referenceSha256="0" * 64), id="reference"),
        pytest.param(
            lambda p, component: p.update(engineDigest="sha256:" + "0" * 64), id="engine-digest"
        ),
        pytest.param(lambda p, component: p.update(status="failed"), id="status"),
    ],
)
def test_composite_runtime_rejects_a_probe_that_does_not_bind_the_exact_identity(
    composite_generation, tmp_path, mutate
):
    directory, component_id = composite_generation
    _pinned_probe(directory)
    probe = _read(directory / "probe.json")
    mutate(probe, component_id)
    altered = tmp_path / "altered-probe.json"
    _write(altered, probe)
    assert not _composite_snapshot(directory, altered).routing_verified


def test_composite_probe_rejects_a_reference_that_belongs_to_another_component(
    composite_generation,
):
    directory, _ = composite_generation
    path = directory / "manifest.json"
    manifest = _read(path)
    manifest["scheduleComponentGenerationId"] = "e" * 64
    _write(path, manifest)
    result = _pinned_probe(directory)
    assert result["status"] == "failed"
    assert result["scheduleComponentGenerationId"] == "e" * 64


@pytest.mark.parametrize(
    ("age", "state"), [(timedelta(hours=72), "stale"), (timedelta(days=7), "expired")]
)
def test_composite_probe_applies_the_same_freshness_rule(composite_generation, age, state):
    directory, _ = composite_generation
    _pin_clock(directory, age)
    result = _pinned_probe(directory)
    assert result["sourceFreshness"]["state"] == state
    assert (result["status"] == "passed") is (state != "expired")
