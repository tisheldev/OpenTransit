"""A journey pinned to one trip ("Ride it", stops and lines overhaul A3).

The passenger picks a departure on a line and the stop where they get off. The answer is
one journey in the ordinary Journey shape, so the client reads and navigates it like any
other:

- the walk from the origin to the board stop is the engine's own street routing: a plan
  with no transit modes (``MotisClient.direct_walks``), timed to arrive at the trip's
  departure there. It is omitted when the origin is a coordinate within 30 m of the stop;
- the ride is built from the dated trip as ``GET /v1/trips/{tripRef}`` serves it (the
  engine's trip, reconciled with the reference timetable), cut to the board and alight
  stops: intermediate stops, boarding direction and side, and the trip's shape cut where
  the engine cuts it for a planned leg (the shape vertex nearest each stop, the stop's own
  coordinate added at each end).
"""

from __future__ import annotations

import math
from datetime import datetime

from opentransit.api.schemas import Geometry, Journey, Leg, Location, Stopover, Timing, Transit
from opentransit.core.generation import instant
from opentransit.core.time import checked_duration_seconds, is_before, to_local_display
from opentransit.motis import (
    EngineFailure,
    PlanResult,
    _has_cancelled_walk,
    _journey_fingerprint,
    _with_platforms,
    assemble_journey,
    boarding,
    normalize,
)
from opentransit.motis_timetable import TimetableFailure, trip_detail

PINNED_RANKING_POLICY = "pinned-trip-v1"
# A coordinate origin this close to the board stop needs no walk leg.
OMIT_WALK_WITHIN_M = 30.0
MISSED_BY_WALK = "PINNED_TRIP_MISSED_BY_WALK"
WALK_UNAVAILABLE = "PINNED_TRIP_WALK_UNAVAILABLE"
# Of the shape vertices nearest a stop, the first one within this much of the nearest is
# taken, so a route that passes a stop twice is cut at the pass the trip is on.
_VERTEX_TIE_M = 1.0
_M_PER_DEG_LAT = 110_574.0
_M_PER_DEG_LON_EQUATOR = 111_320.0


class InvalidPinnedTrip(ValueError):
    """The board or alight stop is not on the trip, or the alight is not after the board."""


