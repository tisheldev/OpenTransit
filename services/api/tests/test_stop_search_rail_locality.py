"""Rail-station tagging, joined-spelling rescue and locality intent in stop search."""

import json
import sqlite3

from test_reference import synthetic_feed

import opentransit.reference as reference_module
from opentransit.reference import STOP_PREFIX, ReferenceStore, build_reference
from opentransit.stop_search import compact_key, search_stops


class _Reference:
    def __init__(self, rows):
        self.rows = rows

    def stop_search_candidates(self):
        return self.rows


def _stop(
    source_id,
    name,
    en=None,
    *,
    city=None,
    routes=0,
    rail=False,
    lat=32.0,
    lon=34.8,
    location_type=0,
    parent=None,
):
    description = f"רחוב:   עיר: {city} רציף:  קומה: " if city else None
    return {
        "source_id": source_id,
        "stop_id": STOP_PREFIX + source_id,
        "parent_station": parent,
        "location_type": location_type,
        "name": name,
        "description": description,
        "translations": {"en": en} if en else {},
        "code": None,
        "latitude": lat,
        "longitude": lon,
        "route_count": routes,
        "rail": rail,
    }


def _ids(result):
    return [item["id"] for item in result["items"]]


# --- rail stations -------------------------------------------------------------


def test_reference_tags_stops_served_by_rail_routes(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    database = tmp_path / "reference.sqlite"
    build_reference(feed, database, "rail-test")
    database.chmod(0o600)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO routes SELECT 'mot:route:rail_1', 'rail_1', agency_id, 'R', 'Rail', "
            "NULL, 2, NULL, NULL, NULL FROM routes LIMIT 1"
        )
        connection.execute(
            "INSERT INTO route_stops VALUES ('mot:route:rail_1', ?)",
            (STOP_PREFIX + "stop_c",),
        )
        connection.execute(
            "UPDATE metadata SET value=? WHERE key='contentSha256'",
            (json.dumps(reference_module._content_hash(connection)),),
        )

    candidates = ReferenceStore(database, "rail-test").stop_search_candidates()
    assert {row["source_id"]: row["rail"] for row in candidates} == {
        "platform_a": False,
        "platform_b": False,
        "station": False,
        "stop_c": True,
    }


def _rail_rows():
    return [
        _stop("rail", "הרצליה", "Hertsliya", routes=500, rail=True),
        _stop("taxi", "מרינה", "Herzliya Marina Taxi Station", routes=2, lat=32.1),
        _stop("rail_jlm", "ירושלים/יצחק נבון", "Yerushalayim/Yits'hak Navon", rail=True),
        _stop("street_a", "יצחק נבון/הבנים", "Yitzhak Navon/HaBanim", lat=32.5),
        _stop("street_b", "יצחק נבון/הרצל", "Yitzhak Navon/Herzl", lat=32.6),
        _stop("plain_bus", "קו 5", "Line 5"),
    ]


def test_rail_stop_is_a_station_and_still_a_stop():
    reference = _Reference(_rail_rows())
    both = search_stops(reference, "Hertsliya", language="en", types=("stop", "station"))
    assert both["items"][0]["id"] == STOP_PREFIX + "rail"
    assert both["items"][0]["kind"] == "station"
    assert both["items"][0]["matchedTypes"] == ["station"]
    station_only = search_stops(reference, "Hertsliya", language="en", types=("station",))
    assert _ids(station_only) == [STOP_PREFIX + "rail"]
    stop_only = search_stops(reference, "Hertsliya", language="en", types=("stop",))
    assert stop_only["items"][0]["kind"] == "stop"
    # Plain bus stops stay stops: not selectable as stations.
    assert search_stops(reference, "Line 5", language="en", types=("station",))["items"] == []


def test_station_word_variants_let_the_city_name_reach_the_rail_stop():
    reference = _Reference(_rail_rows())
    result = search_stops(reference, "Herzliya Station", language="en")
    assert result["items"][0]["id"] == STOP_PREFIX + "rail"
    hebrew = search_stops(reference, "תחנת רכבת הרצליה", language="he")
    assert hebrew["items"][0]["id"] == STOP_PREFIX + "rail"


def test_rail_city_slash_place_name_is_searchable_by_its_place_part():
    reference = _Reference(_rail_rows())
    # Street-named bus stops match "Yitzhak Navon" literally; the rail station named
    # "City/Yits'hak Navon" now leads through its place part and a spelling fold.
    result = search_stops(reference, "Yitzhak Navon", language="en")
    assert result["items"][0]["id"] == STOP_PREFIX + "rail_jlm"
    assert {STOP_PREFIX + "street_a", STOP_PREFIX + "street_b"} <= set(_ids(result))


# --- joined / split Latin spelling ----------------------------------------------


