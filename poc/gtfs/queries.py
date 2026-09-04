"""Queries that turn a loaded database into PRD §6 evidence.

PRD §6 step 5 is "verify that several known Israeli lines and stations
exist", with Tel Aviv, Jerusalem, Haifa, Israel Railways and multiple bus
operators named explicitly. Nothing here hardcodes a route number or a stop
id: cities come out of `stop_desc`, rail comes out of `route_type = 2`, and
operators come out of `agency.txt`. Whatever the feed says is the answer.
"""

from __future__ import annotations

# The three cities PRD §6 names, written as MOT writes them in stop_desc.
# These are municipality strings read out of the feed, not invented ids.
CITY_TEL_AVIV = "תל אביב יפו"
CITY_JERUSALEM = "ירושלים"
CITY_HAIFA = "חיפה"

# GTFS route_type, spec values — 2 = rail, 3 = bus, 0 = tram/light rail.
RAIL, BUS, TRAM = 2, 3, 0


def city_summary(conn, schema: str, city: str, departures: dict) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT stop_id, stop_name FROM {schema}.stops WHERE city = %s", (city,))
        rows = cur.fetchall()
    ids = [r[0] for r in rows]
    total_dep = sum(departures.get(i, 0) for i in ids)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT count(DISTINCT location_type) FROM {schema}.stops WHERE city = %s",
            (city,))
        _ = cur.fetchone()
    return {
        "city": city,
        "stops": len(ids),
        "departures_in_feed_window": total_dep,
        "example_stop_names": [r[1] for r in rows[:5]],
        "ok": len(ids) > 0 and total_dep > 0,
    }


def rail_summary(conn, schema: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT r.agency_id, r.agency_name, count(DISTINCT r.route_id) AS routes, "
            f"       count(t.trip_id) AS trips "
            f"FROM {schema}.routes r LEFT JOIN {schema}.trips t USING (route_id) "
            f"WHERE r.route_type = %s GROUP BY 1, 2 ORDER BY 3 DESC", (RAIL,))
        rows = cur.fetchall()
        cur.execute(
            f"SELECT r.route_id, r.route_short_name, r.route_long_name "
            f"FROM {schema}.routes r WHERE r.route_type = %s "
            f"ORDER BY r.route_id LIMIT 5", (RAIL,))
        examples = cur.fetchall()
    return {
        "route_type": RAIL,
        "operators": [{"agency_id": a, "agency_name": n, "routes": r, "trips": t}
                      for a, n, r, t in rows],
        "example_routes": [{"route_id": a, "short_name": b, "long_name": c}
                           for a, b, c in examples],
        "ok": bool(rows) and any(t > 0 for *_, t in rows),
    }


def bus_operator_summary(conn, schema: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT r.agency_id, r.agency_name, count(DISTINCT r.route_id) AS routes, "
            f"       count(t.trip_id) AS trips "
            f"FROM {schema}.routes r LEFT JOIN {schema}.trips t USING (route_id) "
            f"WHERE r.route_type = %s GROUP BY 1, 2 "
            f"ORDER BY 4 DESC NULLS LAST", (BUS,))
        rows = cur.fetchall()
    ops = [{"agency_id": a, "agency_name": n, "routes": r, "trips": t}
           for a, n, r, t in rows]
    with_trips = [o for o in ops if (o["trips"] or 0) > 0]
    return {
        "route_type": BUS,
        "operator_count": len(ops),
        "operators_with_trips": len(with_trips),
        "top_operators": ops[:10],
        "ok": len(with_trips) >= 2,
    }


