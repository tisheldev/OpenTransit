"""One- and two-character stop queries: the precomputed path must equal exhaustive scoring.

The reference is the unchanged exhaustive implementation: an index whose short-query maps
are switched off scores every row with ``_score_normalized`` and ranks every match. Every
one- and two-character string occurring in the fixture's labels and codes is compared,
for every language, category set, location and limit.
"""

import gc
import json
import random
import weakref

import pytest

from opentransit import stop_search as stop_search_module
from opentransit.reference import STOP_PREFIX
from opentransit.stop_search import (
    _is_short_query,
    _search_uncached,
    _SearchIndex,
    search_stops,
)

TEL_AVIV = (32.0853, 34.7818)
EILAT = (29.5577, 34.9519)
NEARS = (None, TEL_AVIV, EILAT)
TYPE_SETS = (("stop",), ("station",), ("stop", "station"))
LIMITS = (1, 3, 10, 20)


def _row(source_id, name, **fields):
    row = {
        "source_id": source_id,
        "stop_id": STOP_PREFIX + source_id,
        "parent_station": None,
        "location_type": 0,
        "name": name,
        "description": None,
        "translations": {},
        "code": None,
        "latitude": 32.0,
        "longitude": 34.8,
        "route_count": 0,
    }
    row.update(fields)
    return row


def _handwritten_rows():
    desc = "רחוב: {} עיר: {} רציף: 1 קומה: 0"
    rows = [
        _row(
            "st_a", "תחנה מרכזית תל אביב", location_type=1, translations={"en": "Central Tel Aviv"}
        ),
        _row(
            "st_a_p1",
            "תחנה מרכזית/רציף 1",
            parent_station=STOP_PREFIX + "st_a",
            translations={"en": "Central Station/Platform 1"},
            latitude=32.056,
            longitude=34.78,
            code="P1",
        ),
        _row(
            "st_a_p2",
            "קומה 2",
            parent_station=STOP_PREFIX + "st_a",
            description=desc.format("לוינסקי", "תל אביב יפו"),
            latitude=32.057,
            longitude=34.781,
            code="7",
        ),
        _row("rail_h", "הרצליה", translations={"en": "Hertsliya"}, rail=True, route_count=50),
        _row("rail_b", "באר שבע/צפון", translations={"en": "Beersheba North"}, rail=True),
        _row("tsfat", "צפת", translations={"en": "Tsfat Qiryat Wadi Yitzhak"}),
        _row("ta_abbr", "ת. רכבת תא", translations={"en": "Ta Rail"}),
        _row("ab", "אב", translations={"en": "ab"}, code="ab"),
        _row("one", "א", translations={"en": "a"}, code="a"),
        _row("no_geo", "בלי מיקום", latitude=None, longitude=None),
        _row("far_south", "אילת מרכז", translations={"en": "Eilat Center"}, latitude=29.55),
        _row("code_only", "Remote Terminal", code="zp1", translations={}),
        _row("digits", "קו 12 כביש 90", description=desc.format("הרצל 12", "חדרה")),
        _row("dup_a", "אבן גבירול", description=desc.format("אבן גבירול", "תל אביב")),
        _row("dup_b", "אבן גבירול", description=desc.format("אבן גבירול", "תל אביב")),
        _row("arabic", "محطة", translations={"he": "תחנה", "en": "station"}),
    ]
    return rows