def _metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Planar distance between two (lon, lat) points; exact enough at stop scale."""
    scale = _M_PER_DEG_LON_EQUATOR * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * scale, (a[1] - b[1]) * _M_PER_DEG_LAT)


def leg_path(
    shape: list[list[float]] | None,
    positions: list[tuple[float, float] | None],
    board: int,
    alight: int,
) -> list[list[float]] | None:
    """The trip's path from call ``board`` to call ``alight``, as the engine draws a leg.

    ``positions`` are the trip's calls as (lon, lat), in order. Each call from the first to
    the alight one is matched to a shape vertex at or after the previous call's, so the cut
    follows the trip's own order. None without a shape or a call position.
    """
    if not shape or len(shape) < 2 or not 0 <= board < alight < len(positions):
        return None
    vertex = 0
    marks = []
    for position in positions[: alight + 1]:
        if position is None:
            return None
        distances = [_metres(position, (point[0], point[1])) for point in shape[vertex:]]
        nearest = min(distances)
        vertex += next(i for i, d in enumerate(distances) if d <= nearest + _VERTEX_TIE_M)
        marks.append(vertex)
    start, end = positions[board], positions[alight]
    path = [[start[0], start[1]]]
    for point in [*shape[marks[board] : marks[alight] + 1], [end[0], end[1]]]:
        if [point[0], point[1]] != path[-1]:
            path.append([point[0], point[1]])
    return path if len(path) >= 2 else None


def _boardable(value: object) -> bool:
    return value in (0, 2, 3)


def _members(reference, stop_id: str) -> set[str]:
    """A stop and, for a station, its platforms."""
    members = {stop_id}
    stop = reference.stop_ref(stop_id) if reference is not None else None
    for child in (stop or {}).get("children") or ():
        if child.get("stop_id"):
            members.add(child["stop_id"])
    return members


def ride_span(calls: list[dict], reference, board_stop: str, alight_stop: str) -> tuple[int, int]:
    """The first boarding at ``board_stop`` with a later alighting at ``alight_stop``."""
    boards, alights = _members(reference, board_stop), _members(reference, alight_stop)
    for start, call in enumerate(calls):
        if call["stopId"] not in boards or not _boardable(call["pickupType"]):
            continue
        for end in range(start + 1, len(calls)):
            later = calls[end]
            if later["stopId"] in alights and _boardable(later["dropOffType"]):
                return start, end
    raise InvalidPinnedTrip("The trip does not ride from the board stop to the alight stop")


def _clock(value: str | None) -> datetime:
    if value is None:
        raise ValueError("Missing scheduled time")
    return to_local_display(instant(value))


def _place(trip: dict, index: int) -> Location:
    call = trip["calls"][index]
    if call["latitude"] is None or call["longitude"] is None:
        raise ValueError("Trip call without a position")
    codes = trip.get("_engineStopCodes") or []
    return Location(
        name=call["name"] or "",
        latitude=call["latitude"],
        longitude=call["longitude"],
        stopId=call["stopId"],
        stopCode=codes[index] if index < len(codes) else None,
    )


def _stopovers(calls: list[dict]) -> list[Stopover] | None:
    """Calls between boarding and alighting; a stop skipped by schedule is not one."""
    result = []
    for call in calls:
        if call["pickupType"] == 1 and call["dropOffType"] == 1:
            continue
        if call["latitude"] is None or call["longitude"] is None:
            return None
        result.append(
            Stopover(
                name=call["name"] or "",
                stopId=call["stopId"],
                latitude=call["latitude"],
                longitude=call["longitude"],
                scheduledArrival=_optional(call["scheduledArrival"]),
                scheduledDeparture=_optional(call["scheduledDeparture"]),
            )
        )
    return result


def _optional(value: str | None) -> datetime | None:
    return None if value is None else _clock(value)


def transit_leg(trip: dict, board: int, alight: int) -> Leg:
    """The ride from call ``board`` to call ``alight``, shaped like an engine transit leg."""
    mode = trip["mode"]
    if not mode:
        raise ValueError("Trip without a mode")
    calls = trip["calls"]
    start, end = _place(trip, board), _place(trip, alight)
    times = Timing(
        scheduledDeparture=_clock(calls[board]["scheduledDeparture"]),
        scheduledArrival=_clock(calls[alight]["scheduledArrival"]),
    )
    shape = (trip.get("shape") or {}).get("coordinates")
    positions = [
        None
        if call["latitude"] is None or call["longitude"] is None
        else (call["longitude"], call["latitude"])
        for call in calls
    ]
    path = leg_path(shape, positions, board, alight)
    path_geometry = Geometry(coordinates=path) if path else None
    middle = _stopovers(calls[board + 1 : alight])
    ride = Transit(
        operatorId=trip["operatorId"],
        operatorName=trip["operatorName"],
        routeId=trip["routeId"],
        routeShortName=trip["routeShortName"] or "",
        headsign=trip["headsign"],
        engineTripId=trip["tripRef"],
        sourceTripId=trip["sourceTripId"],
        serviceDate=trip["serviceDate"],
        startTime=trip["startTime"],
    )
    return Leg(
        kind="transit",
        mode=mode,
        origin=start,
        destination=end,
        timing=times,
        durationSeconds=int(
            checked_duration_seconds(times.scheduledDeparture, times.scheduledArrival)
        ),
        distanceMeters=None,
        geometry=path_geometry,
        geometryUnavailableReason=None if path_geometry else "not_provided_by_engine",
        transit=ride,
        intermediateStops=middle,
        boarding=boarding(mode, start, end, path_geometry, middle, ride.headsign),
    )


def _retimed(raw: dict, arrival: datetime) -> dict:
    """The engine's walk moved to end exactly at ``arrival`` (its durations kept)."""
    legs = raw["legs"]
    shift = arrival - instant(legs[-1]["scheduledEndTime"])
    moved = []
    for leg in legs:
        moved.append(
            {
                **leg,
                "scheduledStartTime": (instant(leg["scheduledStartTime"]) + shift).isoformat(),
                "scheduledEndTime": (instant(leg["scheduledEndTime"]) + shift).isoformat(),
            }
        )
    return {**raw, "legs": moved}


