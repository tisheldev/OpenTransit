"""One service day's scheduled trips from a MOT GTFS archive, and ride → trip matching.

MOT's SIRI-GTFS mapping joins `LineRef` to `route_id` and `OriginAimedDepartureTime` to the
trip's first departure on the service date. A ride matches when exactly one trip running that
day has that route and first departure. SIRI's `DatedVehicleJourneyRef` (a TripIdToDate
`TripId`) is usually *not* the prefix of that day's GTFS `trip_id` (2026-09-15 pilot: 12,957 of
117,596 matched rides), so it is only a cross-check. Every other outcome is kept as an explicit
unmatched reason; this is replay evidence only, not a live POC-3 match rate.
"""

from __future__ import annotations

import csv
import io
import math
import zipfile
from array import array
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from opentransit.core.time import JERUSALEM

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@dataclass(frozen=True, slots=True)
class Call:
    sequence: int
    stop_id: str
    arrival: int  # epoch seconds on the service date
    departure: int
    distance_m: float | None  # GTFS shape_dist_traveled (metres)


class Trip:
    """One scheduled trip; calls are stored in compact arrays and built on demand."""

    __slots__ = (
        "trip_id",
        "route_id",
        "origin",
        "_sequence",
        "_stops",
        "_arrival",
        "_departure",
        "_distance",
    )

    def __init__(self, trip_id: str, route_id: str, origin: int = 0):
        self.trip_id, self.route_id, self.origin = trip_id, route_id, origin
        self._sequence, self._arrival, self._departure = array("i"), array("i"), array("i")
        self._distance = array("d")
        self._stops: list[str] = []

    def append(
        self, sequence: int, stop_id: str, arrival: int, departure: int, distance_m: float | None
    ) -> None:
        """Add a call; `arrival`/`departure` are seconds from the service-day origin."""
        self._sequence.append(sequence)
        self._stops.append(stop_id)
        self._arrival.append(arrival)
        self._departure.append(departure)
        self._distance.append(math.nan if distance_m is None else distance_m)

    def __len__(self) -> int:
        return len(self._sequence)

    @property
    def calls(self) -> list[Call]:
        order = sorted(range(len(self._sequence)), key=self._sequence.__getitem__)
        return [
            Call(
                sequence=self._sequence[i],
                stop_id=self._stops[i],
                arrival=self.origin + self._arrival[i],
                departure=self.origin + self._departure[i],
                distance_m=None if math.isnan(self._distance[i]) else self._distance[i],
            )
            for i in order
        ]

    def first_departure(self) -> int | None:
        if not self._sequence:
            return None
        first = min(range(len(self._sequence)), key=self._sequence.__getitem__)
        return self.origin + self._departure[first]


@dataclass(slots=True)
class DaySchedule:
    service_date: date
    trips: dict[str, Trip]  # by full trip_id
    routes: dict[str, dict]  # route_id → agency_id, route_short_name, route_desc
    by_origin: dict[tuple[str, int], list[str]] = field(default_factory=dict)
    running_routes: set[str] = field(default_factory=set)


def _rows(archive: zipfile.ZipFile, member: str):
    with archive.open(member) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def active_services(archive: zipfile.ZipFile, day: date) -> set[str]:
    active = set()
    for row in _rows(archive, "calendar.txt"):
        start = datetime.strptime(row["start_date"], "%Y%m%d").date()
        end = datetime.strptime(row["end_date"], "%Y%m%d").date()
        if start <= day <= end and row[WEEKDAYS[day.weekday()]] == "1":
            active.add(row["service_id"])
    if "calendar_dates.txt" in archive.namelist():
        stamp = day.strftime("%Y%m%d")
        for row in _rows(archive, "calendar_dates.txt"):
            if row["date"] != stamp:
                continue
            if row["exception_type"] == "1":
                active.add(row["service_id"])
            elif row["exception_type"] == "2":
                active.discard(row["service_id"])
    return active


def gtfs_seconds(value: str) -> int:
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def service_origin(day: date) -> int:
    """GTFS times count from noon minus 12 h local time (correct across clock changes)."""
    noon = datetime.combine(day, datetime.min.time(), JERUSALEM) + timedelta(hours=12)
    return int(noon.timestamp()) - 12 * 3600


def load_day(feed: Path, day: date) -> DaySchedule:
    with zipfile.ZipFile(feed) as archive:
        services = active_services(archive, day)
        routes = {
            row["route_id"]: {
                "agency_id": row.get("agency_id", ""),
                "route_short_name": row.get("route_short_name", ""),
                "route_desc": row.get("route_desc", ""),
            }
            for row in _rows(archive, "routes.txt")
        }
        origin = service_origin(day)
        trips: dict[str, Trip] = {}
        for row in _rows(archive, "trips.txt"):
            if row["service_id"] in services:
                trips[row["trip_id"]] = Trip(row["trip_id"], row["route_id"], origin)
        stops: dict[str, str] = {}  # one shared string per stop_id
        with archive.open("stop_times.txt") as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            header = next(reader)
            col = {name: header.index(name) for name in header}
            t, arr, dep = col["trip_id"], col["arrival_time"], col["departure_time"]
            seq, stop = col["stop_sequence"], col["stop_id"]
            dist = col.get("shape_dist_traveled")
            for row in reader:
                trip = trips.get(row[t])
                if trip is None:
                    continue
                raw_distance = row[dist] if dist is not None else ""
                stop_id = stops.setdefault(row[stop], row[stop])
                trip.append(
                    int(row[seq]),
                    stop_id,
                    gtfs_seconds(row[arr]),
                    gtfs_seconds(row[dep]),
                    float(raw_distance) if raw_distance else None,
                )
    by_origin: dict[tuple[str, int], list[str]] = defaultdict(list)
    for trip in trips.values():
        first = trip.first_departure()
        if first is not None:
            by_origin[(trip.route_id, first)].append(trip.trip_id)
    running = {trip.route_id for trip in trips.values()}
    return DaySchedule(day, trips, routes, dict(by_origin), running)


def match_ride(schedule: DaySchedule, line_ref: str, origin_departure: int):
    """Return (trip, None) or (None, reason)."""
    candidates = schedule.by_origin.get((line_ref, origin_departure), [])
    if len(candidates) == 1:
        return schedule.trips[candidates[0]], None
    if candidates:
        return None, "ambiguousRouteAndOrigin"
    if line_ref not in schedule.routes:
        return None, "routeNotInFeed"
    if line_ref not in schedule.running_routes:
        return None, "routeNotRunningOnServiceDate"
    return None, "noTripAtOriginTime"
