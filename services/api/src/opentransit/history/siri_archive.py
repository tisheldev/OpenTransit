"""Parse archived MOT SIRI-SM 2.8 snapshots (Open Bus S3 layout) into compact pings.

Archive objects are `stride-siri-requester/YYYY/MM/DD/HH/MM.br`: brotli JSON of one
StopMonitoring response, named by the UTC minute it was requested. Field meanings observed on
the archive (research note, 1 October 2026):

- `FramedVehicleJourneyRef` = service date (`DataFrameRef`) + MOT `TripId`
  (`DatedVehicleJourneyRef`, a TripIdToDate key; usually not that day's GTFS `trip_id` prefix).
- `MonitoredCall.DistanceFromStop` is cumulative metres from the journey start (it increases
  along the ride), despite its name, on the same scale as GTFS `shape_dist_traveled`.
- `Order`/`StopPointRef` name the stop most recently reached: when `Order` advances, that new
  stop lies between the two pings' distances in 91% of changes (2026-09-15 pilot).
- Overlapping snapshots repeat unchanged visits, so the same `RecordedAtTime` recurs.
"""

from __future__ import annotations

import json
from array import array
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

PREFIX = "stride-siri-requester"


@dataclass(frozen=True, slots=True)
class Ping:
    service_date: date
    trip_ref: str  # DatedVehicleJourneyRef == TripIdToDate TripId
    line_ref: str  # GTFS route_id
    operator_ref: str
    origin_departure: int  # OriginAimedDepartureTime, epoch seconds
    recorded_at: int  # epoch seconds
    distance_m: int  # cumulative metres from journey start
    order: int  # sequence position of the stop most recently reached
    stop_code: str
    lat: float
    lon: float
    velocity: int
    vehicle_ref: str


def epoch(value: str) -> int:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"SIRI time without offset: {value}")
    return int(parsed.timestamp())


def minute_keys(start: datetime, end: datetime) -> Iterator[str]:
    """Archive keys for every UTC minute in [start, end)."""
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Archive range must be timezone-aware")
    moment = start.astimezone(UTC).replace(second=0, microsecond=0)
    while moment < end:
        yield f"{PREFIX}/{moment:%Y/%m/%d/%H/%M}.br"
        moment += timedelta(minutes=1)


def parse_snapshot(raw: bytes, *, compressed: bool = True) -> tuple[list[Ping], int]:
    """Return pings plus the count of visits skipped for missing location or distance."""
    if compressed:
        import brotli  # optional `history` dependency group; the API image does not need it

        raw = brotli.decompress(raw)
    document = json.loads(raw)
    deliveries = document["Siri"]["ServiceDelivery"].get("StopMonitoringDelivery") or []
    pings, skipped = [], 0
    for delivery in deliveries:
        for visit in delivery.get("MonitoredStopVisit") or []:
            journey = visit.get("MonitoredVehicleJourney") or {}
            frame = journey.get("FramedVehicleJourneyRef") or {}
            call = journey.get("MonitoredCall") or {}
            location = journey.get("VehicleLocation")
            try:
                pings.append(
                    Ping(
                        service_date=date.fromisoformat(frame["DataFrameRef"]),
                        trip_ref=str(frame["DatedVehicleJourneyRef"]),
                        line_ref=str(journey["LineRef"]),
                        operator_ref=str(journey.get("OperatorRef", "")),
                        origin_departure=epoch(journey["OriginAimedDepartureTime"]),
                        recorded_at=epoch(visit["RecordedAtTime"]),
                        distance_m=int(call["DistanceFromStop"]),
                        order=int(call["Order"]),
                        stop_code=str(call.get("StopPointRef", "")),
                        lat=float(location["Latitude"]),
                        lon=float(location["Longitude"]),
                        velocity=int(journey.get("Velocity") or 0),
                        vehicle_ref=str(journey.get("VehicleRef", "")),
                    )
                )
            except KeyError, TypeError, ValueError:
                skipped += 1
    return pings, skipped


@dataclass(slots=True)
class Ride:
    """One service date's observations of one TripId.

    Pings are kept in compact arrays (a month batch holds millions per day); `points`
    deduplicates by RecordedAtTime, keeping the first copy, when a ride is processed.
    """

    trip_ref: str
    line_ref: str
    operator_ref: str
    origin_departure: int
    at: array = field(default_factory=lambda: array("q"))
    metres: array = field(default_factory=lambda: array("i"))
    orders: array = field(default_factory=lambda: array("i"))
    vehicles: set[str] = field(default_factory=set)

    def add(self, ping: Ping) -> None:
        self.at.append(ping.recorded_at)
        self.metres.append(ping.distance_m)
        self.orders.append(ping.order)
        self.vehicles.add(ping.vehicle_ref)

    @property
    def points(self) -> dict[int, tuple[int, int]]:
        """RecordedAtTime → (metres, order), first copy of each repeated snapshot."""
        result: dict[int, tuple[int, int]] = {}
        for at, metres, order in zip(self.at, self.metres, self.orders, strict=True):
            if at not in result:
                result[at] = (metres, order)
        return result

    @property
    def duplicates(self) -> int:
        return len(self.at) - len(set(self.at))


def load_rides(
    cache: Path, keys: Iterable[str], service_date: date
) -> tuple[dict[str, Ride], dict]:
    """Group one service date's pings by TripId from cached archive files.

    Returns rides plus a provenance/coverage record. Missing minutes are counted, not filled.
    A TripId seen with a different line or origin time is kept under a separate key.
    """
    rides: dict[str, Ride] = {}
    stats = {"files": 0, "missingFiles": [], "pings": 0, "skippedVisits": 0, "otherDatePings": 0}
    for key in keys:
        path = cache / key.removeprefix(PREFIX + "/")
        if not path.exists() or path.stat().st_size == 0:
            stats["missingFiles"].append(key)
            continue
        pings, skipped = parse_snapshot(path.read_bytes())
        stats["files"] += 1
        stats["skippedVisits"] += skipped
        for ping in pings:
            if ping.service_date != service_date:
                stats["otherDatePings"] += 1
                continue
            identity = f"{ping.trip_ref}|{ping.line_ref}|{ping.origin_departure}"
            ride = rides.get(identity)
            if ride is None:
                ride = rides[identity] = Ride(
                    ping.trip_ref, ping.line_ref, ping.operator_ref, ping.origin_departure
                )
            ride.add(ping)
            stats["pings"] += 1
    return rides, stats
