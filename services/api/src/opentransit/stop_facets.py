"""Per-stop mode and direction of travel, derived from the reference timetable."""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

MIN_BEARING_AGREEMENT = 0.8
MODE_PRIORITY = ("rail", "light_rail", "bus")

_EARTH_RADIUS_METRES = 6_371_008.8
_MIN_SEPARATION_METRES = 1.0


@dataclass(frozen=True)
class StopFacets:
    mode: str | None
    bearing_degrees: float | None
    bearing_source: str | None


def dominant_mode(modes: Iterable[str]) -> str | None:
    """The first of rail, light rail and bus among ``modes``.

    ``"other"`` when only other modes are present, ``None`` when there are none.
    """
    present = set(modes)
    if not present:
        return None
    for mode in MODE_PRIORITY:
        if mode in present:
            return mode
    return "other"


def initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float | None:
    """Great-circle initial bearing from point 1 to point 2, degrees clockwise from north.

    ``None`` when the points are less than one metre apart, so no direction can be told.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    haversine = (
        math.sin((phi2 - phi1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    distance = 2 * _EARTH_RADIUS_METRES * math.asin(min(1.0, math.sqrt(haversine)))
    if distance < _MIN_SEPARATION_METRES:
        return None
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    return math.degrees(math.atan2(y, x)) % 360.0


def mean_bearing(
    bearings: Sequence[float], min_agreement: float = MIN_BEARING_AGREEMENT
) -> float | None:
    """Circular mean of ``bearings``, one decimal in ``[0, 360)``.

    ``None`` when there are none or they disagree: the mean unit vector is shorter
    than ``min_agreement``.
    """
    if not bearings:
        return None
    east = sum(math.sin(math.radians(bearing)) for bearing in bearings)
    north = sum(math.cos(math.radians(bearing)) for bearing in bearings)
    if math.hypot(east, north) / len(bearings) < min_agreement:
        return None
    return round(math.degrees(math.atan2(east, north)), 1) % 360.0


def load_stop_facets(
    connection: sqlite3.Connection, mode_of: Callable[[int | None], str]
) -> dict[str, StopFacets]:
    """Mode and direction of travel for every row of ``stops``, keyed by ``stop_id``.

    Columns are read by position, so the connection's ``row_factory`` does not matter.
    ``mode_of`` maps a GTFS ``route_type`` to a mode string (``route_type_mode``).
    """
    positions: dict[str, tuple[float | None, float | None]] = {}
    children: dict[str, list[str]] = defaultdict(list)
    for stop_id, latitude, longitude, parent_station in connection.execute(
        "SELECT stop_id, latitude, longitude, parent_station FROM stops"
    ):
        positions[stop_id] = (latitude, longitude)
        if parent_station is not None:
            children[parent_station].append(stop_id)

    route_modes = {
        route_id: mode_of(route_type)
        for route_id, route_type in connection.execute("SELECT route_id, route_type FROM routes")
    }
    unknown_route_mode = mode_of(None)
    stop_modes: dict[str, set[str]] = defaultdict(set)
    for route_id, stop_id in connection.execute("SELECT route_id, stop_id FROM route_stops"):
        stop_modes[stop_id].add(route_modes.get(route_id, unknown_route_mode))

    leaving: dict[str, list[float]] = defaultdict(list)
    arriving: dict[str, list[float]] = defaultdict(list)
    previous_pattern = previous_stop = None
    for pattern_id, stop_id in connection.execute(
        "SELECT pattern_id, stop_id FROM pattern_stops ORDER BY pattern_id, sequence"
    ):
        if pattern_id == previous_pattern and stop_id != previous_stop:
            bearing = _bearing_between(positions.get(previous_stop), positions.get(stop_id))
            if bearing is not None:
                leaving[previous_stop].append(bearing)
                arriving[stop_id].append(bearing)
        previous_pattern, previous_stop = pattern_id, stop_id

    facets: dict[str, StopFacets] = {}
    for stop_id in positions:
        modes = stop_modes.get(stop_id)
        if not modes:
            modes = set().union(*(stop_modes.get(child, ()) for child in children.get(stop_id, ())))
        if leaving.get(stop_id):
            bearing, source = mean_bearing(leaving[stop_id]), "next_stop"
        else:
            bearing, source = mean_bearing(arriving.get(stop_id, ())), "previous_stop"
        facets[stop_id] = StopFacets(
            dominant_mode(modes), bearing, source if bearing is not None else None
        )
    return facets


def _bearing_between(
    origin: tuple[float | None, float | None] | None,
    destination: tuple[float | None, float | None] | None,
) -> float | None:
    if origin is None or destination is None or None in origin or None in destination:
        return None
    return initial_bearing(*origin, *destination)
