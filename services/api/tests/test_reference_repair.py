"""Exact GTFS legacy translation linkage and sealed-generation repair tests."""

import csv
import hashlib
import json
import sqlite3
import zipfile
from io import StringIO

import pytest
from test_reference import synthetic_feed

from opentransit.build.generations import PARSER_VERSION, _tree_artifact
from opentransit.build.reference_repair import repair_reference_generation
from opentransit.core.artifacts import file_sha256
from opentransit.reference import (
    ReferenceStore,
    _content_hash,
    _translation_rows,
    _validate_translation_rows,
    build_reference,
)


def _translation_zip(path, headers, rows):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        stream = StringIO()
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)
        archive.writestr("translations.txt", stream.getvalue())
    return path


def _schedule_rows(connection):
    result = {}
    for table in ("trip_profiles", "clock_profiles", "clock_profile_calls"):
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        ordering = ",".join(f'"{column}"' for column in columns)
        result[table] = connection.execute(
            f'SELECT * FROM "{table}" ORDER BY {ordering}'
        ).fetchall()
    return result


def test_legacy_translation_rows_are_exact_field_values_with_shared_names(tmp_path):
    feed = tmp_path / "legacy.zip"
    with zipfile.ZipFile(feed, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "translations.txt",
            "trans_id,lang,translation\nSame,EN,Shared English\n",
        )
    with zipfile.ZipFile(feed) as archive:
        rows = list(_translation_rows(archive))
    assert rows == [("stops", "en", "Shared English", "stop_name", "", None, "Same", None)]


def test_reference_builder_imports_legacy_translation_headers(tmp_path):
    original = synthetic_feed(tmp_path / "base.zip")
    feed = tmp_path / "legacy-feed.zip"
    with (
        zipfile.ZipFile(original) as source,
        zipfile.ZipFile(feed, "w", zipfile.ZIP_DEFLATED) as destination,
    ):
        for info in source.infolist():
            if info.filename != "translations.txt":
                destination.writestr(info, source.read(info.filename))
        destination.writestr(
            "translations.txt",
            "trans_id,lang,translation\nCentral,EN,Central English\n",
        )
    database = tmp_path / "reference.sqlite"
    build_reference(feed, database, "legacy-import")
    assert ReferenceStore(database, "legacy-import").stop("station")["translations"] == {
        "en": "Central English"
    }


def test_identical_duplicates_are_ignored_but_conflicts_fail(tmp_path):
    feed = _translation_zip(
        tmp_path / "duplicate.zip",
        ["trans_id", "lang", "translation"],
        [["Same", "EN", "Shared"], ["Same", "en", "Shared"]],
    )
    with zipfile.ZipFile(feed) as archive:
        assert len(list(_translation_rows(archive))) == 1

    conflict = _translation_zip(
        tmp_path / "conflict.zip",
        ["trans_id", "lang", "translation"],
        [["Same", "EN", "Shared"], ["Same", "en", "Different"]],
    )
    with zipfile.ZipFile(conflict) as archive, pytest.raises(ValueError, match="Conflicting"):
        list(_translation_rows(archive))


def test_modern_selector_validation_and_exact_scope(tmp_path):
    modern = _translation_zip(
        tmp_path / "modern.zip",
        ["table_name", "field_name", "language", "translation", "record_id", "field_value"],
        [["stops", "stop_name", "EN", "A", "", "Same"]],
    )
    with zipfile.ZipFile(modern) as archive:
        assert list(_translation_rows(archive))[0][:7] == (
            "stops",
            "en",
            "A",
            "stop_name",
            "",
            None,
            "Same",
        )

    dual = _translation_zip(
        tmp_path / "dual.zip",
        ["table_name", "field_name", "language", "translation", "record_id", "field_value"],
        [["stops", "stop_name", "en", "A", "stop-1", "Not source value"]],
    )
    with zipfile.ZipFile(dual) as archive:
        rows = list(_translation_rows(archive))
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE stops(source_id TEXT, name TEXT)")
    connection.execute("INSERT INTO stops VALUES ('stop-1', 'Same')")
    with pytest.raises(ValueError, match="dual"):
        _validate_translation_rows(connection, rows)

    no_selector = _translation_zip(
        tmp_path / "no-selector.zip",
        ["table_name", "field_name", "language", "translation", "record_id", "field_value"],
        [["stops", "stop_name", "en", "A", "", ""]],
    )
    with zipfile.ZipFile(no_selector) as archive, pytest.raises(ValueError, match="selector"):
        list(_translation_rows(archive))


def test_record_specific_translation_precedes_exact_shared_value(tmp_path):
    database = tmp_path / "reference.sqlite"
    build_reference(synthetic_feed(tmp_path / "feed.zip"), database, "fixture-generation")
    database.chmod(0o600)
    connection = sqlite3.connect(database)
    connection.execute(
        "INSERT INTO stops VALUES ('extra', 'extra', NULL, 'Central', NULL, 32, 34, "
        "NULL, NULL, 0, NULL, NULL, NULL)"
    )
    connection.execute(
        "INSERT INTO translations "
        "(table_name,lang,translation,field_name,record_id,field_value,priority) "
        "VALUES ('stops','en','Specific station','stop_name','station',NULL,0)"
    )
    connection.execute(
        "INSERT INTO translations "
        "(table_name,lang,translation,field_name,record_id,field_value,priority) "
        "VALUES ('stops','en','Shared exact','stop_name','','Central',100)"
    )
    content_hash = _content_hash(connection)
    connection.execute(
        "UPDATE metadata SET value=? WHERE key='contentSha256'",
        (json.dumps(content_hash),),
    )
    connection.commit()
    connection.close()
    database.chmod(0o444)
    store = ReferenceStore(database)
    assert store.stop("station")["translations"]["en"] == "Specific station"
    assert store.stop("extra")["translations"]["en"] == "Shared exact"
    # The field-value row applies to every exact source name match.
    station_candidate = next(
        item for item in store.stop_search_candidates() if item["source_id"] == "station"
    )
    assert station_candidate["translations"]["en"] == "Specific station"


