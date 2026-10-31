"""Generation-local Hebrew/English search over the immutable stop reference."""

from __future__ import annotations

import heapq
import math
import re
import sqlite3
import statistics
import threading
import unicodedata
import weakref
from array import array
from bisect import bisect_right
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from opentransit.reference import STOP_PREFIX, ReferenceStore
from opentransit.search_cache import STOP_RESULT_CACHE_ENTRIES, ResultCache

SUPPORTED_TYPES = frozenset({"stop", "station"})
KNOWN_TYPES = SUPPORTED_TYPES | {"poi", "address"}

# Station words do not identify a place on their own; partial matching ignores them.
_STATION_WORDS = frozenset(
    {
        "תחנת",
        "תחנה",
        "תחנות",
        "רכבת",
        "ת",
        "station",
        "stations",
        "train",
        "rail",
        "railway",
        "terminal",
    }
)
# Whole-token abbreviations used in GTFS stop names (after normalization removes
# geresh/gershayim and periods). Expanded forms are indexed as extra labels.
_ABBREVIATIONS = {
    "ת": "תחנת",
    "תא": "תל אביב",
    "נתבג": "נמל תעופה בן גוריון",
    "רקל": "רכבת קלה",
}
# Curated aliases for hubs whose GTFS stop has no usable English translation.
# Not source data: "Ben Gurion Airport" is Israel Railways' published English
# name for the נתב"ג station. Each entry needs a cited public source.
# Keyed by a normalized name token; values are added as searchable labels.
_ALIASES = {"נתבג": ("ben gurion airport",)}
# Station vocabulary added to rail stops (GTFS rail-route linkage), per script.
_RAIL_SUFFIXES = ("station", "railway station", "train station", "rail station")
_RAIL_PREFIXES_HE = ("תחנת", "תחנת רכבת")
# Latin transliteration folding for Hebrew place names (Yits'hak/Yitzhak,
# Hertsliya/Herzliya, Petach Tikwa/Petah Tiqwa/Petah Tikva).
_FOLDS = (("tz", "z"), ("ts", "z"), ("ch", "h"), ("kh", "h"), ("ck", "k"), ("q", "k"))
_FOLDS += (("w", "v"), ("ph", "f"), ("y", "i"))
_REPEATED = re.compile(r"(.)\1+")
_PARTIAL_MIN_TOKENS = 2
# Shorter compact keys are too ambiguous to match across word boundaries.
_COMPACT_MIN_CHARS = 4
# Transliteration-only matches rank half a tier below the same literal match.
_FOLDED_PENALTY = 0.5
# With a location, a match farther than this ranks two tiers lower.
_NEAR_FAR_M = 10_000.0


# GTFS stop_desc is "רחוב: <street> עיר: <city> רציף: <platform> קומה: <floor>".
_DESC_CITY = re.compile(r"עיר:\s*(.*?)\s*(?:רציף:|קומה:|$)")
# A query that is exactly a locality name ranks that locality's stops (central first,
# then busiest) and any lexical match inside it ahead of lexical matches elsewhere,
# which are usually street-named stops in other cities. Localities come first from the
# reference's OSM administrative level 8 table (names from OSM tags, stops assigned by
# polygon containment at build time); a feed-derived fallback (stop descriptions and
# translations) covers names OSM does not list as a municipality. Nothing is curated.
_LOCALITY_TIER = 1.75
_LOCALITY_OUTSIDE_PENALTY = 2
_LOCALITY_MAX_ROWS = 400
# Within a locality, stops rank by route count discounted with distance from the
# locality's centre (e-folding length below), so a central hub beats both a remote
# hub and a quiet street stop at the centre.
_LOCALITY_DECAY_M = 750.0
_LOCALITY_MIN_ALIAS_CHARS = 3
# Compound OSM names such as "Tel-Aviv–Yafo" or "Kadima - Zoran" also name each part.
_NAME_PART_SPLIT = re.compile(r"\s+[-\u2013\u2014]\s+|[\u2013\u2014]")


@dataclass(frozen=True)
class _LocalityIntent:
    """The stops a locality-name query points at, and how to rank them."""

    members: frozenset[int]
    top_rows: tuple[int, ...]
    centers: tuple[tuple[float, float], ...]
    # True when the feed or the polygons place a row in a different locality.
    foreign: Callable[[int], bool]


def normalize_label(value: str) -> str:
    """Normalize Hebrew marks and punctuation while retaining searchable words."""
    folded = unicodedata.normalize("NFKC", value).casefold()
    chars = []
    for char in folded:
        if unicodedata.category(char) in {"Mn", "Me", "Cf"}:
            continue
        if char in "׳״'\"‘’“”":
            continue
        category = unicodedata.category(char)
        chars.append(" " if category.startswith("P") or category.startswith("Z") else char)
    return " ".join("".join(chars).split())


def fold_transliteration(normalized: str) -> str:
    """Fold common Latin spellings of Hebrew sounds; non-ASCII labels are unchanged."""
    if not normalized or not normalized.isascii():
        return normalized
    words = []
    for word in normalized.split():
        for source, target in _FOLDS:
            word = word.replace(source, target)
        word = _REPEATED.sub(r"\1", word)
        if len(word) > 3 and word.endswith("h") and word[-2] in "aeiou":
            word = word[:-1]
        words.append(word)
    return " ".join(words)


def compact_key(normalized: str) -> str:
    """Space-insensitive key for Latin labels: Beersheba, Be'er Sheva and Beer-Sheba meet.

    Joined and split spellings differ in word boundaries and often in b/v (the Hebrew
    bet/vet), so the key drops spaces, applies the transliteration fold and maps b to v.
    It is used only for a half-tier-lower fallback match, never for literal matches.
    Each word is folded on its own, so a doubled letter across a word boundary
    ("Tikva A") is not collapsed into a different spelling.
    """
    return fold_transliteration(normalized).replace(" ", "").replace("b", "v")


