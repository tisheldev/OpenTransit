"""Parse and validate an MOT GTFS feed by streaming.

PRD §6 requires proving all seven file groups can be parsed and *understood*:
agencies, routes, trips, stops, stop_times, calendar/service, shapes. All
seven are parsed and counted here. ADR 0003 then loads only five tables;
`stop_times` and `shapes` are validated and discarded (see db.py).

Memory discipline: the only structures that survive a pass are per-entity id
maps and small counters. `stop_times.txt` (1.77 GB) and `shapes.txt` (240 MB)
are never materialised.

Service days: KDP-002 — the 10-day feed ships `calendar_dates.txt` and no
`calendar.txt`; the 60-day feed ships the opposite. `parse_services` handles
both and raises `NoServicesDefined` when a feed defines none, because the
failure mode that matters is a feed that quietly produces zero services.
"""

from __future__ import annotations

import collections
import datetime as dt
from dataclasses import dataclass, field
from typing import Iterable

from .gtfstime import GtfsTimeError, format_gtfs_time, parse_gtfs_time
from .zipread import GtfsZip, ReadStats

SEVEN_GROUPS = ["agency", "routes", "trips", "stops", "stop_times", "calendar", "shapes"]

DOW = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]


class NoServicesDefined(RuntimeError):
    """A feed that defines no service days is unusable, not empty. Fail loudly."""


class MissingRequiredFile(RuntimeError):
    pass


def _date(s: str) -> dt.date:
    return dt.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))


# ---------------------------------------------------------------------------
# services
# ---------------------------------------------------------------------------

@dataclass
class Service:
    service_id: str
    source: str                       # "calendar" | "calendar_dates" | "calendar+dates"
    dow: dict[str, int] = field(default_factory=dict)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    active_dates: set[dt.date] = field(default_factory=set)


@dataclass
class ServiceParse:
    services: dict[str, Service]
    calendar_rows: int = 0
    calendar_dates_rows: int = 0
    exception_type_counts: dict[str, int] = field(default_factory=dict)
    has_calendar: bool = False
    has_calendar_dates: bool = False
    stats: dict[str, dict] = field(default_factory=dict)


def parse_services(z: GtfsZip) -> ServiceParse:
    services: dict[str, Service] = {}
    out = ServiceParse(services)
    out.has_calendar = z.has("calendar.txt")
    out.has_calendar_dates = z.has("calendar_dates.txt")

    if out.has_calendar:
        st = ReadStats("calendar.txt")
        for row in z.rows("calendar.txt", st):
            sid = row["service_id"]
            sd, ed = _date(row["start_date"]), _date(row["end_date"])
            dow = {d: int(row[d] or 0) for d in DOW}
            svc = Service(sid, "calendar", dow, sd, ed)
            d = sd
            while d <= ed:
                # date.weekday(): Monday=0..Sunday=6; GTFS names them directly.
                if dow[DOW[(d.weekday() + 1) % 7]] == 1:
                    svc.active_dates.add(d)
                d += dt.timedelta(days=1)
            services[sid] = svc
        out.calendar_rows = st.rows
        out.stats["calendar.txt"] = st.as_dict()

    if out.has_calendar_dates:
        st = ReadStats("calendar_dates.txt")
        exc: collections.Counter[str] = collections.Counter()
        for row in z.rows("calendar_dates.txt", st):
            sid = row["service_id"]
            d = _date(row["date"])
            et = (row["exception_type"] or "").strip()
            exc[et] += 1
            svc = services.get(sid)
            if svc is None:
                svc = Service(sid, "calendar_dates")
                services[sid] = svc
            elif svc.source == "calendar":
                svc.source = "calendar+dates"
            if et == "1":
                svc.active_dates.add(d)
            elif et == "2":
                svc.active_dates.discard(d)
        out.calendar_dates_rows = st.rows
        out.exception_type_counts = dict(exc)
        out.stats["calendar_dates.txt"] = st.as_dict()

    for svc in services.values():
        if svc.active_dates:
            svc.start_date = svc.start_date or min(svc.active_dates)
            svc.end_date = svc.end_date or max(svc.active_dates)

    if not services:
        raise NoServicesDefined(
            f"{z.path.name} defines no services: calendar.txt={out.has_calendar}, "
            f"calendar_dates.txt={out.has_calendar_dates}. KDP-002 — a feed with "
            "neither shape is unusable; refusing to continue with zero services."
        )
    if not any(s.active_dates for s in services.values()):
        raise NoServicesDefined(
            f"{z.path.name} declares {len(services)} services but none is active on "
            "any date. Refusing to continue."
        )
    return out


