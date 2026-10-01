"""Synthetic GTFS reference-store tests; no feed downloads or live evidence."""

import csv
import sqlite3
import zipfile

import pytest

from opentransit.reference import ReferenceStore, build_reference


def synthetic_feed(path):
    members = {
        "agency.txt": (
            ["agency_id", "agency_name", "agency_url", "agency_timezone"],
            [["op_1", "Synthetic operator", "https://example.test", "Asia/Jerusalem"]],
        ),
        "routes.txt": (
            ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type"],
            [["bus_7", "op_1", "7", "Loop", "3"]],
        ),
        "stops.txt": (
            [
                "stop_id",
                "stop_code",
                "stop_name",
                "stop_lat",
                "stop_lon",
                "location_type",
                "parent_station",
                "platform_code",
            ],
            [
                ["platform_a", "A", "Central A", "32.0801", "34.7801", "0", "station", "A"],
                ["platform_b", "B", "Central B", "32.081", "34.781", "0", "station", "B"],
                ["station", "S", "Central", "32.08", "34.78", "1", "", ""],
                ["stop_c", "C", "Harbor", "32.082", "34.782", "0", "", ""],
            ],
        ),
        "translations.txt": (
            [
                "table_name",
                "field_name",
                "language",
                "translation",
                "record_id",
                "record_sub_id",
                "field_value",
            ],
            [["stops", "stop_name", "he", "תחנה מרכזית", "station", "", "Central"]],
        ),
        "trips.txt": (
            ["route_id", "service_id", "trip_id", "direction_id", "trip_headsign"],
            [
                ["bus_7", "weekday", "trip_loop", "0", "Harbor"],
                ["bus_7", "weekday", "trip_reverse", "1", "Central"],
                ["bus_7", "weekend", "trip_loop_variant", "0", "Harbor"],
            ],
        ),
        "calendar.txt": (
            [
                "service_id",
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
                "start_date",
                "end_date",
            ],
            [
                ["weekday", "1", "1", "1", "1", "1", "0", "0", "20250101", "20251231"],
                ["weekend", "1", "1", "1", "1", "1", "0", "0", "20250101", "20251231"],
            ],
        ),
        "calendar_dates.txt": (
            ["service_id", "date", "exception_type"],
            [["weekend", "20250101", "2"]],
        ),
        # Deliberately out of sequence order; repeated platform_a is a distinct call.
        "stop_times.txt": (
            [
                "trip_id",
                "arrival_time",
                "departure_time",
                "stop_id",
                "stop_sequence",
                "pickup_type",
                "drop_off_type",
            ],
            [
                ["trip_loop", "08:30:00", "08:30:00", "platform_a", "17", "0", "0"],
                ["trip_loop", "08:00:00", "08:00:00", "platform_a", "5", "0", "0"],
                ["trip_loop", "08:15:00", "08:15:00", "platform_b", "9", "1", "2"],
                ["trip_loop", "09:00:00", "09:00:00", "stop_c", "21", "0", "0"],
                ["trip_reverse", "09:00:00", "09:00:00", "stop_c", "1", "0", "0"],
                ["trip_reverse", "09:15:00", "09:15:00", "platform_b", "2", "0", "0"],
                ["trip_reverse", "09:30:00", "09:30:00", "platform_a", "3", "0", "0"],
                ["trip_reverse", "09:45:00", "09:45:00", "station", "4", "0", "0"],
                ["trip_loop_variant", "08:00:00", "08:00:00", "platform_a", "5", "0", "0"],
                ["trip_loop_variant", "08:15:00", "08:15:00", "platform_b", "9", "1", "2"],
                ["trip_loop_variant", "08:30:00", "08:30:00", "platform_a", "17", "0", "0"],
                ["trip_loop_variant", "09:00:00", "09:00:00", "stop_c", "21", "0", "0"],
            ],
        ),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, (fields, rows) in members.items():
            from io import StringIO

            stream = StringIO()
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(fields)
            writer.writerows(rows)
            archive.writestr(name, stream.getvalue())
    return path


@pytest.fixture
def reference(tmp_path):
    feed = synthetic_feed(tmp_path / "fixture.zip")
    database = tmp_path / "generation" / "reference.sqlite"
    metadata = build_reference(feed, database, "fixture-generation")
    return database, metadata


def test_build_records_provenance_and_queries_parent_routes_and_patterns(reference):
    database, metadata = reference
    assert metadata.generation_id == "fixture-generation"
    assert len(metadata.source_sha256) == len(metadata.content_sha256) == 64
    assert metadata.counts["stops"] == 4
    assert metadata.counts["pattern_stops"] == 8
    assert metadata.counts["trip_profiles"] == 3
    assert metadata.counts["clock_profiles"] == 2
    timing_policy = metadata.as_dict()["timingPolicy"]
    assert timing_policy == {
        "policyId": "motis-minute-bracket-v1",
        "version": 1,
        "resolutionSeconds": 60,
        "motisSourceCommit": "061857d38a375248ae62b4ce722753368a75e474",
        "nigiriSourceCommit": "0a08a1c09dad25c5d892b2fd7166b03e82d62970",
        "firstArrivalProjected": False,
        "finalDepartureProjected": False,
    }

    store = ReferenceStore(database, "fixture-generation")
    station = store.stop("mot:stop:station")
    assert station["source_id"] == "station"
    assert station["translations"] == {"he": "תחנה מרכזית"}
    platform = store.stop("platform_b")
    assert platform["parent_station"] == "mot:stop:station"
    assert platform["wheelchair_boarding"] is None
    assert platform["routes"][0]["route_id"] == "mot:route:bus_7"
    assert [route["route_id"] for route in station["routes"]] == ["mot:route:bus_7"]
    assert len(station["children"]) == 2

    route = store.route("mot:route:bus_7")
    assert route["agency"]["name"] == "Synthetic operator"
    pattern_page = store.patterns("bus_7", limit=1)
    assert pattern_page["next_cursor"]
    sequences = [
        [call["stop_id"] for call in pattern["stops"]] for pattern in pattern_page["items"]
    ]
    next_page = store.patterns("bus_7", limit=1, cursor=pattern_page["next_cursor"])
    sequences.extend(
        [[call["stop_id"] for call in pattern["stops"]] for pattern in next_page["items"]]
    )
    assert [
        "mot:stop:platform_a",
        "mot:stop:platform_b",
        "mot:stop:platform_a",
        "mot:stop:stop_c",
    ] in sequences
    loop = next(
        pattern
        for pattern in pattern_page["items"] + next_page["items"]
        if len(pattern["stops"]) == 4
        and pattern["stops"][0]["stop_id"] == pattern["stops"][2]["stop_id"]
    )
    assert (loop["stops"][1]["pickup_type"], loop["stops"][1]["drop_off_type"]) == (1, 2)
    route_page = store.route("bus_7", pattern_limit=1)
    assert route_page["patterns_count"] == 2
    assert route_page["patterns_truncated"] is True


def test_nearby_and_bbox_pagination_are_bound_to_generation_and_query(reference):
    database, _ = reference
    store = ReferenceStore(database)
    first = store.stops_near(32.08, 34.78, radius_m=500, limit=2)
    assert len(first["items"]) == 2
    assert first["items"][0]["distance_m"] <= first["items"][1]["distance_m"]
    assert first["next_cursor"]
    second = store.stops_near(32.08, 34.78, radius_m=500, limit=2, cursor=first["next_cursor"])
    assert not {item["stop_id"] for item in first["items"]} & {
        item["stop_id"] for item in second["items"]
    }
    with pytest.raises(ValueError, match="different query/generation"):
        store.stops_near(32.08, 34.78, radius_m=501, limit=2, cursor=first["next_cursor"])

    page = store.stops_in_bbox(32.079, 34.779, 32.083, 34.783, limit=2)
    assert len(page["items"]) == 2
    rest = store.stops_in_bbox(32.079, 34.779, 32.083, 34.783, limit=2, cursor=page["next_cursor"])
    assert len(rest["items"]) == 2


def test_route_filters_and_cursor_pagination(reference):
    database, _ = reference
    store = ReferenceStore(database)
    by_stop = store.routes(stop_id="platform_b")
    assert by_stop["items"][0]["short_name"] == "7"
    assert store.routes(stop_id="station")["items"][0]["short_name"] == "7"
    by_label = store.routes(short_name="7")
    assert [row["source_id"] for row in by_label["items"]] == ["bus_7"]
    with pytest.raises(ValueError, match="route selector"):
        store.routes()


@pytest.mark.parametrize(
    "call",
    [
        lambda store: store.stops_near(32, 34, radius_m=5001),
        lambda store: store.stops_in_bbox(32, 34, 33, 35),
        lambda store: store.routes(limit=101),
    ],
)
def test_query_bounds_are_enforced(reference, call):
    with pytest.raises(ValueError):
        call(ReferenceStore(reference[0]))


def test_generation_verification_and_output_are_immutable(tmp_path):
    feed = synthetic_feed(tmp_path / "fixture.zip")
    database = tmp_path / "reference.sqlite"
    build_reference(feed, database, "g1")
    with pytest.raises(FileExistsError):
        build_reference(feed, database, "g2")
    with pytest.raises(ValueError, match="different generation"):
        ReferenceStore(database, "g2")

    database.chmod(0o600)
    connection = sqlite3.connect(database)
    connection.execute("UPDATE stops SET name='tampered' WHERE source_id='station'")
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="content verification"):
        ReferenceStore(database)


