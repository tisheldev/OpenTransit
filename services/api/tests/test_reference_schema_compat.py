"""Reference schema 2 (no locality tables) stays readable beside the current schema 3.

Preserved generations and any build begun with older code are schema 2. They load read-only,
are verified by the content-hash rules of the version recorded in the file (never recomputed
with schema-3 tables), search with the feed-derived city fallback only, and still pass the
generation, probe and runtime checks. Unknown versions are rejected.
"""

import hashlib
import json
import sqlite3
from datetime import timedelta

import httpx
import pytest
from test_generation_build import inputs  # noqa: F401
from test_generation_probe import current_generation  # noqa: F401
from test_localities import _dataset
from test_probe_composite_freshness import (
    ENGINE,
    PINNED_NOW,
    _pin_clock,
    _pinned_probe,
    _read,
    _write,
)
from test_reference import synthetic_feed
from test_reference_repair import _sealed_parent

from opentransit.build.generations import verify_artifacts
from opentransit.build.reference_repair import repair_reference_generation
from opentransit.core.artifacts import file_sha256
from opentransit.motis import MotisClient
from opentransit.reference import (
    LOCALITY_TABLES,
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    ReferenceStore,
    _timing_policy,
    build_reference,
)
from opentransit.runtime import RuntimeSnapshot
from opentransit.stop_search import search_stops

# Written by the code before schema 3, kept here as the independent definition of the
# schema-2 content identity.
SCHEMA_2_TABLES = (
    "agencies",
    "routes",
    "stops",
    "translations",
    "route_stops",
    "patterns",
    "pattern_stops",
    "calendar_rules",
    "calendar_exceptions",
    "trip_profiles",
    "clock_profiles",
    "clock_profile_calls",
)


def schema_2_content_hash(connection) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(_timing_policy(), sort_keys=True, separators=(",", ":")).encode())
    digest.update(b"\n")
    for table in SCHEMA_2_TABLES:
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        order = ", ".join(f'"{name}"' for name in columns)
        for row in connection.execute(f'SELECT {order} FROM "{table}" ORDER BY {order}'):
            digest.update(
                json.dumps(tuple(row), ensure_ascii=False, separators=(",", ":")).encode()
            )
            digest.update(b"\n")
    return digest.hexdigest()


def downgrade_to_schema_2(database, generation_id=None):
    """Turn a built schema-3 reference into what schema-2 code wrote (returns its metadata)."""
    database.chmod(0o600)
    with sqlite3.connect(database) as connection:
        for table in ("stop_localities", "locality_names", "localities"):
            connection.execute(f"DROP TABLE {table}")
        connection.execute("DELETE FROM metadata WHERE key='localityProvenance'")
        values = {
            key: json.loads(value)
            for key, value in connection.execute("SELECT key, value FROM metadata")
        }
        values["schemaVersion"] = 2
        values["counts"] = {k: v for k, v in values["counts"].items() if k not in LOCALITY_TABLES}
        values["contentSha256"] = schema_2_content_hash(connection)
        if generation_id is not None:
            values["generationId"] = generation_id
        connection.executemany(
            "INSERT INTO metadata(key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            [(key, json.dumps(value, sort_keys=True)) for key, value in values.items()],
        )
    connection = sqlite3.connect(database)
    connection.execute("VACUUM")
    connection.close()
    database.chmod(0o444)
    return values


def set_metadata(database, **changes):
    database.chmod(0o600)
    with sqlite3.connect(database) as connection:
        for key, value in changes.items():
            connection.execute("UPDATE metadata SET value=? WHERE key=?", (json.dumps(value), key))
    database.chmod(0o444)


