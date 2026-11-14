"""Stations over a large area (A1) and line search (A2); synthetic feed, no live evidence."""

import csv
import zipfile
from io import StringIO

import pytest
from test_localities import PBF_SHA, _polygon, _square, _write_context
from test_reference_api import reference_client

from opentransit.api.docs import LineResponse, LinesResponse
from opentransit.api.rate_limit import classify
from opentransit.line_search import line_index, line_key
from opentransit.localities import load_locality_context
from opentransit.reference import ReferenceStore, build_reference

COUNTRY = (29.4, 34.2, 33.4, 35.9)  # south, west, north, east: about 70,000 km²
TEL_AVIV = "תל אביב-יפו"

STOPS = [
    # stop_id, name, lat, lon, location_type, parent
    ("rail_n", "Haifa Center", "32.79", "35.0", "0", ""),
    ("rail_s", "Beer Sheva", "31.24", "34.79", "0", ""),
    ("lr_st", "Allenby", "32.07", "34.77", "1", ""),
    ("lr_p1", "Allenby 1", "32.0701", "34.7701", "0", "lr_st"),
    ("lr_p2", "Allenby 2", "32.0699", "34.7699", "0", "lr_st"),
    ("lr_x", "Carlebach", "32.075", "34.775", "0", ""),
    ("b1", "Reading", "32.1", "34.79", "0", ""),
    ("b2", "Dizengoff", "32.08", "34.774", "0", ""),
    ("b3", "Pilots", "32.06", "34.78", "0", ""),
    ("h1", "Haifa bus", "32.791", "35.001", "0", ""),
    ("h2", "Hadar", "32.8", "35.02", "0", ""),
    ("e1", "Eilat", "29.55", "34.95", "0", ""),
    ("e2", "Eilat port", "29.56", "34.96", "0", ""),
]
ROUTES = [
    # route_id, agency, short name, desc, type, stops in order, headsign
    ("rail1", "2", "", "10001-1-0", "2", ["rail_n", "rail_s"], "Beer Sheva"),
    ("lr1", "9", "R1", "20001-1-0", "0", ["lr_p1", "lr_x"], "Carlebach"),
    ("lr2", "9", "R1", "20001-2-0", "0", ["lr_x", "lr_p2"], "Allenby"),
    ("d8a", "5", "8", "55008-1-0", "3", ["b1", "b2", "b3"], "Pilots"),
    ("d8b", "5", "8", "55008-2-0", "3", ["b3", "b2", "b1"], "Reading"),
    ("d80", "5", "80", "55080-1-0", "3", ["b1", "b3"], "Pilots"),
    ("d82", "5", "82", "55082-1-0", "3", ["b2", "b3"], "Pilots"),
    ("e8", "3", "8", "30008-1-0", "3", ["h1", "h2"], "Hadar"),
    ("e8a", "3", "8א", "30018-1-0", "3", ["e1", "e2"], "Port"),
    ("x8", "3", "8", "", "3", ["e2", "e1"], None),  # No line code: a line of its own.
]


