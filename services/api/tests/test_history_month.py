"""OB-01 multi-day driver: compact storage, per-day files, month tables, held-out check."""

import io
import zipfile
from datetime import date

from opentransit.history.month import (
    BUCKETS,
    MIN_COVERAGE,
    MIN_SAMPLES,
    MIN_SERVICE_DAYS,
    DayWriter,
    HeldOutCheck,
    MonthAggregate,
    bucket_of,
    observe_day,
    publishable,
    read_bucket,
)
from opentransit.history.schedule import load_day, service_origin
from opentransit.history.siri_archive import Ping, Ride

DAY = date(2025, 11, 12)  # Wednesday, winter time (UTC+2)
ORIGIN = service_origin(DAY)
T8 = ORIGIN + 8 * 3600


def feed(tmp_path):
    files = {
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\nwk,1,1,1,1,0,0,1,20251101,20251130\n",
        "routes.txt": "route_id,agency_id,route_short_name,route_desc\n7,3,22,x\n9,5,1,y\n",
        "trips.txt": "route_id,service_id,trip_id\n7,wk,a_1\n7,wk,b_1\n9,wk,c_1\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence,"
        "shape_dist_traveled\n"
        "a_1,08:05:00,08:05:00,B,2,1000\na_1,08:00:00,08:00:00,A,1,0\n"
        "a_1,08:10:00,08:10:00,C,3,2000\n"
        "b_1,09:00:00,09:00:00,A,1,0\nb_1,09:05:00,09:05:00,B,2,1000\n"
        "c_1,08:00:00,08:00:00,X,1,0\nc_1,08:04:00,08:04:00,Y,2,\n",
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    path = tmp_path / "feed.zip"
    path.write_bytes(buffer.getvalue())
    return path


def ping(at, metres, line="7", origin=T8, trip_ref="100"):
    return Ping(DAY, trip_ref, line, "3", origin, at, metres, 1, "s", 32.0, 34.8, 30, "v")


def ride_of(*pings):
    first = pings[0]
    ride = Ride(first.trip_ref, first.line_ref, first.operator_ref, first.origin_departure)
    for each in pings:
        ride.add(each)
    return ride


def test_compact_ride_keeps_first_copy_of_each_recorded_time():
    ride = ride_of(ping(T8, 0), ping(T8, 40), ping(T8 + 60, 500))
    assert ride.points == {T8: (0, 1), T8 + 60: (500, 1)}
    assert ride.duplicates == 1


def test_compact_trip_calls_are_sorted_with_missing_distance(tmp_path):
    schedule = load_day(feed(tmp_path), DAY)
    calls = schedule.trips["a_1"].calls
    assert [(c.sequence, c.stop_id, c.arrival - T8) for c in calls] == [
        (1, "A", 0),
        (2, "B", 300),
        (3, "C", 600),
    ]
    assert schedule.trips["c_1"].calls[1].distance_m is None
    assert schedule.by_origin[("7", T8)] == ["a_1"]


def observed_day(tmp_path):
    schedule = load_day(feed(tmp_path), DAY)
    on_time = ride_of(*(ping(T8 - 60 + 60 * i, max(0, 200 * i - 200)) for i in range(14)))
    sparse = ride_of(ping(T8 + 60, 100, trip_ref="101"), ping(T8 + 120, 300, trip_ref="101"))
    stray = ride_of(ping(T8, 0, line="7", origin=T8 + 1, trip_ref="102"))
    rides = {"r1": on_time, "r2": sparse, "r3": stray}
    writer = DayWriter(tmp_path / "day")
    summary = observe_day(schedule, rides, writer.write)
    writer.close()
    return summary


def test_observe_day_writes_every_scheduled_call_with_outcomes(tmp_path):
    summary = observed_day(tmp_path)
    assert summary["matching"]["outcomes"] == {
        "matched": 2,
        "extraRideForSameTripDropped": 1,
        "noTripAtOriginTime": 1,
        "noTripAtOriginTimeFewerThan3Pings": 1,
    }
    assert summary["matching"]["scheduledTrips"] == 3
    assert summary["matching"]["scheduledTripsObserved"] == 1
    rows = [row for bucket in range(BUCKETS) for row in read_bucket(tmp_path / "day", bucket)]
    by_trip = {}
    for trip_id, _route, sequence, stop_id, _scheduled, delay, _bracket, reason in rows:
        by_trip.setdefault(trip_id, []).append((sequence, stop_id, delay, reason))
    assert [r[3] for r in by_trip["b_1"]] == ["tripNotObserved", "tripNotObserved"]
    assert [r[3] for r in by_trip["c_1"]] == ["tripNotObserved", "tripNotObserved"]
    sequence, stop, delay, reason = by_trip["a_1"][1]
    assert (sequence, stop, reason) == (2, "B", "") and delay is not None  # kept the denser ride
    assert summary["calls"]["tripNotObserved"] == 4
    assert {bucket_of("7"), bucket_of("9")} <= set(range(BUCKETS))


def rows_for(trip, route, delays, base=T8, step=300):
    return [
        (trip, route, index + 1, f"S{index}", base + index * step, delay, bracket, reason)
        for index, delay in enumerate(delays)
        for bracket, reason in [(60, "") if delay is not None else (None, "gapTooLong")]
    ]


def test_month_tables_carry_coverage_days_and_publishability():
    aggregate = MonthAggregate()
    per_day = MIN_SAMPLES // MIN_SERVICE_DAYS + 1
    for day_index in range(MIN_SERVICE_DAYS + 1):
        for trip in range(per_day):
            aggregate.add(day_index, "weekday", rows_for(f"t{trip}", "7", [60, 120, None]))
    rows = {(r["stopId"]): r for r in aggregate.delay_rows()}
    first = rows["S0"]
    assert first["scheduledCalls"] == first["samples"] == (MIN_SERVICE_DAYS + 1) * per_day
    assert first["serviceDays"] == MIN_SERVICE_DAYS + 1 and first["coverage"] == 1.0
    assert first["delayP50Seconds"] == 60 and first["publishable"] is True
    unobserved = rows["S2"]
    assert unobserved["samples"] == 0 and unobserved["delayP50Seconds"] is None
    assert unobserved["publishable"] is False
    segments = {(r["fromStopId"], r["toStopId"]): r for r in aggregate.segment_rows()}
    assert segments[("S0", "S1")]["runP50Seconds"] == 360  # 300 s scheduled + 60 s lost
    assert segments[("S0", "S1")]["scheduledSecondsMedian"] == 300
    assert segments[("S1", "S2")]["samples"] == 0
    hourly = aggregate.hourly_rows()["weekday"]["8"]  # origin calls excluded
    assert hourly["n"] == first["samples"] and hourly["p50"] == 125  # 120 s, 10 s bin centre


def test_publishability_rule_needs_samples_days_and_coverage():
    assert publishable(MIN_SAMPLES, MIN_SERVICE_DAYS, MIN_COVERAGE)
    assert not publishable(MIN_SAMPLES - 1, MIN_SERVICE_DAYS, 1.0)
    assert not publishable(500, MIN_SERVICE_DAYS - 1, 1.0)
    assert not publishable(500, 20, MIN_COVERAGE - 0.01)


def test_held_out_check_reports_band_shares_and_skill_against_schedule():
    calibration = {
        ("7", "S0", 8, "weekday"): {
            "p10": 0,
            "p50": 60,
            "p90": 120,
            "samples": 40,
            "publishable": True,
        }
    }
    check = HeldOutCheck(calibration, baseline=lambda key, scheduled: 0)
    for value in (-30, 30, 50, 70, 90, 100, 110, 115, 130, 60):
        check.add(("7", "S0", 8, "weekday"), value, scheduled=0)
    check.add(("7", "S9", 8, "weekday"), 10, scheduled=0)  # not in calibration
    report = check.report()
    band = report["byStratum"]["publishable"]
    assert band["observations"] == 10
    assert (band["belowP10"], band["aboveP90"]) == (0.1, 0.1)
    assert band["withinP10P90"] == 0.8 and band["belowP50"] == 0.3
    assert report["observationsWithoutCalibrationKey"] == 1
    errors = band["medianAbsErrorSeconds"]
    assert errors["calibrationP50"] < errors["schedule"]