# ---------------------------------------------------------------------------
# the full feed
# ---------------------------------------------------------------------------

@dataclass
class FeedParse:
    name: str
    sha256: str | None = None
    members: dict[str, int] = field(default_factory=dict)
    feed_info: dict[str, str] = field(default_factory=dict)

    agencies: dict[str, dict] = field(default_factory=dict)
    routes: dict[str, dict] = field(default_factory=dict)
    stops: dict[str, dict] = field(default_factory=dict)
    trips: dict[str, dict] = field(default_factory=dict)
    services: ServiceParse | None = None

    rows: dict[str, int] = field(default_factory=dict)
    read_stats: dict[str, dict] = field(default_factory=dict)

    # stop_times aggregates (the rows themselves are discarded — ADR 0003)
    stop_times_rows: int = 0
    stop_times_over_24h: int = 0
    stop_times_max_seconds: int = 0
    stop_times_max_raw: str | None = None
    stop_times_blank_times: int = 0
    stop_times_time_errors: list[str] = field(default_factory=list)
    departures_per_stop: collections.Counter = field(default_factory=collections.Counter)

    # shapes aggregates
    shapes_rows: int = 0
    shapes_distinct: int = 0

    # translations
    translations_rows: int = 0
    translations_schema: str | None = None
    translations_languages: dict[str, int] = field(default_factory=dict)

    # referential integrity (E08)
    integrity: dict[str, int] = field(default_factory=dict)
    integrity_samples: dict[str, list[str]] = field(default_factory=dict)

    # Detail collected only for the stops named in `detail_stop_ids`, so the
    # cost is bounded by those stops rather than by the 30k-stop network.
    # (stop_id, service_id, service-day hour) -> departures
    detail_departures: collections.Counter = field(default_factory=collections.Counter)
    # stop_id -> set of route_ids observed calling there
    detail_routes: dict[str, set] = field(default_factory=dict)

    def row_counts(self) -> dict[str, int]:
        return dict(self.rows)


def _count_rows(z: GtfsZip, member: str, fp: FeedParse) -> int:
    st = ReadStats(member)
    n = 0
    for _ in z.rows(member, st):
        n += 1
    fp.read_stats[member] = st.as_dict()
    return n


