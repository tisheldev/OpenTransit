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

_DATED_TRIP = re.compile(r"\d{8}_\d{2}:\d{2}(?::\d{2})?_mot60day_.+")


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
    exclude_trip_refs: list[str] = Field(
        default_factory=list,
        alias="excludeTripRefs",
        max_length=5,
        description=(
            "Dated trip references (a leg's `transit.engineTripId`) no returned journey may "
            "ride, for example the bus that did not come. Alternatives using one are omitted "
            "(warning `EXCLUDED_TRIP_ALTERNATIVES_OMITTED`); the engine is asked for its "
            "maximum number of alternatives so that others can take their place."
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

    @field_validator("exclude_trip_refs")
    @classmethod
    def dated_trip_refs(cls, value: list[str]) -> list[str]:
        for item in value:
            if not isinstance(item, str) or len(item) > 512 or not _DATED_TRIP.fullmatch(item):
                raise ValueError("Use returned dated trip references")
        return list(dict.fromkeys(value))

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
    platformCode: str | None = Field(
        default=None,
        description=(
            "Platform or bay at a transit stop, from the generation's reference (API-C2); "
            "null when the feed gives none."
        ),
    )


class Stopover(Model):
    """A stop a transit leg passes between boarding and alighting."""

    name: str
    stopId: str | None
    latitude: float
    longitude: float
    scheduledArrival: datetime | None
    scheduledDeparture: datetime | None


class Boarding(Model):
    """Where to wait for a transit leg (board 3: "on this side, toward <place>")."""

    bearingDegrees: float | None = Field(
        description=(
            "Direction the vehicle travels as it leaves the boarding stop, degrees clockwise "
            "from north (0-360); null when neither the leg's path nor its next stop gives one."
        )
    )
    bearingSource: Literal["leg_geometry", "stop_sequence"] | None = Field(
        description=(
            "`leg_geometry`: read over the first 30 m of the leg's path after the stop. "
            "`stop_sequence`: straight towards the next stop (no path)."
        )
    )
    stopSide: Literal["right", "left"] | None = Field(
        description=(
            "Which side of the vehicle's path the stop stands on, facing the direction of "
            "travel. A person is on the stop's side of the road when they are on this side of "
            "the line through `pathPoint` at `bearingDegrees`. Null with "
            "`stopSideUnavailableReason` when it cannot be told from the data."
        )
    )
    stopSideUnavailableReason: (
        Literal[
            "not_a_street_mode",
            "path_has_no_shape_at_stop",
            "stop_on_path",
            "path_far_from_stop",
            "no_leg_geometry",
        ]
        | None
    )
    stopOffsetMeters: float | None = Field(
        description="Distance from the stop to the nearest point of the vehicle's path."
    )
    pathPoint: list[float] | None = Field(
        description="[longitude, latitude] of the vehicle path's point nearest the stop."
    )
    towards: str | None = Field(description="The trip's headsign (where the vehicle is signed to).")
    nextStop: Location | None = Field(
        description="The first stop after boarding (the alighting stop on a one-stop ride)."
    )
    stopCount: int | None = Field(
        description=(
            "Stops travelled until alighting, counting the alighting stop; null when the "
            "engine's intermediate stops are unreadable."
        )
    )


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
    intermediateStops: list[Stopover] | None = Field(
        default=None,
        description="Stops passed between boarding and alighting, in order; null for a walk.",
    )
    boarding: Boarding | None = Field(
        default=None, description="Where and which way to board; null for a walk."
    )


class Journey(Model):
    id: str
    timing: Timing
    durationSeconds: int
    walkingSeconds: int
    walkingDistanceMeters: float | None = Field(
        description=(
            "Sum of walk-leg distances; null when any walk leg's distance is unknown, such "
            "as a transfer whose street path is unavailable (TRANSFER_STREET_PATH_UNAVAILABLE)."
        )
    )
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
