"""Generation-local Hebrew/English search over the immutable stop reference."""

from __future__ import annotations

import math
import re
import sqlite3
import threading
import unicodedata
from functools import lru_cache
from typing import Any

from opentransit.reference import STOP_PREFIX, ReferenceStore

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
# Keyed by a normalized name token; values are added as searchable labels.
_ALIASES = {"נתבג": ("ben gurion airport",)}
# Latin transliteration folding for Hebrew place names (Yits'hak/Yitzhak,
# Hertsliya/Herzliya, Petach Tikwa/Petah Tiqwa/Petah Tikva).
_FOLDS = (("tz", "z"), ("ts", "z"), ("ch", "h"), ("kh", "h"), ("ck", "k"), ("q", "k"))
_FOLDS += (("w", "v"), ("ph", "f"), ("y", "i"))
_REPEATED = re.compile(r"(.)\1+")
_PARTIAL_MIN_TOKENS = 2
# Transliteration-only matches rank half a tier below the same literal match.
_FOLDED_PENALTY = 0.5
# With a location, a match farther than this ranks two tiers lower.
_NEAR_FAR_M = 10_000.0


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


def _expand_abbreviations(normalized: str) -> str | None:
    words = normalized.split()
    if not any(word in _ABBREVIATIONS for word in words):
        return None
    return " ".join(_ABBREVIATIONS.get(word, word) for word in words)


def _label_variants(normalized: list[str]) -> list[str]:
    labels = list(normalized)
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
    """Largest number of query tokens prefix-matched by words of one label."""
    best = 0
    for label in labels:
        words = label.split()
        best = max(best, sum(any(word.startswith(token) for word in words) for token in tokens))
    return best


class _SearchIndex:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
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
        self.codes: list[str] = []
        self.importance: list[int] = []
        for row in rows:
            raw = [row.get("name"), *row["translations"].values(), row.get("description")]
            normalized = [n for value in raw if value and (n := normalize_label(value))]
            self.labels.append(_label_variants(normalized))
            self.folded.append(_folded_labels(self.labels[-1]))
            self.coverage_labels.append(list(dict.fromkeys([*self.labels[-1], *self.folded[-1]])))
            self.codes.append(normalize_label(row.get("code") or ""))
            routes = int(row.get("route_count") or 0)
            routes += sum(
                int(child.get("route_count") or 0)
                for child in self.children_by_parent.get(row["stop_id"], [])
            )
            self.importance.append(routes)
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

    def strict_matches(self, query: str) -> dict[int, float]:
        """Best strict score per row; transliteration-folded matches rank lower."""
        best: dict[int, float] = {}
        for variant in _query_variants(query):
            folded = fold_transliteration(variant)
            for row_index in self.matching_rows(variant):
                score = _score_normalized(variant, self.labels[row_index], self.codes[row_index])
                if score is not None and score < best.get(row_index, 5):
                    best[row_index] = score
            if folded == variant and not variant.isascii():
                continue
            for row_index in self.matching_rows(folded):
                score = _score_normalized(folded, self.folded[row_index], "")
                if score is not None and score + _FOLDED_PENALTY < best.get(row_index, 5):
                    best[row_index] = score + _FOLDED_PENALTY
        return best

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


@lru_cache(maxsize=2)
def _search_index(reference: ReferenceStore) -> _SearchIndex:
    # Each instance belongs to one immutable generation; the bounded cache lets an
    # old captured snapshot finish while preventing unbounded index accumulation.
    return _SearchIndex(reference.stop_search_candidates())


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
    rows = index.rows
    by_source = index.by_source
    scored = index.strict_matches(normalized_query)
    partial = False
    if not scored:
        # Partial coverage is a fallback only: full matches always rank as before.
        scored = {
            row: 10 - covered for row, covered in index.partial_matches(normalized_query).items()
        }
        partial = True

    grouped: dict[str, dict[str, Any]] = {}
    for row_index, score in scored.items():
        row = rows[row_index]
        location_type = row.get("location_type") or 0
        is_station = location_type == 1
        candidate_type = "station" if is_station else "stop"
        if candidate_type not in requested:
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
            base = parent if parent and "station" in requested else row
            display_name, actual_language = _display(base, language)
            # If the station itself did not match, use the matching child label so
            # the passenger can recognize why this station was returned.
            if base is not row and _score(normalized_query, [display_name], None) is None:
                display_name, actual_language = _display(row, language)
            base_index = index.position[base["source_id"]]
            grouped[group_key] = {
                "kind": "station" if parent and "station" in requested else candidate_type,
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
                "matchedTypes": [
                    "station" if parent and "station" in requested else candidate_type
                ],
                "score": score,
                "matched_source_id": row["source_id"],
                "importance": max(index.importance[row_index], index.importance[base_index]),
                "distance": None,
            }

    candidates = list(grouped.values())
    for candidate in candidates:
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
