"""Review slow OB-01 segments from raw pings: standstill, slow movement or frozen distance?

A segment run time is inferred from SIRI cumulative distance. When that distance stops
advancing, either the bus is standing (traffic, a checkpoint, a layover) or the distance feed
froze while the bus kept moving (an artefact). GPS position separates the two: the net
displacement over each frozen stretch is near zero for a standstill and large for an artefact.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

FROZEN_M = 10  # distance change per ping treated as "not advancing"
ARTEFACT_GPS_M = 300  # net GPS movement while frozen that marks a frozen-distance artefact
STATIONARY_SHARE = 0.5


@dataclass(frozen=True, slots=True)
class TracePing:
    at: int
    metres: int
    lat: float
    lon: float
    velocity: int


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlon = phi2 - phi1, math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlon / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def _cross(pings: list[TracePing], target: float) -> float | None:
    for before, after in zip(pings, pings[1:], strict=False):
        if before.metres < target <= after.metres:
            share = (target - before.metres) / (after.metres - before.metres)
            return before.at + share * (after.at - before.at)
    return None


def segment_trace(pings: list[TracePing], start_m: float, end_m: float) -> dict | None:
    """Run time and frozen-distance stretches between `start_m` and `end_m` on one ride."""
    ordered = sorted({ping.at: ping for ping in pings}.values(), key=lambda ping: ping.at)
    entered, left = _cross(ordered, start_m), _cross(ordered, end_m)
    if entered is None or left is None:
        return None
    window = [ping for ping in ordered if entered - 300 <= ping.at <= left + 300]
    inside = [p for p in window if start_m - FROZEN_M <= p.metres <= end_m]
    frozen_s = 0
    gps_net = 0.0
    longest = (0, None, 0.0)  # seconds, (lat, lon), net displacement
    run: list[TracePing] = []

    def close(stretch: list[TracePing]) -> None:
        nonlocal frozen_s, gps_net, longest
        if len(stretch) < 2:
            return
        seconds = stretch[-1].at - stretch[0].at
        net = haversine_m(stretch[0].lat, stretch[0].lon, stretch[-1].lat, stretch[-1].lon)
        frozen_s += seconds
        gps_net += net
        if seconds > longest[0]:
            middle = stretch[len(stretch) // 2]
            longest = (seconds, (round(middle.lat, 5), round(middle.lon, 5)), net)

    for ping in inside:
        if run and abs(ping.metres - run[0].metres) <= FROZEN_M:
            run.append(ping)
            continue
        close(run)
        run = [ping]
    close(run)
    return {
        "runSeconds": round(left - entered),
        "frozenSeconds": frozen_s,
        "gpsNetMetresWhileFrozen": round(gps_net, 1),
        "longestFrozenSeconds": longest[0],
        "longestFrozenAt": longest[1],
        "longestFrozenGpsNetMetres": round(longest[2], 1),
    }


def classify(trace: dict) -> str:
    if trace["gpsNetMetresWhileFrozen"] >= ARTEFACT_GPS_M:
        return "distanceFrozenWhileMoving"
    if trace["runSeconds"] and trace["frozenSeconds"] >= STATIONARY_SHARE * trace["runSeconds"]:
        return "stationary"
    return "movingSlowly"