def parse_feed(path, sha256: str | None = None, *,
               want_stop_times: bool = True,
               want_shapes: bool = True,
               detail_stop_ids: Iterable[str] | None = None,
               detail_selector=None,
               progress=None) -> FeedParse:
    """Stream a whole feed. Returns counts, id maps and integrity findings."""
    fp = FeedParse(name=str(getattr(path, "name", path)), sha256=sha256)
    detail = set(detail_stop_ids or ())
    # departures for the stops of interest, keyed (stop_id, service_id, hour)
    detail_departures: collections.Counter = collections.Counter()
    detail_routes: dict[str, set] = {}

    with GtfsZip(path) as z:
        fp.name = z.path.name
        fp.members = z.sizes()

        for req in ("agency.txt", "routes.txt", "trips.txt", "stops.txt", "stop_times.txt"):
            if not z.has(req):
                raise MissingRequiredFile(f"{fp.name} has no {req}")

        if z.has("feed_info.txt"):
            for row in z.rows("feed_info.txt"):
                fp.feed_info = dict(row)
                break

        # --- agencies -------------------------------------------------
        st = ReadStats("agency.txt")
        for row in z.rows("agency.txt", st):
            fp.agencies[row["agency_id"]] = row
        fp.rows["agency"] = st.rows
        fp.read_stats["agency.txt"] = st.as_dict()

        # --- routes ---------------------------------------------------
        st = ReadStats("routes.txt")
        for row in z.rows("routes.txt", st):
            fp.routes[row["route_id"]] = row
        fp.rows["routes"] = st.rows
        fp.read_stats["routes.txt"] = st.as_dict()

        # --- stops ----------------------------------------------------
        st = ReadStats("stops.txt")
        for row in z.rows("stops.txt", st):
            fp.stops[row["stop_id"]] = row
        fp.rows["stops"] = st.rows
        fp.read_stats["stops.txt"] = st.as_dict()

        # --- calendar / service ---------------------------------------
        fp.services = parse_services(z)
        fp.rows["calendar"] = fp.services.calendar_rows
        fp.rows["calendar_dates"] = fp.services.calendar_dates_rows
        fp.rows["services"] = len(fp.services.services)
        fp.read_stats.update(fp.services.stats)

        # --- trips ----------------------------------------------------
        st = ReadStats("trips.txt")
        bad_route = bad_service = 0
        s_bad_route: list[str] = []
        s_bad_service: list[str] = []
        for row in z.rows("trips.txt", st):
            tid = row["trip_id"]
            fp.trips[tid] = row
            if row["route_id"] not in fp.routes:
                bad_route += 1
                if len(s_bad_route) < 5:
                    s_bad_route.append(f"trip {tid} -> route {row['route_id']}")
            if row["service_id"] not in fp.services.services:
                bad_service += 1
                if len(s_bad_service) < 5:
                    s_bad_service.append(f"trip {tid} -> service {row['service_id']}")
        fp.rows["trips"] = st.rows
        fp.read_stats["trips.txt"] = st.as_dict()
        fp.integrity["trips_with_unknown_route"] = bad_route
        fp.integrity["trips_with_unknown_service"] = bad_service
        fp.integrity_samples["trips_with_unknown_route"] = s_bad_route
        fp.integrity_samples["trips_with_unknown_service"] = s_bad_service

        # stops referencing a missing parent_station
        bad_parent = 0
        s_bad_parent: list[str] = []
        for sid, row in fp.stops.items():
            p = (row.get("parent_station") or "").strip()
            if p and p not in fp.stops:
                bad_parent += 1
                if len(s_bad_parent) < 5:
                    s_bad_parent.append(f"stop {sid} -> parent {p}")
        fp.integrity["stops_with_unknown_parent"] = bad_parent
        fp.integrity_samples["stops_with_unknown_parent"] = s_bad_parent

        # The detail set is chosen once stops and trips are known, so callers
        # can say "every stop in these cities" without a second pass.
        if detail_selector is not None:
            detail |= set(detail_selector(fp))

        # --- stop_times (streamed, then discarded) --------------------
        if want_stop_times:
            st = ReadStats("stop_times.txt")
            bad_trip = bad_stop = 0
            s_bad_trip: list[str] = []
            s_bad_stop: list[str] = []
            seen_trips: set[str] = set()
            n = 0
            for row in z.rows("stop_times.txt", st):
                n += 1
                tid = row["trip_id"]
                sid = row["stop_id"]
                if tid not in fp.trips:
                    bad_trip += 1
                    if len(s_bad_trip) < 5:
                        s_bad_trip.append(f"stop_time trip {tid}")
                if sid not in fp.stops:
                    bad_stop += 1
                    if len(s_bad_stop) < 5:
                        s_bad_stop.append(f"stop_time stop {sid}")
                raw = row.get("departure_time") or row.get("arrival_time") or ""
                try:
                    secs = parse_gtfs_time(raw)
                except GtfsTimeError as e:
                    if len(fp.stop_times_time_errors) < 10:
                        fp.stop_times_time_errors.append(f"line {st.rows}: {e}")
                    secs = None
                if secs is None:
                    fp.stop_times_blank_times += 1
                else:
                    if secs >= 86400:
                        fp.stop_times_over_24h += 1
                    if secs > fp.stop_times_max_seconds:
                        fp.stop_times_max_seconds = secs
                        fp.stop_times_max_raw = raw.strip()
                    fp.departures_per_stop[sid] += 1
                    if detail and sid in detail:
                        trip = fp.trips.get(tid)
                        if trip is not None:
                            detail_departures[(sid, trip["service_id"], secs // 3600)] += 1
                            detail_routes.setdefault(sid, set()).add(trip["route_id"])
                seen_trips.add(tid)
                if progress and n % 5_000_000 == 0:
                    progress(f"    stop_times {n:,} rows")
            fp.stop_times_rows = st.rows
            fp.rows["stop_times"] = st.rows
            fp.read_stats["stop_times.txt"] = st.as_dict()
            fp.integrity["stop_times_with_unknown_trip"] = bad_trip
            fp.integrity["stop_times_with_unknown_stop"] = bad_stop
            fp.integrity_samples["stop_times_with_unknown_trip"] = s_bad_trip
            fp.integrity_samples["stop_times_with_unknown_stop"] = s_bad_stop
            # seen_trips can contain ids that are not in trips.txt, so subtract
            # by membership rather than by size.
            fp.integrity["trips_with_no_stop_times"] = sum(
                1 for t in fp.trips if t not in seen_trips)

        # --- shapes (streamed, then discarded) ------------------------
        if want_shapes and z.has("shapes.txt"):
            st = ReadStats("shapes.txt")
            distinct: set[str] = set()
            for row in z.rows("shapes.txt", st):
                distinct.add(row["shape_id"])
            fp.shapes_rows = st.rows
            fp.shapes_distinct = len(distinct)
            fp.rows["shapes"] = st.rows
            fp.read_stats["shapes.txt"] = st.as_dict()
            trip_shapes = {(t.get("shape_id") or "") for t in fp.trips.values()}
            trip_shapes.discard("")
            fp.integrity["trips_with_unknown_shape"] = len(trip_shapes - distinct)

        # --- translations (E04) ---------------------------------------
        if z.has("translations.txt"):
            st = ReadStats("translations.txt")
            langs: collections.Counter[str] = collections.Counter()
            key = None
            for row in z.rows("translations.txt", st):
                if key is None:
                    key = "language" if "language" in row else (
                        "lang" if "lang" in row else "")
                    fp.translations_schema = (
                        "gtfs-official (table_name/field_name/language/record_id)"
                        if key == "language" else
                        "mot-legacy (trans_id/lang/translation)" if key == "lang"
                        else "unrecognised")
                if key:
                    langs[row.get(key, "")] += 1
            fp.translations_rows = st.rows
            fp.translations_languages = dict(langs)
            fp.rows["translations"] = st.rows
            fp.read_stats["translations.txt"] = st.as_dict()

        # --- remaining small members, counted for completeness --------
        for member in ("fare_attributes.txt", "fare_rules.txt", "networks.txt",
                       "levels.txt", "frequencies.txt", "transfers.txt"):
            if z.has(member):
                fp.rows[member[:-4]] = _count_rows(z, member, fp)

    fp.detail_departures = detail_departures
    fp.detail_routes = detail_routes
    return fp


def max_time_roundtrip(fp: FeedParse) -> dict:
    """E02 evidence: the largest observed time survives parse -> format -> parse."""
    raw = fp.stop_times_max_raw
    if raw is None:
        return {"observed": False}
    secs = parse_gtfs_time(raw)
    back = format_gtfs_time(secs)
    return {
        "observed": True,
        "raw": raw,
        "seconds_from_service_day_start": secs,
        "formatted_back": back,
        "roundtrip_exact": back == raw,
        "day_offset": secs // 86400,
        "wall_clock_within_service_day": f"+{secs // 86400}d {format_gtfs_time(secs % 86400)}",
        "rows_at_or_after_24h": fp.stop_times_over_24h,
    }
