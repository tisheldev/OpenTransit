"""Immutable, generation-scoped GTFS reference data in SQLite.

The builder consumes stop_times as a stream into a SQLite staging table, so a
large feed never needs to be retained in Python memory. Query connections are
read-only and every page cursor is bound to its generation and query.
"""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import json
import math
import os
import sqlite3
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opentransit.core.trip_calls import (
    PINNED_PROJECTION_POLICY,
    SourceCall,
    SourceProfile,
    project_profile,
    source_profile_from_rows,
)

SCHEMA_VERSION = 2
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_SOURCE_PROFILE_CALLS = 10_000
DEFAULT_RADIUS_M = 500
MAX_RADIUS_M = 5000
MAX_BBOX_KM2 = 100
EARTH_RADIUS_M = 6_371_008.8
STOP_PREFIX = "mot:stop:"
ROUTE_PREFIX = "mot:route:"


class SourceProfileLimitError(ValueError):
    """The complete source vector exceeds the safe hydration bound."""


@dataclass(frozen=True)
class ReferenceMetadata:
    generation_id: str
    source_sha256: str
    content_sha256: str
    counts: dict[str, int]
    schema_version: int = SCHEMA_VERSION
    timing_policy: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "generationId": self.generation_id,
            "sourceSha256": self.source_sha256,
            "contentSha256": self.content_sha256,
            "counts": self.counts,
            "schemaVersion": self.schema_version,
            "timingPolicy": self.timing_policy,
        }


def public_stop_id(source_id: str) -> str:
    return STOP_PREFIX + source_id


def public_route_id(source_id: str) -> str:
    return ROUTE_PREFIX + source_id


def _rows(archive: zipfile.ZipFile, member: str):
    try:
        raw = archive.open(member)
    except KeyError as exc:
        raise ValueError(f"Required GTFS member missing: {member}") from exc
    with raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def _translation_rows(archive: zipfile.ZipFile):
    """Normalize modern selectors and the legacy exact stop-name key."""
    try:
        raw = archive.open("translations.txt")
    except KeyError as exc:
        raise ValueError("Required GTFS member missing: translations.txt") from exc
    with raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = set(reader.fieldnames or ())
        legacy = "trans_id" in headers and not (
            {"table_name", "field_name", "record_id", "field_value"} & headers
        )
        rows_by_key: dict[tuple, tuple] = {}
        for line_number, row in enumerate(reader, start=2):
            if legacy:
                table_name, field_name = "stops", "stop_name"
                record_id = ""
                record_sub_id = None
                field_value = row.get("trans_id") or None
                priority = None
                language = (row.get("lang") or "").casefold()
            else:
                table_name = (row.get("table_name") or "").strip().casefold()
                field_name = (row.get("field_name") or "").strip().casefold()
                record_id = row.get("record_id") or ""
                record_sub_id = row.get("record_sub_id") or None
                field_value = row.get("field_value") or None
                priority = _integer(row.get("priority"))
                language = (row.get("language") or row.get("lang") or "").casefold()
                if not record_id and not field_value:
                    raise ValueError(f"Translation has no exact selector at row {line_number}")
            translation = row.get("translation")
            if not table_name or not field_name or not language or translation is None:
                raise ValueError(f"Malformed translation row {line_number}")
            if not record_id and not field_value:
                raise ValueError(f"Translation has an empty selector at row {line_number}")
            key = (table_name, field_name, record_id, record_sub_id, field_value, language)
            previous = rows_by_key.get(key)
            if previous is not None:
                if previous[0] != translation:
                    raise ValueError(
                        f"Conflicting translations for exact selector/language at row {line_number}"
                    )
                continue
            rows_by_key[key] = (translation, priority)
        for key, (translation, priority) in rows_by_key.items():
            table_name, field_name, record_id, record_sub_id, field_value, language = key
            yield (
                table_name,
                language,
                translation,
                field_name,
                record_id,
                record_sub_id,
                field_value,
                priority,
            )


def _validate_translation_rows(connection: sqlite3.Connection, rows: list[tuple]) -> None:
    """Reject contradictory record/value selectors where the source field is known."""
    source_columns = {
        ("stops", "stop_name"): ("stops", "source_id", "name"),
        ("routes", "route_long_name"): ("routes", "source_id", "long_name"),
        ("agencies", "agency_name"): ("agencies", "agency_id", "name"),
    }
    for (
        table_name,
        _lang,
        _translation,
        field_name,
        record_id,
        _sub_id,
        field_value,
        _priority,
    ) in rows:
        if not record_id or not field_value:
            continue
        source = source_columns.get((table_name, field_name))
        if source is None:
            continue
        table, id_column, value_column = source
        row = connection.execute(
            f'SELECT "{value_column}" FROM "{table}" WHERE "{id_column}"=?',
            (record_id,),
        ).fetchone()
        if row is None or row[0] != field_value:
            raise ValueError(
                "Malformed dual translation selector: record and exact source value disagree"
            )


