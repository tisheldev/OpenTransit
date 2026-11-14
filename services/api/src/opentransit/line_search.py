"""Line search by number (stops and lines overhaul, A2).

A line is an operator plus its MOT line code: the part of ``route_desc`` before the first
'-' ("55008" in "55008-1-0"). A MOT route is one direction, so a line groups the routes
that share both; this is the key ``ReferenceStore.stop_lines`` uses to find a line's other
direction. Operator and number alone would merge unrelated lines in different towns.

The index of lines (numbers, operators, routes) is built once per reference store from
the routes table and kept in memory; directions, area and the nearest stop are read per
request for the lines on the page only.
"""

from __future__ import annotations

import bisect
import math
import re
import threading
import weakref
from dataclasses import dataclass
from typing import Any

from opentransit.reference import (
    _cursor_decode,
    _cursor_encode,
    _distance_m,
    _line_code,
    route_type_mode,
)
from opentransit.search_cache import ResultCache
from opentransit.stop_facets import dominant_mode

DEFAULT_LINES_PAGE = 20
MAX_LINES_PAGE = 50
MAX_QUERY_LENGTH = 50
NEAREST_STOP_RADIUS_M = 2000
# Directions and area per line, kept per store (both are fixed for a generation).
DETAIL_CACHE_ENTRIES = 1024
_LEADING_NUMBER = re.compile(r"(\d+)(.*)", re.DOTALL)


@dataclass(frozen=True)
class Line:
    key: str
    short_name: str
    folded: str
    operator_id: str | None
    operator_name: str | None
    mode: str
    route_ids: tuple[str, ...]

    @property
    def order(self) -> tuple:
        """Numeric, then lexical: 8 < 80 < 82 < 800 < 8א; names without digits last."""
        match = _LEADING_NUMBER.fullmatch(self.folded)
        if match:
            return (0, int(match[1]), match[2], self.key)
        return (1, 0, self.folded, self.key)


def fold(text: str) -> str:
    """How a number is compared: trimmed and case-insensitive."""
    return text.strip().casefold()


def line_key(agency_id: str | None, description: str | None, source_id: str) -> str:
    """``<agency_id>:<line code>``; a route without a line code is a line of its own."""
    code = _line_code(description)
    agency = agency_id or ""
    return f"{agency}:{code}" if code is not None else f"{agency}:route:{source_id}"


