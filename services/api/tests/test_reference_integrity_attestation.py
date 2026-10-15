"""Serving relies on the sealed digest only when the build attests a full integrity check.

The build runs ``PRAGMA integrity_check`` on the finished reference before sealing its SHA-256
and records that in the manifest. Startup and the probe compare the digest with the manifest
and then skip the repeated multi-minute check; any reference opened without an attested,
verified digest still gets the full check. Synthetic fixtures only; nothing is live.
"""

import hashlib
import json
import os
import sqlite3
from datetime import date

import httpx
import pytest
from test_generation_build import successful_runner
from test_probe_composite_freshness import _pinned_probe
from test_reference import synthetic_feed
from test_startup_hashing import _client, _stub_catalog

import opentransit.build.generations as generations
import opentransit.reference as reference_module
from opentransit.build.generations import build_generation
from opentransit.core.artifacts import ArtifactDigests
from opentransit.motis import MotisClient
from opentransit.reference import (
    ReferenceStore,
    attested_integrity_sha256,
    build_reference,
    check_reference_integrity,
    integrity_attestation,
)
from opentransit.runtime import RuntimeSnapshot

pytest_plugins = ["test_probe_composite_freshness"]


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _trace_statements(monkeypatch) -> list[str]:
    """Record every SQL statement run on connections opened while the test runs."""
    statements: list[str] = []
    original = sqlite3.connect

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(reference_module.sqlite3, "connect", connect)
    return statements


def _ran_integrity_check(statements) -> bool:
    return any("integrity_check" in statement for statement in statements)


def _corrupt_index_page(path) -> None:
    """Damage one index b-tree page in place; the file size stays the same."""
    with sqlite3.connect(path) as connection:
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        root = connection.execute(
            "SELECT rootpage FROM sqlite_master WHERE type='index' AND rootpage>0 "
            "ORDER BY rootpage LIMIT 1"
        ).fetchone()[0]
    connection.close()
    os.chmod(path, 0o644)  # the built reference is read-only
    with path.open("r+b") as stream:
        stream.seek((root - 1) * page_size + page_size - 300)
        stream.write(b"\x5a" * 292)


@pytest.fixture
def built_reference(tmp_path):
    feed = tmp_path / "feed.zip"
    synthetic_feed(feed)
    database = tmp_path / "reference.sqlite"
    build_reference(feed, database, "fixture-generation")
    return database


def test_attestation_counts_only_when_bound_to_the_sealed_digest():
    sha = "a" * 64
    assert attested_integrity_sha256({"sha256": sha, "integrityCheck": integrity_attestation(sha)})
    assert attested_integrity_sha256({"sha256": sha}) is None  # sealed before attestation
    stale = {"sha256": sha, "integrityCheck": integrity_attestation("b" * 64)}
    assert attested_integrity_sha256(stale) is None
    failed = {"sha256": sha, "integrityCheck": {**integrity_attestation(sha), "result": "bad"}}
    assert attested_integrity_sha256(failed) is None
    quick = {"sha256": sha, "integrityCheck": {**integrity_attestation(sha), "pragma": "quick"}}
    assert attested_integrity_sha256(quick) is None
    assert attested_integrity_sha256({"sha256": "A" * 64}) is None
    assert attested_integrity_sha256(None) is None


def test_attested_open_skips_integrity_check_but_keeps_content_verification(
    built_reference, monkeypatch
):
    statements = _trace_statements(monkeypatch)
    store = ReferenceStore(
        built_reference, "fixture-generation", integrity_attested_sha256=_sha256(built_reference)
    )
    assert store.integrity_verification == "build-attested-sha256"
    assert store.stop("station")
    assert not _ran_integrity_check(statements)
    assert any("FROM metadata" in statement for statement in statements)
    with pytest.raises(ValueError, match="different generation"):
        ReferenceStore(built_reference, "other", integrity_attested_sha256=_sha256(built_reference))


def test_tuple_row_content_hash_equals_the_row_factory_digest(built_reference, monkeypatch):
    """Hashing on plain tuples (for speed) yields the digest the Row-factory scan produced."""
    uri = built_reference.resolve().as_uri() + "?mode=ro&immutable=1"

    def digest(row_factory):
        connection = sqlite3.connect(uri, uri=True)
        try:
            connection.row_factory = row_factory
            return reference_module._content_hash(connection)
        finally:
            connection.close()

    row_digest = digest(sqlite3.Row)  # the previous ReferenceStore computation
    assert digest(None) == row_digest

    factories = []
    original = reference_module._content_hash

    def spy(connection, schema_version=None):
        factories.append(connection.row_factory)
        return original(connection, schema_version)

    monkeypatch.setattr(reference_module, "_content_hash", spy)
    store = ReferenceStore(built_reference, "fixture-generation")
    assert factories == [None]
    assert store.metadata.content_sha256 == row_digest
    assert store.stop("station")  # query connections still use sqlite3.Row


def test_attested_open_reuses_the_startup_digest(built_reference, monkeypatch):
    digests = ArtifactDigests()
    sha = digests.sha256(built_reference)
    reads = []
    original = type(built_reference).open

    def spy(self, mode="r", *args, **kwargs):
        if "b" in mode:
            reads.append(self)
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(type(built_reference), "open", spy)
    ReferenceStore(built_reference, integrity_attested_sha256=sha, digests=digests)
    assert reads == []