def mode_summary(conn, schema: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT route_type, count(*) FROM {schema}.routes GROUP BY 1 ORDER BY 1")
        return {str(k): v for k, v in cur.fetchall()}


def location_type_distribution(conn, schema: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT coalesce(location_type, -1), count(*) FROM {schema}.stops "
            f"GROUP BY 1 ORDER BY 1")
        return {str(k): v for k, v in cur.fetchall()}


def snap_stop(conn, schema: str, lat: float, lon: float, limit: int = 1) -> list[dict]:
    """Nearest real stop(s) to an approximate coordinate, via PostGIS."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT stop_id, stop_name, city, location_type, parent_station, "
            f"       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s),4326)::geography) AS m "
            f"FROM {schema}.stops "
            f"ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326) LIMIT %s",
            (lon, lat, lon, lat, limit))
        return [{"stop_id": a, "stop_name": b, "city": c, "location_type": d,
                 "parent_station": e, "distance_m": round(f, 1)}
                for a, b, c, d, e, f in cur.fetchall()]


def nearest_named(conn, schema: str, lat: float, lon: float, name_he: str,
                  radius_m: int = 1500) -> list[dict]:
    """Stops within `radius_m` whose name contains the corpus's Hebrew name."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT stop_id, stop_name, city, location_type, parent_station, "
            f"       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography) AS m "
            f"FROM {schema}.stops "
            f"WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, %s) "
            f"  AND stop_name ILIKE %s "
            f"ORDER BY m LIMIT 25",
            (lon, lat, lon, lat, radius_m, f"%{name_he}%"))
        return [{"stop_id": a, "stop_name": b, "city": c, "location_type": d,
                 "parent_station": e, "distance_m": round(f, 1)}
                for a, b, c, d, e, f in cur.fetchall()]


def children_of(conn, schema: str, parent_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT stop_id, stop_name, platform_code, location_type "
            f"FROM {schema}.stops WHERE parent_station = %s ORDER BY stop_id",
            (parent_id,))
        return [{"stop_id": a, "stop_name": b, "platform_code": c, "location_type": d}
                for a, b, c, d in cur.fetchall()]


def stations_near(conn, schema: str, lat: float, lon: float,
                  radius_m: int = 400) -> list[dict]:
    """location_type=1 stations near a point, with their platform counts."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT p.stop_id, p.stop_name, count(c.stop_id) AS platforms, "
            f"       ST_Distance(p.geom::geography, ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography) m "
            f"FROM {schema}.stops p LEFT JOIN {schema}.stops c ON c.parent_station = p.stop_id "
            f"WHERE p.location_type = 1 "
            f"  AND ST_DWithin(p.geom::geography, ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography, %s) "
            f"GROUP BY 1,2,p.geom ORDER BY 4", (lon, lat, lon, lat, radius_m))
        return [{"stop_id": a, "stop_name": b, "platforms": c, "distance_m": round(d, 1)}
                for a, b, c, d in cur.fetchall()]


def rail_station_grouping(conn, schema: str) -> dict:
    """How much of the network actually uses parent_station, and for what.

    E09 assumes multi-platform stations are modelled as a parent with child
    platforms. Whether Israeli rail stations are modelled that way at all is a
    question about the feed, so it is measured rather than assumed.
    """
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {schema}.stops WHERE location_type = 1")
        stations = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {schema}.stops WHERE parent_station IS NOT NULL")
        children = cur.fetchone()[0]
        cur.execute(
            f"SELECT count(*) FROM {schema}.stops p WHERE p.location_type = 1 "
            f"AND NOT EXISTS (SELECT 1 FROM {schema}.stops c WHERE c.parent_station = p.stop_id)")
        childless = cur.fetchone()[0]
    return {"stations_location_type_1": stations,
            "stops_with_parent_station": children,
            "stations_with_no_children": childless}


def stations_with_platforms(conn, schema: str, limit: int = 10) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT p.stop_id, p.stop_name, p.city, count(c.stop_id) AS platforms "
            f"FROM {schema}.stops p JOIN {schema}.stops c ON c.parent_station = p.stop_id "
            f"WHERE p.location_type = 1 GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT %s", (limit,))
        return [{"stop_id": a, "stop_name": b, "city": c, "platforms": d}
                for a, b, c, d in cur.fetchall()]


def service_day_trip_counts(conn, schema: str) -> list[dict]:
    """Trips per active service date. This is where Shabbat shows up (E07)."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT d AS service_date, count(*) AS trips "
            f"FROM {schema}.trips t JOIN {schema}.calendars c USING (service_id), "
            f"     unnest(c.active_dates) AS d "
            f"GROUP BY 1 ORDER BY 1")
        return [{"date": a.isoformat(), "trips": b} for a, b in cur.fetchall()]
