"""OpenAPI response models for the timetable and reference reads the client draws from.

These document what the routes return; the routes build their JSON directly (they predate
typed models), so the models are attached with ``responses=`` and never used to serialize.
Tests check real responses against them.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from opentransit.api.schemas import Geometry, Metadata, Model, Problem

PublicMode = Literal["bus", "rail", "light_rail", "cable_car", "funicular", "ferry", "other"]

_MODE_DOC = (
    "The same mode strings journey legs use (`bus`, `rail`, `light_rail`; rarer engine "
    "modes as `cable_car`, `funicular`, `ferry`, else `other`); null when the engine omits it."
)


class DepartureItem(Model):
    scheduledDeparture: datetime
    stopId: str = Field(description="The platform or stop the vehicle leaves from.")
    routeId: str
    routeShortName: str
    headsign: str | None
    operatorId: str | None = Field(
        description="GTFS agency ID (API-C3); null when the engine omits it."
    )
    operatorName: str | None = Field(description="Operator name as in the feed (API-C3).")
    mode: PublicMode | None = Field(description=_MODE_DOC)
    directionId: str | None = Field(description="GTFS direction_id of the trip, if any.")
    platformCode: str | None
    pickupType: int
    tripRef: str = Field(description="Dated trip reference for `GET /v1/trips/{tripRef}`.")
    callSequence: int


class Page(Model):
    nextCursor: str | None


class DeparturesResponse(Model):
    data: list[DepartureItem]
    page: Page
    meta: Metadata


class StopSummary(Model):
    stopId: str
    sourceId: str
    code: str | None
    name: str | None
    description: str | None
    latitude: float | None
    longitude: float | None
    locationType: int | None
    parentStationId: str | None
    wheelchairBoarding: int | None
    platformCode: str | None
    distanceMeters: float = Field(
        description="From `near`; for a station, the distance to its nearest platform."
    )


class NearbyStopDepartures(Model):
    stop: StopSummary
    departuresState: Literal["available", "unavailable"]
    unavailableReason: str | None = Field(
        description="Problem code when this stop's departures could not be read."
    )
    complete: bool = Field(
        description=(
            "False when the per-stop lookup bound stopped before `perStop` lines were found, "
            "or the stop is unavailable. True means every line departing in the window was "
            "considered."
        )
    )
    departures: list[DepartureItem] | None = Field(
        description=(
            "Earliest departure of each line (route and headsign), in time order, at most "
            "`perStop`; null when unavailable. An empty list means no boardable departure "
            "in the window."
        )
    )


class NearbyCoordinate(Model):
    latitude: float
    longitude: float


class NearbyQuery(Model):
    near: NearbyCoordinate
    radiusMeters: float
    stops: int
    perStop: int
    start: datetime = Field(alias="from")
    until: datetime


class NearbyDeparturesResponse(Model):
    data: list[NearbyStopDepartures] = Field(description="Nearest stop first.")
    query: NearbyQuery
    meta: Metadata


class TripCall(Model):
    callSequence: int
    ordinal: int
    stopId: str
    name: str | None = Field(description="Stop name from the feed (API-C1).")
    latitude: float | None = Field(description="API-C1")
    longitude: float | None = Field(description="API-C1")
    platformCode: str | None = Field(description="API-C1")
    scheduledArrival: datetime | None
    scheduledDeparture: datetime | None
    pickupType: int
    dropOffType: int


class Trip(Model):
    tripRef: str
    sourceTripId: str
    serviceDate: date
    startTime: str
    routeId: str
    routeShortName: str
    headsign: str | None
    operatorId: str | None
    operatorName: str | None
    mode: PublicMode | None = Field(description=_MODE_DOC)
    directionId: str | None
    shape: Geometry | None = Field(description="The whole trip's path, first to last stop.")
    calls: list[TripCall]
    timingState: Literal["scheduled"]
    expectedArrival: None
    expectedDeparture: None
    delaySeconds: None
    alerts: Literal["not_enabled"]


class TripResponse(Model):
    data: Trip
    meta: Metadata


class LineStop(Model):
    stopId: str
    name: str | None
    latitude: float | None
    longitude: float | None
    pickupType: int
    dropOffType: int


class LinePattern(Model):
    patternId: str
    routeId: str = Field(
        description=(
            "The route this pattern belongs to. A MOT route is one direction, so with "
            "`patterns=all` the line's other directions (same operator and line code) appear "
            "here under their own route IDs, with `servesStop` false unless they also stop here."
        )
    )
    directionId: str | None
    headsign: str | None
    servesStop: bool = Field(
        description="True when the tapped stop or one of its platforms is on it."
    )
    stopIndex: int | None = Field(
        description=(
            "Index in `stops` of the first call at the tapped stop (or its platform); the "
            "line fans out from here in its direction of travel. Null when not served."
        )
    )
    geometrySource: Literal["stop_sequence"] = Field(
        description=(
            "`stops` is the ordered stop sequence, not the street path. For the street path "
            "of one trip use `GET /v1/trips/{tripRef}` (`shape`)."
        )
    )
    stops: list[LineStop]


class StopLine(Model):
    routeId: str
    routeShortName: str | None
    routeLongName: str | None
    operatorId: str | None
    operatorName: str | None
    mode: PublicMode = Field(description=_MODE_DOC + " Derived from the GTFS route_type.")
    routeType: int | None
    color: str | None
    textColor: str | None
    patterns: list[LinePattern]


class StopLinesResponse(Model):
    data: list[StopLine]
    page: Page
    meta: Metadata


class LineDirection(Model):
    routeId: str = Field(description="One MOT route: one direction (or variant) of the line.")
    headsign: str | None = Field(description="The headsign of its longest pattern, if any.")
    originName: str | None = Field(description="First stop of its longest pattern.")
    destinationName: str | None = Field(description="Last stop of its longest pattern.")


class LineNearestStop(Model):
    stopId: str
    name: str | None
    distanceM: int = Field(description="Straight-line metres from `lat`/`lon`, rounded.")


class LineItem(Model):
    lineKey: str = Field(
        description=(
            "Opaque and stable across generations: the operator (GTFS agency_id) and the MOT "
            "line code (route_desc before the first '-'), as `<agency_id>:<code>`. A route "
            "without a line code is a line of its own (`<agency_id>:route:<route source id>`)."
        )
    )
    shortName: str = Field(description="The line number (`routeShortName`).")
    operatorId: str | None
    operatorName: str | None
    mode: PublicMode = Field(description=_MODE_DOC + " Derived from the GTFS route_type.")
    routeIds: list[str] = Field(description="Its routes, main directions first.")
    directions: list[LineDirection] = Field(description="One per route, in `routeIds` order.")
    area: str | None = Field(
        description=(
            "The locality (OSM admin level 8, Hebrew name) holding at least half of the "
            "line's stops; null for intercity lines or a reference without localities."
        )
    )
    nearestStop: LineNearestStop | None = Field(
        default=None,
        description=(
            "Only when `lat`/`lon` are given: the line's stop (any direction) nearest them, "
            "within 2 km, else null. Absent without `lat`/`lon`."
        ),
    )


class LinesResponse(Model):
    data: list[LineItem] = Field(
        description=(
            "Exact number first, then longer numbers; within each, nearest first when "
            "`lat`/`lon` are given, then by number (8, 80, 82, 800)."
        )
    )
    page: Page
    meta: Metadata


class LineResponse(Model):
    data: LineItem
    meta: Metadata


def _problems(*statuses: int) -> dict:
    return {
        status: {"content": {"application/problem+json": {"schema": Problem.model_json_schema()}}}
        for status in statuses
    }


DEPARTURES_DOC = {200: {"model": DeparturesResponse}, **_problems(404, 422, 503, 504)}
NEARBY_DOC = {200: {"model": NearbyDeparturesResponse}, **_problems(422, 503, 504)}
TRIP_DOC = {200: {"model": TripResponse}, **_problems(404, 422, 503, 504)}
STOP_LINES_DOC = {200: {"model": StopLinesResponse}, **_problems(404, 422, 503)}
LINES_DOC = {200: {"model": LinesResponse}, **_problems(422, 503)}
LINE_DOC = {200: {"model": LineResponse}, **_problems(404, 422, 503)}
