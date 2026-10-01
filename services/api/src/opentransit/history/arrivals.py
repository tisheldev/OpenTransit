"""Infer observed stop times for one ride from archived SIRI distance-along-route pings.

Method (linear referencing): SIRI reports cumulative metres from the journey start; GTFS gives
each call's `shape_dist_traveled`. A call's observed time is when the vehicle's distance first
reaches the call's distance, interpolated linearly between the bracketing pings. The origin uses
the moment the vehicle has moved `ORIGIN_EPSILON_M` past the first stop, so parked
pre-departure pings (SIRI reports a vehicle against its next ride while it waits) never count
as a departure. When a bracket starts from rest (the vehicle was standing at its earlier ping),
movement is assumed to begin as late as `CRUISE_MPS` allows rather than spread evenly over the
gap, which would bias departures early. With about one ping a minute, an inferred time is good
to roughly ±30 s; every inferred time carries its bracket gap so consumers can filter coarse
estimates.
"""

from __future__ import annotations

from dataclasses import dataclass

from opentransit.history.schedule import Call

BACKWARD_TOLERANCE_M = 30  # GPS/odometer jitter tolerated before a ping counts as going backwards
MAX_SPEED_MPS = 35  # ~126 km/h; faster jumps are treated as bad pings
MAX_BRACKET_S = 240  # no estimate across a longer gap in observations
ORIGIN_EPSILON_M = 50
STATIONARY_M = 5  # consecutive pings this close count as standing still
CRUISE_MPS = 6.0  # assumed speed when a bracket starts from rest (~22 km/h urban average)


@dataclass(frozen=True, slots=True)
class TrackPoint:
    at: int
    distance: float


@dataclass(frozen=True, slots=True)
class ObservedCall:
    sequence: int
    stop_id: str
    scheduled: int  # scheduled arrival (departure at the origin)
    observed: int | None
    bracket_s: int | None
    reason: str | None  # why `observed` is None


@dataclass(frozen=True, slots=True)
class TrackStats:
    pings: int  # unique by RecordedAtTime
    backwards: int
    speed_outliers: int


def clean_track(points: dict[int, tuple[int, int]]) -> tuple[list[TrackPoint], TrackStats]:
    """Sort deduplicated pings and keep a non-decreasing, plausible distance path."""
    track: list[TrackPoint] = []
    backwards = outliers = 0
    for at in sorted(points):
        metres = points[at][0]
        if track:
            last = track[-1]
            if metres < last.distance - BACKWARD_TOLERANCE_M:
                backwards += 1
                continue
            if metres - last.distance > MAX_SPEED_MPS * max(at - last.at, 1):
                outliers += 1
                continue
            distance = max(float(metres), last.distance)  # absorb tolerated jitter
        else:
            distance = float(metres)
        track.append(TrackPoint(at, distance))
    return track, TrackStats(len(points), backwards, outliers)


def crossing(track: list[TrackPoint], target: float) -> tuple[int | None, int | None, str | None]:
    """First time the track reaches `target` metres: (time, bracket seconds, failure reason)."""
    if not track:
        return None, None, "noTrack"
    if track[0].distance >= target:
        return None, None, "beforeFirstPing"
    for index, (before, after) in enumerate(zip(track, track[1:], strict=False)):
        if after.distance >= target:
            gap = after.at - before.at
            if gap > MAX_BRACKET_S:
                return None, gap, "gapTooLong"
            start = before.at
            at_rest = index == 0 or before.distance - track[index - 1].distance <= STATIONARY_M
            if at_rest:
                start = max(start, after.at - (after.distance - before.distance) / CRUISE_MPS)
            share = (target - before.distance) / (after.distance - before.distance)
            return round(start + share * (after.at - start)), gap, None
    return None, None, "afterLastPing"


def observe_calls(track: list[TrackPoint], calls: list[Call]) -> list[ObservedCall]:
    observed = []
    for index, call in enumerate(calls):
        if call.distance_m is None:
            observed.append(
                ObservedCall(call.sequence, call.stop_id, call.arrival, None, None, "noDistance")
            )
            continue
        if index == 0:
            at, gap, reason = crossing(track, call.distance_m + ORIGIN_EPSILON_M)
            scheduled = call.departure
        else:
            at, gap, reason = crossing(track, call.distance_m)
            scheduled = call.arrival
        observed.append(ObservedCall(call.sequence, call.stop_id, scheduled, at, gap, reason))
    return observed
