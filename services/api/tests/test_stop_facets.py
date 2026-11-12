"""Stop mode and direction facets; synthetic data only."""

import sqlite3

import pytest
from test_reference import synthetic_feed

from opentransit.reference import build_reference, route_type_mode
from opentransit.stop_facets import (
    StopFacets,
    dominant_mode,
    initial_bearing,
    load_stop_facets,
    mean_bearing,
)


def facets_by_source_id(tmp_path) -> dict[str, StopFacets]:
    feed = synthetic_feed(tmp_path / "feed.zip")
    database = tmp_path / "reference.sqlite"
    build_reference(feed, database, "facets-test")
    connection = sqlite3.connect(database)
    try:
        source_ids = dict(connection.execute("SELECT stop_id, source_id FROM stops"))
        facets = load_stop_facets(connection, route_type_mode)
    finally:
        connection.close()
    return {source_ids[stop_id]: value for stop_id, value in facets.items()}


def tiny(stops=(), routes=(), route_stops=(), pattern_stops=()) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE stops (stop_id TEXT, latitude REAL, longitude REAL, parent_station TEXT);
        CREATE TABLE routes (route_id TEXT, route_type INTEGER);
        CREATE TABLE route_stops (route_id TEXT, stop_id TEXT);
        CREATE TABLE pattern_stops (pattern_id TEXT, sequence INTEGER, stop_id TEXT);
        """
    )
    connection.executemany("INSERT INTO stops VALUES (?, ?, ?, ?)", stops)
    connection.executemany("INSERT INTO routes VALUES (?, ?)", routes)
    connection.executemany("INSERT INTO route_stops VALUES (?, ?)", route_stops)
    connection.executemany("INSERT INTO pattern_stops VALUES (?, ?, ?)", pattern_stops)
    return connection


def test_dominant_mode_prefers_rail_then_light_rail_then_bus():
    assert dominant_mode(["bus", "rail", "bus"]) == "rail"
    assert dominant_mode(["bus", "light_rail"]) == "light_rail"
    assert dominant_mode(["bus"]) == "bus"
    assert dominant_mode(["ferry"]) == "other"
    assert dominant_mode([]) is None


def test_initial_bearing_points_the_way_of_travel():
    assert initial_bearing(32.081, 34.781, 32.0801, 34.7801) == pytest.approx(220.3, abs=0.2)
    assert initial_bearing(32.0, 34.0, 32.1, 34.0) == pytest.approx(0.0, abs=0.1)
    assert initial_bearing(32.0, 34.0, 32.0, 34.1) == pytest.approx(90.0, abs=0.1)
    assert initial_bearing(32.0, 34.0, 32.0, 34.0) is None


def test_mean_bearing_crosses_north_and_refuses_disagreement():
    assert mean_bearing([350.0, 10.0]) == 0.0
    assert mean_bearing([80.0, 100.0]) == pytest.approx(90.0, abs=0.1)
    assert mean_bearing([40.0, 40.0, 220.0]) is None
    assert mean_bearing([0.0, 90.0]) is None
    assert mean_bearing([]) is None


def test_facets_of_the_synthetic_feed(tmp_path):
    found = facets_by_source_id(tmp_path)
    assert found["platform_b"] == StopFacets("bus", pytest.approx(220.3, abs=0.2), "next_stop")
    assert found["stop_c"] == StopFacets("bus", pytest.approx(220.3, abs=0.2), "next_stop")
    assert found["station"] == StopFacets("bus", pytest.approx(220.3, abs=0.2), "previous_stop")
    assert found["platform_a"] == StopFacets("bus", None, None)


def test_a_stop_nothing_serves_has_no_facts():
    connection = tiny(stops=[("lonely", 32.0, 34.0, None)])
    assert load_stop_facets(connection, route_type_mode)["lonely"] == StopFacets(None, None, None)


def test_a_repeated_call_gives_no_direction_of_its_own():
    connection = tiny(
        stops=[("x", 32.0, 34.0, None), ("y", 32.1, 34.0, None)],
        pattern_stops=[("p", 1, "x"), ("p", 2, "x"), ("p", 3, "y")],
    )
    facets = load_stop_facets(connection, route_type_mode)
    assert facets["x"].bearing_degrees == pytest.approx(0.0, abs=0.1)


def test_rail_wins_and_a_parent_takes_its_platforms_mode():
    connection = tiny(
        stops=[
            ("hub", 32.0, 34.0, None),
            ("parent", 32.0, 34.0, None),
            ("platform", 32.0, 34.0, "parent"),
            ("odd", 32.0, 34.0, None),
        ],
        routes=[("bus", 3), ("train", 2), ("unknown", 9999)],
        route_stops=[("bus", "hub"), ("train", "hub"), ("train", "platform"), ("unknown", "odd")],
    )
    facets = load_stop_facets(connection, route_type_mode)
    assert (facets["hub"].mode, facets["parent"].mode, facets["odd"].mode) == (
        "rail",
        "rail",
        "other",
    )
