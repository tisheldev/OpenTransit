"""Postgres + PostGIS cold store for POC-1.

ADR 0003 loads **five** tables — routes, trips, stops, calendars,
`trip_id_to_date` — and deliberately keeps `stop_times` and `shapes` out.
system-design §173: loading stop_times "buys nothing, because MOTIS already
answers both journeys *and* stop departures from RAM". They are parsed and
integrity-checked in parse.py and then discarded.

`agency.txt` is parsed but not given a sixth table; `agency_name` is
denormalised onto `routes` so operator queries work without widening the
load set beyond the five the ADR names.

Everything is loaded with COPY and the 1.96M-row `trip_id_to_date` is
streamed straight from its zip — no intermediate list.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import psycopg

DSN = "host=localhost port=55432 dbname=opentransit_poc user=poc password=poc"

TABLES = ["routes", "trips", "stops", "calendars", "trip_id_to_date"]

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS {s};

DROP TABLE IF EXISTS {s}.trip_id_to_date, {s}.trips, {s}.calendars,
                     {s}.routes, {s}.stops, {s}.ingest_run CASCADE;

CREATE TABLE {s}.routes (
    route_id          text PRIMARY KEY,
    agency_id         text,
    agency_name       text,
    route_short_name  text,
    route_long_name   text,
    route_desc        text,
    route_type        integer,
    route_color       text,
    route_text_color  text
);

CREATE TABLE {s}.stops (
    stop_id         text PRIMARY KEY,
    stop_code       text,
    stop_name       text,
    stop_desc       text,
    city            text,
    stop_lat        double precision,
    stop_lon        double precision,
    location_type   integer,
    parent_station  text,
    zone_id         text,
    platform_code   text,
    geom            geometry(Point, 4326)
);

CREATE TABLE {s}.calendars (
    service_id    text PRIMARY KEY,
    source        text NOT NULL,
    sunday smallint, monday smallint, tuesday smallint, wednesday smallint,
    thursday smallint, friday smallint, saturday smallint,
    start_date    date,
    end_date      date,
    active_dates  date[] NOT NULL
);

CREATE TABLE {s}.trips (
    trip_id                text PRIMARY KEY,
    route_id               text,
    service_id             text,
    trip_headsign          text,
    direction_id           integer,
    shape_id               text,
    wheelchair_accessible  integer
);

CREATE TABLE {s}.trip_id_to_date (
    line_detail_record_id  text,
    office_line_id         text,
    direction              text,
    line_alternative       text,
    from_date              date,
    to_date                date,
    trip_id                text,
    day_in_week            integer,
    departure_time         text
);

CREATE TABLE {s}.ingest_run (
    id                serial PRIMARY KEY,
    ran_at            timestamptz NOT NULL DEFAULT now(),
    feed_name         text,
    feed_sha256       text,
    trip_id_to_date_sha256 text,
    trip_id_to_date_paired boolean,
    notes             text
);
"""

INDEX_SQL = """
CREATE INDEX ON {s}.trips (route_id);
CREATE INDEX ON {s}.trips (service_id);
CREATE INDEX ON {s}.routes (agency_id);
CREATE INDEX ON {s}.routes (route_type);
CREATE INDEX ON {s}.stops (parent_station);
CREATE INDEX ON {s}.stops (city);
CREATE INDEX ON {s}.stops USING gist (geom);
CREATE INDEX ON {s}.trip_id_to_date (trip_id);
ANALYZE {s}.routes; ANALYZE {s}.trips; ANALYZE {s}.stops;
ANALYZE {s}.calendars; ANALYZE {s}.trip_id_to_date;
"""


def connect(dsn: str = DSN) -> psycopg.Connection:
    conn = psycopg.connect(dsn, autocommit=False)
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    conn.commit()
    return conn


def create_schema(conn: psycopg.Connection, schema: str = "public") -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL.format(s=schema))
    conn.commit()


def _int(v):
    v = (v or "").strip()
    if v == "":
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _float(v):
    v = (v or "").strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _city(stop_desc: str | None) -> str | None:
    """MOT packs the municipality into stop_desc.

    10-day feed:  'Street: X City: Y Platform:  Floor:'  (English labels)
    60-day feed:  'רחוב: X עיר: Y רציף:  קומה: '        (Hebrew labels)
    Both shapes are read; no other meaning is inferred from the field.
    """
    if not stop_desc:
        return None
    for start, end in (("City:", "Platform:"), ("עיר:", "רציף:")):
        i = stop_desc.find(start)
        if i == -1:
            continue
        j = stop_desc.find(end, i)
        val = stop_desc[i + len(start): j if j != -1 else None]
        val = val.strip()
        return val or None
    return None