def _source_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _content_hash(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(_timing_policy(), sort_keys=True, separators=(",", ":")).encode())
    digest.update(b"\n")
    for table in (
        "agencies",
        "routes",
        "stops",
        "translations",
        "route_stops",
        "patterns",
        "pattern_stops",
        "calendar_rules",
        "calendar_exceptions",
        "trip_profiles",
        "clock_profiles",
        "clock_profile_calls",
    ):
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        order = ", ".join(f'"{name}"' for name in columns)
        for row in connection.execute(f'SELECT {order} FROM "{table}" ORDER BY {order}'):
            digest.update(
                json.dumps(tuple(row), ensure_ascii=False, separators=(",", ":")).encode()
            )
            digest.update(b"\n")
    return digest.hexdigest()


def _timing_policy() -> dict[str, Any]:
    policy = PINNED_PROJECTION_POLICY
    return {
        "policyId": policy.policy_id,
        "version": policy.version,
        "resolutionSeconds": policy.resolution_seconds,
        "motisSourceCommit": policy.motis_source_commit,
        "nigiriSourceCommit": policy.nigiri_source_commit,
        "firstArrivalProjected": False,
        "finalDepartureProjected": False,
    }


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE agencies (
            agency_id TEXT PRIMARY KEY, source_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL, url TEXT, timezone TEXT, lang TEXT,
            phone TEXT, fare_url TEXT, email TEXT
        );
        CREATE TABLE routes (
            route_id TEXT PRIMARY KEY, source_id TEXT NOT NULL UNIQUE,
            agency_id TEXT, short_name TEXT, long_name TEXT, description TEXT,
            route_type INTEGER, url TEXT, color TEXT, text_color TEXT,
            FOREIGN KEY (agency_id) REFERENCES agencies(agency_id)
        );
        CREATE INDEX routes_agency_idx ON routes(agency_id, route_id);
        CREATE INDEX routes_short_name_idx ON routes(short_name, route_id);
        CREATE TABLE stops (
            stop_id TEXT PRIMARY KEY, source_id TEXT NOT NULL UNIQUE,
            code TEXT, name TEXT, description TEXT, latitude REAL, longitude REAL,
            zone_id TEXT, url TEXT, location_type INTEGER, parent_station TEXT,
            wheelchair_boarding INTEGER, platform_code TEXT,
            FOREIGN KEY (parent_station) REFERENCES stops(stop_id)
                DEFERRABLE INITIALLY DEFERRED
        );
        CREATE INDEX stops_parent_idx ON stops(parent_station, stop_id);
        CREATE INDEX stops_location_idx ON stops(latitude, longitude);
        CREATE TABLE translations (
            translation_id INTEGER PRIMARY KEY, table_name TEXT NOT NULL,
            lang TEXT NOT NULL, translation TEXT NOT NULL, field_name TEXT NOT NULL,
            record_id TEXT NOT NULL, record_sub_id TEXT, field_value TEXT,
            priority INTEGER
        );
        CREATE INDEX translations_record_idx ON translations(record_id, lang);
        CREATE TABLE route_stops (
            route_id TEXT NOT NULL, stop_id TEXT NOT NULL,
            PRIMARY KEY(route_id, stop_id),
            FOREIGN KEY(route_id) REFERENCES routes(route_id),
            FOREIGN KEY(stop_id) REFERENCES stops(stop_id)
        );
        CREATE INDEX route_stops_stop_idx ON route_stops(stop_id, route_id);
        CREATE TABLE patterns (
            pattern_id TEXT PRIMARY KEY, route_id TEXT NOT NULL,
            direction_id TEXT, headsign TEXT,
            FOREIGN KEY(route_id) REFERENCES routes(route_id)
        );
        CREATE INDEX patterns_route_idx ON patterns(route_id, pattern_id);
        CREATE TABLE pattern_stops (
            pattern_id TEXT NOT NULL, sequence INTEGER NOT NULL,
            stop_id TEXT NOT NULL, pickup_type INTEGER NOT NULL,
            drop_off_type INTEGER NOT NULL,
            PRIMARY KEY(pattern_id, sequence),
            FOREIGN KEY(pattern_id) REFERENCES patterns(pattern_id),
            FOREIGN KEY(stop_id) REFERENCES stops(stop_id)
        );
        CREATE TABLE calendar_rules (
            service_id TEXT PRIMARY KEY, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
            monday INTEGER NOT NULL, tuesday INTEGER NOT NULL, wednesday INTEGER NOT NULL,
            thursday INTEGER NOT NULL, friday INTEGER NOT NULL, saturday INTEGER NOT NULL,
            sunday INTEGER NOT NULL
        );
        CREATE TABLE calendar_exceptions (
            service_id TEXT NOT NULL, service_date TEXT NOT NULL,
            exception_type INTEGER NOT NULL,
            PRIMARY KEY(service_id, service_date)
        );
        CREATE TABLE clock_profiles (
            profile_id TEXT PRIMARY KEY, canonical_json TEXT NOT NULL UNIQUE
        );
        CREATE TABLE clock_profile_calls (
            profile_id TEXT NOT NULL, ordinal INTEGER NOT NULL, source_sequence INTEGER NOT NULL,
            stop_id TEXT NOT NULL, arrival_seconds INTEGER, departure_seconds INTEGER,
            pickup_type INTEGER NOT NULL, drop_off_type INTEGER NOT NULL,
            effective_arrival_seconds INTEGER, effective_departure_seconds INTEGER,
            PRIMARY KEY(profile_id, ordinal),
            FOREIGN KEY(profile_id) REFERENCES clock_profiles(profile_id)
        );
        CREATE TABLE trip_profiles (
            source_trip_id TEXT PRIMARY KEY, service_id TEXT NOT NULL, profile_id TEXT NOT NULL,
            FOREIGN KEY(profile_id) REFERENCES clock_profiles(profile_id)
        );
        CREATE INDEX trip_profiles_service_idx ON trip_profiles(service_id, source_trip_id);
        CREATE TABLE trips_stage (
            trip_id TEXT PRIMARY KEY, service_id TEXT NOT NULL, route_id TEXT NOT NULL,
            direction_id TEXT, headsign TEXT
        );
        CREATE TABLE stop_times_stage (
            trip_id TEXT NOT NULL, stop_sequence INTEGER NOT NULL,
            source_stop_id TEXT NOT NULL, stop_id TEXT NOT NULL,
            arrival_time TEXT, departure_time TEXT,
            pickup_type INTEGER NOT NULL, drop_off_type INTEGER NOT NULL,
            PRIMARY KEY(trip_id, stop_sequence)
        );
        """
    )


def _integer(value: str | None, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid GTFS integer: {value}") from exc


def _gtfs_date(value: str) -> str:
    if len(value) != 8 or not value.isdigit():
        raise ValueError(f"Invalid GTFS service date: {value}")
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def _coordinate(value: str | None, low: float, high: float) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid GTFS coordinate: {value}") from exc
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"GTFS coordinate outside valid range: {value}")
    return result


def _batched(rows, size: int = 5000):
    batch = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def build_reference(feed_zip: Path, output_db: Path, generation_id: str) -> ReferenceMetadata:
    """Build a new immutable reference database; an existing output is never replaced."""
    feed_zip = Path(feed_zip)
    output_db = Path(output_db)
    if not generation_id or "\x00" in generation_id:
        raise ValueError("A non-empty generation ID is required")
    output_db.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output_db, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    source_hash = _source_hash(feed_zip)
    connection = sqlite3.connect(output_db)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA defer_foreign_keys=ON")
        _create_schema(connection)
        connection.execute("PRAGMA defer_foreign_keys=ON")
        with zipfile.ZipFile(feed_zip) as archive:
            names = set(archive.namelist())
            if "agency.txt" not in names:
                raise ValueError("Required GTFS member missing: agency.txt")
            agency_rows = _rows(archive, "agency.txt")
            connection.executemany(
                "INSERT INTO agencies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        row.get("agency_id") or "default",
                        row.get("agency_id") or "default",
                        row.get("agency_name", ""),
                        row.get("agency_url") or None,
                        row.get("agency_timezone") or None,
                        row.get("agency_lang") or None,
                        row.get("agency_phone") or None,
                        row.get("agency_fare_url") or None,
                        row.get("agency_email") or None,
                    )
                    for row in agency_rows
                ),
            )
            agency_count = connection.execute("SELECT count(*) FROM agencies").fetchone()[0]
            sole_agency_id = (
                connection.execute("SELECT agency_id FROM agencies").fetchone()[0]
                if agency_count == 1
                else None
            )
            for batch in _batched(_rows(archive, "routes.txt")):
                connection.executemany(
                    "INSERT INTO routes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            public_route_id(row["route_id"]),
                            row["route_id"],
                            row.get("agency_id") or sole_agency_id,
                            row.get("route_short_name") or None,
                            row.get("route_long_name") or None,
                            row.get("route_desc") or None,
                            _integer(row.get("route_type")),
                            row.get("route_url") or None,
                            row.get("route_color") or None,
                            row.get("route_text_color") or None,
                        )
                        for row in batch
                    ],
                )
            for batch in _batched(_rows(archive, "stops.txt")):
                connection.executemany(
                    "INSERT INTO stops VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            public_stop_id(row["stop_id"]),
                            row["stop_id"],
                            row.get("stop_code") or None,
                            row.get("stop_name") or None,
                            row.get("stop_desc") or None,
                            _coordinate(row.get("stop_lat"), -90, 90),
                            _coordinate(row.get("stop_lon"), -180, 180),
                            row.get("zone_id") or None,
                            row.get("stop_url") or None,
                            _integer(row.get("location_type")),
                            public_stop_id(row["parent_station"])
                            if row.get("parent_station")
                            else None,
                            _integer(row.get("wheelchair_boarding")),
                            row.get("platform_code") or None,
                        )
                        for row in batch
                    ],
                )
            if "translations.txt" in names:
                translation_rows = list(_translation_rows(archive))
                _validate_translation_rows(connection, translation_rows)
                for batch in _batched(translation_rows):
                    connection.executemany(
                        """INSERT INTO translations
                        (table_name, lang, translation, field_name, record_id,
                         record_sub_id, field_value, priority)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        batch,
                    )
            for batch in _batched(_rows(archive, "trips.txt")):
                connection.executemany(
                    "INSERT INTO trips_stage VALUES (?, ?, ?, ?, ?)",
                    [
                        (
                            row["trip_id"],
                            row["service_id"],
                            public_route_id(row["route_id"]),
                            row.get("direction_id") or None,
                            row.get("trip_headsign") or None,
                        )
                        for row in batch
                    ],
                )
            if "calendar.txt" in names:
                weekday_names = (
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                )
                for batch in _batched(_rows(archive, "calendar.txt")):
                    connection.executemany(
                        "INSERT INTO calendar_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [
                            (
                                row["service_id"],
                                _gtfs_date(row["start_date"]),
                                _gtfs_date(row["end_date"]),
                                *(_integer(row.get(day), 0) for day in weekday_names),
                            )
                            for row in batch
                        ],
                    )
            if "calendar_dates.txt" in names:
                for batch in _batched(_rows(archive, "calendar_dates.txt")):
                    connection.executemany(
                        "INSERT INTO calendar_exceptions VALUES (?, ?, ?)",
                        [
                            (
                                row["service_id"],
                                _gtfs_date(row["date"]),
                                _integer(row["exception_type"]),
                            )
                            for row in batch
                        ],
                    )
            for batch in _batched(_rows(archive, "stop_times.txt")):
                connection.executemany(
                    "INSERT INTO stop_times_stage VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            row["trip_id"],
                            _integer(row["stop_sequence"]),
                            row["stop_id"],
                            public_stop_id(row["stop_id"]),
                            row.get("arrival_time") or None,
                            row.get("departure_time") or None,
                            _integer(row.get("pickup_type"), 0),
                            _integer(row.get("drop_off_type"), 0),
                        )
                        for row in batch
                    ],
                )
        connection.execute(
            "CREATE INDEX stop_times_order_idx ON stop_times_stage(trip_id, stop_sequence)"
        )
        connection.execute(
            "INSERT INTO route_stops SELECT DISTINCT t.route_id, s.stop_id "
            "FROM trips_stage t JOIN stop_times_stage s USING (trip_id)"
        )
        cursor = connection.execute(
            "SELECT t.trip_id, t.service_id, t.route_id, t.direction_id, t.headsign, "
            "s.stop_sequence, s.source_stop_id, s.stop_id, s.arrival_time, s.departure_time, "
            "s.pickup_type, s.drop_off_type FROM trips_stage t "
            "JOIN stop_times_stage s USING (trip_id) ORDER BY t.trip_id, s.stop_sequence"
        )
        current_trip = None
        service_id = route_id = direction_id = headsign = None
        calls = []
        profile_rows = []

        def save_trip_profile():
            if not profile_rows:
                return
            source_profile = source_profile_from_rows(current_trip, service_id, profile_rows)
            projection = project_profile(source_profile)
            effective = {
                (event.ordinal, event.kind): event.effective_seconds for event in projection.events
            }
            vector = [
                [
                    call.sequence,
                    call.ordinal,
                    call.stop_id,
                    call.arrival_seconds,
                    call.departure_seconds,
                    call.pickup_type,
                    call.drop_off_type,
                    effective.get((call.ordinal, "arrival")),
                    effective.get((call.ordinal, "departure")),
                ]
                for call in source_profile.calls
            ]
            canonical = json.dumps(vector, ensure_ascii=False, separators=(",", ":"))
            profile_id = hashlib.sha256(canonical.encode()).hexdigest()
            connection.execute(
                "INSERT OR IGNORE INTO clock_profiles VALUES (?, ?)",
                (profile_id, canonical),
            )
            saved = connection.execute(
                "SELECT canonical_json FROM clock_profiles WHERE profile_id=?", (profile_id,)
            ).fetchone()[0]
            if saved != canonical:
                raise ValueError("Clock profile hash collision")
            if (
                connection.execute(
                    "SELECT 1 FROM clock_profile_calls WHERE profile_id=? LIMIT 1", (profile_id,)
                ).fetchone()
                is None
            ):
                connection.executemany(
                    "INSERT INTO clock_profile_calls VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            profile_id,
                            call.ordinal,
                            call.sequence,
                            call.stop_id,
                            call.arrival_seconds,
                            call.departure_seconds,
                            call.pickup_type,
                            call.drop_off_type,
                            effective.get((call.ordinal, "arrival")),
                            effective.get((call.ordinal, "departure")),
                        )
                        for call in source_profile.calls
                    ],
                )
            connection.execute(
                "INSERT INTO trip_profiles VALUES (?, ?, ?)",
                (current_trip, service_id, profile_id),
            )

        def save_pattern():
            if not calls:
                return
            signature = json.dumps(
                [route_id, direction_id, headsign, calls], ensure_ascii=False, separators=(",", ":")
            )
            pattern_id = hashlib.sha256(signature.encode()).hexdigest()
            inserted = connection.execute(
                "INSERT OR IGNORE INTO patterns VALUES (?, ?, ?, ?)",
                (pattern_id, route_id, direction_id, headsign),
            ).rowcount
            if inserted:
                connection.executemany(
                    "INSERT INTO pattern_stops VALUES (?, ?, ?, ?, ?)",
                    [(pattern_id, index, *call) for index, call in enumerate(calls)],
                )

        for (
            trip_id,
            trip_service,
            trip_route,
            trip_direction,
            trip_headsign,
            _seq,
            source_stop_id,
            stop_id,
            arrival_time,
            departure_time,
            pickup,
            dropoff,
        ) in cursor:
            if current_trip is not None and trip_id != current_trip:
                save_pattern()
                save_trip_profile()
                calls = []
                profile_rows = []
            if trip_id != current_trip:
                current_trip = trip_id
                service_id = trip_service
                route_id, direction_id, headsign = trip_route, trip_direction, trip_headsign
            calls.append((stop_id, pickup, dropoff))
            profile_rows.append(
                {
                    "trip_id": trip_id,
                    "service_id": trip_service,
                    "stop_sequence": str(_seq),
                    "stop_id": source_stop_id,
                    "arrival_time": arrival_time,
                    "departure_time": departure_time,
                    "pickup_type": pickup,
                    "drop_off_type": dropoff,
                }
            )
        save_pattern()
        save_trip_profile()
        missing_profile = connection.execute(
            "SELECT trip_id FROM trips_stage t LEFT JOIN trip_profiles p "
            "ON p.source_trip_id=t.trip_id WHERE p.source_trip_id IS NULL LIMIT 1"
        ).fetchone()
        if missing_profile:
            raise ValueError(f"Trip has no clock profile: {missing_profile[0]}")
        connection.execute("DROP TABLE trips_stage")
        connection.execute("DROP TABLE stop_times_stage")
        counts = {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "agencies",
                "routes",
                "stops",
                "translations",
                "route_stops",
                "patterns",
                "pattern_stops",
                "calendar_rules",
                "calendar_exceptions",
                "trip_profiles",
                "clock_profiles",
                "clock_profile_calls",
            )
        }
        content_hash = _content_hash(connection)
        metadata = {
            "generationId": generation_id,
            "sourceSha256": source_hash,
            "contentSha256": content_hash,
            "counts": counts,
            "schemaVersion": SCHEMA_VERSION,
            "timingPolicy": _timing_policy(),
            "clockProfileCount": counts["clock_profiles"],
            "tripProfileCount": counts["trip_profiles"],
        }
        connection.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            [(key, json.dumps(value, sort_keys=True)) for key, value in metadata.items()],
        )
        connection.execute("PRAGMA optimize")
        connection.commit()
        connection.execute("VACUUM")
        output_db.chmod(0o444)
        return ReferenceMetadata(
            generation_id, source_hash, content_hash, counts, SCHEMA_VERSION, _timing_policy()
        )
    finally:
        connection.close()


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = phi2 - phi1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _page_limit(limit: int) -> int:
    if isinstance(limit, bool) or not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError("Page size must be between 1 and 100")
    return limit