def _expand_abbreviations(normalized: str) -> str | None:
    words = normalized.split()
    if not any(word in _ABBREVIATIONS for word in words):
        return None
    return " ".join(_ABBREVIATIONS.get(word, word) for word in words)


def _rail_variants(raw_names: list[str]) -> list[str]:
    """Extra labels for a stop served by GTFS rail routes (a rail station).

    The feed names rail stops by place only (no "station" word, no parent) and
    often as "City/Place". Both are derived from the rail-route linkage, not curated:
    the part after the slash is a name passengers use, and "<name> station" forms
    let "Herzliya Station" meet the rail stop named just "Hertsliya".
    """
    tails = [
        t for name in raw_names if "/" in name and (t := normalize_label(name.split("/", 1)[1]))
    ]
    extra = list(tails)
    for label in [n for name in raw_names if (n := normalize_label(name))] + tails:
        if label.isascii():
            extra.extend(f"{label} {word}" for word in _RAIL_SUFFIXES)
        else:
            extra.extend(f"{word} {label}" for word in _RAIL_PREFIXES_HE)
    return extra


def _label_variants(normalized: list[str], rail_names: list[str] | None = None) -> list[str]:
    labels = list(normalized)
    if rail_names:
        labels.extend(_rail_variants(rail_names))
    labels.extend(e for label in normalized if (e := _expand_abbreviations(label)))
    for label in list(labels):
        for token, aliases in _ALIASES.items():
            if token in label.split():
                labels.extend(aliases)
    return list(dict.fromkeys(labels))


def _folded_labels(labels: list[str]) -> list[str]:
    return list(dict.fromkeys(fold_transliteration(label) for label in labels))


def _query_variants(normalized: str) -> list[str]:
    variants = [normalized]
    if expanded := _expand_abbreviations(normalized):
        variants.append(expanded)
    return list(dict.fromkeys(variants))


def _language(value: str) -> str:
    if any("\u0590" <= char <= "\u05ff" for char in value):
        return "he"
    if any("\u0600" <= char <= "\u06ff" for char in value):
        return "ar"
    return "en"


def _display(candidate: dict[str, Any], language: str) -> tuple[str, str]:
    translations = candidate.get("translations", {})
    translated = translations.get(language)
    if translated:
        return translated, language
    original = candidate.get("name") or candidate.get("description") or candidate["source_id"]
    return original, _language(original)


def _score(query: str, labels: list[str], code: str | None) -> int | None:
    return _score_normalized(
        query,
        [normalize_label(label) for label in labels if label],
        normalize_label(code or ""),
    )


def _score_normalized(query: str, normalized: list[str], norm_code: str) -> int | None:
    if query and norm_code and query == norm_code:
        return 0
    if query in normalized:
        return 1
    if any(label.startswith(query) for label in normalized):
        return 2
    tokens = query.split()
    if tokens and any(
        all(any(word.startswith(token) for word in label.split()) for token in tokens)
        for label in normalized
    ):
        return 3
    if any(query in label for label in normalized) or (norm_code and query in norm_code):
        return 4
    return None


def _coverage(tokens: list[str], labels: list[str]) -> int:
    """Largest number of query tokens prefix-matched by words of one label.

    Labels are normalized (words joined by single spaces) and tokens hold no
    whitespace, so "a word starts with the token" is exactly "space + token occurs
    in space + label". The substring test runs in C instead of a per-word loop.
    """
    needles = [" " + token for token in tokens]
    best = 0
    for label in labels:
        padded = " " + label
        covered = sum(needle in padded for needle in needles)
        if covered > best:
            best = covered
            if best == len(needles):
                break
    return best


def _stop_city(row: dict[str, Any]) -> str | None:
    """Normalized Hebrew city from the GTFS stop description, when present."""
    match = _DESC_CITY.search(row.get("description") or "")
    city = normalize_label(match.group(1)) if match else ""
    return city if any(char.isalpha() for char in city) else None


def _locality_aliases(rows: list[dict[str, Any]], cities: set[str]) -> dict[str, str]:
    """Locality name -> normalized Hebrew city, derived only from the feed itself.

    Hebrew city names come from stop descriptions. English names come from stop-name
    translations: when a stop's Hebrew name has a "/"-separated segment that is a
    known city and its English name has the same number of segments, the English
    segment at that position is an English name of that city. Folded Latin keys.
    """
    aliases = {city: city for city in cities}
    votes: dict[str, dict[str, int]] = {}
    for row in rows:
        name, english = row.get("name"), row["translations"].get("en")
        if not name or not english:
            continue
        hebrew_parts, english_parts = name.split("/"), english.split("/")
        if len(hebrew_parts) != len(english_parts):
            continue
        for hebrew, latin in zip(hebrew_parts, english_parts, strict=True):
            city = normalize_label(hebrew)
            key = fold_transliteration(normalize_label(latin))
            if (
                city in cities
                and key.isascii()
                and len(key) >= _LOCALITY_MIN_ALIAS_CHARS
                and not key.replace(" ", "").isdigit()
            ):
                by_city = votes.setdefault(key, {})
                by_city[city] = by_city.get(city, 0) + 1
    for key, by_city in votes.items():
        ranked = sorted(by_city.items(), key=lambda item: (-item[1], item[0]))
        # An English name that points at several cities is ambiguous; skip it.
        if len(ranked) == 1 or ranked[0][1] >= 2 * ranked[1][1]:
            aliases.setdefault(key, ranked[0][0])
    return aliases


