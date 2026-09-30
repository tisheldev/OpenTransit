"""Pinned MOTIS v2.11.2 /api/v6 adapter; full engine identities are preserved."""

import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from opentransit.api.schemas import Geometry, Journey, Leg, Location, Timing, Transit
from opentransit.core.generation import Generation, instant

LOCAL = ZoneInfo("Asia/Jerusalem")
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


class EngineFailure(Exception):
    """A safe dependency failure, without raw engine or request data."""

    def __init__(self, code: str = "ENGINE_UNAVAILABLE", status: int = 503):
        self.code = code
        self.status = status
        super().__init__(code)


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
    return Location(
        name=value["name"],
        latitude=lat,
        longitude=lon,
        stopId=value.get("stopId"),
        stopCode=value.get("stopCode"),
    )


def timing(value: dict) -> Timing:
    start = instant(value["scheduledStartTime"]).astimezone(LOCAL)
    end = instant(value["scheduledEndTime"]).astimezone(LOCAL)
    if end < start:
        raise ValueError("Reversed scheduled times")
    return Timing(scheduledDeparture=start, scheduledArrival=end)


def transit(value: dict) -> Transit:
    engine_id = value["tripId"]
    match = re.fullmatch(r"(\d{8})_(\d{2}:\d{2}(?::\d{2})?)_mot60day_(.+)", engine_id)
    if not match:
        raise ValueError("Unrecognized dated trip identity")
    return Transit(
        operatorId=value["agencyId"],
        operatorName=value["agencyName"],
        routeId=value["routeId"],
        routeShortName=value.get("routeShortName", ""),
        headsign=value.get("headsign"),
        engineTripId=engine_id,
        sourceTripId=match[3],
        serviceDate=datetime.strptime(match[1], "%Y%m%d").date(),
        startTime=match[2],
    )


def normalize(raw: dict, generation: Generation, depart_at: datetime) -> Journey:
    if not isinstance(raw, dict) or not isinstance(raw.get("legs"), list):
        raise ValueError("Invalid itinerary object")
    legs = []
    for item in raw["legs"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid leg object")
        if item.get("realTime") or item.get("cancelled"):
            raise ValueError("Unexpected live data in scheduled engine")
        mode = MODE_MAP[item["mode"]]
        times = timing(item)
        if not generation.contains(times.scheduledDeparture):
            raise ValueError("Leg departure outside coverage")
        if not generation.contains(times.scheduledArrival):
            raise ValueError("Leg arrival outside coverage")
        if times.scheduledDeparture < depart_at:
            raise ValueError("Leg before requested departure")
        start, end = location(item["from"]), location(item["to"])
        if legs:
            previous = legs[-1]
            if times.scheduledDeparture < previous.timing.scheduledArrival:
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
                    (times.scheduledArrival - times.scheduledDeparture).total_seconds()
                ),
                distanceMeters=distance,
                geometry=shape,
                geometryUnavailableReason=None if shape else "not_provided_by_engine",
                transit=None if mode == "walk" else transit(item),
            )
        )
    if not legs:
        raise ValueError("Empty itinerary")
    transfers = raw["transfers"]
    if type(transfers) is not int or transfers < 0:
        raise ValueError("Invalid transfer count")
    times = Timing(
        scheduledDeparture=legs[0].timing.scheduledDeparture,
        scheduledArrival=legs[-1].timing.scheduledArrival,
    )
    return Journey(
        id="journey-1",
        timing=times,
        durationSeconds=int((times.scheduledArrival - times.scheduledDeparture).total_seconds()),
        walkingSeconds=sum(x.durationSeconds for x in legs if x.kind == "walk"),
        walkingDistanceMeters=sum(x.distanceMeters for x in legs if x.kind == "walk"),
        transfers=transfers,
        legs=legs,
    )


class MotisClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def plan(self, query, generation: Generation) -> list[Journey]:
        params = {
            "fromPlace": f"{query.origin.latitude},{query.origin.longitude}",
            "toPlace": f"{query.destination.latitude},{query.destination.longitude}",
            "time": query.depart_at.isoformat(),
            "arriveBy": "false",
            "numItineraries": "1",
        }
        try:
            response = await self.client.get("/api/v6/plan", params=params)
            response.raise_for_status()
            body = response.json()
            candidates = body["itineraries"]
            direct = body["direct"]
            if not isinstance(candidates, list) or not isinstance(direct, list):
                raise ValueError("Invalid itinerary list")
            candidates = candidates or direct
            # Only a successful empty engine result is no-route. Do not substitute
            # a later alternative if the engine's first itinerary is malformed.
            return [normalize(candidates[0], generation, query.depart_at)] if candidates else []
        except httpx.TimeoutException:
            raise EngineFailure("ENGINE_TIMEOUT", 504) from None
        except httpx.HTTPError:
            raise EngineFailure() from None
        except ValueError, KeyError, TypeError, IndexError, OverflowError:
            raise EngineFailure("ENGINE_INVALID_RESPONSE") from None