def test_corrupted_bytes_fail_the_attested_open(built_reference):
    sha = _sha256(built_reference)
    size = built_reference.stat().st_size
    _corrupt_index_page(built_reference)
    assert built_reference.stat().st_size == size
    with pytest.raises(ValueError, match="checksum differs from the manifest"):
        ReferenceStore(built_reference, integrity_attested_sha256=sha)


def test_unattested_open_runs_the_full_check_and_rejects_page_corruption(
    built_reference, monkeypatch
):
    statements = _trace_statements(monkeypatch)
    store = ReferenceStore(built_reference, "fixture-generation")
    assert store.integrity_verification == "sqlite-integrity-check"
    assert _ran_integrity_check(statements)

    _corrupt_index_page(built_reference)
    with pytest.raises(ValueError, match="failed SQLite integrity verification"):
        ReferenceStore(built_reference, "fixture-generation")
    with pytest.raises(ValueError, match="failed SQLite integrity verification"):
        check_reference_integrity(built_reference)


def test_build_checks_the_reference_before_sealing_its_attested_digest(
    inputs, tmp_path, monkeypatch
):
    checked = []
    original = generations.check_reference_integrity

    def check(path):
        checked.append(path.name)
        original(path)

    monkeypatch.setattr(generations, "check_reference_integrity", check)
    output = build_generation(
        inputs, tmp_path / "attested", date(2026, 9, 30), runner=successful_runner([])
    )
    entry = json.loads((output / "manifest.json").read_text(encoding="utf-8"))["artifacts"][
        "reference"
    ]
    assert checked == ["reference.sqlite"]
    assert entry["sha256"] == _sha256(output / "reference.sqlite")
    assert entry["integrityCheck"] == integrity_attestation(entry["sha256"])
    assert attested_integrity_sha256(entry) == entry["sha256"]

    # A reused reference is fully checked by its unattested open before it is copied.
    reused = build_generation(
        inputs,
        tmp_path / "reused",
        date(2026, 9, 30),
        runner=successful_runner([]),
        reference_reuse_generation_path=output,
    )
    reused_entry = json.loads((reused / "manifest.json").read_text(encoding="utf-8"))["artifacts"][
        "reference"
    ]
    assert attested_integrity_sha256(reused_entry) == entry["sha256"]


def test_build_does_not_seal_a_reference_that_fails_the_check(inputs, tmp_path, monkeypatch):
    def failing(path):
        raise ValueError("Reference database failed SQLite integrity verification")

    monkeypatch.setattr(generations, "check_reference_integrity", failing)
    output = tmp_path / "corrupt"
    with pytest.raises(ValueError, match="integrity verification"):
        build_generation(inputs, output, date(2026, 9, 30), runner=successful_runner([]))
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
    assert "reference" not in manifest["artifacts"]


def test_unattested_generation_keeps_the_full_check_at_load(current_generation, monkeypatch):
    """A generation sealed before attestations existed is checked exactly as before."""
    manifest_path = current_generation / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["artifacts"]["reference"]["integrityCheck"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    engine = MotisClient(httpx.AsyncClient(base_url="http://127.0.0.1:58082"))

    statements = _trace_statements(monkeypatch)
    snapshot = RuntimeSnapshot.load(manifest_path, engine)
    assert snapshot.reference.integrity_verification == "sqlite-integrity-check"
    assert _ran_integrity_check(statements)

    # Sealed over damaged bytes without an attestation: the digest matches, the check fails.
    reference = current_generation / "reference.sqlite"
    _corrupt_index_page(reference)
    manifest["artifacts"]["reference"]["sha256"] = _sha256(reference)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="failed SQLite integrity verification"):
        RuntimeSnapshot.load(manifest_path, engine)

    # An attestation copied from other bytes does not cover these ones.
    manifest["artifacts"]["reference"]["integrityCheck"] = integrity_attestation("c" * 64)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="failed SQLite integrity verification"):
        RuntimeSnapshot.load(manifest_path, engine)


def test_attested_startup_and_probe_skip_the_repeated_check(composite_generation, monkeypatch):
    directory, _ = composite_generation
    statements = _trace_statements(monkeypatch)
    _pinned_probe(directory)
    _stub_catalog(monkeypatch, directory)
    with _client(directory) as client:
        snapshot = client.app.state.snapshot
        assert snapshot is not None and snapshot.routing_verified
        assert snapshot.reference.integrity_verification == "build-attested-sha256"
    assert not _ran_integrity_check(statements)


def test_attested_startup_refuses_a_corrupted_reference(composite_generation, monkeypatch):
    directory, _ = composite_generation
    _pinned_probe(directory)
    _stub_catalog(monkeypatch, directory)
    _corrupt_index_page(directory / "reference.sqlite")

    with _client(directory) as client:
        assert client.app.state.snapshot is None
        response = client.get("/readyz")
    assert response.status_code == 503
    assert {"condition": "generation", "reason": "UNAVAILABLE"} in response.json()["errors"]