def _locality_name_forms(name: str) -> list[str]:
    """Normalized forms of an OSM locality name: whole name, then each dash-part.

    A plain hyphen only splits a merged name of three or more long parts
    ("Modiin-Maccabim-Reut"); "Tel-Aviv" or "Be'er-Sheva" are single names.
    """
    parts = [*_NAME_PART_SPLIT.split(name)]
    hyphenated = name.split("-")
    if len(hyphenated) >= 3 and all(len(normalize_label(part)) >= 4 for part in hyphenated):
        parts.extend(hyphenated)
    forms = []
    for candidate in (name, *parts):
        form = normalize_label(candidate)
        if len(form) >= _LOCALITY_MIN_ALIAS_CHARS and any(char.isalpha() for char in form):
            forms.append(form)
    return list(dict.fromkeys(forms))


# A query of one or two characters has no trigram to probe, so every stop would be
# scored in Python (120-250 ms on the national feed), and ranking then groups every
# match (up to all 35,000 stops). Both steps are precomputed or bounded instead.
_SHORT_QUERY_MAX_CHARS = 2
_WORD_START = re.compile(r"(?<!\S)\S{1,2}")
# Per-label separator of the substring blob; normalized labels never contain it
# (normalization splits on whitespace and rejoins with single spaces).
_LABEL_SEPARATOR = "\n"
# Level-4 (substring) row lists computed on demand and kept for repeats.
_SUPERSET_MEMO_ENTRIES = 64
_FAR_PENALTY = 2


def _is_short_query(query: str) -> bool:
    """A single token of one or two characters: the case ``matching_rows`` cannot filter."""
    return 0 < len(query) <= _SHORT_QUERY_MAX_CHARS and not any(c.isspace() for c in query)


class _ShortQueryScores:
    """Exact ``_score_normalized`` results for every one- and two-character query.

    For a single token of at most two characters the scorer is five string predicates
    over a row's labels: the stop code equals the query (0), a label equals it (1), a
    label starts with it (2), a word of a label starts with it (3), or it occurs inside
    a label or the code (4). Levels 0-3 depend only on the leading one or two characters
    of a label or word, so one pass over the labels records the rows of every such
    string; they are built with the index. Level 4 is the superset (every row containing
    the string anywhere): it would be the bulk of the memory and build time, and most
    queries never need it, so it is found on demand with a substring scan of one blob
    and kept for repeats. Rows come out in ascending order per level; a row listed at a
    better level scores that level. ``ascii_only`` limits the keys to ASCII strings (the
    transliteration-folded pass is only queried by Latin text).
    """

    def __init__(
        self, labels: list[list[str]], codes: list[str] | None, *, ascii_only: bool = False
    ) -> None:
        levels: tuple[dict[str, array], ...] = tuple({} for _ in range(4))
        code_rows: dict[str, array] = {}
        starts = array("I")
        offset = 0
        for row_index, row_labels in enumerate(labels):
            starts.append(offset)
            tiers: tuple[set[str], ...] = tuple(set() for _ in range(4))
            code = codes[row_index] if codes is not None else ""
            if code and len(code) <= _SHORT_QUERY_MAX_CHARS:
                tiers[0].add(code)
            for label in row_labels:
                offset += len(label) + 1
                if not label:
                    continue
                if len(label) <= _SHORT_QUERY_MAX_CHARS:
                    tiers[1].add(label)
                tiers[2].update((label[:1], label[:2]))
                for head in _WORD_START.findall(label):
                    tiers[3].update((head[:1], head))
            if ascii_only:
                for tier in tiers:
                    tier.difference_update([key for key in tier if not key.isascii()])
            for level, keys in zip(levels, tiers, strict=True):
                for key in keys:
                    rows = level.get(key)
                    if rows is None:
                        level[key] = rows = array("I")
                    rows.append(row_index)
            if code:
                # Codes are short; their substrings are listed directly.
                keys = {code[i : i + 2] for i in range(len(code) - 1)}
                keys.update(code)
                for key in keys:
                    if not ascii_only or key.isascii():
                        rows = code_rows.get(key)
                        if rows is None:
                            code_rows[key] = rows = array("I")
                        rows.append(row_index)
        self._levels = levels
        self._code_rows = code_rows
        self._starts = starts
        self._blob = _LABEL_SEPARATOR.join(label for row_labels in labels for label in row_labels)
        self._memo: dict[str, array] = {}
        self._memo_lock = threading.Lock()

    def levels_for(self, query: str) -> list[tuple[int, Callable[[], Iterable[int]]]]:
        """(level, rows supplier) for each level that may hold rows for ``query``.

        The level-4 supplier does its scan only when called, so a caller that is satisfied
        by the better levels never pays for it.
        """
        found: list[tuple[int, Callable[[], Iterable[int]]]] = []
        for level in range(4):
            rows = self._levels[level].get(query)
            if rows is not None:
                found.append((level, lambda rows=rows: rows))
        found.append((4, lambda: self.superset(query)))
        return found

    def superset(self, query: str) -> array:
        """Ascending rows with ``query`` inside a label (or the code): the level-4 rows."""
        cached = self._memo.get(query)
        if cached is not None:
            return cached
        blob, starts = self._blob, self._starts
        rows = array("I")
        find = blob.find
        end = len(blob)
        position = find(query)
        while position != -1:
            row = bisect_right(starts, position) - 1
            rows.append(row)
            # One hit is enough for this row: continue at the next row's first label.
            following = starts[row + 1] if row + 1 < len(starts) else end
            position = find(query, max(following, position + 1))
        code_rows = self._code_rows.get(query)
        if code_rows is not None:
            rows = array("I", sorted(set(rows).union(code_rows)))
        with self._memo_lock:
            if len(self._memo) >= _SUPERSET_MEMO_ENTRIES:
                self._memo.pop(next(iter(self._memo)), None)
            self._memo[query] = rows
        return rows

    def scores(self, query: str) -> dict[int, int]:
        """Row -> score for a short single-token query, in ascending row order."""
        superset = self.superset(query)
        if not superset:
            return {}
        scored = dict.fromkeys(superset, 4)
        for score in (3, 2, 1, 0):
            rows = self._levels[score].get(query)
            if rows is not None:
                scored.update(dict.fromkeys(rows, score))
        return scored


