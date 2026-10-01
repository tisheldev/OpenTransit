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
