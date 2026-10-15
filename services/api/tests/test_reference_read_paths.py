"""API-PERF package A: faster reference reads must return exactly what the SQL paths did.

The oracles below are the previous per-request queries, kept verbatim, so every new path
(translation index, slim stop lookup, ``routes(stopId=…)`` driven from the stop index,
pooled connections and the per-generation result cache) is compared with them.
"""

import itertools
import sqlite3
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_reference import synthetic_feed

from opentransit.reference import (
    CONNECTION_CACHE_KIB,
    CONNECTION_MMAP_BYTES,
    CONNECTION_POOL_IDLE,
    ReferenceStore,
    _TranslationIndex,
    build_reference,
    public_stop_id,
)


def sql_translations(connection, table_name, source_id, field_name, source_value=None):
    """The per-request selector the translation index replaces (one full scan per call)."""
    translations = {}
    for lang, translation in connection.execute(
        "SELECT lang, translation FROM translations "
        "WHERE table_name=? AND field_name=? AND "
        "((record_id=?) OR "
        "(record_id='' AND field_value=?)) "
        "AND (record_sub_id IS NULL OR record_sub_id='') "
        "ORDER BY CASE WHEN record_id<>'' THEN 0 ELSE 1 END, "
        "priority DESC, translation_id",
        (table_name, field_name, source_id, source_value),
    ):
        translations.setdefault(lang.casefold(), translation)
    return translations


def sql_routes_by_stop(connection, stop_id, agency_id=None, short_name=None, after=None):
    """The correlated EXISTS form ``routes(stopId=…)`` used before 1.4 (no LIMIT)."""
    normalized = public_stop_id(stop_id.removeprefix("mot:stop:"))
    clauses = [
        "EXISTS (SELECT 1 FROM route_stops rs WHERE rs.route_id=r.route_id "
        "AND (rs.stop_id=? OR rs.stop_id IN "
        "(SELECT stop_id FROM stops WHERE parent_station=?)))"
    ]
    args = [normalized, normalized]
    for clause, value in (
        ("r.agency_id=?", agency_id),
        ("r.short_name=?", short_name),
        ("r.route_id > ?", after),
    ):
        if value is not None:
            clauses.append(clause)
            args.append(value)
    sql = "SELECT r.* FROM routes r WHERE " + " AND ".join(clauses) + " ORDER BY r.route_id"
    connection.row_factory = sqlite3.Row
    return [dict(row) for row in connection.execute(sql, args)]


TRANSLATION_ROWS = [
    # (table, lang, translation, field, record_id, record_sub_id, field_value, priority)
    ("stops", "he", "value-he-low", "stop_name", "", None, "Central", 1),
    ("stops", "HE", "value-he-high", "stop_name", "", "", "Central", 5),
    ("stops", "en", "value-en-null-priority", "stop_name", "", None, "Central", None),
    ("stops", "ar", "value-ar", "stop_name", "", None, "Central", 0),
    ("stops", "en", "record-en", "stop_name", "station", None, "Central", None),
    ("stops", "En", "record-en-second", "stop_name", "station", None, None, 9),
    ("stops", "ru", "record-ru", "stop_name", "station", "", None, None),
    ("stops", "fr", "sub-record-ignored", "stop_name", "station", "x", None, 99),
    ("stops", "fr", "sub-value-ignored", "stop_name", "", "x", "Central", 99),
    ("stops", "de", "other-field", "stop_desc", "station", None, "Central", 99),
    ("routes", "de", "other-table", "stop_name", "station", None, "Central", 99),
    ("stops", "he", "harbor-he", "stop_name", "", None, "Harbor", None),
    ("stops", "he", "null-value", "stop_name", "", None, None, None),
    ("routes", "he", "route-record", "route_long_name", "bus_7", None, None, None),
    ("routes", "en", "route-value-ignored", "route_long_name", "", None, None, 5),
]


@pytest.fixture
def translations_db():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE translations (translation_id INTEGER PRIMARY KEY, table_name TEXT NOT "
        "NULL, lang TEXT NOT NULL, translation TEXT NOT NULL, field_name TEXT NOT NULL, "
        "record_id TEXT NOT NULL, record_sub_id TEXT, field_value TEXT, priority INTEGER)"
    )
    connection.executemany(
        "INSERT INTO translations (table_name, lang, translation, field_name, record_id, "
        "record_sub_id, field_value, priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        TRANSLATION_ROWS,
    )
    yield connection
    connection.close()


def test_translation_index_matches_sql_selector_including_language_order(translations_db):
    source_ids = ["station", "bus_7", "missing", ""]
    values = ["Central", "Harbor", "missing", None, ""]
    pairs = [("stops", "stop_name"), ("routes", "route_long_name"), ("stops", "stop_desc")]
    for (table, field), source_id, value in itertools.product(pairs, source_ids, values):
        index = _TranslationIndex(translations_db, table, field)
        expected = sql_translations(translations_db, table, source_id, field, value)
        # Same languages, same winners and the same insertion order (JSON key order).
        assert list(index.resolve(source_id, value).items()) == list(expected.items()), (
            table,
            field,
            source_id,
            value,
        )
    # Record-id rows win (higher priority first, NULL last; languages case-folded) and
    # value rows only add languages, in that order.
    resolved = _TranslationIndex(translations_db, "stops", "stop_name").resolve(
        "station", "Central"
    )
    assert list(resolved.items()) == [
        ("en", "record-en-second"),
        ("ru", "record-ru"),
        ("he", "value-he-high"),
        ("ar", "value-ar"),
    ]


