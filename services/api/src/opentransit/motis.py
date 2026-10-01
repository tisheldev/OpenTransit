"""Pinned MOTIS v2.11.2 /api/v6 adapter; full engine identities are preserved."""

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime

import httpx

from opentransit.api.schemas import (
    Coordinate,
    Geometry,
    Journey,
    Leg,
    Location,
    StopLocation,
    Timing,
    Transit,
)
from opentransit.core.generation import Generation, instant
from opentransit.core.time import (
    checked_duration_seconds,
    is_before,
    to_local_display,
)

MODE_MAP = {
    "BUS": "bus",
    "COACH": "bus",
    "RAIL": "rail",
    "SUBURBAN": "rail",
    "HIGHSPEED_RAIL": "rail",
    "LONG_DISTANCE": "rail",
    "NIGHT_RAIL": "rail",
    "REGIONAL_RAIL": "rail",
    "REGIONAL_FAST_RAIL": "rail",
    "TRAM": "light_rail",
    "SUBWAY": "light_rail",
    "CABLE_CAR": "cable_car",
    "FUNICULAR": "funicular",
    "FERRY": "ferry",
    "WALK": "walk",
}
RANKING_POLICY = "motis-v2.11.2-feasible-engine-order-v1"
TRANSIT_MODE_MAP = {
    "bus": ("BUS", "COACH"),
    "rail": ("HIGHSPEED_RAIL", "LONG_DISTANCE", "NIGHT_RAIL", "REGIONAL_RAIL", "SUBURBAN"),
    "light_rail": ("TRAM", "SUBWAY"),
}


@dataclass(frozen=True)
class PlanResult:
    """Scheduled alternatives and the adapter's explicit policy disclosures."""

    journeys: list[Journey]
    warnings: list[str]
    ranking_policy: str
    applied_constraints: dict[str, object]


class EngineFailure(Exception):
    """A safe dependency failure, without raw engine or request data."""

    def __init__(self, code: str = "ENGINE_UNAVAILABLE", status: int = 503):
        self.code = code
        self.status = status
        super().__init__(code)


class UnexpectedLiveDataError(ValueError):
    """The scheduled-only adapter received explicitly live-annotated data."""


def geometry(value: dict | None) -> Geometry | None:
    if value is not None and not isinstance(value, dict):
        raise ValueError("Invalid geometry object")
    if not value or not value.get("points"):
        return None
    precision = value.get("precision", 6)
    if not isinstance(precision, int) or not 0 <= precision <= 7:
        raise ValueError("Invalid geometry precision")
    encoded = value["points"]
    if not isinstance(encoded, str) or len(encoded) > 1_000_000:
        raise ValueError("Invalid geometry length")
    coordinates, accumulators, index = [], [0, 0], 0
    while index < len(encoded):
        for axis in range(2):
            result, shift = 0, 0
            while True:
                if index >= len(encoded) or shift > 30:
                    raise ValueError("Truncated geometry")
                part = ord(encoded[index]) - 63
                index += 1
                if not 0 <= part <= 63:
                    raise ValueError("Invalid geometry character")
                result |= (part & 31) << shift
                shift += 5
                if part < 32:
                    break
            accumulators[axis] += ~(result >> 1) if result & 1 else result >> 1
        lat, lon = [x / 10**precision for x in accumulators]
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("Invalid geometry coordinate")
        coordinates.append([lon, lat])
    if len(coordinates) < 2:
        raise ValueError("LineString needs at least two positions")
    return Geometry(coordinates=coordinates)


def location(value: dict) -> Location:
    lat, lon = float(value["lat"]), float(value["lon"])
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90:
        raise ValueError("Invalid location")
    if not -180 <= lon <= 180:
        raise ValueError("Invalid location")
    stop_id = value.get("stopId")
    if stop_id:
        stop_id = _public_reference("stop", stop_id)
    return Location(
        name=value["name"],
        latitude=lat,
        longitude=lon,
        stopId=stop_id,
        stopCode=value.get("stopCode"),
    )


def timing(value: dict) -> Timing:
    start = instant(value["scheduledStartTime"])
    end = instant(value["scheduledEndTime"])
    try:
        checked_duration_seconds(start, end)
    except ValueError as exc:
        raise ValueError("Reversed scheduled times") from exc
    return Timing(
        scheduledDeparture=to_local_display(start),
        scheduledArrival=to_local_display(end),
    )


def _public_reference(kind: str, engine_id: str) -> str:
    prefix = f"mot:{kind}:"
    if engine_id.startswith(prefix):
        return engine_id
    source_id = engine_id.removeprefix("mot60day_")
    return f"{prefix}{source_id}"


def transit(value: dict) -> Transit:
    engine_id = value["tripId"]
    match = re.fullmatch(r"(\d{8})_(\d{2}:\d{2}(?::\d{2})?)_mot60day_(.+)", engine_id)
    if not match:
        raise ValueError("Unrecognized dated trip identity")
    return Transit(
        operatorId=value["agencyId"],
        operatorName=value["agencyName"],
        routeId=_public_reference("route", value["routeId"]),
        routeShortName=value.get("routeShortName", ""),
        headsign=value.get("headsign"),
        engineTripId=engine_id,
        sourceTripId=match[3],
        serviceDate=datetime.strptime(match[1], "%Y%m%d").date(),
        startTime=match[2],
    )