class LineIndex:
    """Every line of one generation, searchable by the start of its number."""

    def __init__(self, store) -> None:
        # A proxy: the registry below is keyed weakly by the store, so its value must not
        # keep the store alive.
        self._store = weakref.proxy(store)
        self._details = ResultCache(DETAIL_CACHE_ENTRIES)
        groups: dict[str, list[Any]] = {}
        for row in store.read_rows(
            "SELECT r.route_id, r.source_id, r.agency_id, r.short_name, r.description, "
            "r.route_type, a.name AS agency_name FROM routes r "
            "LEFT JOIN agencies a ON a.agency_id=r.agency_id ORDER BY r.route_id"
        ):
            key = line_key(row["agency_id"], row["description"], row["source_id"])
            groups.setdefault(key, []).append(row)
        self.by_key: dict[str, Line] = {}
        for key, rows in groups.items():
            # Main directions before alternatives ("55008-1-0", "55008-2-0", "55008-1-1").
            rows.sort(key=lambda row: (row["description"] or "", row["route_id"]))
            names = [row["short_name"] for row in rows if row["short_name"]]
            short_name = min(names, key=lambda name: (-names.count(name), name)) if names else ""
            self.by_key[key] = Line(
                key=key,
                short_name=short_name,
                folded=fold(short_name),
                operator_id=rows[0]["agency_id"],
                operator_name=rows[0]["agency_name"],
                mode=dominant_mode(route_type_mode(row["route_type"]) for row in rows) or "other",
                route_ids=tuple(row["route_id"] for row in rows),
            )
        self._sorted = sorted(
            (line for line in self.by_key.values() if line.folded),
            key=lambda line: (line.folded, line.key),
        )
        self._folded = [line.folded for line in self._sorted]

    def matches(self, query: str) -> list[Line]:
        """Lines whose number starts with ``query`` (already folded)."""
        start = bisect.bisect_left(self._folded, query)
        end = bisect.bisect_left(self._folded, query + "\U0010ffff", lo=start)
        return self._sorted[start:end]

    def search(
        self,
        q: str,
        latitude: float | None = None,
        longitude: float | None = None,
        limit: int = DEFAULT_LINES_PAGE,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Exact number first, then longer numbers; nearest first within each, then number."""
        if isinstance(limit, bool) or not 1 <= limit <= MAX_LINES_PAGE:
            raise ValueError("Line pages hold 1 to 50 lines")
        if not isinstance(q, str) or len(q) > MAX_QUERY_LENGTH or not fold(q):
            raise ValueError("A line number of 1 to 50 characters is required")
        _check_position(latitude, longitude)
        folded = fold(q)
        generation_id = self._store.metadata.generation_id
        query = {"kind": "lines", "q": folded, "lat": latitude, "lon": longitude}
        after = _cursor_decode(cursor, generation_id, query)
        found = self.matches(folded)
        nearest = self._nearest(found, latitude, longitude)

        def rank(line: Line) -> tuple:
            near = nearest.get(line.key)
            return (
                line.folded != folded,
                near is None,
                near["distance"] if near else 0.0,
                line.order,
            )

        ranked = sorted(found, key=rank)
        if after is not None:
            keys = [line.key for line in ranked]
            if after[0] not in keys:
                raise ValueError("Cursor is invalid or belongs to a different query/generation")
            ranked = ranked[keys.index(after[0]) + 1 :]
        page = ranked[:limit]
        items = [self._item(line, nearest, latitude is not None) for line in page]
        next_cursor = (
            _cursor_encode(generation_id, query, [page[-1].key]) if len(ranked) > limit else None
        )
        return {"items": items, "next_cursor": next_cursor, "generation_id": generation_id}

    def line(
        self, key: str, latitude: float | None = None, longitude: float | None = None
    ) -> dict[str, Any] | None:
        _check_position(latitude, longitude)
        found = self.by_key.get(key)
        if found is None:
            return None
        nearest = self._nearest([found], latitude, longitude)
        return self._item(found, nearest, latitude is not None)

    def _item(self, line: Line, nearest: dict, located: bool) -> dict[str, Any]:
        details = self._details.get(line.key)
        if details is None:
            details = self._read_details(line)
            self._details.put(line.key, details)
        item = {
            "lineKey": line.key,
            "shortName": line.short_name,
            "operatorId": line.operator_id,
            "operatorName": line.operator_name,
            "mode": line.mode,
            "routeIds": list(line.route_ids),
            "directions": details["directions"],
            "area": details["area"],
        }
        if located:
            near = nearest.get(line.key)
            item["nearestStop"] = (
                {
                    "stopId": near["stop_id"],
                    "name": near["name"],
                    "distanceM": round(near["distance"]),
                }
                if near
                else None
            )
        return item

    def _read_details(self, line: Line) -> dict[str, Any]:
        marks = ",".join("?" * len(line.route_ids))
        # Per route, its longest pattern (most stops; then pattern ID) describes the direction.
        chosen: dict[str, Any] = {}
        for row in self._store.read_rows(
            "SELECT p.route_id, p.pattern_id, p.headsign, COUNT(*) AS calls FROM patterns p "
            f"JOIN pattern_stops ps ON ps.pattern_id=p.pattern_id WHERE p.route_id IN ({marks}) "
            "GROUP BY p.pattern_id ORDER BY p.route_id, calls DESC, p.pattern_id",
            line.route_ids,
        ):
            chosen.setdefault(row["route_id"], row)
        directions = []
        for route_id in line.route_ids:
            pattern = chosen.get(route_id)
            origin = destination = None
            if pattern is not None:
                ends = {
                    row["sequence"]: row["name"]
                    for row in self._store.read_rows(
                        "SELECT ps.sequence, s.name FROM pattern_stops ps "
                        "JOIN stops s ON s.stop_id=ps.stop_id "
                        "WHERE ps.pattern_id=? AND ps.sequence IN (0, ?)",
                        (pattern["pattern_id"], pattern["calls"] - 1),
                    )
                }
                origin, destination = ends.get(0), ends.get(pattern["calls"] - 1)
            directions.append(
                {
                    "routeId": route_id,
                    "headsign": pattern["headsign"] if pattern is not None else None,
                    "originName": origin,
                    "destinationName": destination,
                }
            )
        return {"directions": directions, "area": self._area(line, marks)}

    def _area(self, line: Line, marks: str) -> str | None:
        """The locality holding at least half of the line's stops, if the reference has them."""
        if not getattr(self._store, "has_localities", False):
            return None
        total = self._store.read_rows(
            f"SELECT COUNT(DISTINCT stop_id) FROM route_stops WHERE route_id IN ({marks})",
            line.route_ids,
        )[0][0]
        if not total:
            return None
        best = self._store.read_rows(
            "SELECT sl.locality_id, COUNT(DISTINCT rs.stop_id) AS stops, l.name_he, l.name "
            "FROM route_stops rs JOIN stop_localities sl ON sl.stop_id=rs.stop_id "
            "JOIN localities l ON l.locality_id=sl.locality_id "
            f"WHERE rs.route_id IN ({marks}) GROUP BY sl.locality_id "
            "ORDER BY stops DESC, sl.locality_id LIMIT 1",
            line.route_ids,
        )
        if not best or 2 * best[0]["stops"] < total:
            return None
        return best[0]["name_he"] or best[0]["name"]

    def _nearest(
        self, lines: list[Line], latitude: float | None, longitude: float | None
    ) -> dict[str, dict[str, Any]]:
        """Per line key, its stop nearest the position (within 2 km)."""
        if latitude is None or longitude is None or not lines:
            return {}
        lat_delta = NEAREST_STOP_RADIUS_M / 110_574
        lon_delta = NEAREST_STOP_RADIUS_M / (111_320 * max(0.01, math.cos(math.radians(latitude))))
        stops = {}
        for row in self._store.read_rows(
            "SELECT stop_id, name, latitude, longitude FROM stops "
            "WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
            (
                latitude - lat_delta,
                latitude + lat_delta,
                longitude - lon_delta,
                longitude + lon_delta,
            ),
        ):
            distance = _distance_m(latitude, longitude, row["latitude"], row["longitude"])
            if distance <= NEAREST_STOP_RADIUS_M:
                stops[row["stop_id"]] = (distance, row["name"])
        owner = {route_id: line.key for line in lines for route_id in line.route_ids}
        nearest: dict[str, dict[str, Any]] = {}
        stop_ids = sorted(stops)
        for chunk_start in range(0, len(stop_ids), 500):
            chunk = stop_ids[chunk_start : chunk_start + 500]
            for row in self._store.read_rows(
                "SELECT route_id, stop_id FROM route_stops INDEXED BY route_stops_stop_idx "
                f"WHERE stop_id IN ({','.join('?' * len(chunk))})",
                chunk,
            ):
                key = owner.get(row["route_id"])
                if key is None:
                    continue
                distance, name = stops[row["stop_id"]]
                best = nearest.get(key)
                if best is None or (distance, row["stop_id"]) < (best["distance"], best["stop_id"]):
                    nearest[key] = {"stop_id": row["stop_id"], "name": name, "distance": distance}
        return nearest


def _check_position(latitude: float | None, longitude: float | None) -> None:
    if (latitude is None) != (longitude is None):
        raise ValueError("Give both lat and lon, or neither")
    if latitude is None:
        return
    for value in (latitude, longitude):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Coordinates must be numbers")
        if not math.isfinite(value):
            raise ValueError("Coordinates must be finite")


_INDEXES: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_INDEX_LOCK = threading.Lock()


def line_index(store) -> LineIndex:
    """The store's line index, built on first use and released with the store."""
    with _INDEX_LOCK:
        index = _INDEXES.get(store)
        if index is None:
            index = LineIndex(store)
            _INDEXES[store] = index
        return index
