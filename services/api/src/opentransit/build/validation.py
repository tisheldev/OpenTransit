"""Streaming GTFS and TripIdToDate validation for immutable build inputs.

This module intentionally has no dependency on ``poc`` code. It keeps only
entity keys, service dates, and small evidence samples in memory; large
``stop_times.txt`` and ``shapes.txt`` members are read one row at a time.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import math
import sqlite3
import stat
import tempfile
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

from opentransit.core.trip_calls import (
    POLICY_ID,
    TripCallError,
    project_profile,
    source_profile_from_rows,
)


class FeedValidationError(ValueError):
    """The candidate inputs cannot safely form a scheduled generation."""

    def __init__(self, report: ValidationReport):
        self.report = report
        failed = [check["id"] for check in report.checks if check["status"] == "fail"]
        super().__init__(f"feed validation failed: {', '.join(failed)}")


@dataclass
class CheckResult:
    id: str
    name: str
    status: str
    detail: str
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationReport:
    gtfs_path: Path
    mapping_path: Path
    checks: list[dict]
    integrity: dict
    service_dates: list[str]
    coverage: dict
    pairing: dict

    @property
    def valid(self) -> bool:
        return not any(check["status"] == "fail" for check in self.checks)

    def as_dict(self) -> dict:
        return {
            "gtfsPath": str(self.gtfs_path),
            "tripIdToDatePath": str(self.mapping_path),
            "valid": self.valid,
            "checks": self.checks,
            "integrity": self.integrity,
            "serviceDates": self.service_dates,
            "coverage": self.coverage,
            "pairing": self.pairing,
        }


REQUIRED = ("agency.txt", "routes.txt", "trips.txt", "stops.txt", "stop_times.txt")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MAX_CALENDAR_SPAN_DAYS = 400


def _rows(archive: zipfile.ZipFile, member: str):
    """Yield strict UTF-8 CSV records and row shape observations."""
    with (
        archive.open(member) as raw,
        io.TextIOWrapper(raw, encoding="utf-8-sig", errors="strict", newline="") as text,
    ):
        reader = csv.DictReader(text)
        if not reader.fieldnames:
            raise ValueError(f"{member} is empty or has no header")
        header = [field.strip() for field in reader.fieldnames]
        if len(header) != len(set(header)) or any(not name for name in header):
            raise ValueError(f"{member} has blank or duplicate column names")
        for row in reader:
            short = any(v is None for k, v in row.items() if k is not None)
            yield (
                reader.line_num,
                {str(k).strip(): (v or "").strip() for k, v in row.items() if k is not None},
                (row.get(None) or ("short" if short else None)),
            )


def _iso_date(value: str, member: str, line: int) -> dt.date:
    try:
        if len(value) != 8 or not value.isdecimal():
            raise ValueError
        return dt.datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"{member}:{line} has invalid YYYYMMDD date {value!r}") from exc


def _mapping_date(value: str, member: str, line: int) -> dt.date:
    try:
        return dt.datetime.strptime(value.split(" ", 1)[0], "%d/%m/%Y").date()
    except ValueError as exc:
        raise ValueError(f"{member}:{line} has invalid DD/MM/YYYY date {value!r}") from exc


def _mapping_weekday(day: dt.date) -> int:
    """MOT mapping convention: Sunday=1 through Saturday=7."""
    return (day.weekday() + 1) % 7 + 1


def _time_seconds(value: str, member: str, line: int) -> int:
    try:
        parts = value.split(":")
        if len(parts) != 3 or not all(part.isdecimal() for part in parts):
            raise ValueError
        hours, minutes, seconds = (int(part) for part in parts)
        if minutes > 59 or seconds > 59:
            raise ValueError
        return hours * 3600 + minutes * 60 + seconds
    except ValueError as exc:
        raise ValueError(f"{member}:{line} has invalid GTFS time {value!r}") from exc


def _format_gtfs_time(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _stop_time_spool(directory: Path | None = None):
    """Disk-backed stop-time uniqueness and chronology index."""
    temporary = tempfile.TemporaryDirectory(prefix="opentransit-validation-", dir=directory)
    connection = sqlite3.connect(Path(temporary.name) / "stop-times.sqlite")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA cache_size=-8192")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute(
        "CREATE TABLE calls (trip_id TEXT NOT NULL, sequence INTEGER NOT NULL, "
        "arrival INTEGER, departure INTEGER, arrival_raw TEXT, departure_raw TEXT, "
        "source_line INTEGER NOT NULL, stop_id TEXT NOT NULL, pickup_type INTEGER NOT NULL, "
        "drop_off_type INTEGER NOT NULL, "
        "PRIMARY KEY (trip_id, sequence)) WITHOUT ROWID"
    )
    return temporary, connection


def _date_range(start: dt.date, end: dt.date, member: str, line: int) -> list[dt.date]:
    if end < start:
        raise ValueError(f"{member}:{line} has reversed date range {start}..{end}")
    if (end - start).days > MAX_CALENDAR_SPAN_DAYS:
        raise ValueError(f"{member}:{line} exceeds {MAX_CALENDAR_SPAN_DAYS}-day span")
    return [start + dt.timedelta(days=offset) for offset in range((end - start).days + 1)]


def _add_unique(target: set[str], value: str, member: str, line: int, samples: list[str]) -> None:
    if not value:
        raise ValueError(f"{member}:{line} has a blank identifier")
    if value in target:
        if len(samples) < 5:
            samples.append(f"{member}:{line} duplicate id {value!r}")
    target.add(value)


def _check(status: str, check_id: str, name: str, detail: str, **evidence) -> dict:
    return CheckResult(check_id, name, status, detail, evidence).as_dict()


def _check_archive_paths(archive: zipfile.ZipFile, label: str) -> None:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ValueError(f"{label} archive contains duplicate member names")
    for info in infos:
        member = PurePosixPath(info.filename)
        if member.is_absolute() or ".." in member.parts or "\\" in info.filename:
            raise ValueError(f"{label} archive contains unsafe member path {info.filename!r}")
        if info.flag_bits & 0x1 or stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError(f"{label} archive contains unsupported encrypted/symlink member")


def validate_feed(
    gtfs_path: Path,
    trip_id_to_date_path: Path,
    *,
    spool_directory: Path | None = None,
) -> ValidationReport:
    """Validate scheduled feed structure, ten POC-1 checks, and date-aware pairing.

    Returns a report even when individual integrity checks fail. Structural
    failures that prevent a meaningful parse raise ``ValueError``; callers
    should treat either outcome as a failed candidate and must not activate it.
    """
    gtfs_path, trip_id_to_date_path = Path(gtfs_path), Path(trip_id_to_date_path)
    checks: list[dict] = []
    integrity: dict[str, dict] = {}
    rows_seen: Counter[str] = Counter()
    duplicates: dict[str, list[str]] = defaultdict(list)

    with zipfile.ZipFile(gtfs_path) as archive:
        _check_archive_paths(archive, "GTFS")
        names = set(archive.namelist())
        missing = set(REQUIRED) - names
        if missing:
            raise ValueError(f"GTFS archive missing required members: {sorted(missing)}")
        if not ({"calendar.txt", "calendar_dates.txt"} & names):
            raise ValueError("GTFS archive needs calendar.txt or calendar_dates.txt")

        agencies: set[str] = set()
        routes: set[str] = set()
        route_agencies: dict[str, str] = {}
        agency_names: dict[str, str] = {}
        service_ids: set[str] = set()
        stops: dict[str, dict] = {}
        trips: dict[str, str] = {}
        trip_routes: dict[str, str] = {}
        services: dict[str, set[dt.date]] = defaultdict(set)
        active_dates: set[dt.date] = set()
        fk = Counter()
        coordinate_errors = 0
        fk_samples: dict[str, list[str]] = defaultdict(list)
        malformed: Counter[str] = Counter()
        max_service_time = 0
        max_service_time_raw = None
        after_midnight_rows = 0
        time_checks = Counter()
        shapes: set[str] = set()
        shape_coord_errors = 0
        translation_languages: Counter[str] = Counter()
        translation_schema = None

        for member, target, key in (
            ("agency.txt", agencies, "agency_id"),
            ("routes.txt", routes, "route_id"),
        ):
            for line, row, extra in _rows(archive, member):
                rows_seen[member] += 1
                if extra:
                    malformed[member] += 1
                _add_unique(target, row.get(key, ""), member, line, duplicates[member])
                if member == "agency.txt":
                    agency_names[row[key]] = row.get("agency_name", "")
                if member == "routes.txt":
                    route_agencies[row[key]] = row.get("agency_id", "")
        if agencies:
            for _route_id, agency_id in route_agencies.items():
                if agency_id and agency_id not in agencies:
                    fk["routes_with_unknown_agency"] += 1

        for line, row, extra in _rows(archive, "stops.txt"):
            rows_seen["stops.txt"] += 1
            if extra:
                malformed["stops.txt"] += 1
            stop_id = row.get("stop_id", "")
            if not stop_id:
                raise ValueError(f"stops.txt:{line} has a blank identifier")
            if stop_id in stops:
                if len(duplicates["stops.txt"]) < 5:
                    duplicates["stops.txt"].append(f"stops.txt:{line} duplicate id {stop_id!r}")
            try:
                lat_s, lon_s = row.get("stop_lat", ""), row.get("stop_lon", "")
                if bool(lat_s) != bool(lon_s):
                    raise ValueError
                if lat_s and lon_s:
                    lat, lon = float(lat_s), float(lon_s)
                    if not (
                        math.isfinite(lat)
                        and math.isfinite(lon)
                        and -90 <= lat <= 90
                        and -180 <= lon <= 180
                    ):
                        raise ValueError
            except ValueError:
                coordinate_errors += 1
                if len(fk_samples["stops_with_invalid_coordinates"]) < 5:
                    fk_samples["stops_with_invalid_coordinates"].append(
                        f"stops.txt:{line} stop {stop_id}"
                    )
            stops[stop_id] = row

        if "calendar.txt" in names:
            for line, row, extra in _rows(archive, "calendar.txt"):
                rows_seen["calendar.txt"] += 1
                if extra:
                    malformed["calendar.txt"] += 1
                service_id = row.get("service_id", "")
                if not service_id:
                    raise ValueError(f"calendar.txt:{line} has blank service_id")
                if service_id in service_ids:
                    duplicates["calendar.txt"].append(f"calendar.txt:{line} duplicate {service_id}")
                service_ids.add(service_id)
                services.setdefault(service_id, set())
                start = _iso_date(row.get("start_date", ""), "calendar.txt", line)
                end = _iso_date(row.get("end_date", ""), "calendar.txt", line)
                for day in _date_range(start, end, "calendar.txt", line):
                    try:
                        active = row[WEEKDAYS[day.weekday()]] == "1"
                    except KeyError as exc:
                        raise ValueError(
                            f"calendar.txt missing weekday field {exc.args[0]}"
                        ) from exc
                    if row[WEEKDAYS[day.weekday()]] not in {"0", "1"}:
                        raise ValueError(f"calendar.txt:{line} has invalid weekday flag")
                    if active:
                        services[service_id].add(day)
        if "calendar_dates.txt" in names:
            for line, row, extra in _rows(archive, "calendar_dates.txt"):
                rows_seen["calendar_dates.txt"] += 1
                if extra:
                    malformed["calendar_dates.txt"] += 1
                service_id = row.get("service_id", "")
                day = _iso_date(row.get("date", ""), "calendar_dates.txt", line)
                exception = row.get("exception_type", "")
                if exception == "1":
                    services[service_id].add(day)
                elif exception == "2":
                    services[service_id].discard(day)
                else:
                    raise ValueError(
                        f"calendar_dates.txt:{line} invalid exception_type {exception!r}"
                    )
        for line, row, extra in _rows(archive, "trips.txt"):
            rows_seen["trips.txt"] += 1
            if extra:
                malformed["trips.txt"] += 1
            trip_id = row.get("trip_id", "")
            if not trip_id:
                raise ValueError(f"trips.txt:{line} has blank trip_id")
            if trip_id in trips:
                duplicates["trips.txt"].append(f"trips.txt:{line} duplicate {trip_id}")
            route_id, service_id = row.get("route_id", ""), row.get("service_id", "")
            if route_id not in routes:
                fk["trips_with_unknown_route"] += 1
            if service_id not in services:
                fk["trips_with_unknown_service"] += 1
            trips[trip_id] = service_id
            trip_routes[trip_id] = route_id

        referenced_services = set(trips.values())
        active_dates = (
            set().union(
                *(
                    services[service_id]
                    for service_id in referenced_services
                    if service_id in services
                )
            )
            if referenced_services
            else set()
        )
        if not active_dates:
            raise ValueError("GTFS trips define no active service dates")

        parent_edges: dict[str, str] = {}
        for stop_id, row in stops.items():
            parent_id = row.get("parent_station", "")
            if parent_id:
                if parent_id not in stops:
                    fk["stops_with_unknown_parent"] += 1
                else:
                    parent_edges[stop_id] = parent_id
        cyclic_parent_ids: set[str] = set()
        for start in parent_edges:
            seen: set[str] = set()
            current = start
            while current in parent_edges:
                if current in seen:
                    cyclic_parent_ids.update(seen)
                    break
                seen.add(current)
                current = parent_edges[current]
        fk["stops_in_parent_cycle"] = len(cyclic_parent_ids)

        seen_trips: set[str] = set()
        stop_time_rows = 0
        pickup_dropoff_errors = 0
        spool, calls = _stop_time_spool(spool_directory)
        profile_cursor = None
        try:
            for line, row, extra in _rows(archive, "stop_times.txt"):
                stop_time_rows += 1
                if extra:
                    malformed["stop_times.txt"] += 1
                trip_id, stop_id = row.get("trip_id", ""), row.get("stop_id", "")
                if trip_id not in trips:
                    fk["stop_times_with_unknown_trip"] += 1
                if stop_id not in stops:
                    fk["stop_times_with_unknown_stop"] += 1
                sequence_raw = row.get("stop_sequence", "")
                try:
                    sequence = int(sequence_raw)
                    if sequence < 0:
                        raise ValueError
                except ValueError as exc:
                    raise ValueError(f"stop_times.txt:{line} has invalid stop_sequence") from exc
                parsed_times = {}
                for field_name in ("arrival_time", "departure_time"):
                    value = row.get(field_name, "")
                    parsed_times[field_name] = (
                        _time_seconds(value, "stop_times.txt", line) if value else None
                    )
                    seconds = parsed_times[field_name]
                    if seconds is not None:
                        if seconds > max_service_time:
                            max_service_time = seconds
                            max_service_time_raw = value
                        if seconds >= 86400:
                            after_midnight_rows += 1
                arrival, departure = parsed_times["arrival_time"], parsed_times["departure_time"]
                if arrival is not None and departure is not None and departure < arrival:
                    time_checks["departure_before_arrival"] += 1
                for field_name in ("pickup_type", "drop_off_type"):
                    value = row.get(field_name, "") or "0"
                    if value not in {"0", "1", "2", "3"}:
                        pickup_dropoff_errors += 1
                pickup = row.get("pickup_type", "") or "0"
                dropoff = row.get("drop_off_type", "") or "0"
                pickup_value = int(pickup) if pickup in {"0", "1", "2", "3"} else -1
                dropoff_value = int(dropoff) if dropoff in {"0", "1", "2", "3"} else -1
                before = calls.total_changes
                calls.execute(
                    "INSERT OR IGNORE INTO calls VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        trip_id,
                        sequence,
                        arrival,
                        departure,
                        row.get("arrival_time") or None,
                        row.get("departure_time") or None,
                        line,
                        stop_id,
                        pickup_value,
                        dropoff_value,
                    ),
                )
                if calls.total_changes == before:
                    time_checks["duplicate_trip_stop_sequence"] += 1
                seen_trips.add(trip_id)
            calls.commit()
            chronology_query = (
                "WITH ordered AS (SELECT trip_id, sequence, arrival, departure, "
                "arrival_raw, departure_raw, source_line, "
                "LAG(sequence) OVER (PARTITION BY trip_id ORDER BY sequence) previous_sequence, "
                "LAG(COALESCE(departure, arrival)) OVER "
                "(PARTITION BY trip_id ORDER BY sequence) previous_seconds, "
                "LAG(COALESCE(departure_raw, arrival_raw)) OVER "
                "(PARTITION BY trip_id ORDER BY sequence) previous_raw, "
                "LAG(source_line) OVER (PARTITION BY trip_id ORDER BY sequence) previous_line "
                "FROM calls WHERE arrival IS NOT NULL OR departure IS NOT NULL) "
                "SELECT trip_id, previous_sequence, sequence, previous_raw, "
                "COALESCE(arrival_raw, departure_raw), previous_line, source_line "
                "FROM ordered WHERE previous_seconds IS NOT NULL "
                "AND COALESCE(arrival, departure) < previous_seconds ORDER BY trip_id, sequence"
            )
            chronology_count = calls.execute(
                "WITH ordered AS (SELECT trip_id, sequence, arrival, departure, "
                "LAG(COALESCE(departure, arrival)) OVER "
                "(PARTITION BY trip_id ORDER BY sequence) previous_seconds FROM calls "
                "WHERE arrival IS NOT NULL OR departure IS NOT NULL) "
                "SELECT COUNT(*) FROM ordered WHERE previous_seconds IS NOT NULL "
                "AND COALESCE(arrival, departure) < previous_seconds"
            ).fetchone()[0]
            chronology_samples = []
            chronology_agencies: set[str] = set()
            chronology_trip_count = calls.execute(
                "WITH ordered AS (SELECT trip_id, sequence, arrival, departure, "
                "LAG(COALESCE(departure, arrival)) OVER "
                "(PARTITION BY trip_id ORDER BY sequence) previous_seconds FROM calls "
                "WHERE arrival IS NOT NULL OR departure IS NOT NULL) "
                "SELECT COUNT(DISTINCT trip_id) FROM ordered "
                "WHERE previous_seconds IS NOT NULL "
                "AND COALESCE(arrival, departure) < previous_seconds"
            ).fetchone()[0]
            affected_trips_query = (
                "WITH ordered AS (SELECT trip_id, sequence, arrival, departure, "
                "LAG(COALESCE(departure, arrival)) OVER "
                "(PARTITION BY trip_id ORDER BY sequence) previous_seconds FROM calls "
                "WHERE arrival IS NOT NULL OR departure IS NOT NULL) "
                "SELECT DISTINCT trip_id FROM ordered "
                "WHERE previous_seconds IS NOT NULL "
                "AND COALESCE(arrival, departure) < previous_seconds"
            )
            for (trip_id,) in calls.execute(affected_trips_query):
                agency_id = route_agencies.get(trip_routes.get(trip_id, ""), "")
                if agency_id:
                    chronology_agencies.add(agency_id)
            for sample_row in calls.execute(chronology_query):
                trip_id = sample_row[0]
                agency_id = route_agencies.get(trip_routes.get(trip_id, ""), "")
                if len(chronology_samples) < 20:
                    chronology_samples.append(
                        {
                            "tripId": trip_id,
                            "routeId": trip_routes.get(trip_id),
                            "serviceId": trips.get(trip_id),
                            "agencyId": agency_id or None,
                            "agencyName": agency_names.get(agency_id) or None,
                            "operatorId": agency_id or None,
                            "operatorName": agency_names.get(agency_id) or None,
                            "previousSequence": sample_row[1],
                            "sequence": sample_row[2],
                            "previousTime": sample_row[3],
                            "currentTime": sample_row[4],
                            "previousSourceLine": sample_row[5],
                            "sourceLine": sample_row[6],
                        }
                    )
            time_checks["non_chronological_stop_times"] = chronology_count
            time_checks["cross_call_chronology"] = {
                "count": chronology_count,
                "verdict": "diagnostic_fail" if chronology_count else "pass",
                "blocking": False,
                "affectedTripCount": chronology_trip_count,
                "affectedAgencyCount": len(chronology_agencies),
                "affectedOperatorCount": len(chronology_agencies),
                "affectedAgencyIds": sorted(chronology_agencies)[:20],
                "affectedOperators": [
                    {
                        "id": agency_id,
                        "name": agency_names.get(agency_id) or None,
                    }
                    for agency_id in sorted(chronology_agencies)[:20]
                ],
                "samples": chronology_samples,
            }
            time_checks["pickup_dropoff_rule_errors"] = pickup_dropoff_errors

            effective_event_count = 0
            effective_profile_count = 0
            effective_projection_errors = 0
            effective_samples = []
            profile_cursor = calls.execute(
                "SELECT trip_id, sequence, arrival, departure, stop_id, pickup_type, "
                "drop_off_type, source_line FROM calls ORDER BY trip_id, sequence"
            )
            profile_trip_id = None
            profile_rows = []

            def validate_profile():
                nonlocal effective_event_count, effective_profile_count
                nonlocal effective_projection_errors
                if not profile_rows:
                    return
                service_id = trips.get(profile_trip_id)
                try:
                    profile = source_profile_from_rows(
                        profile_trip_id,
                        service_id or "",
                        [
                            {
                                "trip_id": profile_trip_id,
                                "service_id": service_id,
                                "stop_sequence": str(row["sequence"]),
                                "stop_id": row["stop_id"],
                                "arrival_seconds": row["arrival"],
                                "departure_seconds": row["departure"],
                                "pickup_type": row["pickup_type"],
                                "drop_off_type": row["drop_off_type"],
                            }
                            for row in profile_rows
                        ],
                    )
                    projection = project_profile(profile)
                    expected_events = max(0, 2 * len(profile.calls) - 2)
                    if len(projection.events) != expected_events:
                        raise TripCallError(
                            "Required effective clock event is missing; interpolation is unverified"
                        )
                    effective_event_count += len(projection.events)
                    effective_profile_count += 1
                except (TripCallError, TypeError, ValueError) as exc:
                    effective_projection_errors += 1
                    if len(effective_samples) < 20:
                        effective_samples.append(
                            {
                                "tripId": profile_trip_id,
                                "serviceId": service_id,
                                "sourceLineStart": profile_rows[0]["source_line"],
                                "sourceLineEnd": profile_rows[-1]["source_line"],
                                "error": str(exc),
                            }
                        )

            for row in profile_cursor:
                if profile_trip_id is not None and row["trip_id"] != profile_trip_id:
                    validate_profile()
                    profile_rows = []
                if row["trip_id"] != profile_trip_id:
                    profile_trip_id = row["trip_id"]
                profile_rows.append(row)
            validate_profile()
            missing_profiles = sum(trip_id not in seen_trips for trip_id in trips)
            if missing_profiles:
                effective_projection_errors += missing_profiles
                if len(effective_samples) < 20:
                    effective_samples.append(
                        {
                            "error": "Trip definitions without stop-time calls",
                            "count": missing_profiles,
                        }
                    )
            time_checks["effective_chronology"] = {
                "policyId": POLICY_ID,
                "status": "fail" if effective_projection_errors else "pass",
                "blocking": True,
                "feedTripCount": len(trips),
                "validatedProfileCount": effective_profile_count,
                "effectiveEventCount": effective_event_count,
                "profileErrorCount": effective_projection_errors,
                "samples": effective_samples,
                "bounds": {
                    "resolutionSeconds": 60,
                    "eventFloorCeiling": "every effective event remains inside its raw minute",
                    "intervalDistortionStrictlyLessThanSeconds": 60,
                    "firstArrivalProjected": False,
                    "finalDepartureProjected": False,
                },
            }
        finally:
            if profile_cursor is not None:
                profile_cursor.close()
            calls.close()
            spool.cleanup()
        fk["trips_with_no_stop_times"] = sum(trip_id not in seen_trips for trip_id in trips)

        if "shapes.txt" in names:
            for line, row, extra in _rows(archive, "shapes.txt"):
                rows_seen["shapes.txt"] += 1
                if extra:
                    malformed["shapes.txt"] += 1
                shape_id = row.get("shape_id", "")
                if not shape_id:
                    raise ValueError(f"shapes.txt:{line} has blank shape_id")
                shapes.add(shape_id)
                try:
                    lat, lon = float(row["shape_pt_lat"]), float(row["shape_pt_lon"])
                    if not (
                        math.isfinite(lat)
                        and math.isfinite(lon)
                        and -90 <= lat <= 90
                        and -180 <= lon <= 180
                    ):
                        raise ValueError
                    int(row["shape_pt_sequence"])
                except KeyError, ValueError:
                    shape_coord_errors += 1
        unknown_shapes = 0
        if "shapes.txt" in names:
            # trips are small relative to stop_times; retain their shape ids in
            # this separate streaming scan rather than retaining all trip rows.
            with zipfile.ZipFile(gtfs_path) as trip_archive:
                for _, row, _ in _rows(trip_archive, "trips.txt"):
                    shape_id = row.get("shape_id", "")
                    if shape_id and shape_id not in shapes:
                        unknown_shapes += 1

        if "translations.txt" in names:
            for _line, row, extra in _rows(archive, "translations.txt"):
                rows_seen["translations.txt"] += 1
                if extra:
                    malformed["translations.txt"] += 1
                if translation_schema is None:
                    translation_schema = (
                        "gtfs-official"
                        if "language" in row
                        else "mot-legacy"
                        if "lang" in row
                        else "unrecognised"
                    )
                language_key = "language" if "language" in row else "lang"
                language = row.get(language_key, "")
                if language:
                    translation_languages[language] += 1

    for table, samples in duplicates.items():
        integrity[f"duplicate_{table.removesuffix('.txt')}_ids"] = {
            "count": len(samples),
            "samples": samples[:5],
        }
    integrity["foreign_keys"] = {"counts": dict(fk), "samples": dict(fk_samples)}
    integrity["stop_coordinates"] = {
        "invalidRows": coordinate_errors,
        "samples": fk_samples.get("stops_with_invalid_coordinates", []),
    }
    integrity["malformed_rows"] = dict(malformed)
    integrity["shape_references"] = {
        "unknown_trip_shapes": unknown_shapes,
        "invalid_shape_points": shape_coord_errors,
    }
    integrity["time_integrity"] = {
        "stopTimeRows": stop_time_rows,
        "afterMidnightRows": after_midnight_rows,
        "maxSeconds": max_service_time,
        "maxTimeRoundTrip": {
            "raw": max_service_time_raw,
            "formatted": _format_gtfs_time(max_service_time),
            "matches": (
                max_service_time_raw is not None
                and _time_seconds(_format_gtfs_time(max_service_time), "stop_times.txt", 0)
                == max_service_time
            ),
        },
        **dict(time_checks),
    }
    integrity["translations"] = {
        "rows": rows_seen["translations.txt"],
        "schema": translation_schema,
        "languages": dict(translation_languages),
    }

    # TripIdToDate dates are retained by full GTFS trip id and service id below.
    mapping_rows: dict[str, list[tuple[dt.date, dt.date, int]]] = defaultdict(list)
    mapping_bad_ranges: list[str] = []
    with zipfile.ZipFile(trip_id_to_date_path) as mapping_archive:
        _check_archive_paths(mapping_archive, "TripIdToDate")
        if "TripIdToDate.txt" not in mapping_archive.namelist():
            raise ValueError("TripIdToDate archive has no TripIdToDate.txt")
        for line, row, extra in _rows(mapping_archive, "TripIdToDate.txt"):
            rows_seen["TripIdToDate.txt"] += 1
            if extra and extra != [""]:
                malformed["TripIdToDate.txt"] += 1
            trip_key = row.get("TripId", "").split("_", 1)[0]
            if not trip_key:
                raise ValueError(f"TripIdToDate.txt:{line} has blank TripId")
            start = _mapping_date(row.get("FromDate", ""), "TripIdToDate.txt", line)
            end = _mapping_date(row.get("ToDate", ""), "TripIdToDate.txt", line)
            try:
                day_in_week = int(row.get("DayInWeek", ""))
            except ValueError as exc:
                raise ValueError(f"TripIdToDate.txt:{line} has invalid DayInWeek") from exc
            if day_in_week not in range(1, 8):
                raise ValueError(f"TripIdToDate.txt:{line} has invalid DayInWeek {day_in_week}")
            if end < start:
                mapping_bad_ranges.append(f"TripIdToDate.txt:{line} {start}..{end}")
                continue
            mapping_rows[trip_key].append((start, end, day_in_week))

    # The base ID only locates candidate mapping rows. Every match below is
    # reported against the complete trip_id and its actual GTFS service dates.
    trip_samples: list[dict] = []
    missing_trip_dates = []
    partially_mapped_trip_dates: set[dt.date] = set()
    service_date_pairs_evaluated = 0
    dormant_trip_definitions = 0
    pair_keys = {key for key, ranges in mapping_rows.items() if ranges}
    mapped_service_dates: set[dt.date] = set()
    for trip_id, service_id in trips.items():
        dates = sorted(services.get(service_id, set()))
        if not dates:
            dormant_trip_definitions += 1
        service_date_pairs_evaluated += len(dates)
        key = trip_id.split("_", 1)[0]
        ranges = mapping_rows.get(key, [])
        covered = [
            day
            for day in dates
            if any(
                start <= day <= end and weekday == _mapping_weekday(day)
                for start, end, weekday in ranges
            )
        ]
        mapped_service_dates.update(covered)
        if dates and len(covered) != len(dates):
            missing_trip_dates.append(trip_id)
            partially_mapped_trip_dates.update(day for day in dates if day not in set(covered))
        if len(trip_samples) < 20:
            trip_samples.append(
                {
                    "tripId": trip_id,
                    "serviceId": service_id,
                    "activeServiceDateCount": len(dates),
                    "mappingDateCount": len(covered),
                    "mappingServiceDates": [day.isoformat() for day in covered],
                }
            )
    unmatched_keys = sorted({trip_id.split("_", 1)[0] for trip_id in trips} - pair_keys)
    mapping_start = min(
        (start for ranges in mapping_rows.values() for start, _, _ in ranges),
        default=None,
    )
    mapping_end = max(
        (end for ranges in mapping_rows.values() for _, end, _ in ranges),
        default=None,
    )
    feed_start, feed_end = min(active_dates), max(active_dates)
    date_windows_overlap = bool(
        mapping_start and mapping_end and not (mapping_end < feed_start or mapping_start > feed_end)
    )
    for sample in chronology_samples:
        service_days = services.get(sample["serviceId"], set())
        sample["activeServiceDateCount"] = len(service_days)
        sample["dormant"] = not service_days
        sample["activeInImportWindow"] = any(feed_start <= day <= feed_end for day in service_days)
    pairing = {
        "feedTripCount": len(trips),
        "fullTripIdentityCount": len(trips),
        "dormantTripDefinitions": dormant_trip_definitions,
        "serviceDatePairsEvaluated": service_date_pairs_evaluated,
        "feedJoinKeyCount": len({t.split("_", 1)[0] for t in trips}),
        "mappingKeyCount": len(pair_keys),
        "unmatchedJoinKeyCount": len(unmatched_keys),
        "unmatchedJoinKeySamples": unmatched_keys[:10],
        "tripsWithoutMappedServiceDates": len(missing_trip_dates),
        "tripSamplesWithoutMappedDates": missing_trip_dates[:10],
        "unmappedActiveServiceDateCount": len(partially_mapped_trip_dates),
        "unmappedServiceDateSamples": [
            d.isoformat() for d in sorted(partially_mapped_trip_dates)[:20]
        ],
        "matchedServiceDateCount": len(mapped_service_dates),
        "feedServiceDateCount": len(active_dates),
        "feedServiceDates": [d.isoformat() for d in sorted(active_dates)],
        "mappingDateRange": (
            [mapping_start.isoformat(), mapping_end.isoformat()]
            if mapping_start and mapping_end
            else None
        ),
        "feedDateWindow": [feed_start.isoformat(), feed_end.isoformat()],
        "dateWindowsOverlap": date_windows_overlap,
        "staticPairingVerdict": (
            "ACCEPTED"
            if trips and not unmatched_keys and date_windows_overlap and not mapping_bad_ranges
            else "REJECTED"
        ),
        "serviceDateCoverageDiagnostic": "warning_only_not_realtime_proof",
        "reversedRanges": mapping_bad_ranges[:10],
        "fullTripIdentityUsedForValidation": True,
        "tripDateEvidenceSamples": trip_samples,
    }

    fk_failures = {key: count for key, count in fk.items() if count}
    duplicate_count = sum(len(items) for items in duplicates.values())
    malformed_count = sum(malformed.values())
    shape_bad = bool(unknown_shapes or shape_coord_errors)
    effective_integrity = integrity.get("time_integrity", {}).get("effective_chronology", {})
    bad_time = bool(
        time_checks["departure_before_arrival"]
        or time_checks["duplicate_trip_stop_sequence"]
        or time_checks["pickup_dropoff_rule_errors"]
        or effective_integrity.get("profileErrorCount", 0)
    )
    bad_coordinates = bool(coordinate_errors)
    bad_parent = bool(fk["stops_with_unknown_parent"] or fk["stops_in_parent_cycle"])
    no_translations = "translations.txt" not in names
    checks.extend(
        [
            _check(
                "not_observed",
                "E01",
                "GET content hash and archive validation",
                "Package uses full GET, SHA-256, and ZIP checks without HEAD; live HEAD/GET "
                "comparison and refresh run were not performed.",
                liveFetch="not_observed",
                codePath="implemented",
            ),
            _check(
                (
                    "not_observed"
                    if after_midnight_rows == 0
                    else "pass"
                    if integrity["time_integrity"]["maxTimeRoundTrip"]["matches"]
                    else "fail"
                ),
                "E02",
                "GTFS stop times",
                "Stop times were streamed and parsed, including values over 24:00:00.",
                afterMidnightRows=after_midnight_rows,
                maxSeconds=max_service_time,
                integrity=integrity["time_integrity"],
            ),
            _check(
                "not_observed",
                "E03",
                "Hebrew encoding round-trip",
                "CSV text decoded as strict UTF-8, but a database write/read round-trip is "
                "outside feed validation.",
                strictUtf8=True,
                databaseRoundTrip="not_observed",
            ),
            _check(
                (
                    "not_observed"
                    if no_translations
                    else "fail"
                    if malformed.get("translations.txt")
                    else "pass"
                ),
                "E04",
                "Translations parsing and preservation",
                "Translations were parsed without sanitization."
                if not no_translations
                else "translations.txt is absent from this feed.",
                **integrity["translations"],
            ),
            _check(
                "pass"
                if trips and not unmatched_keys and date_windows_overlap and not mapping_bad_ranges
                else "fail",
                "E05",
                "TripIdToDate key and service-window pairing",
                "Static acceptance requires complete normalized key coverage and an overlapping "
                "known date window. Per-full-trip service-date and weekday gaps are diagnostic "
                "warnings, not realtime matching proof.",
                **{k: v for k, v in pairing.items() if k != "tripDateEvidence"},
            ),
            _check(
                "not_observed",
                "E06",
                "Primary versus comparison feed",
                "The schedule generation validates the accepted 60-day feed; the 10-day "
                "comparison feed was not fetched.",
                comparison="not_observed",
            ),
            _check(
                "not_observed",
                "E07",
                "Service exceptions and reduced service",
                "Actual active service dates were expanded; Shabbat/festival counts and "
                "reduced-service evidence were not computed.",
                calendarRows=rows_seen["calendar.txt"],
                calendarDatesRows=rows_seen["calendar_dates.txt"],
                activeServiceDateCount=len(active_dates),
                dates=[d.isoformat() for d in sorted(active_dates)],
            ),
            _check(
                "pass" if not fk_failures else "fail",
                "E08",
                "Foreign keys and orphans",
                "Trip, route, service, stop, stop-time, and shape references were counted.",
                counts=dict(fk),
                samples=dict(fk_samples),
            ),
            _check(
                "fail" if bad_parent else "pass",
                "E09",
                "Parent stations and stop grouping",
                "Parent stop references and cycles were checked structurally; human station "
                "resolution review remains separate.",
                stopCount=len(stops),
                parentCount=len(parent_edges),
                parentIssues=fk["stops_with_unknown_parent"] + fk["stops_in_parent_cycle"],
            ),
            _check(
                "not_observed",
                "E10",
                "Cold refresh through queryable generation",
                "A validation pass does not build or query a generation.",
                coldRun="not_observed",
            ),
        ]
    )

    checks.extend(
        [
            _check(
                "fail" if duplicate_count else "pass",
                "V01",
                "Duplicate identifiers",
                f"Found {duplicate_count} duplicate primary identifiers.",
                duplicates=dict(duplicates),
            ),
            _check(
                "fail" if bad_coordinates else "pass",
                "V02",
                "Stop coordinates",
                f"Found {coordinate_errors} invalid coordinate rows.",
            ),
            _check(
                "fail" if shape_bad else "pass",
                "V03",
                "Shape references and points",
                "Shape points are streamed and trip shape references are checked.",
                **integrity["shape_references"],
            ),
            _check(
                "fail" if bad_time else "pass",
                "V04",
                "Stop time integrity",
                "Arrival/departure values and duplicate per-trip stop sequences were checked; "
                "rows need not be pre-sorted. Raw cross-call decreases remain separately "
                "reported diagnostics; candidate validity requires each trip's bounded "
                "minute projection to pass.",
                **integrity["time_integrity"],
            ),
            _check(
                "fail" if malformed_count else "pass",
                "V05",
                "CSV row integrity",
                f"Found {malformed_count} rows with a different width than their header.",
                counts=dict(malformed),
            ),
            _check(
                "fail" if mapping_bad_ranges else "pass",
                "V06",
                "Mapping ranges",
                "All TripIdToDate date ranges are valid and non-reversed.",
                reversedRanges=mapping_bad_ranges[:10],
            ),
            _check(
                "pass",
                "V07",
                "Actual service date coverage",
                "Coverage uses actual active dates, including calendar-date additions "
                "and removals.",
                dateCount=len(active_dates),
                first=min(active_dates).isoformat(),
                last=max(active_dates).isoformat(),
            ),
            _check(
                "fail" if bad_parent else "pass",
                "V08",
                "Parent reference graph",
                "Parent stop links exist and do not form cycles.",
                missing=fk["stops_with_unknown_parent"],
                cycles=fk["stops_in_parent_cycle"],
            ),
            _check(
                "pass"
                if trips and not unmatched_keys and date_windows_overlap and not mapping_bad_ranges
                else "fail",
                "V09",
                "Trip identity and service-date mapping",
                "Complete normalized key coverage and overlapping known service windows gate "
                "the static build. Full identity date and weekday gaps remain diagnostic "
                "warnings and are not realtime proof.",
                unmatchedKeys=len(unmatched_keys),
                tripsWithDateGaps=len(missing_trip_dates),
                unmappedActiveServiceDateCount=len(partially_mapped_trip_dates),
                dateWindowsOverlap=date_windows_overlap,
                staticVerdict=pairing["staticPairingVerdict"],
                serviceDateCoverage="warning_only_not_realtime_proof",
            ),
            _check(
                "fail" if not active_dates else "pass",
                "V10",
                "Calendar definitions",
                "At least one real active service date is required.",
                activeDateCount=len(active_dates),
            ),
        ]
    )

    report = ValidationReport(
        gtfs_path,
        trip_id_to_date_path,
        checks,
        integrity,
        [day.isoformat() for day in sorted(active_dates)],
        {
            "from": min(active_dates).isoformat(),
            "through": max(active_dates).isoformat(),
            "activeDateCount": len(active_dates),
        },
        pairing,
    )
    if not report.valid:
        raise FeedValidationError(report)
    return report
