"""OB-01 historical inference on hand-built pings and a tiny GTFS archive (no downloads)."""

import io
import json
import zipfile
from datetime import UTC, date, datetime

from opentransit.history.arrivals import (
    CRUISE_MPS,
    MAX_BRACKET_S,
    ORIGIN_EPSILON_M,
    TrackPoint,
    clean_track,
    crossing,
    observe_calls,
)
from opentransit.history.distributions import Accumulator, day_type, percentile
from opentransit.history.schedule import Call, load_day, match_ride, service_origin
from opentransit.history.siri_archive import Ping, Ride, minute_keys, parse_snapshot

DAY = date(2026, 9, 15)
T0 = service_origin(DAY) + 8 * 3600  # 08:00 local


def ping(at, distance, order=1, trip_ref="100", line_ref="7"):
    return Ping(DAY, trip_ref, line_ref, "3", T0, at, distance, order, "s", 32.0, 34.8, 30, "v")


def ride(*pings):
    result = Ride("100", "7", "3", T0)
    for each in pings:
        result.add(each)
    return result


def test_snapshot_parsing_keeps_identity_and_cumulative_distance():
    visit = {
        "RecordedAtTime": "2026-09-15T08:01:00+03:00",
        "MonitoredVehicleJourney": {
            "LineRef": "7",
            "FramedVehicleJourneyRef": {
                "DataFrameRef": "2026-09-15",
                "DatedVehicleJourneyRef": "100",
            },
            "OperatorRef": "3",
            "OriginAimedDepartureTime": "2026-09-15T08:00:00+03:00",
            "VehicleLocation": {"Longitude": "34.8", "Latitude": "32.0"},
            "Velocity": "40",
            "VehicleRef": "v",
            "MonitoredCall": {"StopPointRef": "61362", "Order": "4", "DistanceFromStop": "1500"},
        },
    }
    no_location = {"RecordedAtTime": visit["RecordedAtTime"], "MonitoredVehicleJourney": {}}
    body = {
        "Siri": {
            "ServiceDelivery": {
                "StopMonitoringDelivery": [{"MonitoredStopVisit": [visit, no_location]}]
            }
        }
    }
    pings, skipped = parse_snapshot(json.dumps(body).encode(), compressed=False)
    assert skipped == 1
    (only,) = pings
    assert (only.service_date, only.trip_ref, only.line_ref) == (DAY, "100", "7")
    assert only.distance_m == 1500 and only.order == 4
    assert only.recorded_at - only.origin_departure == 60


def test_archive_keys_are_utc_minutes():
    start = datetime(2026, 9, 14, 23, 58, tzinfo=UTC)
    keys = list(minute_keys(start, datetime(2026, 9, 15, 0, 1, tzinfo=UTC)))
    assert keys == [
        "stride-siri-requester/2026/09/14/23/58.br",
        "stride-siri-requester/2026/09/14/23/59.br",
        "stride-siri-requester/2026/09/15/00/00.br",
    ]


def test_track_cleaning_drops_duplicates_backward_jumps_and_teleports():
    pings = [
        ping(T0, 0),
        ping(T0, 0),  # same RecordedAtTime from an overlapping snapshot
        ping(T0 + 60, 500),
        ping(T0 + 120, 480),  # 20 m back: tolerated jitter, held at 500
        ping(T0 + 180, 300),  # 200 m back: dropped
        ping(T0 + 240, 20_000),  # 19.5 km in 2 min: dropped
        ping(T0 + 300, 1500),
    ]
    observed = ride(*pings)
    track, stats = clean_track(observed.points)
    assert [(p.at - T0, p.distance) for p in track] == [(0, 0), (60, 500), (120, 500), (300, 1500)]
    assert (observed.duplicates, stats.backwards, stats.speed_outliers) == (1, 1, 1)


def test_crossing_interpolates_and_refuses_long_gaps():
    track = [
        TrackPoint(-60, -300),
        TrackPoint(0, 0),
        TrackPoint(60, 600),
        TrackPoint(60 + MAX_BRACKET_S + 1, 900),
    ]
    assert crossing(track, 300) == (30, 60, None)  # moving at both ends: plain interpolation
    assert crossing(track, 700)[2] == "gapTooLong"
    assert crossing(track, -300)[2] == "beforeFirstPing"
    assert crossing(track, 5000)[2] == "afterLastPing"