class _SearchIndex:
    def __init__(
        self, rows: list[dict[str, Any]], localities: list[dict[str, Any]] | None = None
    ) -> None:
        self.rows = tuple(rows)
        self.by_source = {row["source_id"]: row for row in rows}
        self.by_source.update({row["stop_id"]: row for row in rows})
        self.position = {row["source_id"]: index for index, row in enumerate(rows)}
        self.children_by_parent: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if row.get("parent_station"):
                self.children_by_parent.setdefault(row["parent_station"], []).append(row)
        for children in self.children_by_parent.values():
            children.sort(key=lambda item: item["source_id"])
        # Pre-normalized labels (with abbreviation, alias and transliteration
        # variants) are computed once per immutable generation.
        self.labels: list[list[str]] = []
        self.folded: list[list[str]] = []
        self.coverage_labels: list[list[str]] = []
        self.compact: list[list[str]] = []
        self.codes: list[str] = []
        self.importance: list[int] = []
        for row in rows:
            raw = [row.get("name"), *row["translations"].values(), row.get("description")]
            normalized = [n for value in raw if value and (n := normalize_label(value))]
            rail_names = (
                [v for v in (row.get("name"), *row["translations"].values()) if v]
                if row.get("rail") and row.get("location_type") != 1
                else None
            )
            self.labels.append(_label_variants(normalized, rail_names))
            self.folded.append(_folded_labels(self.labels[-1]))
            self.coverage_labels.append(list(dict.fromkeys([*self.labels[-1], *self.folded[-1]])))
            # Only multi-word Latin labels differ from their folded form once joined.
            self.compact.append(
                list(
                    dict.fromkeys(
                        key
                        for label in self.labels[-1]
                        if label.isascii()
                        and " " in label
                        and len(key := compact_key(label)) >= _COMPACT_MIN_CHARS
                    )
                )
            )
            self.codes.append(normalize_label(row.get("code") or ""))
            routes = int(row.get("route_count") or 0)
            routes += sum(
                int(child.get("route_count") or 0)
                for child in self.children_by_parent.get(row["stop_id"], [])
            )
            self.importance.append(routes)
        self.city_of = [_stop_city(row) for row in rows]
        by_city: dict[str, list[int]] = {}
        for row_index, city in enumerate(self.city_of):
            if city:
                by_city.setdefault(city, []).append(row_index)
        self.city_rows = {
            city: sorted(members, key=lambda i: (-self.importance[i], i))[:_LOCALITY_MAX_ROWS]
            for city, members in by_city.items()
        }
        # Median stop position approximates the city centre without any boundary data.
        self.city_center = {
            city: (
                statistics.median(rows[i]["latitude"] for i in located),
                statistics.median(rows[i]["longitude"] for i in located),
            )
            for city, members in by_city.items()
            if (
                located := [
                    i
                    for i in members
                    if rows[i].get("latitude") is not None and rows[i].get("longitude") is not None
                ]
            )
        }
        self.city_members = {city: frozenset(members) for city, members in by_city.items()}
        self.locality_aliases = _locality_aliases(rows, set(by_city))
        self._index_osm_localities(localities or [])
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.lock = threading.Lock()
        self.connection.execute(
            "CREATE VIRTUAL TABLE labels USING fts5(candidate_index UNINDEXED, "
            "label, tokenize='trigram')"
        )
        values = [
            (index, label)
            for index, (labels, folded) in enumerate(zip(self.labels, self.folded, strict=True))
            for label in dict.fromkeys([*labels, *folded])
        ]
        values.extend((index, code) for index, code in enumerate(self.codes) if code)
        self.connection.executemany(
            "INSERT INTO labels(candidate_index, label) VALUES (?, ?)", values
        )
        # Compact keys live in their own table so ordinary probes stay as cheap as before.
        self.connection.execute(
            "CREATE VIRTUAL TABLE compact_labels USING fts5(candidate_index UNINDEXED, "
            "label, tokenize='trigram')"
        )
        self.connection.executemany(
            "INSERT INTO compact_labels(candidate_index, label) VALUES (?, ?)",
            [(index, key) for index, keys in enumerate(self.compact) for key in keys],
        )
        # One- and two-character queries are answered from these maps instead of scoring
        # every row. Setting both to None restores exhaustive scoring (tests use that as
        # the reference); the literal pass also scores the stop code, the folded pass not.
        self.short_literal: _ShortQueryScores | None = _ShortQueryScores(self.labels, self.codes)
        self.short_folded: _ShortQueryScores | None = _ShortQueryScores(
            self.folded, None, ascii_only=True
        )
        self._index_row_statics()
        # Complete results of this generation only; released with the index.
        self.results = ResultCache(STOP_RESULT_CACHE_ENTRIES)

    def _index_row_statics(self) -> None:
        """Per-row facts the bounded short-query ranking reads instead of row dicts."""
        rows, position = self.rows, self.position
        self.row_sid = [row["source_id"] for row in rows]
        self.row_station = [(row.get("location_type") or 0) == 1 for row in rows]
        self.row_rail = [
            bool(row.get("rail")) and not station
            for row, station in zip(rows, self.row_station, strict=True)
        ]
        self.row_parent = [-1] * len(rows)
        self.row_group = list(range(len(rows)))
        self.row_lat: list[float | None] = []
        self.row_lon: list[float | None] = []
        # A station that itself has a parent would be listed under its parent's ID while
        # forming its own group; the bounded ranking assumes that never happens.
        self.short_ranking_exact = True
        for index, row in enumerate(rows):
            parent_source = row.get("parent_station")
            parent = self.by_source.get(parent_source) if parent_source else None
            if parent is not None:
                self.row_parent[index] = position[parent["source_id"]]
                if not self.row_station[index]:
                    self.row_group[index] = self.row_parent[index]
                else:
                    self.short_ranking_exact = False
            located = row.get("latitude") is not None and row.get("longitude") is not None
            self.row_lat.append(row["latitude"] if located else None)
            self.row_lon.append(row["longitude"] if located else None)
        self.display_norm: dict[str, list[str]] = {}
        for language in ("he", "en"):
            memo: dict[str, str] = {}
            names = []
            for row in rows:
                shown = _display(row, language)[0]
                if (norm := memo.get(shown)) is None:
                    norm = memo[shown] = normalize_label(shown)
                names.append(norm)
            self.display_norm[language] = names

    def _index_osm_localities(self, localities: list[dict[str, Any]]) -> None:
        """Name forms and stop membership of the reference's OSM localities."""
        self.osm_localities = localities
        self.osm_by_name: dict[str, set[int]] = {}
        self.osm_by_folded: dict[str, set[int]] = {}
        self.osm_by_compact: dict[str, set[int]] = {}
        index_of = {item["locality_id"]: number for number, item in enumerate(localities)}
        members: dict[int, list[int]] = {}
        self.row_localities: list[frozenset[int]] = []
        for row_index, row in enumerate(self.rows):
            held = frozenset(
                index_of[key] for key in row.get("locality_ids") or () if key in index_of
            )
            self.row_localities.append(held)
            for number in held:
                members.setdefault(number, []).append(row_index)
        for number, item in enumerate(localities):
            for _language, name, _tag in item["names"]:
                for form in _locality_name_forms(name):
                    self.osm_by_name.setdefault(form, set()).add(number)
                    if form.isascii():
                        folded = fold_transliteration(form)
                        self.osm_by_folded.setdefault(folded, set()).add(number)
                        if len(key := compact_key(form)) >= _COMPACT_MIN_CHARS:
                            self.osm_by_compact.setdefault(key, set()).add(number)
        self.osm_members = {number: frozenset(rows) for number, rows in members.items()}
        self.osm_top = {
            number: tuple(sorted(rows, key=lambda i: (-self.importance[i], i))[:_LOCALITY_MAX_ROWS])
            for number, rows in members.items()
        }

    def _compact_rows(self, key: str) -> list[int]:
        escaped = key.replace('"', '""')
        with self.lock:
            rows = self.connection.execute(
                "SELECT DISTINCT candidate_index FROM compact_labels WHERE label MATCH ?",
                (f'"{escaped}"',),
            ).fetchall()
        return sorted(int(row[0]) for row in rows)

    def _token_rows(self, token: str) -> set[int]:
        escaped = token.replace('"', '""')
        rows = self.connection.execute(
            "SELECT DISTINCT candidate_index FROM labels WHERE label MATCH ?",
            (f'"{escaped}"',),
        )
        return {int(row[0]) for row in rows}

    def matching_rows(self, query: str) -> list[int]:
        tokens = tuple(dict.fromkeys(token for token in query.split() if len(token) >= 3))
        if not tokens:
            return list(range(len(self.rows)))
        with self.lock:
            matches = [self._token_rows(token) for token in tokens]
        return sorted(set.intersection(*matches)) if matches else []

    def locality_for(self, query: str) -> _LocalityIntent | None:
        """The locality whose name is exactly the query, in Hebrew or folded Latin.

        OSM localities (reference table) win; otherwise a feed-derived city name.
        A locality that holds no stop is ignored: it is not a place to search stops in.
        """
        if (intent := self._osm_intent(query)) is not None:
            return intent
        city = self.locality_aliases.get(query)
        if city is None and query.isascii():
            city = self.locality_aliases.get(fold_transliteration(query))
        if city is None:
            return None
        center = self.city_center.get(city)
        return _LocalityIntent(
            self.city_members[city],
            tuple(self.city_rows[city]),
            (center,) if center else (),
            # No city in the feed (for example rail stops) is not evidence of another city.
            lambda row_index: self.city_of[row_index] not in (None, city),
        )

    def _osm_intent(self, query: str) -> _LocalityIntent | None:
        if not self.osm_localities:
            return None
        matched = set(self.osm_by_name.get(query, ()))
        if query.isascii():
            matched |= self.osm_by_folded.get(fold_transliteration(query), set())
            if not matched and len(key := compact_key(query)) >= _COMPACT_MIN_CHARS:
                matched = set(self.osm_by_compact.get(key, ()))
        matched = {number for number in matched if number in self.osm_members}
        if not matched:
            return None
        ordered = sorted(matched)
        members = frozenset().union(*(self.osm_members[number] for number in ordered))
        top = sorted(
            {row for number in ordered for row in self.osm_top[number]},
            key=lambda i: (-self.importance[i], i),
        )[: _LOCALITY_MAX_ROWS * len(ordered)]
        return _LocalityIntent(
            members,
            tuple(top),
            tuple(self.osm_localities[number]["center"] for number in ordered),
            # Placed in other polygons only; a row in no polygon is unknown, not foreign.
            lambda row_index: bool(self.row_localities[row_index]) and row_index not in members,
        )

    def _scored_rows(self, query: str, *, folded: bool) -> Iterable[tuple[int, int]]:
        """(row, score) for every row the scorer accepts, in ascending row order."""
        short = self.short_folded if folded else self.short_literal
        if short is not None and _is_short_query(query):
            return short.scores(query).items()
        return self._exhaustive_scores(query, folded=folded)

    def _exhaustive_scores(self, query: str, *, folded: bool) -> Iterable[tuple[int, int]]:
        for row_index in self.matching_rows(query):
            if folded:
                score = _score_normalized(query, self.folded[row_index], "")
            else:
                score = _score_normalized(query, self.labels[row_index], self.codes[row_index])
            if score is not None:
                yield row_index, score

    def _score_sources(self, query: str) -> dict[float, list[Callable[[], Iterable[int]]]]:
        """Rows by the score ``strict_matches`` would give them, as suppliers per score.

        The same variants and passes as ``strict_matches``; a row listed under several
        scores takes the lowest, because callers visit scores in ascending order. Level 4
        of a short query is a supplier that scans only when called.
        """
        sources: dict[float, list[Callable[[], Iterable[int]]]] = {}

        def add(text: str, *, folded: bool, penalty: float) -> None:
            short = self.short_folded if folded else self.short_literal
            if short is not None and _is_short_query(text):
                for level, supplier in short.levels_for(text):
                    sources.setdefault(level + penalty, []).append(supplier)
                return
            by_score: dict[int, list[int]] = {}
            for row_index, score in self._exhaustive_scores(text, folded=folded):
                by_score.setdefault(score, []).append(row_index)
            for score, found in by_score.items():
                sources.setdefault(score + penalty, []).append(lambda found=found: found)

        for variant in _query_variants(query):
            folded = fold_transliteration(variant)
            add(variant, folded=False, penalty=0.0)
            if folded == variant and not variant.isascii():
                continue
            add(folded, folded=True, penalty=_FOLDED_PENALTY)
        return sources

    def short_winners(
        self,
        query: str,
        language: str,
        near: tuple[float, float] | None,
        requested: set[str],
        limit: int,
    ) -> dict[int, float] | None:
        """The rows that decide the first ``limit`` results of a one- or two-character query.

        Ranking such a query by grouping all of its matches (up to every stop) costs
        100-300 ms, yet only ``limit`` results leave. This visits matches in ascending
        score, groups them exactly as ``search_stops`` does (a parent and its platforms
        form one group, the lowest (score, source ID) row represents it, the display name
        falls back to the matching row's own), keys each group with the same ordering the
        ranking uses, and stops once ``limit`` groups are certain to beat everything not
        yet visited (an unseen group scores at least the next level, and a distant one is
        pushed back two levels, so the check compares the limit-th best effective score).
        It returns each winning group's representative row with its score; ``search_stops``
        then builds and orders those candidates with the unchanged code. ``None`` means the
        general path must run (not a short query, nothing matched, or an unusual index).
        """
        if (
            not self.short_ranking_exact
            or self.short_literal is None
            or self.short_folded is None
            or not _is_short_query(query)
        ):
            return None
        sources = self._score_sources(query)
        if not sources:
            return None
        values = sorted(sources)
        station_requested = "station" in requested
        stop_requested = "stop" in requested
        row_sid, row_station, row_rail = self.row_sid, self.row_station, self.row_rail
        row_parent, row_group = self.row_parent, self.row_group
        names = self.display_norm[language]
        best: dict[int, tuple[float, int]] = {}
        keyed: list[tuple[tuple, int, float]] = []
        for step, value in enumerate(values):
            fresh: list[int] = []
            for supplier in sources[value]:
                for row in supplier():
                    # Same filter as the grouping loop: category requested, or a rail stop.
                    if not (
                        row_rail[row] or (station_requested if row_station[row] else stop_requested)
                    ):
                        continue
                    group = row_group[row]
                    current = best.get(group)
                    if current is None:
                        best[group] = (value, row)
                        fresh.append(group)
                    elif current[0] == value and row_sid[row] < row_sid[current[1]]:
                        best[group] = (value, row)
            for group in fresh:
                row = best[group][1]
                base = row_parent[row] if station_requested and row_parent[row] >= 0 else row
                name = names[base]
                if base != row and query not in name:
                    # The station's label does not show the match: show the platform's.
                    name = names[row]
                distance = math.inf
                effective = value
                if near is not None:
                    if self.row_lat[base] is not None:
                        distance = _distance_m(
                            near[0], near[1], self.row_lat[base], self.row_lon[base]
                        )
                    if distance > _NEAR_FAR_M:
                        effective = value + _FAR_PENALTY
                keyed.append(((effective, distance, name, row_sid[base]), row, value))
            if len(keyed) >= limit:
                bound = heapq.nsmallest(limit, (item[0][0] for item in keyed))[-1]
                if step + 1 == len(values) or bound < values[step + 1]:
                    break
        if not keyed:
            return None
        return {row: value for _key, row, value in heapq.nsmallest(limit, keyed)}

    def strict_matches(self, query: str) -> dict[int, float]:
        """Best strict score per row; transliteration-folded matches rank lower."""
        best: dict[int, float] = {}
        for variant in _query_variants(query):
            folded = fold_transliteration(variant)
            for row_index, score in self._scored_rows(variant, folded=False):
                if score < best.get(row_index, 5):
                    best[row_index] = score
            if folded == variant and not variant.isascii():
                continue
            for row_index, score in self._scored_rows(folded, folded=True):
                if score + _FOLDED_PENALTY < best.get(row_index, 5):
                    best[row_index] = score + _FOLDED_PENALTY
        if not best:
            # Joined/split spelling is a rescue for queries nothing else matched; it
            # costs one more index probe, so it never runs next to a literal match.
            for variant in _query_variants(query):
                self._add_compact_matches(variant, best)
        return best

    def _add_compact_matches(self, variant: str, best: dict[int, float]) -> None:
        """Join-insensitive Latin match: exact or prefix of a label's compact key."""
        if not variant.isascii() or len(key := compact_key(variant)) < _COMPACT_MIN_CHARS:
            return
        for row_index in self._compact_rows(key):
            labels = self.compact[row_index]
            if key in labels:
                score = 1
            elif any(label.startswith(key) for label in labels):
                score = 2
            else:
                continue
            if score + _FOLDED_PENALTY < best.get(row_index, 5):
                best[row_index] = score + _FOLDED_PENALTY

    def partial_matches(self, query: str) -> dict[int, int]:
        """Rows covering most significant tokens when no row matches all of them."""
        result: dict[int, int] = {}
        variants = _query_variants(query)
        variants += [fold_transliteration(variant) for variant in variants]
        for variant in dict.fromkeys(variants):
            tokens = [t for t in dict.fromkeys(variant.split()) if t not in _STATION_WORDS]
            if len(tokens) < _PARTIAL_MIN_TOKENS:
                continue
            need = max(_PARTIAL_MIN_TOKENS, math.ceil(len(tokens) / 2))
            long_tokens = [token for token in tokens if len(token) >= 3]
            # Trigram sets are supersets of prefix matches, so a row covering `need`
            # tokens must appear in at least `need - short` long-token sets.
            required = need - (len(tokens) - len(long_tokens))
            if required <= 0:
                pool: set[int] | list[int] = range(len(self.rows))
            else:
                with self.lock:
                    sets = [self._token_rows(token) for token in long_tokens]
                hits: dict[int, int] = {}
                for matched in sets:
                    for row_index in matched:
                        hits[row_index] = hits.get(row_index, 0) + 1
                pool = [row for row, count in hits.items() if count >= required]
            for row_index in pool:
                covered = _coverage(tokens, self.coverage_labels[row_index])
                if covered >= need and covered > result.get(row_index, 0):
                    result[row_index] = covered
        return result


