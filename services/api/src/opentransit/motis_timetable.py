"""Scheduled MOTIS trip hydration and bounded stop departures."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
import threading
from collections import OrderedDict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx

from opentransit.core.time import as_utc_instant, engine_time, parse_utc_instant
from opentransit.core.trip_calls import (
    EngineCall,
    EngineProfile,
    ExpectedUtcEvent,
    ReconciliationError,
    reconcile_profile,
)
from opentransit.motis import geometry
from opentransit.reference import SourceProfileLimitError

_TRIP_ID = re.compile(r"(\d{8})_(\d{2}:\d{2}(?::\d{2})?)_mot60day_(.+)\Z")
_MOTIS_NAMESPACE = "mot60day_"
_JERUSALEM = ZoneInfo("Asia/Jerusalem")
_CACHE_SIZE = 128
_trip_cache: OrderedDict[tuple[str, str], dict] = OrderedDict()
_cache_lock = threading.RLock()
_DEPARTURES_MAX_EVENTS = 10_000
_ENGINE_RESPONSE_MAX_BYTES = 8 * 1024 * 1024
_DEPARTURES_TOTAL_RESPONSE_MAX_BYTES = 32 * 1024 * 1024


class TimetableFailure(Exception):
    """Safe API failure from missing or inconsistent schedule evidence."""

    def __init__(self, code: str = "DATA_UNAVAILABLE", status: int = 503):
        self.code = code
        self.status = status
        super().__init__(code)


class InvalidDepartureCursor(ValueError):
    """A cursor does not match this generation and exact departures query."""


def parse_dated_trip_id(value: str) -> tuple[date, str, str]:
    """Parse a complete MOTIS trip occurrence ID without trimming its source ID."""
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("Invalid dated trip ID")
    match = _TRIP_ID.fullmatch(value)
    if match is None:
        raise ValueError("Invalid dated trip ID")
    try:
        service_date = datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("Invalid service date") from exc
    hours, minutes, *seconds = (int(part) for part in match.group(2).split(":"))
    if minutes >= 60 or (seconds and seconds[0] >= 60):
        raise ValueError("Invalid start time")
    return service_date, match.group(2), match.group(3)


def _service_day_utc(service_date: date) -> datetime:
    """MOTIS/Nigiri service-day midnight using the noon-offset DST rule."""
    noon = datetime.combine(service_date, time(12), tzinfo=_JERUSALEM).astimezone(UTC)
    return noon - timedelta(hours=12)


def _stop_source_id(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Missing engine stop identity")
    if value.startswith("mot:stop:"):
        return value.removeprefix("mot:stop:")
    if not value.startswith(_MOTIS_NAMESPACE):
        raise ValueError("Unexpected engine stop namespace")
    return value.removeprefix(_MOTIS_NAMESPACE)


def _scheduled_clock(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid scheduled engine clock")
    return parse_utc_instant(value)


def _source_profile(reference, source_trip_id: str):
    try:
        return reference.source_profile(source_trip_id)
    except SourceProfileLimitError, OSError, sqlite3.Error:
        raise TimetableFailure("DATA_UNAVAILABLE", 503) from None


def _service_active(reference, service_id: str, service_date: date) -> bool | None:
    try:
        return reference.service_active(service_id, service_date)
    except OSError, sqlite3.Error:
        raise TimetableFailure("DATA_UNAVAILABLE", 503) from None


def _trip_vector(body: object, expected_id: str) -> tuple[dict, list[dict]]:
    if not isinstance(body, dict) or not isinstance(body.get("legs"), list):
        raise ValueError("Malformed engine trip response")
    matches = [leg for leg in body["legs"] if isinstance(leg, dict) and leg.get("mode") != "WALK"]
    if len(matches) != 1 or matches[0].get("tripId") != expected_id:
        raise ValueError("Engine trip response is not one exact dated occurrence")
    leg = matches[0]
    if leg.get("realTime") is not False or leg.get("cancelled") not in (False, None):
        raise ValueError("Unexpected live or cancelled schedule data")
    origin, destination = leg.get("from"), leg.get("to")
    middle = leg.get("intermediateStops", [])
    if (
        not isinstance(origin, dict)
        or not isinstance(destination, dict)
        or not isinstance(middle, list)
    ):
        raise ValueError("Malformed engine trip calls")
    calls = [origin]
    calls.extend(middle)
    calls.append(destination)
    if any(not isinstance(call, dict) for call in calls):
        raise ValueError("Malformed engine trip call")
    return leg, calls


def _expected_events(profile, service_date: date) -> tuple[ExpectedUtcEvent, ...]:
    from opentransit.core.trip_calls import project_profile

    projection = project_profile(profile)
    base = _service_day_utc(service_date)
    return tuple(
        ExpectedUtcEvent(
            event.sequence,
            event.ordinal,
            event.kind,
            event.effective_seconds,
            base + timedelta(seconds=event.effective_seconds),
        )
        for event in projection.events
    )


def hydrate_trip(profile, engine_id: str, body: object) -> dict:
    """Reconcile a complete dated engine occurrence and return original source calls."""
    service_date, start_time, source_id = parse_dated_trip_id(engine_id)
    if profile.trip_id != source_id:
        raise ReconciliationError("Dated engine ID source suffix differs from full source ID")
    leg, engine_calls = _trip_vector(body, engine_id)
    source_calls = profile.calls
    if len(source_calls) != len(engine_calls):
        raise ReconciliationError("Engine/source call count mismatch")

    reconciled_calls = []
    result_calls = []
    engine_pickup_types = []
    expected_events = _expected_events(profile, service_date)
    clocks_by_ordinal = {}
    for event in expected_events:
        clocks_by_ordinal.setdefault(event.ordinal, {})[event.kind] = event.at_utc
    for ordinal, (source, engine) in enumerate(zip(source_calls, engine_calls, strict=True)):
        stop_id = _stop_source_id(engine.get("stopId"))
        arrival = _scheduled_clock(engine.get("scheduledArrival"))
        departure = _scheduled_clock(engine.get("scheduledDeparture"))
        if engine.get("cancelled") is True:
            raise ReconciliationError("Cancelled calls are not a scheduled result")
        # Nigiri does not expose the two boundary events in its normalized call vector.
        reconciled_calls.append(
            EngineCall(
                stop_id,
                None if ordinal == 0 else arrival,
                None if ordinal == len(source_calls) - 1 else departure,
            )
        )
        engine_pickup_types.append(engine.get("pickupType"))
        expected_by_kind = clocks_by_ordinal.get(ordinal, {})
        result_calls.append(
            {
                "callSequence": source.sequence,
                "ordinal": source.ordinal,
                "stopId": f"mot:stop:{source.stop_id}",
                "scheduledArrival": (
                    expected_by_kind.get("arrival").isoformat().replace("+00:00", "Z")
                    if "arrival" in expected_by_kind
                    else None
                ),
                "scheduledDeparture": (
                    expected_by_kind.get("departure").isoformat().replace("+00:00", "Z")
                    if "departure" in expected_by_kind
                    else None
                ),
                "pickupType": source.pickup_type,
                "dropOffType": source.drop_off_type,
            }
        )
    engine_profile = EngineProfile(
        engine_trip_id=engine_id,
        source_trip_id=source_id,
        service_id=profile.service_id,
        service_date=service_date,
        calls=tuple(reconciled_calls),
    )
    result = reconcile_profile(
        profile,
        engine_profile,
        expected_engine_trip_id=engine_id,
        expected_service_date=service_date,
        expected_utc_events=expected_events,
    )
    shape = geometry(leg.get("legGeometry"))
    return {
        "tripRef": engine_id,
        "sourceTripId": source_id,
        "serviceDate": service_date.isoformat(),
        "startTime": start_time,
        "routeId": _public_route(leg.get("routeId")),
        "routeShortName": leg.get("routeShortName", ""),
        "headsign": leg.get("headsign"),
        "shape": shape.model_dump(mode="json") if shape else None,
        "calls": result_calls,
        "timingState": "scheduled",
        "expectedArrival": None,
        "expectedDeparture": None,
        "delaySeconds": None,
        "alerts": "not_enabled",
        "_reconciliation": result,
        "_engineCallPickupTypes": engine_pickup_types,
    }


def _public_route(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Missing route identity")
    if value.startswith("mot:route:"):
        return value
    if value.startswith("mot60day_"):
        value = value.removeprefix("mot60day_")
    else:
        raise ValueError("Unexpected engine route namespace")
    return f"mot:route:{value}"


async def _request_json(
    snapshot,
    path: str,
    params: dict,
    *,
    not_found: bool = False,
    byte_budget: dict[str, int] | None = None,
) -> object:
    try:
        async with snapshot.motis.client.stream("GET", path, params=params) as response:
            if response.status_code == 404 and not_found:
                raise TimetableFailure("NOT_FOUND", 404)
            response.raise_for_status()
            chunks = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > _ENGINE_RESPONSE_MAX_BYTES:
                    raise TimetableFailure("DATA_UNAVAILABLE", 503)
                if byte_budget is not None:
                    byte_budget["bytes"] += len(chunk)
                    if byte_budget["bytes"] > _DEPARTURES_TOTAL_RESPONSE_MAX_BYTES:
                        raise TimetableFailure("DATA_UNAVAILABLE", 503)
                chunks.append(chunk)
            return json.loads(b"".join(chunks))
    except TimetableFailure:
        raise
    except httpx.TimeoutException:
        raise TimetableFailure("ENGINE_TIMEOUT", 504) from None
    except httpx.HTTPStatusError:
        raise TimetableFailure() from None
    except httpx.HTTPError:
        raise TimetableFailure() from None
    except ValueError, TypeError, json.JSONDecodeError:
        raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503) from None


async def _fetch_trip(snapshot, profile, engine_id: str, *, byte_budget=None) -> dict:
    key = (snapshot.generation.id, engine_id)
    with _cache_lock:
        cached = _trip_cache.get(key)
        if cached is not None:
            _trip_cache.move_to_end(key)
            return cached
    body = await _request_json(
        snapshot,
        "/api/v6/trip",
        {
            "tripId": engine_id,
            "withScheduledSkippedStops": "true",
            "joinInterlinedLegs": "false",
            "detailedLegs": "true",
        },
        not_found=True,
        byte_budget=byte_budget,
    )
    try:
        result = hydrate_trip(profile, engine_id, body)
    except ValueError, KeyError, TypeError, IndexError:
        raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503) from None
    with _cache_lock:
        _trip_cache[key] = result
        _trip_cache.move_to_end(key)
        while len(_trip_cache) > _CACHE_SIZE:
            _trip_cache.popitem(last=False)
    return result


async def trip_detail(snapshot, engine_id: str) -> dict | None:
    if snapshot.reference is None or not snapshot.routing_verified:
        raise TimetableFailure()
    try:
        service_date, _, source_id = parse_dated_trip_id(engine_id)
    except ValueError:
        raise TimetableFailure("INVALID_REQUEST", 422) from None
    profile = _source_profile(snapshot.reference, source_id)
    if profile is None:
        return None
    active = _service_active(snapshot.reference, profile.service_id, service_date)
    if active is None:
        raise TimetableFailure("DATA_UNAVAILABLE", 503)
    if not active:
        return None
    expected = _expected_events(profile, service_date)
    if not expected or any(not snapshot.generation.contains(event.at_utc) for event in expected):
        raise TimetableFailure("OUTSIDE_SERVICE_WINDOW", 422)
    return await _fetch_trip(snapshot, profile, engine_id)


def _pickup_allowed(value: object) -> bool:
    return value in (0, 2, 3)


def _engine_boardable(value: object) -> bool:
    return value not in {"NOT_ALLOWED", "FORBIDDEN", 1, "1"}


def _departure_cursor(generation_id: str, query: dict, position: list) -> str:
    payload = {
        "v": 1,
        "g": generation_id,
        "q": hashlib.sha256(
            json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "p": position,
    }
    return (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


def _decode_departure_cursor(cursor: str | None, generation_id: str, query: dict):
    if cursor is None:
        return None
    try:
        if not isinstance(cursor, str) or len(cursor) > 2048:
            raise ValueError
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        payload = json.loads(raw)
        digest = hashlib.sha256(
            json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        position = payload["p"]
        if (
            payload["v"] != 1
            or payload["g"] != generation_id
            or payload["q"] != digest
            or not isinstance(position, list)
            or len(position) != 4
            or not all(isinstance(item, str) for item in position[:3])
            or isinstance(position[3], bool)
            or not isinstance(position[3], int)
            or position[3] < 0
        ):
            raise ValueError
        position_time = parse_utc_instant(position[0])
        if position_time.isoformat() != position[0]:
            raise ValueError
        if not (
            parse_utc_instant(query["from"]) <= position_time < parse_utc_instant(query["until"])
        ):
            raise ValueError
        parse_dated_trip_id(position[1])
        if position[2] not in query["stopIds"]:
            raise ValueError
        return position
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise InvalidDepartureCursor("Invalid departure cursor") from exc


async def departures(
    snapshot, stop_ref: str, start: datetime, horizon: int, limit: int, cursor: str | None
):
    """Return a replayable exact-window page; any incomplete upstream page fails closed."""
    if snapshot.reference is None or not snapshot.routing_verified:
        raise TimetableFailure()
    start_utc = as_utc_instant(start)
    end_utc = start_utc + timedelta(minutes=horizon)
    if not snapshot.generation.contains(start_utc) or end_utc > as_utc_instant(
        snapshot.generation.coverage_until
    ):
        raise TimetableFailure("OUTSIDE_SERVICE_WINDOW", 422)
    stop = snapshot.reference.stop(stop_ref)
    if stop is None:
        return None
    children = stop.get("children") or []
    stop_ids = [stop["source_id"], *(child["source_id"] for child in children)]
    stop_ids = list(dict.fromkeys(stop_ids))
    platform_codes = {stop["source_id"]: stop.get("platform_code")}
    platform_codes.update({child["source_id"]: child.get("platform_code") for child in children})
    query = {
        "stop": stop_ref,
        "stopIds": stop_ids,
        "from": start_utc.isoformat(),
        "until": end_utc.isoformat(),
        "horizonMinutes": horizon,
        "limit": limit,
    }
    after = _decode_departure_cursor(cursor, snapshot.generation.id, query)
    if after is not None and len(after) != 4:
        raise InvalidDepartureCursor("Invalid departure cursor position")
    events: dict[tuple, dict] = {}
    profiles: dict[str, tuple[object, dict]] = {}
    wire_event_count = 0
    byte_budget = {"bytes": 0}
    for source_stop_id in stop_ids:
        body = await _request_json(
            snapshot,
            "/api/v6/stoptimes",
            {
                "stopId": f"mot60day_{source_stop_id}",
                "time": engine_time(start_utc),
                "arriveBy": "false",
                "direction": "LATER",
                "window": str(horizon * 60),
                "n": "1",
                "exactRadius": "true",
                "radius": "0",
                "withScheduledSkippedStops": "true",
                "realtimeMode": "OFF",
                "withAlerts": "false",
            },
            byte_budget=byte_budget,
        )
        if not isinstance(body, dict) or not isinstance(body.get("stopTimes"), list):
            raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503)
        wire_items = body["stopTimes"]
        wire_event_count += len(wire_items)
        if wire_event_count > _DEPARTURES_MAX_EVENTS:
            raise TimetableFailure("DATA_UNAVAILABLE", 503)
        for item in wire_items:
            if (
                not isinstance(item, dict)
                or item.get("realTime") is not False
                or item.get("cancelled")
            ):
                raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503)
            place = item.get("place")
            if not isinstance(place, dict) or place.get("cancelled") not in (False, None):
                raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503)
            wire_stop = _stop_source_id(place.get("stopId"))
            clock_text = place.get("scheduledDeparture")
            try:
                at = _scheduled_clock(clock_text)
            except ValueError:
                raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503) from None
            if at is None or at < start_utc or at >= end_utc:
                continue
            engine_id = item.get("tripId")
            if not isinstance(engine_id, str):
                raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503)
            try:
                service_date, _, source_trip = parse_dated_trip_id(engine_id)
            except ValueError:
                raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503) from None
            if item.get("tripCancelled"):
                raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503)
            if engine_id not in profiles:
                profile = _source_profile(snapshot.reference, source_trip)
                if profile is None:
                    raise TimetableFailure("DATA_UNAVAILABLE", 503)
                active = _service_active(snapshot.reference, profile.service_id, service_date)
                if active is None:
                    raise TimetableFailure("DATA_UNAVAILABLE", 503)
                if not active:
                    raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503)
                trip = await _fetch_trip(snapshot, profile, engine_id, byte_budget=byte_budget)
                profiles[engine_id] = (profile, trip)
            profile, trip = profiles[engine_id]
            wire_call_matches = [
                call
                for call in trip["calls"]
                if call["stopId"] == f"mot:stop:{wire_stop}"
                and _scheduled_clock(call["scheduledDeparture"]) == at
            ]
            if not wire_call_matches:
                raise TimetableFailure("ENGINE_INVALID_RESPONSE", 503)
            matched_calls = [
                call
                for call in trip["calls"]
                if call["stopId"].removeprefix("mot:stop:") in stop_ids
                and _scheduled_clock(call["scheduledDeparture"]) == at
            ]
            for call in matched_calls:
                source = profile.calls[call["ordinal"]]
                engine_pickup = trip["_engineCallPickupTypes"][call["ordinal"]]
                if not _pickup_allowed(source.pickup_type) or not _engine_boardable(engine_pickup):
                    continue
                call_stop_id = source.stop_id
                exact = (at.isoformat(), engine_id, call_stop_id, source.sequence)
                events[exact] = {
                    "scheduledDeparture": at.isoformat().replace("+00:00", "Z"),
                    "stopId": f"mot:stop:{call_stop_id}",
                    "routeId": trip["routeId"],
                    "routeShortName": trip["routeShortName"],
                    "headsign": item.get("headsign") or trip.get("headsign"),
                    "platformCode": (
                        place.get("platformCode")
                        if call_stop_id == wire_stop
                        else platform_codes.get(call_stop_id)
                    )
                    or platform_codes.get(call_stop_id),
                    "pickupType": source.pickup_type,
                    "tripRef": engine_id,
                    "callSequence": source.sequence,
                }
    ordered = sorted(events.items(), key=lambda pair: pair[0])
    if after is not None:
        ordered = [entry for entry in ordered if list(entry[0]) > after]
    page = ordered[:limit]
    next_cursor = None
    if len(ordered) > limit and page:
        next_cursor = _departure_cursor(snapshot.generation.id, query, list(page[-1][0]))
    return {"items": [item for _, item in page], "nextCursor": next_cursor}
