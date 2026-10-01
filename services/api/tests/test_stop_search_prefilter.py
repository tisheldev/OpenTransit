"""Conservative stop-search prefilter behavior for mixed-length query tokens."""

from opentransit import stop_search as stop_search_module
from opentransit.reference import STOP_PREFIX
from opentransit.stop_search import _SearchIndex, search_stops


class _ReferenceFixture:
    def __init__(self, rows):
        self.rows = rows

    def stop_search_candidates(self):
        return self.rows


def _rows():
    return [
        {
            "source_id": "platform_a",
            "stop_id": STOP_PREFIX + "platform_a",
            "parent_station": None,
            "location_type": 0,
            "name": "Central A",
            "description": None,
            "translations": {},
            "code": "CA",
            "latitude": 32.08,
            "longitude": 34.78,
        },
        {
            "source_id": "station",
            "stop_id": STOP_PREFIX + "station",
            "parent_station": None,
            "location_type": 1,
            "name": "Central Station",
            "description": None,
            "translations": {"he": "תחנה מרכזית"},
            "code": "S1",
            "latitude": 32.081,
            "longitude": 34.781,
        },
        {
            "source_id": "code_only",
            "stop_id": STOP_PREFIX + "code_only",
            "parent_station": None,
            "location_type": 0,
            "name": "Remote Terminal",
            "description": None,
            "translations": {},
            "code": "ZP100",
            "latitude": 32.082,
            "longitude": 34.782,
        },
        {
            "source_id": "cross_label",
            "stop_id": STOP_PREFIX + "cross_label",
            "parent_station": None,
            "location_type": 0,
            "name": "Harbor",
            "description": "Central terminal",
            "translations": {},
            "code": None,
            "latitude": 32.083,
            "longitude": 34.783,
        },
        {
            "source_id": "short_only",
            "stop_id": STOP_PREFIX + "short_only",
            "parent_station": None,
            "location_type": 0,
            "name": "A B",
            "description": None,
            "translations": {},
            "code": None,
            "latitude": 32.084,
            "longitude": 34.784,
        },
    ]


def test_mixed_short_and_long_tokens_keep_english_hebrew_and_code_matches():
    rows = _rows()
    index = _SearchIndex(rows)
    assert (
        search_stops(_ReferenceFixture(rows), "a central", language="en")["items"][0]["id"]
        == STOP_PREFIX + "platform_a"
    )
    assert (
        search_stops(_ReferenceFixture(rows), "ת תחנה", language="he")["items"][0]["id"]
        == STOP_PREFIX + "station"
    )
    assert (
        search_stops(_ReferenceFixture(rows), "zp100", language="en")["items"][0]["id"]
        == STOP_PREFIX + "code_only"
    )
    assert index.matching_rows("a central") == [0, 1, 3]


def test_all_short_tokens_keep_the_complete_scan_and_full_scorer():
    rows = _rows()
    index = _SearchIndex(rows)
    assert index.matching_rows("a b") == list(range(len(rows)))
    result = search_stops(_ReferenceFixture(rows), "a b", language="en")
    assert [item["id"] for item in result["items"]] == [STOP_PREFIX + "short_only"]


def test_cross_label_prefilter_candidate_is_rejected_by_full_query_scorer():
    rows = _rows()
    index = _SearchIndex(rows)
    candidate_index = next(i for i, row in enumerate(rows) if row["source_id"] == "cross_label")
    assert candidate_index in index.matching_rows("harbor central")
    assert search_stops(_ReferenceFixture(rows), "harbor central", language="en")["items"] == []


def test_indexed_search_matches_exhaustive_scoring_for_fixture_queries(monkeypatch):
    rows = _rows()
    indexed = _SearchIndex(rows)
    exhaustive = _SearchIndex(rows)
    exhaustive.matching_rows = lambda _query: list(range(len(rows)))
    reference = _ReferenceFixture(rows)

    queries = (
        ("a central", "en"),
        ("central station", "en"),
        ("ת תחנה", "he"),
        ("zp100", "en"),
        ("harbor central", "en"),
        ("a b", "en"),
        ("missing label", "en"),
    )
    for query, language in queries:
        monkeypatch.setattr(stop_search_module, "_search_index", lambda _ref: indexed)
        actual = search_stops(reference, query, language=language)
        monkeypatch.setattr(stop_search_module, "_search_index", lambda _ref: exhaustive)
        expected = search_stops(reference, query, language=language)
        assert actual == expected, query


def _hub_rows():
    def stop(source_id, name, en=None, routes=0, lat=32.0, lon=34.8):
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
        }

    return [
        stop("rail_herzliya", "הרצליה", "Hertsliya", routes=500),
        stop("bus_marina", "מרינה", "Herzliya Marina Taxi Station", routes=2),
        stop("airport", "נתב''ג", None, routes=300),
        stop("street_bg", "בן גוריון/הרצל", "Ben Gurion/Herzl", routes=3),
        stop("terminal", "ת. רכבת תל אביב- סבידור/רציפים", "Tel Aviv-Savidor Train Stations"),
        stop("near_far", "Central Station", "Central Station", lat=32.8, lon=35.0),
        stop("near_close", "Central Bus Station North", "Central Bus Station North"),
    ]


def test_transliteration_folding_matches_gtfs_english_spelling():
    reference = _ReferenceFixture(_hub_rows())
    result = search_stops(reference, "Herzliya", language="en")
    assert STOP_PREFIX + "rail_herzliya" in [item["id"] for item in result["items"]]


def test_abbreviation_and_curated_alias_reach_airport_stop():
    reference = _ReferenceFixture(_hub_rows())
    hebrew = search_stops(reference, "נמל תעופה בן גוריון", language="he")
    assert hebrew["items"][0]["id"] == STOP_PREFIX + "airport"
    english = search_stops(reference, "Ben Gurion Airport", language="en")
    assert english["items"][0]["id"] == STOP_PREFIX + "airport"


def test_partial_coverage_is_only_a_fallback_and_needs_two_tokens():
    reference = _ReferenceFixture(_hub_rows())
    # No stop carries every token; the terminal covers tel/aviv/savidor.
    result = search_stops(reference, "Tel Aviv Savidor Center", language="en")
    assert result["items"][0]["id"] == STOP_PREFIX + "terminal"
    # A single significant token never triggers partial matching.
    assert search_stops(reference, "Savidor Unknownword", language="en")["items"] == []
    # Partial ties prefer the busier stop.
    tie = search_stops(reference, "Ben Gurion Airoport", language="en")
    assert tie["items"][0]["id"] == STOP_PREFIX + "airport"


def test_near_bias_orders_full_token_matches_by_distance():
    reference = _ReferenceFixture(_hub_rows())
    result = search_stops(reference, "Central Station", language="en", near=(32.0, 34.8))
    assert result["items"][0]["id"] == STOP_PREFIX + "near_close"
    without_near = search_stops(reference, "Central Station", language="en")
    assert without_near["items"][0]["id"] == STOP_PREFIX + "near_far"