def normalize(
    raw: dict,
    generation: Generation,
    depart_at: datetime,
    *,
    arrive_by: bool = False,
    allowed_modes: set[str] | None = None,
) -> Journey:
    if not isinstance(raw, dict) or not isinstance(raw.get("legs"), list):
        raise ValueError("Invalid itinerary object")
    legs = []
    for item in raw["legs"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid leg object")
        if item.get("realTime"):
            raise UnexpectedLiveDataError("Unexpected live data in scheduled engine")
        if item.get("cancelled"):
            raise ValueError("Unexpected live data in scheduled engine")
        mode = MODE_MAP[item["mode"]]
        if mode != "walk" and allowed_modes is not None and mode not in allowed_modes:
            raise ValueError("Engine alternative contains an unrequested transit mode")
        times = timing(item)
        if not generation.contains(times.scheduledDeparture):
            raise ValueError("Leg departure outside coverage")
        if not generation.contains(times.scheduledArrival):
            raise ValueError("Leg arrival outside coverage")
        if not arrive_by and is_before(times.scheduledDeparture, depart_at):
            raise ValueError("Leg before requested departure")
        if arrive_by and is_before(depart_at, times.scheduledArrival):
            raise ValueError("Leg after requested arrival")
        start, end = location(item["from"]), location(item["to"])
        if legs:
            previous = legs[-1]
            if is_before(times.scheduledDeparture, previous.timing.scheduledArrival):
                raise ValueError("Overlapping legs")
            if (
                abs(previous.destination.latitude - start.latitude) > 0.0001
                or abs(previous.destination.longitude - start.longitude) > 0.0001
            ):
                raise ValueError("Disconnected legs")
        distance = item.get("distance")
        if distance is not None and (not math.isfinite(distance) or distance < 0):
            raise ValueError("Invalid leg distance")
        if mode == "walk" and distance is None:
            raise ValueError("Missing walking distance")
        shape = geometry(item.get("legGeometry"))
        legs.append(
            Leg(
                kind="walk" if mode == "walk" else "transit",
                mode=mode,
                origin=start,
                destination=end,
                timing=times,
                durationSeconds=int(
                    checked_duration_seconds(times.scheduledDeparture, times.scheduledArrival)
                ),
                distanceMeters=distance,
                geometry=shape,
                geometryUnavailableReason=None if shape else "not_provided_by_engine",
                transit=None if mode == "walk" else transit(item),
            )
        )
    if not legs:
        raise ValueError("Empty itinerary")
    transfers = raw.get("transfers", 0) if all(x.mode == "walk" for x in legs) else raw["transfers"]
    if type(transfers) is not int or transfers < 0:
        raise ValueError("Invalid transfer count")
    times = Timing(
        scheduledDeparture=legs[0].timing.scheduledDeparture,
        scheduledArrival=legs[-1].timing.scheduledArrival,
    )
    return Journey(
        id="journey-pending",
        timing=times,
        durationSeconds=int(
            checked_duration_seconds(times.scheduledDeparture, times.scheduledArrival)
        ),
        walkingSeconds=sum(x.durationSeconds for x in legs if x.kind == "walk"),
        walkingDistanceMeters=sum(x.distanceMeters for x in legs if x.kind == "walk"),
        transfers=transfers,
        legs=legs,
    )


def _journey_fingerprint(journey: Journey) -> str:
    identity = [
        {
            "mode": leg.mode,
            "departure": instant(leg.timing.scheduledDeparture.isoformat()).isoformat(),
            "arrival": instant(leg.timing.scheduledArrival.isoformat()).isoformat(),
            "from": leg.origin.stopId or [leg.origin.latitude, leg.origin.longitude],
            "to": leg.destination.stopId or [leg.destination.latitude, leg.destination.longitude],
            "trip": leg.transit.engineTripId if leg.transit else None,
            "route": leg.transit.routeId if leg.transit else None,
        }
        for leg in journey.legs
    ]
    stable = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "journey-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20]


def _engine_place(value: Coordinate | StopLocation, reference) -> str:
    if isinstance(value, Coordinate):
        return f"{value.latitude},{value.longitude}"
    if reference is None:
        raise EngineFailure("DATA_UNAVAILABLE", 503)
    stop = reference.stop(value.stopId)
    if stop is None:
        raise EngineFailure("NOT_FOUND", 404)
    source_id = stop.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        raise EngineFailure("DATA_UNAVAILABLE", 503)
    return source_id if source_id.startswith("mot60day_") else f"mot60day_{source_id}"


def _has_cancelled_walk(raw: object) -> bool:
    if not isinstance(raw, dict) or not isinstance(raw.get("legs"), list):
        return False
    return any(
        isinstance(leg, dict) and leg.get("mode") == "WALK" and leg.get("cancelled")
        for leg in raw["legs"]
    )


class MotisClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def ready(self, now: datetime) -> bool:
        """Engine health only; candidate/generation correctness needs separate probes."""
        try:
            response = await self.client.get(
                "/api/v6/plan",
                params={
                    "fromPlace": "32.0836,34.7981",
                    "toPlace": "32.0838,34.8044",
                    "time": now.isoformat(),
                    "numItineraries": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            return isinstance(data["itineraries"], list) and isinstance(data["direct"], list)
        except httpx.HTTPError, ValueError, KeyError, TypeError:
            return False

    async def plan(self, query, generation: Generation, reference=None) -> PlanResult:
        try:
            origin = _engine_place(query.origin, reference)
            destination = _engine_place(query.destination, reference)
        except EngineFailure:
            raise
        except OSError, sqlite3.Error:
            raise EngineFailure("DATA_UNAVAILABLE", 503) from None
        transit_modes = list(
            dict.fromkeys(mode for selected in query.modes for mode in TRANSIT_MODE_MAP[selected])
        )
        params = {
            "fromPlace": origin,
            "toPlace": destination,
            "time": query.time_anchor.isoformat(),
            "arriveBy": str(query.is_arrive_by).lower(),
            "numItineraries": str(query.results),
            "maxItineraries": "5",
            "timetableView": "true",
            "realtimeMode": "OFF",
            "transitModes": ",".join(transit_modes),
            "directModes": "WALK",
            "maxPreTransitTime": str(query.max_access_walk_minutes * 60),
            "maxPostTransitTime": str(query.max_egress_walk_minutes * 60),
            "maxDirectTime": str(query.max_direct_walk_minutes * 60),
            "detailedLegs": "true",
            "joinInterlinedLegs": "false",
            "withScheduledSkippedStops": "true",
            "detailedTransfers": "true",
            "preTransitModes": "WALK",
            "postTransitModes": "WALK",
            "language": query.lang,
        }
        constraints: dict[str, object] = {
            "timeMode": "arriveBy" if query.is_arrive_by else "departAt",
            "modes": list(query.modes),
            "maxAccessWalkMinutes": query.max_access_walk_minutes,
            "maxEgressWalkMinutes": query.max_egress_walk_minutes,
            "maxDirectWalkMinutes": query.max_direct_walk_minutes,
            "engineWalkCapConformance": "unverified",
            "transferWalkLimit": "not_enforced",
        }
        warnings: list[str] = []
        try:
            response = await self.client.get("/api/v6/plan", params=params)
            response.raise_for_status()
            body = response.json()
            candidates = body["itineraries"]
            direct = body["direct"]
            if not isinstance(candidates, list) or not isinstance(direct, list):
                raise ValueError("Invalid itinerary list")
            raw_alternatives = candidates + direct
            if not raw_alternatives:
                return PlanResult([], warnings, RANKING_POLICY, constraints)

            journeys: list[Journey] = []
            seen: set[str] = set()
            for alternative in raw_alternatives:
                if _has_cancelled_walk(alternative):
                    if "INFEASIBLE_STREET_ALTERNATIVES_OMITTED" not in warnings:
                        warnings.append("INFEASIBLE_STREET_ALTERNATIVES_OMITTED")
                    continue
                try:
                    journey = normalize(
                        alternative,
                        generation,
                        query.time_anchor,
                        arrive_by=query.is_arrive_by,
                        allowed_modes=set(query.modes),
                    )
                except UnexpectedLiveDataError:
                    raise EngineFailure("ENGINE_INVALID_RESPONSE") from None
                except ValueError, KeyError, TypeError, IndexError, OverflowError:
                    if "INVALID_ENGINE_ALTERNATIVE_OMITTED" not in warnings:
                        warnings.append("INVALID_ENGINE_ALTERNATIVE_OMITTED")
                    continue
                fingerprint = _journey_fingerprint(journey)
                if fingerprint in seen:
                    if "DUPLICATE_ALTERNATIVES_OMITTED" not in warnings:
                        warnings.append("DUPLICATE_ALTERNATIVES_OMITTED")
                    continue
                seen.add(fingerprint)
                journeys.append(journey.model_copy(update={"id": fingerprint}))
                if len(journeys) >= query.results:
                    break
            if raw_alternatives and not journeys:
                if warnings == ["INFEASIBLE_STREET_ALTERNATIVES_OMITTED"]:
                    # Every alternative lacked a street path: an empty search with the
                    # disclosure, not a malformed engine response.
                    return PlanResult([], warnings, RANKING_POLICY, constraints)
                raise EngineFailure("ENGINE_INVALID_RESPONSE")
            return PlanResult(journeys, warnings, RANKING_POLICY, constraints)
        except EngineFailure:
            raise
        except OSError, sqlite3.Error:
            raise EngineFailure("DATA_UNAVAILABLE", 503) from None
        except httpx.TimeoutException:
            raise EngineFailure("ENGINE_TIMEOUT", 504) from None
        except httpx.HTTPError:
            raise EngineFailure() from None
        except ValueError, KeyError, TypeError, IndexError, OverflowError:
            raise EngineFailure("ENGINE_INVALID_RESPONSE") from None
