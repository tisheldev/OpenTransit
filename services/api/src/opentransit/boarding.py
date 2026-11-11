"""Where a rider boards: the vehicle's direction of travel and the stop's side of its path.

Board 3 (client design, 11 November) labels the boarding stop "on this side, toward <place>".
The client knows where the person stands; the API supplies the vehicle's bearing as it leaves
the stop, the point on the vehicle's path nearest the stop, and which side of that path
(relative to the direction of travel) the stop stands on. The person is on the stop's side
when the same cross-product test puts them on that side of the line through ``pathPoint``.

MOTIS starts a transit leg's geometry at the stop's own coordinate and then joins the trip's
shape, so the first segment is a connector, not road. The side is measured against the shape
after that connector. A rail leg's geometry is station to station, so no side is given.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_M_PER_DEG_LAT = 110_574.0
_M_PER_DEG_LON_EQUATOR = 111_320.0
# The bearing is read over this length of path past the stop: long enough to ignore a kink
# at the stop, short enough to stay on the street the stop is on.
BEARING_LOOKAHEAD_M = 30.0
# The stop's offset from the vehicle path must fall in this band for a side to be stated: a
# stop on the line itself has no side, and one far off it means the shape does not describe
# the street at the stop.
SIDE_MIN_OFFSET_M = 1.5
SIDE_MAX_OFFSET_M = 40.0
# Modes that run on the street, where "which side of the road" means something.
STREET_MODES = frozenset({"bus", "light_rail"})


@dataclass(frozen=True)
class BoardingGeometry:
    bearing_degrees: float | None
    bearing_source: str | None
    stop_side: str | None
    stop_offset_meters: float | None
    path_point: tuple[float, float] | None  # (lon, lat)
    side_unavailable_reason: str | None


def _project(lon: float, lat: float, origin: tuple[float, float]) -> tuple[float, float]:
    lon0, lat0 = origin
    scale = _M_PER_DEG_LON_EQUATOR * math.cos(math.radians(lat0))
    return (lon - lon0) * scale, (lat - lat0) * _M_PER_DEG_LAT


def _unproject(x: float, y: float, origin: tuple[float, float]) -> tuple[float, float]:
    lon0, lat0 = origin
    scale = _M_PER_DEG_LON_EQUATOR * math.cos(math.radians(lat0))
    return lon0 + x / scale, lat0 + y / _M_PER_DEG_LAT


def _bearing(dx: float, dy: float) -> float:
    return round(math.degrees(math.atan2(dx, dy)) % 360.0, 1)


def _nearest_on_path(points, start_segment: int):
    """(distance, segment index, t, x, y) of the path point nearest the origin (0, 0)."""
    best = None
    for index in range(start_segment, len(points) - 1):
        (ax, ay), (bx, by) = points[index], points[index + 1]
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length2))
        x, y = ax + t * dx, ay + t * dy
        distance = math.hypot(x, y)
        if best is None or distance < best[0]:
            best = (distance, index, t, x, y)
    return best


def _ahead(points, index: int, x: float, y: float, length: float) -> tuple[float, float] | None:
    """The point ``length`` metres further along the path from (x, y) on segment ``index``."""
    remaining = length
    cx, cy = x, y
    for nxt in points[index + 1 :]:
        step = math.hypot(nxt[0] - cx, nxt[1] - cy)
        if step >= remaining and step > 0:
            ratio = remaining / step
            return cx + ratio * (nxt[0] - cx), cy + ratio * (nxt[1] - cy)
        remaining -= step
        cx, cy = nxt
    if (cx, cy) == (x, y):
        return None
    return cx, cy


def boarding_geometry(
    stop: tuple[float, float],
    path: list[list[float]] | None,
    next_stop: tuple[float, float] | None,
    mode: str,
) -> BoardingGeometry:
    """Bearing and side of a boarding stop; ``stop``/``next_stop`` are (lon, lat)."""
    points = []
    for item in path or []:
        projected = _project(float(item[0]), float(item[1]), stop)
        if not points or projected != points[-1]:
            points.append(projected)
    if len(points) >= 2:
        # Skip MOTIS's connector from the stop's own coordinate to the shape.
        start = 1 if math.hypot(*points[0]) < 0.5 and len(points) >= 3 else 0
        _, index, _, x, y = _nearest_on_path(points, start)
        ahead = _ahead(points, index, x, y, BEARING_LOOKAHEAD_M)
        if ahead is not None:
            dx, dy = ahead[0] - x, ahead[1] - y
            bearing = _bearing(dx, dy)
            offset = math.hypot(x, y)
            reason = None
            side = None
            if mode not in STREET_MODES:
                reason = "not_a_street_mode"
            elif start == 0:
                reason = "path_has_no_shape_at_stop"
            elif offset < SIDE_MIN_OFFSET_M:
                reason = "stop_on_path"
            elif offset > SIDE_MAX_OFFSET_M:
                reason = "path_far_from_stop"
            else:
                # Cross product of travel direction and (stop - path point); stop is at 0,0.
                cross = dx * (0 - y) - dy * (0 - x)
                side = "left" if cross > 0 else "right"
            if reason in (None, "stop_on_path"):
                lon, lat = _unproject(x, y, stop)
                offset_m, path_point = round(offset, 1), (round(lon, 7), round(lat, 7))
            else:
                # The path does not describe the street at the stop: nothing to measure.
                offset_m, path_point = None, None
            return BoardingGeometry(bearing, "leg_geometry", side, offset_m, path_point, reason)
    if next_stop is not None:
        dx, dy = _project(next_stop[0], next_stop[1], stop)
        if math.hypot(dx, dy) > 0:
            return BoardingGeometry(
                _bearing(dx, dy), "stop_sequence", None, None, None, "no_leg_geometry"
            )
    return BoardingGeometry(None, None, None, None, None, "no_leg_geometry")