# One index per live reference (one per live snapshot). Keying weakly by the reference
# ties the index's lifetime to its snapshot: an old snapshot that is still finishing
# in-flight requests keeps its own index, and the index is released with the snapshot
# instead of being evicted by whichever generations were activated most recently.
_INDEXES: weakref.WeakKeyDictionary[ReferenceStore, _SearchIndex] = weakref.WeakKeyDictionary()
# Serializes builds only. Lookups of an existing index never take it, so a candidate
# snapshot's multi-second build cannot stall requests or readiness on the serving one.
_BUILD_LOCK = threading.Lock()


def _search_index(reference: ReferenceStore) -> _SearchIndex:
    """Return the reference's index, building it exactly once if it does not exist yet.

    Serving never relies on the lazy path: activation calls ``prepare_search_index``
    before a snapshot is published. Concurrent first callers share one build.
    """
    index = _INDEXES.get(reference)
    if index is not None:
        return index
    with _BUILD_LOCK:
        index = _INDEXES.get(reference)
        if index is None:
            # References without OSM locality data (or test doubles) have no localities.
            localities = getattr(reference, "search_localities", None)
            index = _SearchIndex(
                reference.stop_search_candidates(), localities() if localities else None
            )
            _INDEXES[reference] = index
        return index


def prepare_search_index(reference: ReferenceStore) -> None:
    """Build the immutable stop-search index before any passenger request needs it.

    Blocking (about 3.5 s on the national feed): call from a worker thread.
    """
    _search_index(reference)