def _random_rows(count=260, seed=20261003):
    rng = random.Random(seed)
    hebrew = "אבגדהוזחטיכלמנסעפצקרשת"
    latin = "abcdefghiklmnoprstuvwyzq"
    digits = "0123456789"

    def word(alphabet, low=1, high=6):
        return "".join(rng.choice(alphabet) for _ in range(rng.randint(low, high)))

    rows = []
    station_ids: list[str] = []
    for index in range(count):
        source_id = f"r{index:04d}"
        name = " ".join(word(hebrew) for _ in range(rng.randint(1, 3)))
        english = " ".join(word(latin) for _ in range(rng.randint(1, 3)))
        translations = {}
        if rng.random() < 0.7:
            translations["en"] = english
        if rng.random() < 0.1:
            translations["he"] = word(hebrew)
        kind = rng.random()
        fields = {}
        if kind < 0.12:
            fields["location_type"] = 1
            station_ids.append(source_id)
        elif kind < 0.4 and station_ids:
            fields["parent_station"] = STOP_PREFIX + rng.choice(station_ids)
        if rng.random() < 0.15:
            fields["rail"] = True
        if rng.random() < 0.3:
            fields["code"] = word(latin + digits, 1, 4)
        if rng.random() < 0.5:
            fields["description"] = f"רחוב: {word(hebrew)} {word(digits, 1, 2)} עיר: {word(hebrew)}"
        if rng.random() < 0.9:
            fields["latitude"] = rng.uniform(29.6, 33.2)
            fields["longitude"] = rng.uniform(34.3, 35.7)
        else:
            fields["latitude"] = fields["longitude"] = None
        fields["route_count"] = rng.randint(0, 30)
        rows.append(_row(source_id, name, translations=translations, **fields))
    # Row order differs from source-ID order, so ties cannot resolve by position alone.
    rng.shuffle(rows)
    return rows


def _prefixes(index):
    """Every one- and two-character string of the labels, folded labels and codes."""
    keys = {"zz", "ק", "qq", "9", "ts", "ch", "w", "y"}
    for labels in [*index.labels, *index.folded]:
        text = "\n".join(labels)
        keys.update(text)
        keys.update(text[i : i + 2] for i in range(len(text) - 1))
    for code in index.codes:
        keys.update(code)
        keys.update(code[i : i + 2] for i in range(len(code) - 1))
    return sorted(key for key in keys if _is_short_query(key))


def _exhaustive_twin(rows):
    """The same rows with the short-query maps off: the original exhaustive path."""
    twin = _SearchIndex(rows)
    twin.short_literal = twin.short_folded = None
    return twin


@pytest.fixture(scope="module", params=["handwritten", "random"])
def rows(request):
    return _handwritten_rows() if request.param == "handwritten" else _random_rows()


@pytest.fixture(scope="module")
def index(rows):
    return _SearchIndex(rows)


@pytest.fixture(scope="module")
def exhaustive(rows):
    return _exhaustive_twin(rows)


def test_short_scores_equal_exhaustive_scoring_for_every_prefix(index, exhaustive):
    prefixes = _prefixes(index)
    assert len(prefixes) > 40
    for prefix in prefixes:
        actual = index.strict_matches(prefix)
        expected = exhaustive.strict_matches(prefix)
        assert actual == expected, prefix
        # Same rows in the same insertion order: tie-breaking cannot differ.
        assert list(actual.items()) == list(expected.items()), prefix


def test_short_ranking_equals_exhaustive_ranking_for_every_prefix_and_parameter(index, exhaustive):
    compared = 0
    for prefix in _prefixes(index):
        for language in ("he", "en"):
            for types in TYPE_SETS:
                for near in NEARS:
                    expected = _search_uncached(
                        exhaustive, prefix, language, near, set(types), (), 20
                    )
                    for limit in LIMITS:
                        actual = _search_uncached(
                            index, prefix, language, near, set(types), (), limit
                        )
                        sliced = {**expected, "items": expected["items"][:limit]}
                        assert actual == sliced, (prefix, language, types, near, limit)
                        # Byte-for-byte, including key order and number types.
                        assert json.dumps(actual) == json.dumps(sliced)
                        compared += 1
    assert compared > 1000


