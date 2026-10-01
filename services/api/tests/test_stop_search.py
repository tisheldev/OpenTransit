from test_reference import synthetic_feed

from opentransit.reference import ReferenceStore, build_reference
from opentransit.stop_search import normalize_label, search_stops


def test_hebrew_marks_punctuation_and_translation_search_are_normalized(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    database = tmp_path / "reference.sqlite"
    build_reference(feed, database, "search-test")
    reference = ReferenceStore(database, "search-test")

    assert normalize_label("תַּחֲנָה־מֶרְכָּזִית׳") == "תחנה מרכזית"
    assert normalize_label("בֵּית־סֵפֶר") == "בית ספר"
    assert normalize_label("בֵּיה״ס") == "ביהס"
    result = search_stops(reference, "תַחֲנָה מרכזית׳", language="en", limit=5)
    assert len(result["items"]) == 1
    candidate = result["items"][0]
    assert candidate["id"] == "mot:stop:station"
    assert candidate["kind"] == "station"
    # The fixture has no English translation, so the original Hebrew label is retained.
    assert candidate["displayName"] == "Central"
    assert candidate["languageUsed"] == "en"
    assert candidate["platformIds"] == ["mot:stop:platform_a", "mot:stop:platform_b"]


def test_candidate_accessor_is_complete_and_search_result_resolves(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    database = tmp_path / "reference.sqlite"
    build_reference(feed, database, "search-test")
    reference = ReferenceStore(database, "search-test")

    candidates = reference.stop_search_candidates()
    assert len(candidates) == 4
    assert {row["source_id"] for row in candidates} == {
        "station",
        "platform_a",
        "platform_b",
        "stop_c",
    }
    result = search_stops(reference, "central", language="he")
    assert result["items"]
    returned = result["items"][0]["id"]
    assert reference.stop(returned) is not None


def test_unsupported_categories_are_reported_without_false_empty_success(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    database = tmp_path / "reference.sqlite"
    build_reference(feed, database, "search-test")
    reference = ReferenceStore(database, "search-test")

    partial = search_stops(reference, "station", types=("station", "address"))
    assert partial["partial"] is True
    assert partial["unavailable_types"] == ["address"]
    try:
        search_stops(reference, "station", types=("poi",))
    except ValueError as exc:
        assert exc.__class__.__name__ == "UnavailableCategoryError"
    else:
        raise AssertionError("Unsupported-only category must not return empty success")