def test_composed_generation_keeps_component_bytes_and_uses_public_cursor_namespace(reference):
    database, _ = reference
    component = ReferenceStore(database, "fixture-generation")
    composed = ReferenceStore(
        database,
        "fixture-generation",
        cursor_generation_id="composite-address-generation",
    )
    assert composed.component_generation_id == component.component_generation_id
    assert composed.stop("station") == component.stop("station")
    assert composed.metadata.generation_id == "composite-address-generation"
    with pytest.raises(ValueError, match="different generation"):
        ReferenceStore(
            database,
            "wrong-component",
            cursor_generation_id="composite-address-generation",
        )

    first = composed.stops_near(32.08, 34.78, radius_m=500, limit=2)
    with pytest.raises(ValueError, match="different query/generation"):
        component.stops_near(32.08, 34.78, radius_m=500, limit=2, cursor=first["next_cursor"])


def test_source_profiles_preserve_full_identity_raw_projection_and_loop_ordinals(reference):
    store = ReferenceStore(reference[0])
    profile = store.source_profile("trip_loop")
    assert profile.trip_id == "trip_loop"
    assert profile.service_id == "weekday"
    assert [(call.sequence, call.ordinal, call.stop_id) for call in profile.calls] == [
        (5, 0, "platform_a"),
        (9, 1, "platform_b"),
        (17, 2, "platform_a"),
        (21, 3, "stop_c"),
    ]
    assert (profile.calls[1].pickup_type, profile.calls[1].drop_off_type) == (1, 2)
    from opentransit.core.trip_calls import project_profile

    projection = project_profile(profile)
    assert [(event.sequence, event.kind, event.raw_seconds) for event in projection.events] == [
        (5, "departure", 8 * 3600),
        (9, "arrival", 8 * 3600 + 15 * 60),
        (9, "departure", 8 * 3600 + 15 * 60),
        (17, "arrival", 8 * 3600 + 30 * 60),
        (17, "departure", 8 * 3600 + 30 * 60),
        (21, "arrival", 9 * 3600),
    ]
    assert projection.raw_events[0].projected is False
    assert projection.raw_events[-1].projected is False
    assert projection.raw_events[0].effective_seconds is None
    assert projection.raw_events[-1].effective_seconds is None
    with sqlite3.connect(reference[0]) as connection:
        stored = connection.execute(
            "SELECT source_sequence, arrival_seconds, departure_seconds, "
            "effective_arrival_seconds, effective_departure_seconds "
            "FROM clock_profile_calls WHERE profile_id=(SELECT profile_id FROM trip_profiles "
            "WHERE source_trip_id='trip_loop') ORDER BY ordinal"
        ).fetchall()
    assert stored[0] == (5, 8 * 3600, 8 * 3600, None, 8 * 3600)
    assert stored[1] == (
        9,
        8 * 3600 + 15 * 60,
        8 * 3600 + 15 * 60,
        8 * 3600 + 15 * 60,
        8 * 3600 + 15 * 60,
    )
    assert stored[-1] == (21, 9 * 3600, 9 * 3600, 9 * 3600, None)
    assert store.source_profile("unknown/full-trip-id") is None
    assert store.service_active("weekday", "2025-01-01") is True
    assert store.service_active("weekend", "2025-01-01") is False
    assert store.service_active("unrecorded", "2025-01-01") is None


def test_reference_content_and_profile_dedup_are_deterministic(tmp_path):
    feed = synthetic_feed(tmp_path / "fixture.zip")
    first = build_reference(feed, tmp_path / "first.sqlite", "stable")
    second = build_reference(feed, tmp_path / "second.sqlite", "stable")
    assert first.content_sha256 == second.content_sha256
    assert first.counts["trip_profiles"] == 3
    assert first.counts["clock_profiles"] == 2
    store = ReferenceStore(tmp_path / "first.sqlite")
    assert store.source_profile("trip_loop_variant").service_id == "weekend"


def test_source_profile_bound_fails_instead_of_returning_a_truncated_loop(reference, monkeypatch):
    import opentransit.reference as reference_module

    store = ReferenceStore(reference[0])
    monkeypatch.setattr(reference_module, "MAX_SOURCE_PROFILE_CALLS", 3)
    with pytest.raises(reference_module.SourceProfileLimitError, match="Complete source trip"):
        store.source_profile("trip_loop")
    monkeypatch.setattr(reference_module, "MAX_SOURCE_PROFILE_CALLS", 4)
    profile = store.source_profile("trip_loop")
    assert len(profile.calls) == 4
    assert [call.sequence for call in profile.calls] == [5, 9, 17, 21]
