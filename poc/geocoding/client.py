"""Thin client for the MOTIS built-in geocoder.

MOTIS v2.11.2 exposes `GET /api/v1/geocode`. Observed parameters:

    text        the query string (required)
    language    accepted; had **no observed effect** on this build (see POC-5 notes)
    place       "lat,lon" bias point
    placeBias   multiplier on the distance term; MOTIS default is 1.0

Use 127.0.0.1, never `localhost`: inside the MOTIS image `localhost` resolves to
`::1` and MOTIS binds IPv4 only. Agent B already lost time to this.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

BASE = "http://127.0.0.1:58080"
GEOCODE = BASE + "/api/v1/geocode"


@dataclass
class Hit:
    """One geocoder candidate, normalised down to what scoring needs."""

    rank: int
    type: str
    name: str
    id: str
    lat: float
    lon: float
    score: float | None = None
    modes: list[str] = field(default_factory=list)
    areas: list[str] = field(default_factory=list)
    category: str | None = None

    @property
    def source(self) -> str:
        """Where the candidate came from: the GTFS feed, or OSM."""
        if self.id.startswith("mot60day_"):
            return "gtfs"
        if self.id.startswith(("way/", "node/", "relation/")):
            return "osm"
        return "other"

    def to_json(self) -> dict:
        return {
            "rank": self.rank,
            "type": self.type,
            "source": self.source,
            "name": self.name,
            "id": self.id,
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "modes": self.modes,
            "city": self.city,
        }

    @property
    def city(self) -> str | None:
        """The adminLevel-8 area name, i.e. the municipality, when MOTIS gives one."""
        return self.areas[0] if self.areas else None


@dataclass
class Response:
    hits: list[Hit]
    latency_ms: float
    url: str
    error: str | None = None


def _areas(raw: dict) -> list[str]:
    out = []
    for a in raw.get("areas") or []:
        if a.get("adminLevel") in (8, 8.0):
            out.append(a.get("name", ""))
    return out


def geocode(
    text: str,
    *,
    place: tuple[float, float] | None = None,
    place_bias: float | None = None,
    language: str | None = None,
    limit: int = 10,
    timeout: float = 30.0,
) -> Response:
    params: dict[str, str] = {"text": text}
    if place is not None:
        params["place"] = f"{place[0]},{place[1]}"
    if place_bias is not None:
        params["placeBias"] = str(place_bias)
    if language:
        params["language"] = language

    url = GEOCODE + "?" + urllib.parse.urlencode(params)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return Response([], (time.perf_counter() - t0) * 1000.0, url, error=repr(e))
    latency = (time.perf_counter() - t0) * 1000.0

    hits = []
    for i, h in enumerate(raw[:limit], start=1):
        hits.append(
            Hit(
                rank=i,
                type=h.get("type", "?"),
                name=h.get("name", ""),
                id=str(h.get("id", "")),
                lat=float(h["lat"]),
                lon=float(h["lon"]),
                score=h.get("score"),
                modes=list(h.get("modes") or []),
                areas=_areas(h),
                category=h.get("category"),
            )
        )
    return Response(hits, latency, url)


def healthy(timeout: float = 10.0) -> bool:
    """One cheap probe so a total outage is reported as such rather than as 100 failures."""
    r = geocode("Tel Aviv", limit=1, timeout=timeout)
    return r.error is None and bool(r.hits)
