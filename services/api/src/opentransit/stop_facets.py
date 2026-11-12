"""Per-stop mode and direction of travel, derived from the reference timetable."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
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