def _beersheba_rows():
    return [
        _stop("bs", "באר שבע מרכז", "Be'er Sheva Central Station/Alight", lat=31.24, lon=34.8),
        _stop("other", "קו", "Center Line"),
    ]


def test_compact_key_ignores_spaces_apostrophes_and_b_v():
    assert compact_key("beer sheva") == compact_key("beersheba")
    assert compact_key("tikva a").endswith("tikvaa")  # no cross-word letter collapsing


def test_joined_spelling_is_rescued_when_nothing_else_matches():
    reference = _Reference(_beersheba_rows())
    result = search_stops(reference, "Beersheba Central Station", language="en")
    assert _ids(result) == [STOP_PREFIX + "bs"]
    spaced = search_stops(reference, "Beer Sheba Central", language="en")
    assert _ids(spaced) == [STOP_PREFIX + "bs"]


def test_joined_spelling_never_displaces_a_literal_match():
    rows = [
        *_beersheba_rows(),
        _stop("literal", "אחר", "Beersheba Central Station Annex", lat=32.9),
    ]
    result = search_stops(_Reference(rows), "Beersheba Central Station", language="en")
    assert _ids(result) == [STOP_PREFIX + "literal"]


# --- locality intent -------------------------------------------------------------


def _city_rows():
    return [
        # Two stops in Petah Tikva; the central one is busier and nearer the centre.
        _stop(
            "pt_center",
            "מרכז פתח תקווה",
            "Petah Tikva Center",
            city="פתח תקווה",
            routes=90,
            lat=32.089,
            lon=34.886,
        ),
        _stop("pt_edge", "קצה", "Edge", city="פתח תקווה", routes=300, lat=32.2, lon=35.0),
        _stop("pt_mid", "אמצע", "Middle", city="פתח תקווה", routes=5, lat=32.0895, lon=34.8865),
        # Street named Petah Tikva in another city: literal prefix match, wrong place.
        _stop(
            "street",
            "פתח תקווה/הגפן",
            "Petah Tikva A",
            city="תל אביב יפו",
            routes=50,
            lat=32.07,
            lon=34.77,
        ),
        # A Petah Tikva street stop in the city: provides the English alias by alignment.
        _stop("alias", "פתח תקווה", "Petah Tikva", city="גבעתיים", routes=3, lat=32.07, lon=34.81),
        # Rail stop without city information in the feed.
        _stop("rail", "קרית אריה", "Kiriyat Arieh", routes=141, rail=True, lat=32.106, lon=34.863),
    ]


def test_city_name_query_prefers_stops_in_that_city_over_street_named_stops():
    reference = _Reference(_city_rows())
    result = search_stops(reference, "Petah Tikva", language="en")
    ids = _ids(result)
    # Centre-band stops first (busiest within the band), then the rest of the city,
    # and the street-named stop in another city last.
    assert ids[0] == STOP_PREFIX + "pt_center"
    assert ids.index(STOP_PREFIX + "pt_edge") < ids.index(STOP_PREFIX + "street")
    assert ids.index(STOP_PREFIX + "pt_mid") < ids.index(STOP_PREFIX + "street")
    # Hebrew city name and a spelling variant resolve to the same locality.
    hebrew = search_stops(reference, "פתח תקווה", language="he")
    assert hebrew["items"][0]["id"] == STOP_PREFIX + "pt_center"
    variant = search_stops(reference, "Petach Tikwa", language="en")
    assert variant["items"][0]["id"] == STOP_PREFIX + "pt_center"


def test_locality_intent_needs_an_exact_city_name_and_keeps_response_semantics():
    reference = _Reference(_city_rows())
    # Not exactly a city name: ordinary lexical ranking, street-named stop included.
    result = search_stops(reference, "Petah Tikva A", language="en", types=("stop", "station"))
    assert result["items"][0]["id"] == STOP_PREFIX + "street"
    mixed = search_stops(reference, "Petah Tikva", language="en", types=("stop", "poi"))
    assert mixed["matched_types"] == ["stop"]
    assert mixed["unavailable_types"] == ["poi"]
    assert mixed["partial"] is True


def test_cityless_rail_stop_with_an_exact_label_is_not_demoted_by_locality():
    rows = [
        *_city_rows(),
        _stop(
            "rail_pt", "פתח תקווה", "Petah Tikva Rail", rail=True, routes=10, lat=32.09, lon=34.886
        ),
    ]
    rows[-1]["translations"] = {"en": "Petah Tikva"}
    result = search_stops(_Reference(rows), "Petah Tikva", language="en")
    assert STOP_PREFIX + "rail_pt" in _ids(result)[:3]


def test_near_still_orders_locality_results_by_distance():
    reference = _Reference(_city_rows())
    result = search_stops(
        reference, "Petah Tikva", language="en", near=(32.2, 35.0), types=("stop",), limit=3
    )
    assert result["items"][0]["id"] == STOP_PREFIX + "pt_edge"
