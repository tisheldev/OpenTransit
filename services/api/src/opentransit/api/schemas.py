import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Coordinate(Model):
    kind: Literal["coordinate"]
    latitude: float = Field(ge=29.0, le=34.0, strict=True, allow_inf_nan=False)
    longitude: float = Field(ge=34.0, le=36.0, strict=True, allow_inf_nan=False)


class StopLocation(Model):
    kind: Literal["stop"]
    stopId: str = Field(min_length=10, max_length=250)

    @field_validator("stopId")
    @classmethod
    def public_stop_reference(cls, value: str) -> str:
        if not value.startswith("mot:stop:") or len(value.removeprefix("mot:stop:")) == 0:
            raise ValueError("Use a namespaced stop reference")
        return value


class PlaceLocation(Model):
    kind: Literal["place"]
    placeRef: str = Field(min_length=1, max_length=768)


LocationInput = Annotated[Coordinate | StopLocation | PlaceLocation, Field(discriminator="kind")]


class JourneyRequest(Model):
    origin: LocationInput = Field(alias="from")
    destination: LocationInput = Field(alias="to")
    depart_at: AwareDatetime | None = Field(
        default=None,
        alias="departAt",
        description="ISO timestamp with an explicit offset. Exactly one of departAt/arriveBy.",
    )
    arrive_by: AwareDatetime | None = Field(
        default=None,
        alias="arriveBy",
        description="ISO timestamp with an explicit offset. Exactly one of departAt/arriveBy.",
    )
    modes: list[Literal["bus", "rail", "light_rail"]] = Field(
        default_factory=lambda: ["bus", "rail", "light_rail"],
        min_length=1,
        description="Unique transit modes the engine may use. Walking is always allowed.",
    )
    results: int = Field(
        default=3, ge=1, le=5, strict=True, description="Maximum alternatives to return (1-5)."
    )
    lang: Literal["he", "en"] = "he"
    max_access_walk_minutes: int = Field(
        default=15,
        alias="maxAccessWalkMinutes",
        ge=1,
        le=30,
        strict=True,
        description=(
            "Cap on the first walk before boarding, in whole minutes (1-30). Sent to the "
            "engine as maxPreTransitTime. Does not bound walking between transit legs."
        ),
    )
    max_egress_walk_minutes: int = Field(
        default=15,
        alias="maxEgressWalkMinutes",
        ge=1,
        le=30,
        strict=True,
        description=(
            "Cap on the last walk after alighting, in whole minutes (1-30). Sent to the "
            "engine as maxPostTransitTime. Does not bound walking between transit legs."
        ),
    )
    max_direct_walk_minutes: int = Field(
        default=30,
        alias="maxDirectWalkMinutes",
        ge=1,
        le=30,
        strict=True,
        description=(
            "Cap on a walk-only alternative, in whole minutes (1-30). Sent to the engine "
            "as maxDirectTime."
        ),
    )

    @field_validator("depart_at", "arrive_by", mode="before")
    @classmethod
    def explicit_offset(cls, value: object) -> object:
        if value is None:
            raise ValueError("Use an ISO timestamp with an explicit offset")
        if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value
        ):
            raise ValueError("Use an ISO timestamp with an explicit offset")
        return value

    @field_validator("modes")
    @classmethod
    def unique_modes(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Modes must be unique")
        return value

    @model_validator(mode="after")
    def exactly_one_time_anchor(self):
        if (self.depart_at is None) == (self.arrive_by is None):
            raise ValueError("Provide exactly one of departAt or arriveBy")
        return self

    @property
    def time_anchor(self) -> datetime:
        return self.depart_at if self.depart_at is not None else self.arrive_by

    @property
    def is_arrive_by(self) -> bool:
        return self.arrive_by is not None


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
    rankingPolicy: str = "motis-v2.11.2-feasible-engine-order-v1"
    appliedConstraints: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Constraints the adapter sent to the engine, plus disclosures. "
            "transferWalkLimit is always not_enforced: walking between transit legs is "
            "unbounded and totalled per journey in walkingSeconds. engineWalkCapConformance "
            "states whether the engine's enforcement of the caps has been verified."
        ),
    )
    warnings: list[str] = Field(default_factory=list)


class JourneyResponse(Model):
    data: JourneyData
    meta: Metadata
