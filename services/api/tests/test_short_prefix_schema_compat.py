"""The short-query path on real ReferenceStores of schema 2 and schema 3.

Schema 2 (preserved generations) has no locality tables and keeps the feed-derived city
fallback; schema 3 adds OSM localities. Both must load unchanged and answer every one- and
two-character query exactly as the exhaustive path does.
"""

import pytest
from test_localities import _dataset
from test_reference import synthetic_feed
from test_reference_schema_compat import schema_2_reference  # noqa: F401
from test_stop_search_short_prefix import NEARS, TYPE_SETS, _prefixes

from opentransit import stop_search as stop_search_module
from opentransit.reference import ReferenceStore, build_reference
from opentransit.stop_search import _search_uncached, _SearchIndex, search_stops


def _exhaustive_twin(store):
    twin = _SearchIndex(store.stop_search_candidates(), store.search_localities())
    twin.short_literal = twin.short_folded = None
    return twin


def _assert_equivalent(store):
    index = stop_search_module._search_index(store)
    twin = _exhaustive_twin(store)
    prefixes = _prefixes(index)
    assert len(prefixes) > 20
    for prefix in prefixes:
        assert list(index.strict_matches(prefix).items()) == list(
            twin.strict_matches(prefix).items()
        ), prefix
        for language in ("he", "en"):
            for types in TYPE_SETS:
                for near in NEARS:
                    expected = _search_uncached(twin, prefix, language, near, set(types), (), 10)
                    actual = _search_uncached(index, prefix, language, near, set(types), (), 10)
                    assert actual == expected, (prefix, language, types, near)
    return index


def test_schema_2_reference_short_queries_equal_the_exhaustive_path(schema_2_reference):  # noqa: F811
    database, _ = schema_2_reference
    store = ReferenceStore(database, "g2")
    assert store.metadata.schema_version == 2 and store.has_localities is False
    index = _assert_equivalent(store)
    assert index.osm_localities == []
    assert search_stops(store, "Central")["items"]
    assert search_stops(store, "ce")["items"], "a two-character query finds stops by name"


def test_schema_3_reference_with_localities_short_queries_equal_the_exhaustive_path(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    database = tmp_path / "v3.sqlite"
    build_reference(feed, database, "g3", localities=_dataset(tmp_path))
    store = ReferenceStore(database, "g3")
    assert store.metadata.schema_version == 3 and store.has_localities is True
    index = _assert_equivalent(store)
    assert index.osm_localities, "the fixture carries OSM localities"
    assert search_stops(store, "ce")["items"]


@pytest.mark.parametrize("query", ["ce", "ra", "ת"])
def test_public_short_search_matches_between_a_store_and_its_cached_repeat(tmp_path, query):
    feed = synthetic_feed(tmp_path / "feed.zip")
    database = tmp_path / "v3.sqlite"
    build_reference(feed, database, "g3")
    store = ReferenceStore(database, "g3")
    raw = query if len(query) > 1 else query + "'"
    first = search_stops(store, raw, language="en")
    second = search_stops(store, raw, language="en")
    assert first == second
