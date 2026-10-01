"""Lossless GTFS trip-call parsing, bounded minute projection and engine reconciliation.

The projected schedule is diagnostic and candidate-local. Raw chronology is retained
beside it and is never rewritten or presented as repaired source evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

MOTIS_SOURCE_COMMIT = "061857d38a375248ae62b4ce722753368a75e474"
NIGIRI_SOURCE_COMMIT = "0a08a1c09dad25c5d892b2fd7166b03e82d62970"
PROJECTION_POLICY_VERSION = 1
TIME_RESOLUTION_SECONDS = 60
POLICY_ID = "motis-minute-bracket-v1"

EventKind = Literal["arrival", "departure"]
_TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2})\Z")
_SEQUENCE_RE = re.compile(r"\d+\Z")


class TripCallError(ValueError):
    """Malformed or unprojectable source trip-call data."""


class ReconciliationError(ValueError):
    """Source profile does not exactly match its dated engine counterpart."""


@dataclass(frozen=True)
class ProjectionPolicy:
    policy_id: str = POLICY_ID
    motis_source_commit: str = MOTIS_SOURCE_COMMIT
    nigiri_source_commit: str = NIGIRI_SOURCE_COMMIT
    version: int = PROJECTION_POLICY_VERSION
    resolution_seconds: int = TIME_RESOLUTION_SECONDS


PINNED_PROJECTION_POLICY = ProjectionPolicy()


@dataclass(frozen=True)
class SourceCall:
    """One source row with full identity, source sequence and ordered occurrence."""

    trip_id: str
    service_id: str
    sequence: int
    ordinal: int
    stop_id: str
    arrival_seconds: int | None
    departure_seconds: int | None
    pickup_type: int
    drop_off_type: int

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (self.trip_id, self.service_id, self.stop_id)
        ):
            raise TripCallError("Trip, service and source stop IDs must be nonempty")
        if type(self.sequence) is not int or self.sequence < 0:
            raise TripCallError("stop_sequence must be a nonnegative integer")
        if type(self.ordinal) is not int or self.ordinal < 0:
            raise TripCallError("call ordinal must be a nonnegative integer")
        for name, value in (
            ("arrival_seconds", self.arrival_seconds),
            ("departure_seconds", self.departure_seconds),
        ):
            if value is not None and (type(value) is not int or value < 0):
                raise TripCallError(f"{name} must be a nonnegative integer or None")
        if self.arrival_seconds is None and self.departure_seconds is None:
            raise TripCallError("A source call must provide arrival or departure time")
        for name, value in (
            ("pickup_type", self.pickup_type),
            ("drop_off_type", self.drop_off_type),
        ):
            if type(value) is not int or not 0 <= value <= 3:
                raise TripCallError(f"{name} must be an integer from 0 through 3")
        if (
            self.arrival_seconds is not None
            and self.departure_seconds is not None
            and self.departure_seconds < self.arrival_seconds
        ):
            raise TripCallError("A call's raw departure precedes its raw arrival")


@dataclass(frozen=True)
class SourceProfile:
    """A complete ordered source trip; the full feed trip ID is never normalized."""

    trip_id: str
    service_id: str
    calls: tuple[SourceCall, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "calls", tuple(self.calls))
        if not self.trip_id or not self.service_id:
            raise TripCallError("Trip and service IDs must be nonempty")
        if len(self.calls) < 2:
            raise TripCallError("A source profile must contain at least two calls")
        if any(not isinstance(call, SourceCall) for call in self.calls):
            raise TripCallError("A source profile may contain only SourceCall values")
        if any(
            call.trip_id != self.trip_id or call.service_id != self.service_id
            for call in self.calls
        ):
            raise TripCallError("Call identity differs from its source profile")
        sequences = [call.sequence for call in self.calls]
        if len(set(sequences)) != len(sequences):
            raise TripCallError("Duplicate stop_sequence values are invalid")
        if sequences != sorted(sequences):
            raise TripCallError("Source calls must be ordered by numeric stop_sequence")
        if [call.ordinal for call in self.calls] != list(range(len(self.calls))):
            raise TripCallError("Call ordinals must be contiguous and follow source order")


def _sequence(value: object) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, str) and _SEQUENCE_RE.fullmatch(value):
        result = int(value)
    else:
        raise TripCallError("stop_sequence must be a numeric integer")
    if result < 0:
        raise TripCallError("stop_sequence must be nonnegative")
    return result


def _seconds(value: object, field: str) -> int | None:
    if value is None or value == "":
        return None
    if type(value) is int:
        result = value
    elif isinstance(value, str):
        match = _TIME_RE.fullmatch(value)
        if not match:
            raise TripCallError(f"{field} must be seconds or an HH:MM:SS GTFS time")
        hours, minutes, seconds = (int(part) for part in match.groups())
        if minutes >= 60 or seconds >= 60:
            raise TripCallError(f"{field} has invalid minute or second values")
        result = hours * 3600 + minutes * 60 + seconds
    else:
        raise TripCallError(f"{field} must be seconds or an HH:MM:SS GTFS time")
    if result < 0:
        raise TripCallError(f"{field} must be nonnegative")
    return result


def _clock(row: dict, seconds_name: str, time_name: str) -> int | None:
    has_seconds = row.get(seconds_name) not in (None, "")
    has_time = row.get(time_name) not in (None, "")
    if has_seconds and has_time:
        seconds_value = _seconds(row[seconds_name], seconds_name)
        time_value = _seconds(row[time_name], time_name)
        if seconds_value != time_value:
            raise TripCallError(f"Conflicting {seconds_name} and {time_name} values")
        return seconds_value
    return _seconds(row.get(seconds_name) if has_seconds else row.get(time_name), time_name)


def source_profile_from_rows(trip_id: str, service_id: str, rows: list[dict]) -> SourceProfile:
    """Parse GTFS stop-time rows, sorting only by their explicit numeric sequence."""
    if not isinstance(trip_id, str) or not trip_id:
        raise TripCallError("Full source trip_id is required")
    if not isinstance(service_id, str) or not service_id:
        raise TripCallError("Full service_id is required")
    if not isinstance(rows, list) or len(rows) < 2:
        raise TripCallError("At least two stop-time rows are required")
    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            raise TripCallError("Each stop-time row must be a mapping")
        if (
            row.get("trip_id", trip_id) != trip_id
            or row.get("service_id", service_id) != service_id
        ):
            raise TripCallError("Stop-time row identity differs from its trip/service profile")
        parsed.append((_sequence(row.get("stop_sequence", row.get("sequence"))), row))
    sequences = [sequence for sequence, _ in parsed]
    if len(set(sequences)) != len(sequences):
        raise TripCallError("Duplicate stop_sequence values are invalid")
    if sequences != sorted(sequences):
        raise TripCallError("Stop-time rows contain nonmonotonic stop_sequence values")
    calls = []
    for ordinal, (sequence, row) in enumerate(parsed):
        stop_id = row.get("stop_id")
        pickup = row.get("pickup_type", 0)
        drop_off = row.get("drop_off_type", row.get("dropoff_type", 0))
        if isinstance(pickup, str) and pickup.isdigit():
            pickup = int(pickup)
        if isinstance(drop_off, str) and drop_off.isdigit():
            drop_off = int(drop_off)
        calls.append(
            SourceCall(
                trip_id,
                service_id,
                sequence,
                ordinal,
                stop_id,
                _clock(row, "arrival_seconds", "arrival_time"),
                _clock(row, "departure_seconds", "departure_time"),
                pickup,
                drop_off,
            )
        )
    return SourceProfile(trip_id, service_id, tuple(calls))


@dataclass(frozen=True)
class ProjectedEvent:
    sequence: int
    ordinal: int
    stop_id: str
    kind: EventKind
    raw_seconds: int
    effective_seconds: int


@dataclass(frozen=True)
class RawEvent:
    sequence: int
    ordinal: int
    stop_id: str
    kind: EventKind
    raw_seconds: int
    projected: bool
    effective_seconds: int | None


@dataclass(frozen=True)
class RawChronologyDiagnostic:
    previous_sequence: int
    previous_ordinal: int
    previous_kind: EventKind
    previous_seconds: int
    sequence: int
    ordinal: int
    kind: EventKind
    raw_seconds: int
    regression_seconds: int


@dataclass(frozen=True)
class ProfileProjection:
    profile: SourceProfile
    events: tuple[ProjectedEvent, ...]
    raw_events: tuple[RawEvent, ...]
    raw_chronology_diagnostics: tuple[RawChronologyDiagnostic, ...]
    policy: ProjectionPolicy = PINNED_PROJECTION_POLICY

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "raw_events", tuple(self.raw_events))
        object.__setattr__(
            self, "raw_chronology_diagnostics", tuple(self.raw_chronology_diagnostics)
        )

    @property
    def raw_chronology_clean(self) -> bool:
        return not self.raw_chronology_diagnostics


def _raw_events(profile: SourceProfile) -> list[tuple[SourceCall, EventKind, int]]:
    result = []
    for call in profile.calls:
        if call.arrival_seconds is not None:
            result.append((call, "arrival", call.arrival_seconds))
        if call.departure_seconds is not None:
            result.append((call, "departure", call.departure_seconds))
    return result


def project_profile(profile: SourceProfile) -> ProfileProjection:
    """Apply the pinned bounded minute projection without changing raw source calls."""
    all_raw = _raw_events(profile)
    projected_keys = set()
    candidates: list[tuple[SourceCall, EventKind, int]] = []
    calls = profile.calls
    if calls[0].departure_seconds is not None:
        candidates.append((calls[0], "departure", calls[0].departure_seconds))
        projected_keys.add((calls[0].ordinal, "departure"))
    for call in calls[1:-1]:
        if call.arrival_seconds is not None:
            candidates.append((call, "arrival", call.arrival_seconds))
            projected_keys.add((call.ordinal, "arrival"))
        if call.departure_seconds is not None:
            candidates.append((call, "departure", call.departure_seconds))
            projected_keys.add((call.ordinal, "departure"))
    if calls[-1].arrival_seconds is not None:
        candidates.append((calls[-1], "arrival", calls[-1].arrival_seconds))
        projected_keys.add((calls[-1].ordinal, "arrival"))
    if len(candidates) < 2:
        raise TripCallError("Source profile has fewer than two projectable clock events")

    diagnostics: list[RawChronologyDiagnostic] = []
    previous_raw: tuple[SourceCall, EventKind, int] | None = None
    for event in all_raw:
        if previous_raw is not None and event[2] < previous_raw[2]:
            previous_call, previous_kind, previous_seconds = previous_raw
            call, kind, raw_seconds = event
            diagnostics.append(
                RawChronologyDiagnostic(
                    previous_call.sequence,
                    previous_call.ordinal,
                    previous_kind,
                    previous_seconds,
                    call.sequence,
                    call.ordinal,
                    kind,
                    raw_seconds,
                    previous_seconds - raw_seconds,
                )
            )
        previous_raw = event

    effective_events: list[ProjectedEvent] = []
    previous_effective: int | None = None
    previous_candidate_raw: int | None = None
    for call, kind, raw_seconds in candidates:
        raw_floor = (raw_seconds // TIME_RESOLUTION_SECONDS) * TIME_RESOLUTION_SECONDS
        raw_ceil = ((raw_seconds + TIME_RESOLUTION_SECONDS - 1) // TIME_RESOLUTION_SECONDS) * (
            TIME_RESOLUTION_SECONDS
        )
        effective = raw_floor if previous_effective is None else max(previous_effective, raw_floor)
        if not raw_floor <= effective <= raw_ceil:
            raise TripCallError(
                f"Projected {kind} at sequence {call.sequence} escapes its raw minute bounds"
            )
        if previous_effective is not None and previous_candidate_raw is not None:
            raw_interval = raw_seconds - previous_candidate_raw
            effective_interval = effective - previous_effective
            distortion = abs(effective_interval - raw_interval)
            if distortion >= TIME_RESOLUTION_SECONDS:
                raise TripCallError(
                    f"Projected interval before sequence {call.sequence} distorts by "
                    f"{distortion} seconds"
                )
        effective_events.append(
            ProjectedEvent(call.sequence, call.ordinal, call.stop_id, kind, raw_seconds, effective)
        )
        previous_effective = effective
        previous_candidate_raw = raw_seconds

    event_by_key = {(event.ordinal, event.kind): event for event in effective_events}
    raw_events = tuple(
        RawEvent(
            call.sequence,
            call.ordinal,
            call.stop_id,
            kind,
            raw_seconds,
            (call.ordinal, kind) in projected_keys,
            event_by_key[(call.ordinal, kind)].effective_seconds
            if (call.ordinal, kind) in event_by_key
            else None,
        )
        for call, kind, raw_seconds in all_raw
    )
    return ProfileProjection(
        profile,
        tuple(effective_events),
        raw_events,
        tuple(diagnostics),
    )


@dataclass(frozen=True)
class EngineCall:
    stop_id: str
    arrival_utc: datetime | None
    departure_utc: datetime | None

    def __post_init__(self) -> None:
        if not isinstance(self.stop_id, str) or not self.stop_id:
            raise ReconciliationError("Engine call stop_id must be nonempty")


@dataclass(frozen=True)
class EngineProfile:
    engine_trip_id: str
    source_trip_id: str
    service_id: str
    service_date: date
    calls: tuple[EngineCall, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "calls", tuple(self.calls))
        if not self.engine_trip_id or not self.source_trip_id or not self.service_id:
            raise ReconciliationError("Engine trip identity fields must be nonempty")
        if isinstance(self.service_date, datetime) or not isinstance(self.service_date, date):
            raise ReconciliationError("Engine service_date must be an exact calendar date")
        if not self.calls:
            raise ReconciliationError("Engine profile has no ordered calls")
        if any(not isinstance(call, EngineCall) for call in self.calls):
            raise ReconciliationError("Engine profile may contain only EngineCall values")
        for call in self.calls:
            if not call.stop_id:
                raise ReconciliationError("Engine call stop_id must be nonempty")


@dataclass(frozen=True)
class ExpectedUtcEvent:
    sequence: int
    ordinal: int
    kind: EventKind
    effective_seconds: int
    at_utc: datetime

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or type(self.ordinal) is not int:
            raise ReconciliationError("Expected event sequence and ordinal must be integers")
        if self.kind not in {"arrival", "departure"}:
            raise ReconciliationError("Expected event kind is unknown")
        if type(self.effective_seconds) is not int or self.effective_seconds < 0:
            raise ReconciliationError("Expected event effective_seconds must be nonnegative")
        _require_utc(self.at_utc, "Expected clock")


@dataclass(frozen=True)
class ReconciliationResult:
    profile_id: str
    service_id: str
    engine_trip_id: str
    service_date: date
    stop_vector: tuple[str, ...]
    projected_events: tuple[ProjectedEvent, ...]
    expected_utc_events: tuple[ExpectedUtcEvent, ...]
    raw_chronology_diagnostics: tuple[RawChronologyDiagnostic, ...]
    policy: ProjectionPolicy = PINNED_PROJECTION_POLICY
    structural_match: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "stop_vector", tuple(self.stop_vector))
        object.__setattr__(self, "projected_events", tuple(self.projected_events))
        object.__setattr__(self, "expected_utc_events", tuple(self.expected_utc_events))
        object.__setattr__(
            self, "raw_chronology_diagnostics", tuple(self.raw_chronology_diagnostics)
        )

    @property
    def raw_chronology_clean(self) -> bool:
        return not self.raw_chronology_diagnostics


def _require_utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise ReconciliationError(f"{label} must be an explicit UTC datetime")
    return value.astimezone(UTC)


def _engine_events(profile: EngineProfile) -> dict[tuple[int, EventKind], datetime]:
    events = {}
    for ordinal, call in enumerate(profile.calls):
        for kind, instant in (
            ("arrival", call.arrival_utc),
            ("departure", call.departure_utc),
        ):
            if instant is None:
                continue
            key = ordinal, kind
            if key in events:
                raise ReconciliationError("Engine profile contains duplicate call clock fields")
            events[key] = _require_utc(instant, "Engine clock")
    return events


def reconcile_profile(
    source_profile: SourceProfile,
    engine_profile: EngineProfile,
    *,
    expected_engine_trip_id: str,
    expected_service_date: date,
    expected_utc_events: tuple[ExpectedUtcEvent, ...] | list[ExpectedUtcEvent],
) -> ReconciliationResult:
    """Match exact dated identity, every ordered stop call and verified UTC event clocks."""
    if engine_profile.source_trip_id != source_profile.trip_id:
        raise ReconciliationError("Engine source trip ID differs from the full source trip ID")
    if engine_profile.service_id != source_profile.service_id:
        raise ReconciliationError("Engine service ID differs from the source service ID")
    if engine_profile.engine_trip_id != expected_engine_trip_id:
        raise ReconciliationError("Full dated engine trip identity differs from the expected ID")
    if engine_profile.service_date != expected_service_date:
        raise ReconciliationError("Engine service date differs from the expected service date")
    if len(engine_profile.calls) != len(source_profile.calls):
        raise ReconciliationError("Source and engine ordered call counts differ")
    source_stops = tuple(call.stop_id for call in source_profile.calls)
    engine_stops = tuple(call.stop_id for call in engine_profile.calls)
    if source_stops != engine_stops:
        raise ReconciliationError("Whole ordered stop-call vectors differ")

    projection = project_profile(source_profile)
    expected = tuple(expected_utc_events)
    expected_keys = tuple((event.sequence, event.ordinal, event.kind) for event in expected)
    projected_keys = tuple(
        (event.sequence, event.ordinal, event.kind) for event in projection.events
    )
    if expected_keys != projected_keys:
        raise ReconciliationError(
            "Expected UTC clock event keys differ from projected source calls"
        )
    if tuple(event.effective_seconds for event in expected) != tuple(
        event.effective_seconds for event in projection.events
    ):
        raise ReconciliationError(
            "Expected UTC clocks are not bound to projected effective seconds"
        )
    engine_events = _engine_events(engine_profile)
    expected_by_ordinal = {
        (event.ordinal, event.kind): _require_utc(event.at_utc, "Expected clock")
        for event in expected
    }
    if set(engine_events) != set(expected_by_ordinal):
        raise ReconciliationError("Engine clock fields are missing, extra or unknown")
    for key, expected_at in expected_by_ordinal.items():
        if engine_events[key] != expected_at:
            raise ReconciliationError(
                f"Engine UTC clock differs from verified expected clock at ordinal {key[0]}"
            )
    return ReconciliationResult(
        source_profile.trip_id,
        source_profile.service_id,
        engine_profile.engine_trip_id,
        engine_profile.service_date,
        source_stops,
        projection.events,
        expected,
        projection.raw_chronology_diagnostics,
        projection.policy,
    )