def _validate_coordinates(*values: float) -> None:
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("Coordinates must be finite numbers")


def _cursor_encode(generation_id: str, query: dict[str, Any], position: list[Any]) -> str:
    payload = {
        "v": 1,
        "g": generation_id,
        "q": hashlib.sha256(
            json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "p": position,
    }
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(encoded).decode().rstrip("=")


def _cursor_decode(
    cursor: str | None,
    generation_id: str,
    query: dict[str, Any],
    position_kind: str = "string",
) -> list[Any] | None:
    if cursor is None:
        return None
    try:
        if not isinstance(cursor, str) or not cursor or len(cursor) > 2048:
            raise ValueError
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        payload = json.loads(raw)
        expected_query = hashlib.sha256(
            json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if payload["v"] != 1 or payload["g"] != generation_id or payload["q"] != expected_query:
            raise ValueError
        position = payload["p"]
        if not isinstance(position, list):
            raise ValueError
        if position_kind == "distance":
            if (
                len(position) != 2
                or isinstance(position[0], bool)
                or not isinstance(position[0], (int, float))
                or not math.isfinite(position[0])
                or not isinstance(position[1], str)
            ):
                raise ValueError
        elif len(position) != 1 or not isinstance(position[0], str):
            raise ValueError
        return position
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError("Cursor is invalid or belongs to a different query/generation") from exc


class ReferenceStore:
    """Read-only query interface for one verified generation."""

    def __init__(
        self,
        path: Path,
        expected_generation_id: str | None = None,
        *,
        cursor_generation_id: str | None = None,
    ) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        self._uri = self.path.resolve().as_uri() + "?mode=ro&immutable=1"
        with self._connect() as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise ValueError("Reference database failed SQLite integrity verification")
            values = {
                key: json.loads(value)
                for key, value in connection.execute("SELECT key, value FROM metadata")
            }
            if values.get("schemaVersion") != SCHEMA_VERSION:
                raise ValueError("Unsupported reference database schema")
            if (
                expected_generation_id is not None
                and values.get("generationId") != expected_generation_id
            ):
                raise ValueError("Reference database belongs to a different generation")
            if _content_hash(connection) != values.get("contentSha256"):
                raise ValueError("Reference database content verification failed")
        # A composed public generation can reuse these immutable bytes. Verify
        # their embedded component identity above, but scope pagination cursors
        # to the composed public identity so references cannot cross generations.
        self.component_generation_id = values["generationId"]
        self.metadata = ReferenceMetadata(
            cursor_generation_id or values["generationId"],
            values["sourceSha256"],
            values["contentSha256"],
            values["counts"],
            values["schemaVersion"],
            values.get("timingPolicy"),
        )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self._uri, uri=True)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            yield connection
        finally:
            connection.close()

    def _page(
        self, rows: list[dict[str, Any]], limit: int, query: dict[str, Any], position
    ) -> dict[str, Any]:
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = (
            _cursor_encode(self.metadata.generation_id, query, position(items[-1]))
            if has_more
            else None
        )
        return {
            "items": items,
            "next_cursor": next_cursor,
            "generation_id": self.metadata.generation_id,
        }

    def source_profile(self, full_source_trip_id: str) -> SourceProfile | None:
        """Read one exact source trip profile without normalizing its identity."""
        if not isinstance(full_source_trip_id, str) or not full_source_trip_id:
            raise ValueError("A full source trip ID is required")
        with self._connect() as connection:
            profile = connection.execute(
                "SELECT service_id, profile_id FROM trip_profiles WHERE source_trip_id=?",
                (full_source_trip_id,),
            ).fetchone()
            if profile is None:
                return None
            rows = connection.execute(
                "SELECT ordinal, source_sequence, stop_id, arrival_seconds, departure_seconds, "
                "pickup_type, drop_off_type FROM clock_profile_calls "
                "WHERE profile_id=? ORDER BY ordinal LIMIT ?",
                (profile["profile_id"], MAX_SOURCE_PROFILE_CALLS + 1),
            ).fetchall()
        if len(rows) > MAX_SOURCE_PROFILE_CALLS:
            raise SourceProfileLimitError("Complete source trip exceeds the stop-call bound")
        calls = tuple(
            SourceCall(
                full_source_trip_id,
                profile["service_id"],
                row["source_sequence"],
                row["ordinal"],
                row["stop_id"],
                row["arrival_seconds"],
                row["departure_seconds"],
                row["pickup_type"],
                row["drop_off_type"],
            )
            for row in rows
        )
        return SourceProfile(full_source_trip_id, profile["service_id"], calls)

    def service_active(self, service_id: str, service_date: Any) -> bool | None:
        """Resolve one service date from compact GTFS calendar rules and overrides."""
        if not isinstance(service_id, str) or not service_id:
            raise ValueError("A source service ID is required")
        date_text = (
            service_date.isoformat() if hasattr(service_date, "isoformat") else str(service_date)
        )
        try:
            from datetime import date

            parsed = date.fromisoformat(date_text)
        except (TypeError, ValueError) as exc:
            raise ValueError("Service date must be an ISO calendar date") from exc
        date_text = parsed.isoformat()
        with self._connect() as connection:
            exception = connection.execute(
                "SELECT exception_type FROM calendar_exceptions "
                "WHERE service_id=? AND service_date=?",
                (service_id, date_text),
            ).fetchone()
            if exception is not None:
                return exception[0] == 1
            rule = connection.execute(
                "SELECT * FROM calendar_rules WHERE service_id=?", (service_id,)
            ).fetchone()
        if rule is None:
            return None
        if not rule["start_date"] <= date_text <= rule["end_date"]:
            return False
        weekdays = (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
        return bool(rule[weekdays[parsed.weekday()]])

    def stops_near(
        self,
        latitude: float,
        longitude: float,
        radius_m: float = DEFAULT_RADIUS_M,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        limit = _page_limit(limit)
        _validate_coordinates(latitude, longitude, radius_m)
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("Coordinates are outside valid ranges")
        if not math.isfinite(radius_m) or not 0 < radius_m <= MAX_RADIUS_M:
            raise ValueError("Radius must be greater than 0 and at most 5000 metres")
        query = {"kind": "near", "lat": latitude, "lon": longitude, "radius": radius_m}
        after = _cursor_decode(cursor, self.metadata.generation_id, query, "distance")
        lat_delta = radius_m / 110_574
        lon_scale = max(0.01, math.cos(math.radians(latitude)))
        lon_delta = min(180, radius_m / (111_320 * lon_scale))
        with self._connect() as connection:
            candidates = connection.execute(
                "SELECT * FROM stops WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
                (
                    max(-90, latitude - lat_delta),
                    min(90, latitude + lat_delta),
                    max(-180, longitude - lon_delta),
                    min(180, longitude + lon_delta),
                ),
            ).fetchall()
            found = []
            for row in candidates:
                distance = _distance_m(latitude, longitude, row["latitude"], row["longitude"])
                if distance <= radius_m:
                    item = self._stop_item(row)
                    item["distance_m"] = distance
                    found.append(item)
        found.sort(key=lambda row: (row["distance_m"], row["stop_id"]))
        if after is not None:
            found = [row for row in found if [row["distance_m"], row["stop_id"]] > after]
        return self._page(
            found[: limit + 1], limit, query, lambda row: [row["distance_m"], row["stop_id"]]
        )

    def stops_in_bbox(
        self,
        south: float,
        west: float,
        north: float,
        east: float,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        limit = _page_limit(limit)
        _validate_coordinates(south, west, north, east)
        if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
            raise ValueError("Bounding box coordinates are invalid")
        height = _distance_m(south, west, north, west) / 1000
        closest_to_equator = max(south, min(north, 0))
        width = _distance_m(closest_to_equator, west, closest_to_equator, east) / 1000
        if height * width > MAX_BBOX_KM2:
            raise ValueError("Bounding box exceeds 100 square kilometres")
        query = {"kind": "bbox", "south": south, "west": west, "north": north, "east": east}
        after = _cursor_decode(cursor, self.metadata.generation_id, query)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM stops WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ? "
                "AND stop_id > ? ORDER BY stop_id LIMIT ?",
                (south, north, west, east, after[0] if after else "", limit + 1),
            ).fetchall()
            found = [self._stop_item(row) for row in rows]
        return self._page(found, limit, query, lambda row: [row["stop_id"]])

    @staticmethod
    def _stop_item(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "stop_id": row["stop_id"],
            "source_id": row["source_id"],
            "code": row["code"],
            "name": row["name"],
            "description": row["description"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "location_type": row["location_type"],
            "parent_station": row["parent_station"],
            "wheelchair_boarding": row["wheelchair_boarding"],
            "platform_code": row["platform_code"],
        }

    def stop(self, stop_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM stops WHERE stop_id=? OR source_id=?", (stop_id, stop_id)
            ).fetchone()
            if row is None:
                return None
            item = self._stop_item(row)
            item["translations"] = self._translations(
                connection, "stops", row["source_id"], "stop_name", row["name"]
            )
            item["children"] = [
                self._stop_item(child)
                for child in connection.execute(
                    "SELECT * FROM stops WHERE parent_station=? ORDER BY stop_id",
                    (row["stop_id"],),
                )
            ]
            item["routes"] = [
                dict(route)
                for route in connection.execute(
                    "SELECT DISTINCT r.* FROM routes r JOIN route_stops rs USING(route_id) "
                    "WHERE rs.stop_id=? OR rs.stop_id IN "
                    "(SELECT stop_id FROM stops WHERE parent_station=?) ORDER BY r.route_id",
                    (row["stop_id"], row["stop_id"]),
                )
            ]
            if row["parent_station"]:
                parent = connection.execute(
                    "SELECT * FROM stops WHERE stop_id=?", (row["parent_station"],)
                ).fetchone()
                item["parent"] = self._stop_item(parent) if parent else None
            return item

    def stop_search_candidates(self) -> list[dict[str, Any]]:
        """Return the complete stop/station search corpus from this immutable database.

        This intentionally exposes only stop rows and stop-name translations. Search
        indexes are built in memory by the caller; this method never mutates the
        generation-scoped reference file.
        """
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM stops ORDER BY stop_id").fetchall()
            # Route counts are a search tie-break signal for partial matches only.
            route_counts = dict(
                connection.execute(
                    "SELECT stop_id, COUNT(*) FROM route_stops GROUP BY stop_id"
                ).fetchall()
            )
            stops_by_source_id = {row["source_id"]: row for row in rows}
            source_ids_by_name: dict[str, list[str]] = {}
            for row in rows:
                if row["name"] is not None:
                    source_ids_by_name.setdefault(row["name"], []).append(row["source_id"])
            translations: dict[str, dict[str, str]] = {}
            for row in connection.execute(
                "SELECT record_id, field_value, lang, translation "
                "FROM translations "
                "WHERE table_name='stops' AND field_name='stop_name' "
                "AND (record_sub_id IS NULL OR record_sub_id='') "
                "ORDER BY CASE WHEN record_id<>'' THEN 0 ELSE 1 END, "
                "priority DESC, translation_id"
            ):
                record_id = row["record_id"]
                if record_id:
                    target_ids = (record_id,) if record_id in stops_by_source_id else ()
                else:
                    target_ids = source_ids_by_name.get(row["field_value"], ())
                for source_id in target_ids:
                    translations.setdefault(source_id, {}).setdefault(
                        row["lang"].casefold(), row["translation"]
                    )
        return [
            {
                **self._stop_item(row),
                "translations": translations.get(row["source_id"], {}),
                "route_count": route_counts.get(row["stop_id"], 0),
            }
            for row in rows
        ]

    @staticmethod
    def _translations(
        connection: sqlite3.Connection,
        table_name: str,
        source_id: str,
        field_name: str,
        source_value: str | None = None,
    ) -> dict[str, str]:
        translations = {}
        for row in connection.execute(
            "SELECT lang, translation FROM translations "
            "WHERE table_name=? AND field_name=? AND "
            "((record_id=?) OR "
            "(record_id='' AND field_value=?)) "
            "AND (record_sub_id IS NULL OR record_sub_id='') "
            "ORDER BY CASE WHEN record_id<>'' THEN 0 ELSE 1 END, "
            "priority DESC, translation_id",
            (table_name, field_name, source_id, source_value),
        ):
            translations.setdefault(row["lang"].casefold(), row["translation"])
        return translations

    def routes(
        self,
        stop_id: str | None = None,
        agency_id: str | None = None,
        short_name: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        limit = _page_limit(limit)
        if stop_id is None and agency_id is None and short_name is None:
            raise ValueError("At least one route selector is required")
        query = {"kind": "routes", "stop": stop_id, "agency": agency_id, "short_name": short_name}
        after = _cursor_decode(cursor, self.metadata.generation_id, query)
        clauses, args = [], []
        if stop_id is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM route_stops rs WHERE rs.route_id=r.route_id "
                "AND (rs.stop_id=? OR rs.stop_id IN "
                "(SELECT stop_id FROM stops WHERE parent_station=?)))"
            )
            normalized_stop = public_stop_id(stop_id.removeprefix(STOP_PREFIX))
            args.extend((normalized_stop, normalized_stop))
        if agency_id is not None:
            clauses.append("r.agency_id=?")
            args.append(agency_id)
        if short_name is not None:
            clauses.append("r.short_name=?")
            args.append(short_name)
        if after:
            clauses.append("r.route_id > ?")
            args.append(after[0])
        sql = "SELECT r.* FROM routes r"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY r.route_id LIMIT ?"
        args.append(limit + 1)
        with self._connect() as connection:
            found = [dict(row) for row in connection.execute(sql, args)]
        return self._page(found, limit, query, lambda row: [row["route_id"]])

    def route(
        self,
        route_id: str,
        pattern_limit: int = DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any] | None:
        pattern_limit = _page_limit(pattern_limit)
        source_id = route_id.removeprefix(ROUTE_PREFIX)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM routes WHERE route_id=? OR source_id=?", (route_id, source_id)
            ).fetchone()
            if row is None:
                return None
            item = dict(row)
            item["translations"] = self._translations(
                connection, "routes", row["source_id"], "route_long_name"
            )
            item["agency"] = (
                dict(
                    connection.execute(
                        "SELECT * FROM agencies WHERE agency_id=?", (row["agency_id"],)
                    ).fetchone()
                )
                if row["agency_id"]
                else None
            )
            pattern_rows = connection.execute(
                "SELECT * FROM patterns WHERE route_id=? ORDER BY pattern_id LIMIT ?",
                (row["route_id"], pattern_limit),
            ).fetchall()
            pattern_count = connection.execute(
                "SELECT count(*) FROM patterns WHERE route_id=?", (row["route_id"],)
            ).fetchone()[0]
            item["patterns"] = [
                {
                    "pattern_id": pattern["pattern_id"],
                    "direction_id": pattern["direction_id"],
                    "headsign": pattern["headsign"],
                }
                for pattern in pattern_rows[:pattern_limit]
            ]
            item["patterns_count"] = pattern_count
            item["patterns_truncated"] = pattern_count > len(pattern_rows)
            return item

    def patterns(
        self,
        route_id: str,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        limit = _page_limit(limit)
        normalized_route = public_route_id(route_id.removeprefix(ROUTE_PREFIX))
        query = {"kind": "patterns", "route": normalized_route}
        after = _cursor_decode(cursor, self.metadata.generation_id, query)
        with self._connect() as connection:
            patterns = connection.execute(
                "SELECT * FROM patterns WHERE route_id=? AND pattern_id>? "
                "ORDER BY pattern_id LIMIT ?",
                (normalized_route, after[0] if after else "", limit + 1),
            ).fetchall()
            found = []
            for pattern in patterns:
                item = dict(pattern)
                item["stops"] = [
                    dict(call)
                    for call in connection.execute(
                        "SELECT sequence, stop_id, pickup_type, drop_off_type FROM pattern_stops "
                        "WHERE pattern_id=? ORDER BY sequence",
                        (pattern["pattern_id"],),
                    )
                ]
                found.append(item)
        return self._page(found, limit, query, lambda row: [row["pattern_id"]])