async def _walk(snapshot, query, origin: str, board: Location, departure: datetime) -> list[Leg]:
    """The engine's walk to the board stop arriving at ``departure``; [] when it has none."""
    candidates = await snapshot.motis.direct_walks(
        origin,
        "mot60day_" + board.stopId.removeprefix("mot:stop:"),
        departure,
        max_seconds=query.max_direct_walk_minutes * 60,
        language=query.lang,
    )
    for raw in candidates:
        if _has_cancelled_walk(raw):
            continue
        try:
            walk = normalize(
                _retimed(raw, departure),
                snapshot.generation,
                departure,
                arrive_by=True,
                allowed_modes=set(),
            )
        except ValueError, KeyError, TypeError, IndexError, OverflowError:
            continue
        if all(leg.kind == "walk" for leg in walk.legs):
            return list(walk.legs)
    return []


def _origin(query, reference) -> tuple[str, tuple[float, float] | None, str | None]:
    """The engine place of the origin, its (lon, lat) when a coordinate, and its stop ID."""
    origin = query.origin
    if getattr(origin, "kind", None) == "coordinate":
        return f"{origin.latitude},{origin.longitude}", (origin.longitude, origin.latitude), None
    stop = reference.stop_ref(origin.stopId)
    if stop is None:
        raise EngineFailure("NOT_FOUND", 404)
    source_id = stop["source_id"]
    place = source_id if source_id.startswith("mot60day_") else f"mot60day_{source_id}"
    return place, None, origin.stopId


async def pinned_journey(snapshot, query) -> PlanResult:
    """One journey: the walk to the board stop, then the pinned trip to the alight stop.

    Raises ``TimetableFailure`` (``TRIP_NOT_FOUND`` 404 for an unknown or inactive trip),
    ``InvalidPinnedTrip`` and ``EngineFailure``.
    """
    pin = query.pinned_trip
    reference = snapshot.reference
    try:
        trip = await trip_detail(snapshot, pin.tripRef)
    except TimetableFailure as exc:
        if exc.code == "NOT_FOUND":
            raise TimetableFailure("TRIP_NOT_FOUND", 404) from None
        raise
    if trip is None:
        raise TimetableFailure("TRIP_NOT_FOUND", 404)
    board, alight = ride_span(trip["calls"], reference, pin.boardStopId, pin.alightStopId)
    try:
        ride = transit_leg(trip, board, alight)
    except ValueError, KeyError, TypeError, IndexError, OverflowError:
        raise EngineFailure("ENGINE_INVALID_RESPONSE") from None
    constraints: dict[str, object] = {
        "timeMode": "arriveBy" if query.is_arrive_by else "departAt",
        "pinnedTrip": pin.model_dump(),
        "maxDirectWalkMinutes": query.max_direct_walk_minutes,
        "engineWalkCapConformance": "unverified",
        "transferWalkLimit": "not_enforced",
    }
    warnings: list[str] = []
    place, point, origin_stop = _origin(query, reference)
    start = ride.origin
    departure = ride.timing.scheduledDeparture
    near = point is not None and _metres(point, (start.longitude, start.latitude)) <= (
        OMIT_WALK_WITHIN_M
    )
    if near or (origin_stop is not None and origin_stop in _members(reference, start.stopId)):
        walk = []
    else:
        walk = await _walk(snapshot, query, place, start, departure)
        if not walk:
            return PlanResult([], [WALK_UNAVAILABLE], PINNED_RANKING_POLICY, constraints)
    leave = walk[0].timing.scheduledDeparture if walk else departure
    if query.depart_at is not None and is_before(leave, query.depart_at):
        warnings.append(MISSED_BY_WALK)
    try:
        journey: Journey = assemble_journey([*walk, ride], 0)
    except ValueError:
        raise EngineFailure("ENGINE_INVALID_RESPONSE") from None
    journey = _with_platforms(journey, reference)
    journey = journey.model_copy(update={"id": _journey_fingerprint(journey)})
    return PlanResult([journey], warnings, PINNED_RANKING_POLICY, constraints)
