"""Focused exact-selector translation linkage for stop search candidates."""

import csv
import io
import json
import sqlite3
import zipfile

from test_reference import synthetic_feed

import opentransit.reference as reference_module
from opentransit.reference import ReferenceStore, build_reference


def _csv_text(headers, rows):
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue()


def _search_feed(path):
    synthetic_feed(path)
    with zipfile.ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}

    stop_reader = csv.DictReader(io.StringIO(members["stops.txt"].decode()))
    stop_headers = stop_reader.fieldnames
    stops = []
    for row in stop_reader:
        if row["stop_id"] in {"station", "stop_c"}:
            row["stop_name"] = "Shared"
        stops.append([row[name] for name in stop_headers])
    members["stops.txt"] = _csv_text(stop_headers, stops).encode()

    translation_headers = [
        "table_name",
        "field_name",
        "language",
        "translation",
        "record_id",
        "record_sub_id",
        "field_value",
        "priority",
    ]
    translation_rows = [
        # A record selector wins over the higher-priority exact-name fallback.
        ["stops", "stop_name", "en", "Specific station", "station", "", "", "1"],
        ["stops", "stop_name", "EN", "Shared English", "", "", "Shared", "100"],
        ["stops", "stop_name", "he", "שם משותף", "", "", "Shared", "4"],
        # Case-folded language tags share first-wins behavior across selectors;
        # the record selector wins even when its priority is lower.
        ["stops", "stop_name", "EN", "Alpha higher", "platform_a", "", "", "2"],
        ["stops", "stop_name", "en", "Alpha fallback", "", "", "Central A", "9"],
        ["routes", "stop_name", "es", "Wrong table", "station", "", "Shared", "999"],
        ["stops", "stop_desc", "it", "Wrong field", "station", "", "Shared", "999"],
        ["stops", "stop_name", "de", "Wrong sub-ID", "station", "platform_a", "Shared", "999"],
    ]
    members["translations.txt"] = _csv_text(translation_headers, translation_rows).encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)
    return path


def test_stop_search_candidates_use_exact_linkage_and_preserve_order(tmp_path):
    feed = _search_feed(tmp_path / "search.zip")
    database = tmp_path / "reference.sqlite"
    build_reference(feed, database, "search-linkage")
    # Preserve a sealed synthetic edge case the builder correctly rejects on fresh
    # imports: an unknown record ID paired with a value that belongs to real stops.
    database.chmod(0o600)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO translations "
            "(table_name,lang,translation,field_name,record_id,record_sub_id,field_value,priority) "
            "VALUES ('stops','fr','Must not attach','stop_name','missing',NULL,'Shared',999)"
        )
        content_hash = reference_module._content_hash(connection)
        connection.execute(
            "UPDATE metadata SET value=? WHERE key='contentSha256'",
            (json.dumps(content_hash),),
        )

    candidates = ReferenceStore(database, "search-linkage").stop_search_candidates()

    assert [candidate["source_id"] for candidate in candidates] == [
        "platform_a",
        "platform_b",
        "station",
        "stop_c",
    ]
    by_source_id = {candidate["source_id"]: candidate for candidate in candidates}
    assert by_source_id["platform_a"]["translations"] == {"en": "Alpha higher"}
    assert by_source_id["station"]["translations"] == {
        "en": "Specific station",
        "he": "שם משותף",
    }
    assert by_source_id["stop_c"]["translations"] == {
        "en": "Shared English",
        "he": "שם משותף",
    }
    assert by_source_id["platform_b"]["translations"] == {}
