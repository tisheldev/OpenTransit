"""Scoring for POC-5.

A case PASSES when the geocoder's **top-1** result is within `expect.tol_m` of the
corpus coordinate. Top-1 is the strict reading and is what the headline uses.

`hit_rank` records the 1-based rank of the first candidate inside tolerance within the
top 5. A real planner shows a dropdown, so top-5 is the softer, also-useful number —
it is reported separately and never substituted for the top-1 figure.
"""

from __future__ import annotations

import math

EARTH_M = 6371008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_M * math.asin(math.sqrt(a))


def hit_rank(hits, lat: float, lon: float, tol_m: float, depth: int = 5) -> int | None:
    for h in hits[:depth]:
        if haversine_m(h.lat, h.lon, lat, lon) <= tol_m:
            return h.rank
    return None


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile. No numpy dependency for four numbers."""
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, math.ceil(p / 100.0 * len(s)) - 1))
    return s[k]