def lines_feed(path):
    stop_times = []
    for route_id, *_, stops, _ in ROUTES:
        for sequence, stop_id in enumerate(stops, start=1):
            clock = f"08:{sequence * 5:02d}:00"
            stop_times.append([f"t_{route_id}", clock, clock, stop_id, str(sequence)])
    members = {
        "agency.txt": (
            ["agency_id", "agency_name", "agency_url", "agency_timezone"],
            [
                [agency, name, "https://example.test", "Asia/Jerusalem"]
                for agency, name in (("2", "רכבת ישראל"), ("3", "אגד"), ("5", "דן"), ("9", "LR"))
            ],
        ),
        "routes.txt": (
            ["route_id", "agency_id", "route_short_name", "route_long_name", "route_desc"]
            + ["route_type"],
            [[r[0], r[1], r[2], f"Line {r[0]}", r[3], r[4]] for r in ROUTES],
        ),
        "stops.txt": (
            ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type", "parent_station"],
            [list(stop) for stop in STOPS],
        ),
        "trips.txt": (
            ["route_id", "service_id", "trip_id", "direction_id", "trip_headsign"],
            [[r[0], "s", f"t_{r[0]}", "0", r[6] or ""] for r in ROUTES],
        ),
        "calendar.txt": (
            ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday"]
            + ["saturday", "sunday", "start_date", "end_date"],
            [["s", "1", "1", "1", "1", "1", "1", "1", "20260101", "20261231"]],
        ),
        "stop_times.txt": (
            ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
            stop_times,
        ),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, (fields, rows) in members.items():
            stream = StringIO()
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(fields)
            writer.writerows(rows)
            archive.writestr(name, stream.getvalue())
    return path


def tel_aviv(tmp_path):
    tags = {"boundary": "administrative", "admin_level": "8", "name": TEL_AVIV}
    tags |= {"name:he": TEL_AVIV, "name:en": "Tel Aviv-Yafo"}
    context = _write_context(
        tmp_path / "context.jsonl", [(1, tags, _polygon(_square(34.76, 32.05, 34.80, 32.11)))]
    )
    return load_locality_context(context, expected_osm_sha256=PBF_SHA)


@pytest.fixture
def store(tmp_path):
    database = tmp_path / "reference.sqlite"
    feed = lines_feed(tmp_path / "feed.zip")
    build_reference(feed, database, "lines-test", localities=tel_aviv(tmp_path))
    store = ReferenceStore(database, "lines-test")
    yield store
    store.close()


def _ids(page):
    return [item["stop_id"].removeprefix("mot:stop:") for item in page["items"]]


# --- A1: stations over a large area ----------------------------------------------------


def test_station_filter_folds_platforms_and_covers_the_country(store):
    page = store.stops_in_bbox(*COUNTRY, limit=100, modes=["rail", "light_rail"])
    assert _ids(page) == ["lr_st", "lr_x", "rail_n", "rail_s"]
    assert page["next_cursor"] is None
    by_id = {item["stop_id"]: item for item in page["items"]}
    assert by_id["mot:stop:lr_st"]["mode"] == "light_rail"  # From its platforms.
    assert by_id["mot:stop:lr_st"]["location_type"] == 1
    assert by_id["mot:stop:rail_n"]["mode"] == "rail"
    # Items are today's stop items, with mode and direction.
    assert {"mode", "bearing_degrees", "bearing_source", "platform_code"} <= set(
        by_id["mot:stop:lr_x"]
    )
    assert _ids(store.stops_in_bbox(*COUNTRY, modes=["rail"])) == ["rail_n", "rail_s"]
    assert _ids(store.stops_in_bbox(*COUNTRY, modes=["light_rail"])) == ["lr_st", "lr_x"]
    # The bbox still bounds the result: only Tel Aviv's stations.
    assert _ids(store.stops_in_bbox(32.0, 34.7, 32.2, 34.9, modes=["light_rail", "rail"])) == [
        "lr_st",
        "lr_x",
    ]


def test_station_filter_pages_and_binds_the_cursor_to_the_modes(store):
    first = store.stops_in_bbox(*COUNTRY, limit=3, modes=["rail", "light_rail"])
    assert _ids(first) == ["lr_st", "lr_x", "rail_n"]
    second = store.stops_in_bbox(
        *COUNTRY, limit=3, cursor=first["next_cursor"], modes=["light_rail", "rail"]
    )
    assert _ids(second) == ["rail_s"] and second["next_cursor"] is None
    with pytest.raises(ValueError, match="different query/generation"):
        store.stops_in_bbox(*COUNTRY, limit=3, cursor=first["next_cursor"], modes=["rail"])


def test_other_mode_filters_keep_the_small_area_and_list_platforms(store):
    with pytest.raises(ValueError, match="area limit"):
        store.stops_in_bbox(*COUNTRY, modes=["bus"])
    with pytest.raises(ValueError, match="area limit"):
        store.stops_in_bbox(*COUNTRY, modes=["rail", "bus"])
    with pytest.raises(ValueError, match="area limit"):
        store.stops_in_bbox(*COUNTRY)
    box = (32.05, 34.76, 32.11, 34.80)
    assert _ids(store.stops_in_bbox(*box, modes=["bus"])) == ["b1", "b2", "b3"]
    mixed = _ids(store.stops_in_bbox(*box, limit=100, modes=["bus", "light_rail"]))
    assert mixed == ["b1", "b2", "b3", "lr_p1", "lr_p2", "lr_st", "lr_x"]
    first = store.stops_in_bbox(*box, limit=2, modes=["bus"])
    rest = store.stops_in_bbox(*box, limit=2, cursor=first["next_cursor"], modes=["bus"])
    assert _ids(first) + _ids(rest) == ["b1", "b2", "b3"]
    unfiltered = _ids(store.stops_in_bbox(*box, limit=100))
    assert "lr_p1" in unfiltered and "b1" in unfiltered
    with pytest.raises(ValueError, match="Unknown stop mode"):
        store.stops_in_bbox(*box, modes=["tram"])
    with pytest.raises(ValueError, match="Unknown stop mode"):
        store.stops_in_bbox(*box, modes=[])


def test_stops_endpoint_mode_filter(manifest, engine_route):
    with reference_client(manifest, engine_route, feed_builder=lines_feed) as client:
        country = "34.2,29.4,35.9,33.4"
        response = client.get("/v1/stops", params={"bbox": country, "mode": "rail,light_rail"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert [item["sourceId"] for item in body["data"]] == ["lr_st", "lr_x", "rail_n", "rail_s"]
        assert body["data"][0]["mode"] == "light_rail" and "bearingDegrees" in body["data"][0]
        assert body["page"] == {"nextCursor": None}
        paged = client.get(
            "/v1/stops", params={"bbox": country, "mode": "rail,light_rail", "limit": 2}
        ).json()
        rest = client.get(
            "/v1/stops",
            params={
                "bbox": country,
                "mode": "light_rail,rail",
                "limit": 2,
                "cursor": paged["page"]["nextCursor"],
            },
        )
        assert [item["sourceId"] for item in rest.json()["data"]] == ["rail_n", "rail_s"]
        for params in (
            {"bbox": country, "mode": "bus"},
            {"bbox": country, "mode": "rail,bus"},
            {"bbox": country, "mode": "tram"},
            {"bbox": country, "mode": "rail,rail"},
            {"bbox": country, "mode": "rail,"},
            {"near": "32.07,34.77", "mode": "rail"},
        ):
            refused = client.get("/v1/stops", params=params)
            assert refused.status_code == 422, params
            assert refused.json()["code"] == "INVALID_REQUEST"
        local = client.get("/v1/stops", params={"bbox": "34.76,32.05,34.80,32.11", "mode": "bus"})
        assert [item["sourceId"] for item in local.json()["data"]] == ["b1", "b2", "b3"]


# --- A2: line search ---------------------------------------------------------------------


def _keys(page):
    return [item["lineKey"] for item in page["items"]]


def test_line_keys_group_directions_by_operator_and_line_code(store):
    index = line_index(store)
    assert line_index(store) is index  # Built once per store.
    dan8 = index.by_key["5:55008"]
    assert dan8.route_ids == ("mot:route:d8a", "mot:route:d8b")
    assert (dan8.short_name, dan8.operator_name, dan8.mode) == ("8", "דן", "bus")
    assert "3:30008" in index.by_key  # Egged's 8 in Haifa is another line.
    assert index.by_key["3:route:x8"].route_ids == ("mot:route:x8",)
    assert index.by_key["9:20001"].mode == "light_rail"
    assert line_key("5", "55008-2-0", "d8b") == "5:55008"
    assert line_key("5", None, "r") == "5:route:r"


def test_exact_number_first_then_prefix_by_number(store):
    page = line_index(store).search("8")
    assert _keys(page) == ["3:30008", "3:route:x8", "5:55008", "3:30018", "5:55080", "5:55082"]
    assert all("nearestStop" not in item for item in page["items"])
    assert line_index(store).search(" 8 ")["items"] == page["items"]
    assert _keys(line_index(store).search("80")) == ["5:55080"]
    assert _keys(line_index(store).search("r")) == ["9:20001"]  # Case-insensitive.
    assert line_index(store).search("9")["items"] == []
    for bad in ("", "   ", "x" * 51):
        with pytest.raises(ValueError):
            line_index(store).search(bad)
    with pytest.raises(ValueError):
        line_index(store).search("8", 32.08, None)
    with pytest.raises(ValueError):
        line_index(store).search("8", limit=51)


def test_nearest_lines_first_within_each_group(store):
    page = line_index(store).search("8", 32.08, 34.774)  # At Dizengoff (b2).
    assert _keys(page) == ["5:55008", "3:30008", "3:route:x8", "5:55082", "3:30018", "5:55080"]
    dan8, egged8 = page["items"][0], page["items"][1]
    assert dan8["nearestStop"] == {"stopId": "mot:stop:b2", "name": "Dizengoff", "distanceM": 0}
    assert egged8["nearestStop"] is None  # Haifa is not within 2 km.
    # Line 80 stops at Reading and Pilots only, both just over 2 km away.
    assert page["items"][-1]["nearestStop"] is None


def test_line_item_shape(store):
    [item] = [i for i in line_index(store).search("8")["items"] if i["lineKey"] == "5:55008"]
    assert item == {
        "lineKey": "5:55008",
        "shortName": "8",
        "operatorId": "5",
        "operatorName": "דן",
        "mode": "bus",
        "routeIds": ["mot:route:d8a", "mot:route:d8b"],
        "directions": [
            {
                "routeId": "mot:route:d8a",
                "headsign": "Pilots",
                "originName": "Reading",
                "destinationName": "Pilots",
            },
            {
                "routeId": "mot:route:d8b",
                "headsign": "Reading",
                "originName": "Pilots",
                "destinationName": "Reading",
            },
        ],
        "area": TEL_AVIV,
    }
    egged = line_index(store).line("3:30008")
    assert egged["area"] is None  # No locality holds its stops.
    assert line_index(store).line("3:route:x8")["directions"][0]["headsign"] is None
    assert line_index(store).line("5:99999") is None


def test_line_search_pages_with_a_bound_cursor(store):
    index = line_index(store)
    everything = _keys(index.search("8", 32.08, 34.774))
    seen, cursor = [], None
    while True:
        page = index.search("8", 32.08, 34.774, limit=4, cursor=cursor)
        seen += _keys(page)
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == everything
    first = index.search("8", limit=2)
    with pytest.raises(ValueError, match="different query"):
        index.search("8", 32.08, 34.774, limit=2, cursor=first["next_cursor"])
    with pytest.raises(ValueError, match="different query"):
        index.search("80", limit=2, cursor=first["next_cursor"])


def test_lines_endpoints(manifest, engine_route, tmp_path):
    with reference_client(
        manifest, engine_route, feed_builder=lines_feed, localities=tel_aviv(tmp_path)
    ) as client:
        response = client.get("/v1/lines", params={"q": "8", "lat": 32.08, "lon": 34.774})
        assert response.status_code == 200, response.text
        body = response.json()
        LinesResponse.model_validate(body)
        assert body["data"][0]["lineKey"] == "5:55008"
        assert body["data"][0]["area"] == TEL_AVIV
        assert body["data"][0]["nearestStop"]["distanceM"] == 0
        assert body["page"] == {"nextCursor": None}
        first = client.get("/v1/lines", params={"q": "8", "limit": 2}).json()
        assert len(first["data"]) == 2 and first["page"]["nextCursor"]
        second = client.get(
            "/v1/lines", params={"q": "8", "limit": 2, "cursor": first["page"]["nextCursor"]}
        )
        assert second.status_code == 200
        wrong = client.get("/v1/lines", params={"q": "80", "cursor": first["page"]["nextCursor"]})
        assert wrong.status_code == 422 and wrong.json()["code"] == "INVALID_CURSOR"
        one = client.get("/v1/lines/5:55008")
        assert one.status_code == 200
        LineResponse.model_validate(one.json())
        assert "nearestStop" not in one.json()["data"]
        located = client.get("/v1/lines/5:55008", params={"lat": 32.06, "lon": 34.78}).json()
        assert located["data"]["nearestStop"]["stopId"] == "mot:stop:b3"
        assert client.get("/v1/lines/5:99999").status_code == 404
        for params in (
            {},
            {"q": ""},
            {"q": "  "},
            {"q": "8", "lat": 32.08},
            {"q": "8", "lat": 40, "lon": 34.7},
            {"q": "8", "limit": 51},
        ):
            refused = client.get("/v1/lines", params=params)
            assert refused.status_code == 422, params
            assert refused.headers["content-type"] == "application/problem+json"


def test_line_search_is_a_standard_rate_bucket():
    assert classify("GET", "/v1/lines") == "standard"
    assert classify("GET", "/v1/lines/5:55008") == "standard"