def search_index_ready(reference: ReferenceStore | None) -> bool:
    """Whether the reference's index already exists (never builds it)."""
    return reference is not None and reference in _INDEXES


def search_stops(
    reference: ReferenceStore,
    query: str,
    *,
    language: str = "he",
    near: tuple[float, float] | None = None,
    types: tuple[str, ...] = ("stop", "station"),
    limit: int = 10,
) -> dict[str, Any]:
    """Return ranked, parent-deduplicated stop/station candidates.

    Unsupported categories are returned explicitly. A request for only an
    unsupported category raises ``UnavailableCategoryError`` for the API layer.
    """
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200:
        raise ValueError("Search query must contain 2 to 200 characters")
    if language not in {"he", "en"}:
        raise ValueError("Language must be he or en")
    if not 1 <= limit <= 20:
        raise ValueError("Limit must be between 1 and 20")
    if not types or len(set(types)) != len(types) or any(t not in KNOWN_TYPES for t in types):
        raise ValueError("Place types must be stop, station, poi, or address")
    unsupported = tuple(sorted(set(types) - SUPPORTED_TYPES))
    requested = set(types) & SUPPORTED_TYPES
    if not requested:
        raise UnavailableCategoryError(unsupported)

    normalized_query = normalize_label(query.strip())
    if not normalized_query:
        raise ValueError("Search query contains no searchable characters")

    index = _search_index(reference)
    # Everything that shapes the result is in the key (the query only through its
    # normalized form, which is all the search reads). The cache belongs to this index,
    # so it is empty for every new snapshot and released with the retired one. Results
    # are deterministic for one immutable generation, so a hit equals a fresh search.
    cache_key = (normalized_query, language, near, tuple(sorted(types)), limit)
    cacheable = near is None or all(math.isfinite(value) for value in near)
    if cacheable and (cached := index.results.get(cache_key)) is not None:
        return cached
    result = _search_uncached(
        index, normalized_query, language, near, requested, unsupported, limit
    )
    if cacheable:
        index.results.put(cache_key, result)
    return result