def test_public_search_is_identical_cold_warm_and_against_the_exhaustive_path(rows):
    class Reference:
        def __init__(self, source):
            self.source = source

        def stop_search_candidates(self):
            return self.source

    fast, slow = Reference(rows), Reference(rows)
    slow_index = _exhaustive_twin(rows)
    stop_search_module._INDEXES[slow] = slow_index
    prefixes = _prefixes(stop_search_module._search_index(fast))
    for prefix in prefixes[:: max(1, len(prefixes) // 60)]:
        if len(prefix.strip()) < 2:
            prefix = prefix + prefix  # the public API needs two raw characters
        for near in NEARS:
            kwargs = {"language": "he", "near": near, "types": ("stop", "station"), "limit": 10}
            expected = search_stops(slow, prefix, **kwargs)
            cold = search_stops(fast, prefix, **kwargs)
            warm = search_stops(fast, prefix, **kwargs)
            assert cold == expected and warm == expected, (prefix, near)
            assert json.dumps(warm) == json.dumps(expected)


def test_queries_that_are_not_short_single_tokens_use_the_general_path(index, exhaustive):
    assert not _is_short_query("a b")
    assert not _is_short_query("abc")
    assert not _is_short_query("")
    assert not _is_short_query(" a")
    assert index.short_winners("a b", "he", None, {"stop"}, 10) is None
    assert index.short_winners("abc", "he", None, {"stop"}, 10) is None
    for query in ("a b", "א ב", "ab cd"):
        actual = _search_uncached(index, query, "en", None, {"stop", "station"}, (), 10)
        expected = _search_uncached(exhaustive, query, "en", None, {"stop", "station"}, (), 10)
        assert actual == expected


def test_a_query_nothing_matches_falls_back_and_returns_an_empty_success(index):
    result = search_stops_for_index(index, "ךך")
    assert result["items"] == [] and result["unavailable_types"] == []
    assert index.short_winners("ךך", "he", None, {"stop"}, 10) is None


def search_stops_for_index(index, query, **kwargs):
    return _search_uncached(
        index,
        query,
        kwargs.get("language", "he"),
        kwargs.get("near"),
        set(kwargs.get("types", ("stop", "station"))),
        (),
        kwargs.get("limit", 10),
    )


def test_ranking_stops_at_the_better_levels_when_enough_groups_are_certain():
    rows = [
        _row(f"s{i}", f"אבא {i}", latitude=32.0 + i / 10_000, longitude=34.8) for i in range(30)
    ]
    rows.append(_row("deep", "xאבx"))  # "אב" occurs only inside: level 4
    index = _SearchIndex(rows)
    scans = []
    real = index.short_literal.superset
    index.short_literal.superset = lambda query: scans.append(query) or real(query)
    result = search_stops_for_index(index, "אב", limit=10)
    assert len(result["items"]) == 10
    assert scans == [], "the substring scan is only for queries the better levels cannot answer"
    # Asking for more than the better levels hold does reach the substring level.
    everything = search_stops_for_index(index, "אב", limit=20)
    assert len(everything["items"]) == 20
    assert scans == []
    rows_without_depth = rows[:3] + [rows[-1]]
    small = _SearchIndex(rows_without_depth)
    small_scans = []
    real_small = small.short_literal.superset
    small.short_literal.superset = lambda query: small_scans.append(query) or real_small(query)
    reached = search_stops_for_index(small, "אב", limit=10)
    assert small_scans == ["אב"]
    assert {item["id"] for item in reached["items"]} >= {STOP_PREFIX + "deep"}


def test_a_station_with_a_parent_disables_the_bounded_ranking_but_stays_exact():
    rows = _handwritten_rows()
    rows.append(
        _row(
            "odd_station",
            "תחנה ילדה",
            location_type=1,
            parent_station=STOP_PREFIX + "st_a",
            translations={"en": "Odd station"},
        )
    )
    index = _SearchIndex(rows)
    assert index.short_ranking_exact is False
    assert index.short_winners("תח", "he", None, {"stop", "station"}, 10) is None
    twin = _exhaustive_twin(rows)
    for prefix in ("תח", "od", "a", "st"):
        for language in ("he", "en"):
            assert search_stops_for_index(
                index, prefix, language=language
            ) == search_stops_for_index(twin, prefix, language=language)


def test_superset_scan_finds_rows_of_empty_and_repeated_labels():
    rows = [
        _row("x0", "aaa"),
        _row("x1", "bab"),
        _row("x2", "ba", description=None),
        _row("x3", ""),
    ]
    index = _SearchIndex(rows)
    assert list(index.short_literal.superset("aa")) == [0]
    assert list(index.short_literal.superset("ba")) == [1, 2]
    assert list(index.short_literal.superset("b")) == [1, 2]
    assert list(index.short_literal.superset("zz")) == []


def test_results_cache_is_bound_to_the_index_and_dropped_with_it():
    class Reference:
        def __init__(self, rows):
            self.rows = rows

        def stop_search_candidates(self):
            return self.rows

    first = Reference([_row("only_a", "Alpha Station", translations={"en": "Alpha Station"})])
    second = Reference([_row("only_b", "Beta Station", translations={"en": "Beta Station"})])
    for reference in (first, second):
        assert search_stops(reference, "Station", language="en")["items"]
    first_index = stop_search_module._search_index(first)
    second_index = stop_search_module._search_index(second)
    assert first_index.results is not second_index.results
    assert len(first_index.results) == len(second_index.results) == 1
    ids = [item["id"] for item in search_stops(second, "Station", language="en")["items"]]
    assert ids == [STOP_PREFIX + "only_b"]
    watch = weakref.ref(first_index.results)
    del first_index
    del first
    gc.collect()
    assert watch() is None, "a retired generation's cached results are released with its index"


def test_cache_returns_copies_and_distinguishes_every_result_parameter():
    class Reference:
        def stop_search_candidates(self):
            return _handwritten_rows()

    reference = Reference()
    base = {"language": "en", "near": None, "types": ("stop", "station"), "limit": 10}
    first = search_stops(reference, "Central", **base)
    first["items"][0]["displayName"] = "mutated"
    first["items"].append({"junk": True})
    again = search_stops(reference, "Central", **base)
    assert again["items"][0]["displayName"] != "mutated" and {"junk": True} not in again["items"]
    index = stop_search_module._search_index(reference)
    assert index.results.hits >= 1
    variants = [
        {**base, "language": "he"},
        {**base, "near": TEL_AVIV},
        {**base, "near": (TEL_AVIV[0], TEL_AVIV[1] + 1e-6)},
        {**base, "types": ("station",)},
        {**base, "limit": 3},
    ]
    before = len(index.results)
    for kwargs in variants:
        search_stops(reference, "Central", **kwargs)
    assert len(index.results) == before + len(variants)
    # Case and punctuation normalize to one key; the order of the types does not matter.
    search_stops(reference, "  CENTRAL.", **base)
    search_stops(reference, "central", **{**base, "types": ("station", "stop")})
    assert len(index.results) == before + len(variants)


def test_invalid_requests_raise_and_are_never_cached():
    class Reference:
        def stop_search_candidates(self):
            return _handwritten_rows()

    reference = Reference()
    for bad in ({"query": "x"}, {"query": "central", "limit": 0}, {"query": "!!"}):
        with pytest.raises(ValueError):
            search_stops(reference, bad["query"], limit=bad.get("limit", 10))
    index = stop_search_module._search_index(reference)
    assert len(index.results) == 0


def test_result_cache_is_bounded():
    from opentransit.search_cache import ResultCache

    cache = ResultCache(2)
    for key in ("a", "b", "c"):
        cache.put(key, {"key": key})
    assert len(cache) == 2 and cache.get("a") is None
    assert cache.get("b") == {"key": "b"}
    cache.put("d", {"key": "d"})  # "c" is now least recently used
    assert cache.get("c") is None and cache.get("b") is not None