def test_translation_results_are_independent_copies(translations_db):
    index = _TranslationIndex(translations_db, "stops", "stop_name")
    first = index.resolve("station", "Central")
    first["en"] = "edited"
    assert index.resolve("station", "Central")["en"] == "record-en-second"


def _richer_feed(path):
    """The synthetic feed plus routes that reach the station through both platforms, the
    station itself or only another stop, so DISTINCT, ordering and paging all matter."""
    base = synthetic_feed(path.with_name("base.zip"))
    extra = {
        "routes.txt": ["bus_10,op_1,10,Ten,3", "bus_8,op_1,8,Eight,3", "bus_9,op_1,7,Nine,3"],
        "trips.txt": [
            "bus_10,weekday,t10,0,Harbor",
            "bus_8,weekday,t8,0,B",
            "bus_9,weekday,t9,0,C",
        ],
        "stop_times.txt": [
            "t10,10:00:00,10:00:00,station,1,0,0",
            "t10,10:10:00,10:10:00,stop_c,2,0,0",
            "t8,11:00:00,11:00:00,platform_a,1,0,0",
            "t8,11:10:00,11:10:00,platform_b,2,0,0",
            "t9,12:00:00,12:00:00,stop_c,1,0,0",
            "t9,12:10:00,12:10:00,platform_b,2,0,0",
        ],
    }
    with zipfile.ZipFile(base) as source, zipfile.ZipFile(path, "w") as target:
        for name in source.namelist():
            lines = source.read(name).decode("utf-8").splitlines()
            target.writestr(name, "".join(f"{line}\n" for line in lines + extra.get(name, [])))
    return path


@pytest.fixture
def store(tmp_path):
    feed = _richer_feed(tmp_path / "fixture.zip")
    database = tmp_path / "generation" / "reference.sqlite"
    build_reference(feed, database, "fixture-generation")
    store = ReferenceStore(database, "fixture-generation")
    yield store
    store.close()