def load_routes(conn, fp, schema="public") -> int:
    agencies = {aid: row.get("agency_name") for aid, row in fp.agencies.items()}
    n = 0
    with conn.cursor() as cur, cur.copy(
        f"COPY {schema}.routes (route_id, agency_id, agency_name, route_short_name, "
        f"route_long_name, route_desc, route_type, route_color, route_text_color) "
        f"FROM STDIN"
    ) as cp:
        for rid, r in fp.routes.items():
            aid = r.get("agency_id")
            cp.write_row((rid, aid, agencies.get(aid), r.get("route_short_name"),
                          r.get("route_long_name"), r.get("route_desc"),
                          _int(r.get("route_type")), r.get("route_color"),
                          r.get("route_text_color")))
            n += 1
    return n


def load_stops(conn, fp, schema="public") -> int:
    n = 0
    with conn.cursor() as cur, cur.copy(
        f"COPY {schema}.stops (stop_id, stop_code, stop_name, stop_desc, city, "
        f"stop_lat, stop_lon, location_type, parent_station, zone_id, platform_code) "
        f"FROM STDIN"
    ) as cp:
        for sid, s in fp.stops.items():
            cp.write_row((sid, s.get("stop_code"), s.get("stop_name"), s.get("stop_desc"),
                          _city(s.get("stop_desc")), _float(s.get("stop_lat")),
                          _float(s.get("stop_lon")), _int(s.get("location_type")),
                          (s.get("parent_station") or None), s.get("zone_id"),
                          s.get("platform_code")))
            n += 1
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE {schema}.stops SET geom = ST_SetSRID(ST_MakePoint(stop_lon, stop_lat), 4326) "
            f"WHERE stop_lat IS NOT NULL AND stop_lon IS NOT NULL"
        )
    return n


def load_calendars(conn, fp, schema="public") -> int:
    n = 0
    with conn.cursor() as cur, cur.copy(
        f"COPY {schema}.calendars (service_id, source, sunday, monday, tuesday, "
        f"wednesday, thursday, friday, saturday, start_date, end_date, active_dates) "
        f"FROM STDIN"
    ) as cp:
        for sid, svc in fp.services.services.items():
            d = svc.dow
            cp.write_row((sid, svc.source,
                          d.get("sunday"), d.get("monday"), d.get("tuesday"),
                          d.get("wednesday"), d.get("thursday"), d.get("friday"),
                          d.get("saturday"),
                          svc.start_date, svc.end_date, sorted(svc.active_dates)))
            n += 1
    return n


def load_trips(conn, fp, schema="public") -> int:
    n = 0
    with conn.cursor() as cur, cur.copy(
        f"COPY {schema}.trips (trip_id, route_id, service_id, trip_headsign, "
        f"direction_id, shape_id, wheelchair_accessible) FROM STDIN"
    ) as cp:
        for tid, t in fp.trips.items():
            cp.write_row((tid, t.get("route_id"), t.get("service_id"),
                          t.get("trip_headsign"), _int(t.get("direction_id")),
                          (t.get("shape_id") or None),
                          _int(t.get("wheelchair_accessible"))))
            n += 1
    return n


def load_trip_id_to_date(conn, zip_path: Path, schema: str = "public") -> int:
    """Stream TripIdToDate.txt from its zip straight into COPY."""
    from .pairing import MEMBER, _int as _pint, _parse_dt
    from .zipread import GtfsZip

    n = 0
    with GtfsZip(zip_path) as z, conn.cursor() as cur, cur.copy(
        f"COPY {schema}.trip_id_to_date (line_detail_record_id, office_line_id, "
        f"direction, line_alternative, from_date, to_date, trip_id, day_in_week, "
        f"departure_time) FROM STDIN"
    ) as cp:
        for row in z.rows(MEMBER):
            cp.write_row((row.get("LineDetailRecordId"), row.get("OfficeLineId"),
                          row.get("Direction"), row.get("LineAlternative"),
                          _parse_dt(row.get("FromDate")), _parse_dt(row.get("ToDate")),
                          row.get("TripId"), _pint(row.get("DayInWeek")),
                          row.get("DepartureTime")))
            n += 1
    return n


def create_indexes(conn, schema: str = "public") -> None:
    with conn.cursor() as cur:
        cur.execute(INDEX_SQL.format(s=schema))
    conn.commit()


def record_run(conn, schema: str, feed_name: str, feed_sha: str | None,
               t2d_sha: str | None, paired: bool | None, notes: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {schema}.ingest_run (feed_name, feed_sha256, "
            f"trip_id_to_date_sha256, trip_id_to_date_paired, notes) "
            f"VALUES (%s, %s, %s, %s, %s)",
            (feed_name, feed_sha, t2d_sha, paired, notes))
    conn.commit()


def table_counts(conn, schema: str = "public") -> dict[str, int]:
    out = {}
    with conn.cursor() as cur:
        for t in TABLES:
            cur.execute(f"SELECT count(*) FROM {schema}.{t}")
            out[t] = cur.fetchone()[0]
    return out