def _search_uncached(
    index: _SearchIndex,
    normalized_query: str,
    language: str,
    near: tuple[float, float] | None,
    requested: set[str],
    unsupported: tuple[str, ...],
    limit: int,
) -> dict[str, Any]:
    rows = index.rows
    by_source = index.by_source
    locality = index.locality_for(normalized_query)
    # A one- or two-character query would score and group every stop; only the rows that
    # decide the first `limit` results are kept, and the code below ranks those unchanged.
    short = (
        index.short_winners(normalized_query, language, near, requested, limit)
        if locality is None
        else None
    )
    partial = False
    if short is not None:
        scored = short
    else:
        scored = index.strict_matches(normalized_query)
        if not scored:
            # Partial coverage is a fallback only: full matches always rank as before.
            scored = {
                row: 10 - covered
                for row, covered in index.partial_matches(normalized_query).items()
            }
            partial = True
    centers: tuple[tuple[float, float], ...] = ()
    locality_hits: set[int] = set()
    if locality is not None:
        # The query names a locality: its stops lead (an exact label inside it still
        # ranks first); lexical matches placed in other localities (street-named stops)
        # rank after them.
        ranked_scores: dict[int, float] = {}
        for row_index, score in (scored if not partial else {}).items():
            if row_index in locality.members:
                ranked_scores[row_index] = min(score, _LOCALITY_TIER)
            elif locality.foreign(row_index):
                ranked_scores[row_index] = score + _LOCALITY_OUTSIDE_PENALTY
            else:
                ranked_scores[row_index] = score
        for row_index in locality.top_rows:
            if row_index not in ranked_scores or ranked_scores[row_index] > _LOCALITY_TIER:
                ranked_scores[row_index] = _LOCALITY_TIER
                locality_hits.add(row_index)
        scored, partial = ranked_scores, False
        centers = locality.centers

    grouped: dict[str, dict[str, Any]] = {}
    for row_index, score in scored.items():
        row = rows[row_index]
        location_type = row.get("location_type") or 0
        is_station = location_type == 1
        # A stop served by a GTFS rail route is a rail station in both vocabularies:
        # selectable as a stop and, because the feed gives it no parent or
        # location_type 1, also as a station.
        rail = bool(row.get("rail")) and not is_station
        candidate_type = "station" if is_station else "stop"
        if candidate_type not in requested and not rail:
            continue

        parent_source = row.get("parent_station")
        parent = by_source.get(parent_source) if parent_source else None
        station = parent if parent else row if is_station else None
        # Keep the station identity when a platform matches its translated/name/code
        # labels, and retain the matching platform as an actionable child reference.
        group_key = parent["source_id"] if parent and not is_station else row["source_id"]
        grouped_candidate = grouped.get(group_key)
        if grouped_candidate is None or (score, row["source_id"]) < (
            grouped_candidate["score"],
            grouped_candidate["matched_source_id"],
        ):
            as_station = "station" in requested and (parent is not None or rail)
            base = parent if parent and "station" in requested else row
            kind = "station" if as_station else candidate_type
            display_name, actual_language = _display(base, language)
            # If the station itself did not match, use the matching child label so
            # the passenger can recognize why this station was returned.
            if (
                base is not row
                and row_index not in locality_hits
                and _score(normalized_query, [display_name], None) is None
            ):
                display_name, actual_language = _display(row, language)
            base_index = index.position[base["source_id"]]
            grouped[group_key] = {
                "kind": kind,
                "id": STOP_PREFIX + base["source_id"],
                "displayName": display_name,
                "languageUsed": actual_language,
                "locality": base.get("description") or None,
                "coordinates": (
                    {"latitude": base["latitude"], "longitude": base["longitude"]}
                    if base.get("latitude") is not None and base.get("longitude") is not None
                    else None
                ),
                "stopCode": base.get("code"),
                "parentId": (
                    STOP_PREFIX + parent_source if parent_source and base is row else None
                ),
                "platformIds": [
                    STOP_PREFIX + child["source_id"]
                    for child in index.children_by_parent.get(station["stop_id"], [])
                ]
                if station
                else [],
                "matchedTypes": [kind],
                "score": score,
                "matched_source_id": row["source_id"],
                "importance": max(index.importance[row_index], index.importance[base_index]),
                "distance": None,
            }

    candidates = list(grouped.values())
    for candidate in candidates:
        if centers and candidate["coordinates"] is not None:
            offset = min(
                _distance_m(
                    center[0],
                    center[1],
                    candidate["coordinates"]["latitude"],
                    candidate["coordinates"]["longitude"],
                )
                for center in centers
            )
            candidate["center_offset"] = offset
            candidate["centrality"] = candidate["importance"] * math.exp(
                -offset / _LOCALITY_DECAY_M
            )
        if near is not None and candidate["coordinates"] is not None:
            lat, lon = near
            stop_lat = candidate["coordinates"]["latitude"]
            stop_lon = candidate["coordinates"]["longitude"]
            candidate["distance"] = _distance_m(lat, lon, stop_lat, stop_lon)

    def rank(item: dict[str, Any]) -> tuple:
        score = item["score"]
        distance = item["distance"] if item["distance"] is not None else math.inf
        name = normalize_label(item["displayName"])
        if partial:
            # Partial matches: most tokens covered, then the busiest stop.
            return (score, distance, -item["importance"], name, item["id"])
        if locality is not None:
            effective = score + (2 if near is not None and distance > _NEAR_FAR_M else 0)
            offset = item.get("center_offset", math.inf)
            centrality = -item.get("centrality", 0.0)
            return (effective, distance, centrality, offset, -item["importance"], name, item["id"])
        if near is not None:
            # With a location, a distant match drops two tiers so a nearby all-token
            # match can outrank a far exact/prefix one; ties order by distance.
            effective = score + (2 if distance > _NEAR_FAR_M else 0)
            return (effective, distance, name, item["id"])
        return (score, distance, name, item["id"])

    candidates.sort(key=rank)
    for candidate in candidates:
        candidate.pop("score", None)
        candidate.pop("matched_source_id", None)
        candidate.pop("importance", None)
        candidate.pop("center_offset", None)
        candidate.pop("centrality", None)
        if candidate["distance"] is None:
            candidate.pop("distance")
    return {
        "items": candidates[:limit],
        "matched_types": sorted(requested),
        "unavailable_types": list(unsupported),
        "partial": bool(unsupported),
    }


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_008.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lam = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    value = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(value))


class UnavailableCategoryError(ValueError):
    def __init__(self, categories: tuple[str, ...]) -> None:
        self.categories = categories
        super().__init__("Requested place categories are unavailable")