def _sealed_parent(path, gtfs):
    config = path / "config.yml"
    config.write_text("schedule_only: true\n", encoding="utf-8")
    input_sha = file_sha256(gtfs)
    identity = {
        "inputs": {"israel-public-transportation.zip": input_sha},
        "configSha256": file_sha256(config),
        "engineDigest": "sha256:fixture",
        "parserVersion": 1,
        "referenceSchemaVersion": 2,
        "timingPolicy": {"policyId": "fixture"},
        "mode": "real",
        "window": {"firstDay": "2025-01-01", "days": 1},
        "importMemoryCapBytes": 1024,
        "localEngineSlot": "blue",
        "validationEvidenceSha256": "f" * 64,
    }
    generation_id = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    database = path / "reference.sqlite"
    metadata = build_reference(gtfs, database, generation_id)
    # Emulate the legacy importer: selector columns were lost before this repair.
    database.chmod(0o600)
    connection = sqlite3.connect(database)
    connection.execute("DELETE FROM translations")
    content_hash = _content_hash(connection)
    connection.execute(
        "UPDATE metadata SET value=? WHERE key='contentSha256'",
        (json.dumps(content_hash),),
    )
    connection.commit()
    connection.close()
    database.chmod(0o444)

    graph_dir = path / "motis"
    graph_dir.mkdir()
    (graph_dir / "graph.bin").write_bytes(b"synthetic graph")
    manifest = {
        "schemaVersion": 1,
        "state": "ready",
        "mode": "real",
        "parserVersion": 1,
        "referenceSchemaVersion": 2,
        "engineDigest": "sha256:fixture",
        "generationId": generation_id,
        "identity": identity,
        "inputs": {
            "israel-public-transportation.zip": {
                "sha256": input_sha,
                "checkedAt": "2025-01-01T00:00:00+00:00",
            }
        },
        "configSha256": file_sha256(config),
        "coverage": {"from": "2025-01-01T00:00:00+02:00", "until": "2025-01-02T00:00:00+02:00"},
        "validatedAt": "2025-01-01T00:00:00+00:00",
        "sourceCheckedAt": "2025-01-01T00:00:00+00:00",
        "serviceDates": {"from": "2025-01-01", "through": "2025-01-31"},
        "artifacts": {
            "reference": {
                "path": "reference.sqlite",
                "sha256": file_sha256(database),
                "contentSha256": content_hash,
                "counts": metadata.counts,
            },
            "config": {"path": "config.yml", "sha256": file_sha256(config)},
            "motis": _tree_artifact(graph_dir),
        },
    }
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest, generation_id


def test_repair_clones_parent_changes_only_parser_identity_and_preserves_schedule(tmp_path):
    gtfs = synthetic_feed(tmp_path / "source.zip")
    parent = tmp_path / "parent"
    parent.mkdir()
    manifest, parent_id = _sealed_parent(parent, gtfs)
    parent_identity = manifest["identity"]
    with sqlite3.connect(parent / "reference.sqlite") as connection:
        before_schedule = _schedule_rows(connection)
    graph_hash = manifest["artifacts"]["motis"]["sha256"]
    config_hash = manifest["artifacts"]["config"]["sha256"]
    parent_db_hash = file_sha256(parent / "reference.sqlite")

    output = tmp_path / "repaired"
    repaired = repair_reference_generation(parent, gtfs, output)
    result = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((output / "translation-repair.json").read_text(encoding="utf-8"))
    assert result["state"] == "ready"
    assert result["parserVersion"] == PARSER_VERSION == 2
    assert result["identity"]["parserVersion"] == 2
    for key in parent_identity.keys() - {"parserVersion"}:
        assert result["identity"][key] == parent_identity[key]
    assert result["generationId"] != parent_id
    assert result["artifacts"]["config"]["sha256"] == config_hash
    assert result["artifacts"]["motis"]["sha256"] == graph_hash
    assert file_sha256(parent / "reference.sqlite") == parent_db_hash
    with sqlite3.connect(output / "reference.sqlite") as connection:
        after_schedule = _schedule_rows(connection)
    assert after_schedule == before_schedule
    store = ReferenceStore(output / "reference.sqlite", result["generationId"])
    assert store.stop("station")["translations"]["he"] == "תחנה מרכזית"
    assert provenance["state"] == "ready"
    assert provenance["freshnessRenewed"] is False
    assert (
        provenance["gtfsSourceSha256"]
        == manifest["inputs"]["israel-public-transportation.zip"]["sha256"]
    )
    assert repaired == output


def test_repair_rejects_source_hash_mismatch_without_touching_parent(tmp_path):
    gtfs = synthetic_feed(tmp_path / "source.zip")
    parent = tmp_path / "parent"
    parent.mkdir()
    _sealed_parent(parent, gtfs)
    wrong = tmp_path / "wrong.zip"
    wrong.write_bytes(gtfs.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="source archive hash"):
        repair_reference_generation(parent, wrong, tmp_path / "failed")