@pytest.fixture
def schema_2_reference(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    database = tmp_path / "v2.sqlite"
    build_reference(feed, database, "g2", localities=_dataset(tmp_path))
    return database, downgrade_to_schema_2(database)


def test_supported_versions_are_exactly_two_and_three():
    assert SUPPORTED_SCHEMA_VERSIONS == (2, 3) and SCHEMA_VERSION == 3


def test_schema_2_reference_loads_searches_and_verifies_by_its_own_version(schema_2_reference):
    database, values = schema_2_reference
    store = ReferenceStore(database, "g2")
    assert store.metadata.schema_version == 2
    assert store.has_localities is False
    assert not any(table in values["counts"] for table in LOCALITY_TABLES)
    assert store.metadata.content_sha256 == values["contentSha256"]
    # The older identity is verified, not recomputed with schema-3 tables.
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert not tables & set(LOCALITY_TABLES)

    candidates = store.stop_search_candidates()
    assert candidates and all(row["locality_ids"] == [] for row in candidates)
    assert store.search_localities() == []
    # Search runs on the feed-derived fallback and still finds stops by name.
    results = search_stops(store, "Central")
    assert results
    # Ordinary reads are unaffected.
    assert store.stop("station")["name"]


def test_schema_2_identity_equals_the_schema_3_identity_of_a_build_without_localities(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    plain = build_reference(feed, tmp_path / "plain.sqlite", "g1")
    values = downgrade_to_schema_2(tmp_path / "plain.sqlite")
    assert values["contentSha256"] == plain.content_sha256
    assert ReferenceStore(tmp_path / "plain.sqlite", "g1").metadata.content_sha256 == (
        plain.content_sha256
    )


def test_schema_2_tampering_is_detected_by_the_schema_2_hash(schema_2_reference):
    database, _ = schema_2_reference
    database.chmod(0o600)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE stops SET name='tampered' WHERE source_id='station'")
    with pytest.raises(ValueError, match="content verification"):
        ReferenceStore(database, "g2")


def test_schema_2_file_with_stray_locality_tables_never_reads_them(schema_2_reference):
    database, _ = schema_2_reference
    database.chmod(0o600)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            "CREATE TABLE localities (locality_id TEXT, name TEXT);"
            "CREATE TABLE locality_names (locality_id TEXT);"
            "CREATE TABLE stop_localities (stop_id TEXT, locality_id TEXT);"
            "INSERT INTO localities VALUES ('osm:relation:1', 'Injected');"
        )
    database.chmod(0o444)
    store = ReferenceStore(database, "g2")  # identity ignores tables the version lacks
    assert store.search_localities() == []
    assert all(row["locality_ids"] == [] for row in store.stop_search_candidates())


@pytest.mark.parametrize("version", [0, 1, 4, 99, "3", None, True, 2.5])
def test_unknown_schema_versions_are_rejected(schema_2_reference, version):
    database, _ = schema_2_reference
    set_metadata(database, schemaVersion=version)
    with pytest.raises(ValueError, match="Unsupported reference database schema"):
        ReferenceStore(database, "g2")


def test_schema_3_requires_its_locality_tables(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    database = tmp_path / "v3.sqlite"
    build_reference(feed, database, "g3")
    assert ReferenceStore(database, "g3").has_localities is True
    database.chmod(0o600)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE stop_localities")
    with pytest.raises(ValueError, match="lacks its schema 3 table stop_localities"):
        ReferenceStore(database, "g3")


def _downgrade_generation(directory):
    """Rewrite a built generation as the schema-2 code would have sealed it."""
    manifest_path = directory / "manifest.json"
    manifest = _read(manifest_path)
    identity = dict(manifest["identity"], referenceSchemaVersion=2)
    generation_id = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    values = downgrade_to_schema_2(directory / "reference.sqlite", generation_id)
    manifest.update(
        {"identity": identity, "generationId": generation_id, "referenceSchemaVersion": 2}
    )
    manifest["artifacts"]["reference"].update(
        sha256=file_sha256(directory / "reference.sqlite"),
        contentSha256=values["contentSha256"],
        counts=values["counts"],
    )
    _write(manifest_path, manifest)
    return manifest


def test_schema_2_generation_passes_artifact_probe_and_runtime_verification(current_generation):  # noqa: F811
    manifest = _downgrade_generation(current_generation)
    assert verify_artifacts(current_generation)["generationId"] == manifest["generationId"]
    _pin_clock(current_generation, timedelta(hours=1))
    result = _pinned_probe(current_generation)
    assert result["status"] == "passed", result.get("failure")
    assert result["generationId"] == manifest["generationId"]
    assert "localities" not in result["referenceCounts"]

    import asyncio

    client = httpx.AsyncClient(base_url=ENGINE)
    try:
        snapshot = RuntimeSnapshot.load(
            current_generation / "manifest.json",
            MotisClient(client),
            probe_path=current_generation / "probe.json",
        )
        assert snapshot.routing_verified
        assert snapshot.reference.metadata.schema_version == 2
        assert snapshot.reference.has_localities is False
    finally:
        asyncio.run(client.aclose())
    assert PINNED_NOW  # the pinned clock the helpers share


def test_repair_of_a_schema_2_parent_keeps_schema_2_and_its_identity_rules(tmp_path):
    gtfs = synthetic_feed(tmp_path / "source.zip")
    parent = tmp_path / "parent"
    parent.mkdir()
    manifest, _ = _sealed_parent(parent, gtfs)
    values = downgrade_to_schema_2(parent / "reference.sqlite", manifest["generationId"])
    manifest["artifacts"]["reference"].update(
        sha256=file_sha256(parent / "reference.sqlite"),
        contentSha256=values["contentSha256"],
        counts=values["counts"],
    )
    _write(parent / "manifest.json", manifest)

    output = repair_reference_generation(parent, gtfs, tmp_path / "repaired")
    result = _read(output / "manifest.json")
    repaired = ReferenceStore(output / "reference.sqlite", result["generationId"])
    assert repaired.metadata.schema_version == 2
    assert repaired.has_localities is False
    assert not any(table in repaired.metadata.counts for table in LOCALITY_TABLES)
    assert repaired.stop("station")["translations"]["he"] == "תחנה מרכזית"
