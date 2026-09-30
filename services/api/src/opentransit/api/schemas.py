import re
from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Coordinate(Model):
    kind: Literal["coordinate"]
    latitude: float = Field(ge=29.0, le=34.0, strict=True, allow_inf_nan=False)
    longitude: float = Field(ge=34.0, le=36.0, strict=True, allow_inf_nan=False)


class JourneyRequest(Model):
    origin: Coordinate = Field(alias="from")
    destination: Coordinate = Field(alias="to")
    depart_at: AwareDatetime = Field(alias="departAt")

    @field_validator("depart_at", mode="before")
    @classmethod
    def explicit_offset(cls, value: object) -> object:
        if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value
        ):
            raise ValueError("Use an ISO timestamp with an explicit offset")
        return value


class Problem(Model):
    type: str
    title: str
    status: int
    code: str
    detail: str
    requestId: str
    errors: list[dict[str, str]] | None = None


class Location(Model):
    name: str
    latitude: float
    longitude: float
    stopId: str | None = None
    stopCode: str | None = None


class Timing(Model):
    scheduledDeparture: datetime
    scheduledArrival: datetime
    timingState: Literal["scheduled"] = "scheduled"
    expectedDeparture: None = None
    expectedArrival: None = None
    delaySeconds: None = None
    observedAt: None = None


class Geometry(Model):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]]


class Transit(Model):
    operatorId: str
    operatorName: str
    routeId: str
    routeShortName: str
    headsign: str | None
    engineTripId: str
    sourceTripId: str
    serviceDate: date
    startTime: str


class Leg(Model):
    kind: Literal["walk", "transit"]
    mode: str
    origin: Location = Field(alias="from")
    destination: Location = Field(alias="to")
    timing: Timing
    durationSeconds: int
    distanceMeters: float | None
    geometry: Geometry | None
    geometryUnavailableReason: str | None
    transit: Transit | None


class Journey(Model):
    id: str
    timing: Timing
    durationSeconds: int
    walkingSeconds: int
    walkingDistanceMeters: float
    transfers: int
    legs: list[Leg]


class JourneyData(Model):
    outcome: Literal["routes_found", "no_route"]
    journeys: list[Journey]
    alerts: None = None


class Coverage(Model):
    start: datetime = Field(alias="from")
    until: datetime


class Capabilities(Model):
    realtime: Literal["not_enabled"] = "not_enabled"
    alerts: Literal["not_enabled"] = "not_enabled"


class Metadata(Model):
    requestId: str
    generationId: str
    generatedAt: datetime
    dataBuiltAt: datetime
    mode: Literal["real", "fixture"]
    coverage: Coverage
    freshness: str
    capabilities: Capabilities = Field(default_factory=Capabilities)
    attribution: list[str] = Field(
        default_factory=lambda: ["Israel Ministry of Transport", "© OpenStreetMap contributors"]
    )
    rankingPolicy: str = "motis-v2.11.2-order-first-itinerary"
    warnings: list[str] = Field(default_factory=list)


class JourneyResponse(Model):
    data: JourneyData
    meta: Metadata