def test_parked_pre_departure_pings_do_not_count_as_departure():
    calls = [
        Call(1, "A", T0, T0, 0.0),
        Call(2, "B", T0 + 300, T0 + 300, 1000.0),
        Call(3, "C", T0 + 600, T0 + 600, 2000.0),
    ]
    # Reported against the ride from 30 min early while parked at the origin (last parked ping
    # 08:01); next ping 08:03 at 600 m. Even spreading would put departure at 08:01:10.
    parked = [ping(T0 - 1800 + 60 * i, 0) for i in range(32)]
    moving = [ping(T0 + 180, 600), ping(T0 + 300, 800), ping(T0 + 420, 1200), ping(T0 + 600, 2100)]
    track, _ = clean_track(ride(*parked, *moving).points)
    origin, stop_b, stop_c = observe_calls(track, calls)
    start = T0 + 180 - 600 / CRUISE_MPS  # latest start that still covers 600 m by 08:03
    assert origin.observed == round(start + ORIGIN_EPSILON_M / 600 * (T0 + 180 - start))
    assert origin.observed > T0  # never earlier than the scheduled departure here
    assert stop_b.observed - stop_b.scheduled == 60  # moving through: plain interpolation
    assert stop_c.observed - stop_c.scheduled == -20  # 20 s ahead of schedule at C


def test_distribution_rows_carry_samples_and_israeli_day_types():
    assert [day_type(date(2026, 9, d)) for d in (13, 17, 18, 19)] == [
        "weekday",
        "weekday",
        "friday",
        "saturday",
    ]
    assert percentile([0, 10, 20, 30], 0.5) == 15
    accumulator = Accumulator("weekday")
    for late in (60, 120, 180):
        accumulator.add(
            "7",
            [
                observe_like("A", T0, T0 + late),
                observe_like("B", T0 + 300, T0 + 300 + late * 2),
            ],
        )
    (delay_a, delay_b) = accumulator.delay_rows()
    assert delay_a["samples"] == 3 and delay_a["delayP50Seconds"] == 120 and delay_a["hour"] == 8
    (segment,) = accumulator.segment_rows()
    assert segment["scheduledSecondsMedian"] == 300 and segment["runP50Seconds"] == 420


def observe_like(stop, scheduled, observed):
    from opentransit.history.arrivals import ObservedCall

    return ObservedCall(0, stop, scheduled, observed, 60, None)


def gtfs_zip() -> bytes:
    buffer = io.BytesIO()
    files = {
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\nwk,1,1,1,1,0,0,1,20260901,20261031\nsat,0,0,0,0,0,1,0,20260901,"
        "20261031\n",
        "calendar_dates.txt": "service_id,date,exception_type\nwk,20260916,2\n",
        "routes.txt": "route_id,agency_id,route_short_name,route_desc\n7,3,22,30022-1-#\n"
        "8,3,23,30023-1-#\n",
        "trips.txt": "route_id,service_id,trip_id\n7,wk,100_150926\n7,sat,100_190926\n"
        "7,wk,200_150926\n7,wk,200_160926\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence,"
        "shape_dist_traveled\n100_150926,08:05:00,08:05:00,B,2,1000\n"
        "100_150926,08:00:00,08:00:00,A,1,0\n100_190926,09:00:00,09:00:00,A,1,0\n"
        "200_150926,09:00:00,09:00:00,A,1,0\n200_160926,09:00:00,09:00:00,A,1,0\n",
    }
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


def test_day_schedule_matches_rides_by_route_and_origin_time(tmp_path):
    feed = tmp_path / "feed.zip"
    feed.write_bytes(gtfs_zip())
    schedule = load_day(feed, DAY)
    assert set(schedule.trips) == {"100_150926", "200_150926", "200_160926"}
    trip, reason = match_ride(schedule, "7", T0)
    assert reason is None and trip.trip_id == "100_150926"
    assert [c.stop_id for c in trip.calls] == ["A", "B"] and trip.calls[1].distance_m == 1000.0
    assert match_ride(schedule, "7", T0 + 60) == (None, "noTripAtOriginTime")
    assert match_ride(schedule, "9", T0) == (None, "routeNotInFeed")
    assert match_ride(schedule, "8", T0) == (None, "routeNotRunningOnServiceDate")
    assert match_ride(schedule, "7", T0 + 3600) == (None, "ambiguousRouteAndOrigin")
    assert set(load_day(feed, date(2026, 9, 16)).trips) == set()  # removed by calendar_dates