def _raw(store):
    connection = sqlite3.connect(store._uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _stop_rows(store):
    with _raw(store) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM stops ORDER BY stop_id")]


def test_stop_detail_translations_equal_the_sql_selector_for_every_stop(store):
    with _raw(store) as connection:
        for row in _stop_rows(store):
            expected = sql_translations(
                connection, "stops", row["source_id"], "stop_name", row["name"]
            )
            assert store.stop(row["stop_id"])["translations"] == expected
            assert store.stop(row["source_id"])["translations"] == expected
        route = connection.execute("SELECT route_id, source_id FROM routes").fetchone()
        expected = sql_translations(connection, "routes", route[1], "route_long_name")
    assert store.route(route[0])["translations"] == expected


def test_slim_stop_lookup_matches_the_full_stop_for_every_id_form(store):
    for row in _stop_rows(store):
        full = store.stop(row["stop_id"])
        expected = {
            "stop_id": full["stop_id"],
            "source_id": full["source_id"],
            "platform_code": full["platform_code"],
            "children": [
                {
                    "stop_id": child["stop_id"],
                    "source_id": child["source_id"],
                    "platform_code": child["platform_code"],
                }
                for child in full["children"]
            ],
        }
        assert store.stop_ref(row["stop_id"]) == expected
        assert store.stop_ref(row["source_id"]) == expected
    station = store.stop_ref("mot:stop:station")
    assert [child["source_id"] for child in station["children"]] == ["platform_a", "platform_b"]
    assert store.stop_ref("mot:stop:missing") is None
    assert store.stop("mot:stop:missing") is None
    # The slim lookup needs no database connection at all.
    store.close()
    assert store._idle == []
    assert store.stop_ref("station")["source_id"] == "station"


@pytest.mark.parametrize(
    ("by_agency", "short_name"), [(False, None), (True, None), (False, "7"), (True, "missing")]
)
def test_routes_by_stop_equal_the_exists_query_across_pages(store, by_agency, short_name):
    selectors = [row["stop_id"] for row in _stop_rows(store)]
    selectors += [row["source_id"] for row in _stop_rows(store)] + ["mot:stop:missing"]
    with _raw(store) as connection:
        agency_id = connection.execute("SELECT agency_id FROM agencies").fetchone()[0]
        station_routes = sql_routes_by_stop(connection, "mot:stop:station")
    # The station is reached directly and through both platforms, by several routes.
    assert len(station_routes) == 4
    agency_id = agency_id if by_agency else None
    for selector in selectors:
        with _raw(store) as connection:
            expected = sql_routes_by_stop(connection, selector, agency_id, short_name)
        found, cursor = [], None
        while True:
            page = store.routes(selector, agency_id, short_name, limit=1, cursor=cursor)
            assert len(page["items"]) <= 1
            found.extend(page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert found == expected, selector
        # One page at the default size is the same list.
        assert store.routes(selector, agency_id, short_name)["items"] == expected


def test_routes_by_stop_query_drives_from_the_stop_index(store):
    traced = []
    with store._connect() as connection:
        pass
    connection.set_trace_callback(traced.append)  # The idle connection the query reuses.
    store._routes("mot:stop:station", None, None, 20, None)
    connection.set_trace_callback(None)
    sql = next(statement for statement in traced if "route_stops" in statement)
    plan = " | ".join(row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + sql))
    # The station and both platforms are bound literally; no scan of routes or route_stops.
    assert "'mot:stop:platform_a'" in sql and "'mot:stop:platform_b'" in sql
    assert "route_stops_stop_idx" in plan
    assert "SCAN" not in plan


def test_pooled_connections_are_reused_read_only_and_tuned(store):
    with store._connect() as first:
        pass
    with store._connect() as second:
        assert second is first
        assert second.execute("PRAGMA query_only").fetchone()[0] == 1
        assert second.execute("PRAGMA mmap_size").fetchone()[0] in (0, CONNECTION_MMAP_BYTES)
        assert second.execute("PRAGMA cache_size").fetchone()[0] == -CONNECTION_CACHE_KIB
        with pytest.raises(sqlite3.OperationalError):
            second.execute("DELETE FROM stops")


def test_pool_keeps_a_bounded_number_of_idle_connections_and_drops_failed_ones(store):
    contexts = [store._connect() for _ in range(CONNECTION_POOL_IDLE + 2)]
    opened = [context.__enter__() for context in contexts]
    assert len({id(connection) for connection in opened}) == len(opened)
    for context in contexts:
        context.__exit__(None, None, None)
    assert len(store._idle) == CONNECTION_POOL_IDLE

    with pytest.raises(sqlite3.OperationalError), store._connect() as connection:
        connection.execute("SELECT * FROM no_such_table")
    assert connection not in store._idle
    assert len(store._idle) == CONNECTION_POOL_IDLE - 1

    store.close()
    assert store._idle == []
    assert store.stop("station")["stop_id"] == "mot:stop:station"
    assert store._idle == []  # A closed store opens and closes per query.


def test_construction_holds_no_connection_open(store):
    fresh = ReferenceStore(store.path, "fixture-generation")
    assert fresh._idle == []
    fresh.stop("station")
    assert len(fresh._idle) == 1
    fresh.close()


def test_concurrent_reads_from_many_threads_match_single_threaded_results(store):
    stop_ids = [row["stop_id"] for row in _stop_rows(store)]
    expected = {stop_id: store._stop(stop_id) for stop_id in stop_ids}
    expected_routes = {
        stop_id: store._routes(stop_id, None, None, 20, None) for stop_id in stop_ids
    }
    barrier = threading.Barrier(8)

    def read(index):
        barrier.wait()
        stop_id = stop_ids[index % len(stop_ids)]
        return (
            stop_id,
            store.stop(stop_id),
            store.routes(stop_id),
            store.patterns("bus_7"),
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(read, range(64)))
    for stop_id, stop, routes, patterns in results:
        assert stop == expected[stop_id]
        assert routes == expected_routes[stop_id]
        assert patterns == store._patterns("bus_7", 20, None)
    assert len(store._idle) <= CONNECTION_POOL_IDLE


def test_cached_results_equal_fresh_queries_and_cannot_be_edited_by_callers(store):
    first = store.stop("mot:stop:station")
    first["translations"]["he"] = "edited"
    first["children"].clear()
    again = store.stop("mot:stop:station")
    assert again == store._stop("mot:stop:station")
    assert again["translations"]["he"] == "תחנה מרכזית"
    assert len(again["children"]) == 2

    route = store.route("bus_7")
    route["patterns"].clear()
    assert store.route("bus_7") == store._route("bus_7", 20)
    page = store.patterns("bus_7", limit=1)
    assert store.patterns("bus_7", limit=1) == store._patterns("bus_7", 1, None)
    assert store.patterns("bus_7", limit=1, cursor=page["next_cursor"]) == store._patterns(
        "bus_7", 1, page["next_cursor"]
    )
    assert store._details["stop"].hits >= 1
    assert store._details["route"].hits >= 1


def test_misses_and_invalid_requests_are_not_cached(store):
    assert store.stop("mot:stop:missing") is None
    assert store.route("mot:route:missing") is None
    assert len(store._details["stop"]) == 0
    assert len(store._details["route"]) == 0
    with pytest.raises(ValueError):
        store.routes("mot:stop:station", cursor="not-a-cursor")
    with pytest.raises(ValueError):
        store.patterns("bus_7", limit=0)
    assert len(store._details["routes"]) == 0
    assert len(store._details["patterns"]) == 0


def test_cursors_stay_bound_to_the_query_through_the_cache(store):
    page = store.routes("mot:stop:station", limit=1)
    assert page["generation_id"] == "fixture-generation"
    with pytest.raises(ValueError, match="different query/generation"):
        store.routes("mot:stop:stop_c", limit=1, cursor=page["next_cursor"] or "x")
