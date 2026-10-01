"""OSM locality data in the reference build and locality-name search."""

import hashlib
import json
import sqlite3

import pytest
from test_reference import synthetic_feed

from opentransit.localities import (
    PreparedGeometry,
    assign_stops,
    build_locality,
    load_locality_context,
    name_entries,
    representative_point,
)
from opentransit.reference import STOP_PREFIX, ReferenceStore, build_reference
from opentransit.stop_search import search_stops

PBF_SHA = "a" * 64


def _square(lon0, lat0, lon1, lat1):
    return [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]


def _polygon(*rings):
    return {"type": "Polygon", "coordinates": list(rings)}


TAGS_CENTRAL = {
    "boundary": "administrative",
    "admin_level": "8",
    "name": "מרכזיה",
    "name:he": "מרכזיה",
    "name:en": "Centralia",
    "alt_name:en": "Central City;Centralville",
    "name:fr": "Centralie",
}


def _write_context(path, localities, *, sha=PBF_SHA):
    lines = [{"type": "ContextHeader", "sourceSha256": sha, "schemaVersion": 1}]
    lines.append({"type": "Street", "osmType": "W", "osmId": "1", "tags": {}, "coordinates": []})
    for osm_id, tags, geometry in localities:
        lines.append(
            {
                "type": "Locality",
                "osmType": "R",
                "osmId": str(osm_id),
                "tags": tags,
                "geometry": geometry,
            }
        )
    path.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n", "utf-8"
    )
    return path


# --- geometry -------------------------------------------------------------------


def test_containment_excludes_holes_and_handles_multipolygons():
    donut = _polygon(_square(0, 0, 10, 10), _square(4, 4, 6, 6))
    geometry = PreparedGeometry(donut)
    assert geometry.contains(2, 2)
    assert not geometry.contains(5, 5)  # inside the hole
    assert not geometry.contains(20, 20)
    assert geometry.contains(0, 5)  # boundary counts as inside
    multi = PreparedGeometry(
        {
            "type": "MultiPolygon",
            "coordinates": [[_square(0, 0, 1, 1)], [_square(5, 5, 6, 6)]],
        }
    )
    assert multi.contains(0.5, 0.5) and multi.contains(5.5, 5.5)
    assert not multi.contains(3, 3)
    assert multi.bbox == (0, 0, 6, 6)


def test_representative_point_lies_inside_concave_and_holed_shapes():
    c_shape = _polygon(
        [[0, 0], [10, 0], [10, 3], [3, 3], [3, 7], [10, 7], [10, 10], [0, 10], [0, 0]]
    )
    # The centroid of a C shape lies in the notch; the point must still be inside.
    point = representative_point(c_shape)
    assert PreparedGeometry(c_shape).contains(*point)
    donut = _polygon(_square(0, 0, 10, 10), _square(2, 2, 8, 8))
    assert PreparedGeometry(donut).contains(*representative_point(donut))
    # Rings wound the other way round give the same answer.
    reversed_donut = _polygon(_square(0, 0, 10, 10)[::-1], _square(2, 2, 8, 8)[::-1])
    assert representative_point(reversed_donut) == representative_point(donut)


def test_name_entries_split_alternatives_and_keep_language_and_tag():
    entries = name_entries(
        {
            "name": "ירושלים | القدس",
            "name:en": "Jerusalem",
            "alt_name:en": "Yerushalayim; Al Quds",
            "name:ar1": "ignored",
            "wikidata": "Q1",
        }
    )
    assert ("", "ירושלים", "name") in entries and ("", "القدس", "name") in entries
    assert ("en", "Al Quds", "alt_name:en") in entries
    assert all(tag != "name:ar1" for _, _, tag in entries)
    assert list(entries) == sorted(entries)


def test_assign_stops_returns_every_containing_locality_sorted():
    big = build_locality("R", 1, TAGS_CENTRAL, _polygon(_square(34.0, 32.0, 35.0, 33.0)))
    small = build_locality(
        "R", 2, {**TAGS_CENTRAL, "name": "Small"}, _polygon(_square(34.5, 32.4, 34.6, 32.5))
    )
    stops = [
        ("s_in_both", 32.45, 34.55),
        ("s_in_big", 32.9, 34.1),
        ("s_nowhere", 31.0, 34.1),
        ("s_unlocated", None, None),
    ]
    assert assign_stops([big, small], stops) == [
        ("s_in_big", "osm:relation:1"),
        ("s_in_both", "osm:relation:1"),
        ("s_in_both", "osm:relation:2"),
    ]


