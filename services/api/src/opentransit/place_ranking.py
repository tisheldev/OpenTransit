"""Order stop and geocoder candidates by how well each one answers the query.

The stop index, Photon (addresses) and MOTIS (points of interest) each rank only their own
candidates, and their scores cannot be compared. Alternating their lists by position let a
loose match from one backend sit above an exact match from another: for "הפועל 13 הרצליה"
the stop search has no full match and falls back to stops sharing any two words, so stops
that share only "13" and the city took every other place, the first one included.

Every candidate is therefore given a penalty for the query words it does not account for,
judged from its name (label, street, house number) and its context (locality; for a stop,
the street and city in its description):

* words must match whole words (one wrong letter, the doubled-vav/yod spellings and the
  Latin transliteration fold are tolerated); only the last word, which may still be being
  typed, also matches as a prefix;
* a missing word costs more than a missing house number, so the right street in the right
  city (no such house number mapped) precedes the same house number in another city;
* a candidate whose own name accounts for no query word (it only shares the city or the
  number) is pushed back further;
* a word that cannot be judged, because the candidate has text in another script only
  (an English street name with a Hebrew city), costs no more than a missing house number;
* stop candidates from a full stop-index match are trusted as they are; stops from the
  index's partial-coverage fallback are judged against every label the index holds for
  them (translations, abbreviations), which the caller passes in.

Candidates with equal penalties keep their backend's order and alternate between the two
pools as before, stops first; an address leads when the query reads as a street address
(a word and a number). Segments of one street, or several nodes of one house address, are
listed once.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from opentransit.stop_search import fold_transliteration, normalize_label

RANKING_POLICY = "query-coverage-tiers-v1"

_WORD_MISS = 3
_NUMBER_MISS = 1
_UNJUDGED = 1
_NAME_UNMATCHED = 2
# One wrong, missing or extra letter still matches, for words long enough that a different
# word one letter away is unlikely (Hebrew words of four letters often differ by one).
_TYPO_MIN_CHARS = 5
_SAME_ADDRESS_M = 250.0
# Words that say "this is a street" and name nothing; ignored when other words remain.
_GENERIC_WORDS = frozenset({"street", "st", "רחוב", "רח"})


@dataclass(frozen=True)
class _Query:
    words: tuple[str, ...]
    numbers: tuple[str, ...]
    typing: str | None  # the last token, which may still be being typed


def merge_candidates(
    query: str,
    stops: list[dict[str, Any]],
    geocoders: list[dict[str, Any]],
    limit: int,
    *,
    stop_fallback: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """The first ``limit`` candidates of both pools, best answers to ``query`` first.

    ``stop_fallback`` is ``search_stops``' ``coverage_fallback``: ``None`` when the stops
    are full matches, otherwise each stop ID's searchable labels (``name``) and description
    (``context``), because those stops cover only some of the query's words.
    """
    parsed = _parse(query)
    tiers: dict[int, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}
    for item in stops:
        penalty = 0 if stop_fallback is None else _stop_penalty(parsed, item, stop_fallback)
        tiers.setdefault(penalty, ([], []))[0].append(item)
    for item in geocoders:
        penalty = _penalty(
            parsed,
            _text_words(
                item.get("displayName"),
                item.get("name"),
                item.get("street"),
                item.get("houseNumber"),
            ),
            _text_words(item.get("locality")),
        )
        tiers.setdefault(penalty, ([], []))[1].append(item)

    address_query = bool(parsed.words and parsed.numbers)
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    addresses: list[tuple[tuple[str, str, str], str, float | None, float | None]] = []
    for penalty in sorted(tiers):
        tier_stops, tier_geocoders = tiers[penalty]
        address_first = (
            address_query and bool(tier_geocoders) and tier_geocoders[0].get("kind") == "address"
        )
        pools = (tier_geocoders, tier_stops) if address_first else (tier_stops, tier_geocoders)
        for index in range(max(len(tier_stops), len(tier_geocoders))):
            for pool in pools:
                if index >= len(pool):
                    continue
                item = pool[index]
                location_ref = item.get("locationRef") or {}
                identity = location_ref.get("stopId", location_ref.get("placeRef"))
                key = (location_ref.get("kind"), identity)
                if key in seen or _repeats_an_address(item, addresses):
                    continue
                seen.add(key)
                merged.append(item)
                if len(merged) >= limit:
                    return merged
    return merged


def _parse(query: str) -> _Query:
    """Distinct query words and numbers, normalized like candidate text."""
    tokens = _text_words(query)
    words = [token for token in dict.fromkeys(tokens) if not token[0].isdigit()]
    numbers = [token for token in dict.fromkeys(tokens) if token[0].isdigit()]
    named = [word for word in words if word not in _GENERIC_WORDS]
    return _Query(tuple(named or words), tuple(numbers), tokens[-1] if tokens else None)


def _text_words(*values: Any) -> list[str]:
    found: list[str] = []
    for value in values:
        if isinstance(value, str) and value:
            found.extend(_spelling_key(word) for word in normalize_label(value).split())
    return found


def _spelling_key(word: str) -> str:
    """One key for spellings of one word.

    Latin: the stop index's transliteration fold (Petach/Petah, Tiqwa/Tikva). Hebrew: the
    full and defective spellings that differ by a doubled vav or yod (תקווה/תקוה).
    """
    if word.isascii():
        return fold_transliteration(word)
    while "וו" in word:
        word = word.replace("וו", "ו")
    while "יי" in word:
        word = word.replace("יי", "י")
    return word


def _script(word: str) -> str | None:
    for char in word:
        if 0x0590 <= ord(char) <= 0x05FF:  # Hebrew block
            return "hebrew"
        if char.isascii() and char.isalpha():
            return "latin"
    return None


def _scripts(words: list[str]) -> set[str]:
    return {script for word in words if (script := _script(word)) is not None}


def _stop_penalty(
    query: _Query, item: dict[str, Any], fallback: Mapping[str, Mapping[str, Any]]
) -> int:
    known = fallback.get(item.get("id"))
    if known is None:
        return _penalty(
            query, _text_words(item.get("displayName")), _text_words(item.get("locality"))
        )
    return _penalty(query, _text_words(*known.get("name", ())), _text_words(known.get("context")))


def _penalty(query: _Query, name_words: list[str], context_words: list[str]) -> int:
    name_scripts, context_scripts = _scripts(name_words), _scripts(context_words)
    fields = [scripts for scripts in (name_scripts, context_scripts) if scripts]
    missed = unjudged = 0
    name_judged = name_hit = False
    for token in query.words:
        prefix = token == query.typing
        script = _script(token)
        name_judged = name_judged or script in name_scripts
        if _has_word(token, name_words, prefix=prefix):
            name_hit = True
        elif _has_word(token, context_words, prefix=prefix):
            continue
        elif fields and all(script in scripts for scripts in fields):
            missed += 1
        else:
            # Some text of this candidate is in another script only; the word may be there.
            unjudged += 1
    if name_judged and not name_hit:
        # A readable name that accounts for nothing is not excused by an unreadable locality.
        missed, unjudged = missed + unjudged, 0
    penalty = _WORD_MISS * missed + (_UNJUDGED if unjudged else 0)
    all_words = name_words + context_words
    penalty += _NUMBER_MISS * sum(not _has_number(token, all_words) for token in query.numbers)
    if name_judged and not name_hit:
        penalty += _NAME_UNMATCHED
    return penalty


def _has_word(token: str, words: list[str], *, prefix: bool) -> bool:
    if token in words or (prefix and any(word.startswith(token) for word in words)):
        return True
    return len(token) >= _TYPO_MIN_CHARS and any(_one_edit_apart(token, word) for word in words)


def _has_number(token: str, words: list[str]) -> bool:
    """The same number, alone or with a letter suffix ("13" also finds "13א"), never "130"."""
    return any(
        word.startswith(token) and (len(word) == len(token) or not word[len(token)].isdigit())
        for word in words
    )


def _one_edit_apart(first: str, second: str) -> bool:
    if abs(len(first) - len(second)) > 1:
        return False
    if len(first) > len(second):
        first, second = second, first
    index = 0
    while index < len(first) and first[index] == second[index]:
        index += 1
    if len(first) == len(second):
        return first[index + 1 :] == second[index + 1 :]
    return first[index:] == second[index + 1 :]


def _repeats_an_address(
    item: dict[str, Any],
    kept: list[tuple[tuple[str, str, str], str, float | None, float | None]],
) -> bool:
    """Whether an address candidate names an address already listed; records it if not.

    OSM maps one street as several ways and one house address as several nodes. They are the
    same answer when the locality is the same, or (the locality label can differ by language
    or be absent) when they are close together.
    """
    if item.get("kind") != "address":
        return False
    street = " ".join(_text_words(item.get("street") or item.get("displayName")))
    number = " ".join(_text_words(item.get("houseNumber")))
    signature = (str(item.get("addressLevel")), street, number)
    locality = " ".join(_text_words(item.get("locality")))
    coordinates = item.get("coordinates") or {}
    latitude, longitude = coordinates.get("latitude"), coordinates.get("longitude")
    for kept_signature, kept_locality, kept_latitude, kept_longitude in kept:
        if kept_signature != signature:
            continue
        if locality and locality == kept_locality:
            return True
        if (
            None not in (latitude, longitude, kept_latitude, kept_longitude)
            and _distance_m(latitude, longitude, kept_latitude, kept_longitude) <= _SAME_ADDRESS_M
        ):
            return True
    kept.append((signature, locality, latitude, longitude))
    return False


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lam = phi2 - phi1, math.radians(lon2 - lon1)
    value = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * 6_371_008.8 * math.asin(math.sqrt(value))