# --- context loading ---------------------------------------------------------------


def test_load_context_records_provenance_and_binds_the_osm_input(tmp_path):
    path = _write_context(
        tmp_path / "context-v1.jsonl",
        [(7, TAGS_CENTRAL, _polygon(_square(34.775, 32.075, 34.785, 32.0815)))],
    )
    dataset = load_locality_context(path, expected_osm_sha256=PBF_SHA)
    assert [item.locality_id for item in dataset.localities] == ["osm:relation:7"]
    assert dataset.provenance["osmPbfSha256"] == PBF_SHA
    assert dataset.provenance["contextSha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert dataset.provenance["localityCount"] == 1
    with pytest.raises(ValueError, match="different OSM input"):
        load_locality_context(path, expected_osm_sha256="b" * 64)


def test_load_context_checks_a_neighbouring_extraction_manifest(tmp_path):
    path = _write_context(
        tmp_path / "context-v1.jsonl",
        [(7, TAGS_CENTRAL, _polygon(_square(34.775, 32.075, 34.785, 32.0815)))],
    )
    manifest = tmp_path / "extraction-manifest.json"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(
        json.dumps(
            {
                "output": {"sha256": digest},
                "source": {"sha256": PBF_SHA},
                "reader": {"library": "pyosmium", "version": "4.3.1"},
            }
        ),
        "utf-8",
    )
    assert load_locality_context(path).provenance["reader"]["library"] == "pyosmium"
    manifest.write_text(json.dumps({"output": {"sha256": "0" * 64}, "source": {"sha256": PBF_SHA}}))
    with pytest.raises(ValueError, match="disagrees"):
        load_locality_context(path)


def test_load_context_rejects_bad_headers_and_records(tmp_path):
    bad_header = tmp_path / "bad.jsonl"
    bad_header.write_text('{"type":"Street"}\n', "utf-8")
    with pytest.raises(ValueError, match="header"):
        load_locality_context(bad_header)
    empty = _write_context(tmp_path / "empty.jsonl", [])
    with pytest.raises(ValueError, match="no localities"):
        load_locality_context(empty)
    wrong_level = _write_context(
        tmp_path / "level.jsonl",
        [(7, {**TAGS_CENTRAL, "admin_level": "6"}, _polygon(_square(0, 0, 1, 1)))],
    )
    with pytest.raises(ValueError, match="invalid"):
        load_locality_context(wrong_level)


# --- reference build ------------------------------------------------------------------


def _dataset(tmp_path):
    path = _write_context(
        tmp_path / "context-v1.jsonl",
        [
            (7, TAGS_CENTRAL, _polygon(_square(34.775, 32.075, 34.785, 32.0815))),
            (
                8,
                {**TAGS_CENTRAL, "name": "Elsewhere", "name:he": "אחרת", "name:en": "Elsewhere"},
                _polygon(_square(35.5, 33.0, 35.6, 33.1)),
            ),
        ],
    )
    return load_locality_context(path, expected_osm_sha256=PBF_SHA)


def test_reference_build_stores_localities_and_binds_provenance(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    dataset = _dataset(tmp_path)
    plain = build_reference(feed, tmp_path / "plain.sqlite", "g1")
    first = build_reference(feed, tmp_path / "first.sqlite", "g1", localities=dataset)
    second = build_reference(feed, tmp_path / "second.sqlite", "g1", localities=dataset)
    assert first.content_sha256 == second.content_sha256  # deterministic
    assert first.content_sha256 != plain.content_sha256
    assert plain.counts["localities"] == 0 and plain.counts["stop_localities"] == 0
    assert first.counts["localities"] == 2
    assert first.counts["locality_names"] > 4

    store = ReferenceStore(tmp_path / "first.sqlite", "g1")
    assert store.metadata.schema_version == 3
    candidates = {row["source_id"]: row["locality_ids"] for row in store.stop_search_candidates()}
    assert candidates == {
        "platform_a": ["osm:relation:7"],
        "platform_b": ["osm:relation:7"],
        "station": ["osm:relation:7"],
        "stop_c": [],  # Harbor lies north of the polygon
    }
    summary = {item["locality_id"]: item for item in store.search_localities()}
    assert set(summary) == {"osm:relation:7", "osm:relation:8"}
    assert summary["osm:relation:7"]["name_en"] == "Centralia"
    assert ("en", "Central City", "alt_name:en") in summary["osm:relation:7"]["names"]
    assert "geometry" not in summary["osm:relation:7"]
    with sqlite3.connect(tmp_path / "first.sqlite") as connection:
        provenance = json.loads(
            connection.execute(
                "SELECT value FROM metadata WHERE key='localityProvenance'"
            ).fetchone()[0]
        )
        geometry = connection.execute(
            "SELECT geometry FROM localities WHERE locality_id='osm:relation:7'"
        ).fetchone()[0]
    assert provenance["osmPbfSha256"] == PBF_SHA
    assert json.loads(geometry)["type"] == "Polygon"
    assert ReferenceStore(tmp_path / "plain.sqlite", "g1").search_localities() == []


def test_content_verification_covers_locality_provenance(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    build_reference(feed, tmp_path / "ref.sqlite", "g1", localities=_dataset(tmp_path))
    database = tmp_path / "ref.sqlite"
    database.chmod(0o600)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE metadata SET value=? WHERE key='localityProvenance'",
            (json.dumps({"osmPbfSha256": "f" * 64}),),
        )
    with pytest.raises(ValueError, match="content verification"):
        ReferenceStore(database, "g1")


# --- search ----------------------------------------------------------------------------


class _Reference:
    def __init__(self, rows, localities):
        self.rows = rows
        self.localities = localities

    def stop_search_candidates(self):
        return self.rows

    def search_localities(self):
        return self.localities


def _stop(source_id, name, en=None, *, localities=(), routes=0, rail=False, lat=32.0, lon=34.8):
    return {
        "source_id": source_id,
        "stop_id": STOP_PREFIX + source_id,
        "parent_station": None,
        "location_type": 0,
        "name": name,
        "description": None,
        "translations": {"en": en} if en else {},
        "code": None,
        "latitude": lat,
        "longitude": lon,
        "route_count": routes,
        "rail": rail,
        "locality_ids": list(localities),
    }


def _locality(number, names, center):
    return {
        "locality_id": f"osm:relation:{number}",
        "name": names[0][1],
        "name_he": None,
        "name_en": None,
        "place": None,
        "center": center,
        "bbox": (0.0, 0.0, 0.0, 0.0),
        "names": names,
    }


TLV = "osm:relation:1"
RAM = "osm:relation:2"
EMPTY = "osm:relation:3"


def _reference():
    localities = [
        _locality(
            1,
            [
                ("", "תל־אביב–יפו", "name"),
                ("", "תל אביב", "short_name"),
                ("en", "Tel-Aviv", "name:en"),
                ("fr", "Tel Aviv-Jaffa", "name:fr"),
            ],
            (32.08, 34.78),
        ),
        _locality(2, [("", "רמת גן", "name"), ("en", "Ramat Gan", "name:en")], (32.07, 34.82)),
        _locality(3, [("en", "Ghostville", "name:en")], (31.0, 34.0)),
        _locality(4, [("", "Binyamina - Givat Ada", "name:en")], (32.5, 34.9)),
    ]
    rows = [
        # Rail hub without any city in the feed, inside Tel Aviv by polygon.
        _stop(
            "savidor",
            "תל אביב סבידור",
            "Tel Aviv Savidor",
            localities=[TLV],
            routes=1000,
            rail=True,
            lat=32.083,
            lon=34.798,
        ),
        _stop(
            "dizengoff",
            "דיזנגוף",
            "Dizengoff Center",
            localities=[TLV],
            routes=60,
            lat=32.0805,
            lon=34.7805,
        ),
        _stop("remote", "קצה", "Edge", localities=[TLV], routes=500, lat=32.14, lon=34.84),
        # Street named after the city, placed in Ramat Gan by polygon.
        _stop(
            "street",
            "תל אביב/הגפן",
            "Tel Aviv St/HaGefen",
            localities=[RAM],
            routes=50,
            lat=32.07,
            lon=34.82,
        ),
        _stop(
            "ramat",
            "מרכז רמת גן",
            "Ramat Gan Center",
            localities=[RAM],
            routes=30,
            lat=32.0705,
            lon=34.8205,
        ),
        # Not inside any polygon.
        _stop("free", "תל אביב/ללא", "Tel Aviv/Free", routes=5, lat=33.0, lon=35.0),
    ]
    return _Reference(rows, localities)


def _ids(result):
    return [item["id"] for item in result["items"]]


def test_osm_locality_leads_with_central_then_busy_stops_and_demotes_foreign_streets():
    result = search_stops(_reference(), "Tel Aviv", language="en")
    ids = _ids(result)
    # The rail hub carries no feed city, yet polygon containment puts it in the city.
    assert set(ids[:3]) == {STOP_PREFIX + x for x in ("savidor", "dizengoff", "remote")}
    # Route count discounted by distance from the centre: the central rail hub first,
    # the busy-but-remote stop after the quiet central one.
    assert ids[:3] == [STOP_PREFIX + x for x in ("savidor", "dizengoff", "remote")]
    assert ids.index(STOP_PREFIX + "street") > ids.index(STOP_PREFIX + "remote")
    # A stop in no polygon is unknown, not foreign: it keeps its lexical rank.
    assert ids.index(STOP_PREFIX + "free") < ids.index(STOP_PREFIX + "street")


@pytest.mark.parametrize(
    "query",
    [
        "תל אביב",
        "תל אביב יפו",
        "Tel Aviv",
        "tel-aviv",
        "Tel Aviv-Jaffa",
        "Tel Aviv Jaffa",
        "TELAVIV",
    ],
)
def test_locality_names_resolve_in_hebrew_latin_variants_and_compact_spelling(query):
    result = search_stops(_reference(), query, language="en")
    assert result["items"][0]["id"] == STOP_PREFIX + "savidor"


def test_part_of_a_compound_name_names_the_locality():
    rows = [
        _stop("kadima", "קדימה", "Binyamina", localities=["osm:relation:4"], lat=32.5, lon=34.9),
        _stop("other", "אחר", "Other"),
    ]
    reference = _Reference(
        rows, [_locality(4, [("", "Binyamina - Givat Ada", "name")], (32.5, 34.9))]
    )
    assert _ids(search_stops(reference, "Givat Ada", language="en"))[:1] == [STOP_PREFIX + "kadima"]


def test_locality_without_stops_is_ignored_and_ordinary_search_runs():
    rows = [_stop("ghost_street", "Ghostville Road", "Ghostville Road", lat=31.2)]
    reference = _Reference(rows, [_locality(3, [("en", "Ghostville", "name:en")], (31.0, 34.0))])
    result = search_stops(reference, "Ghostville", language="en")
    assert _ids(result) == [STOP_PREFIX + "ghost_street"]


def test_unlisted_city_names_still_use_the_feed_derived_fallback():
    reference = _reference()
    reference.rows.append(
        {
            **_stop("pt", "מרכז פתח תקווה", "Petah Tikva Center", routes=9, lat=32.089, lon=34.886),
            "description": "רחוב:   עיר: פתח תקווה רציף:  קומה: ",
        }
    )
    reference.rows.append(
        {
            **_stop("pt2", "קצה", "Edge", routes=1, lat=32.2, lon=35.0),
            "description": "רחוב:   עיר: פתח תקווה רציף:  קומה: ",
        }
    )
    result = search_stops(reference, "פתח תקווה", language="he")
    assert _ids(result)[:2] == [STOP_PREFIX + "pt", STOP_PREFIX + "pt2"]


def test_reference_without_locality_data_behaves_as_before():
    reference = _Reference(_reference().rows, [])
    # No polygons: "Tel Aviv" is only a lexical query and the street-named stop matches.
    ids = _ids(search_stops(reference, "Tel Aviv St", language="en"))
    assert ids[0] == STOP_PREFIX + "street"


def test_near_still_orders_locality_results_by_distance():
    result = search_stops(
        _reference(), "Tel Aviv", language="en", near=(32.14, 34.84), types=("stop",), limit=3
    )
    assert result["items"][0]["id"] == STOP_PREFIX + "remote"
