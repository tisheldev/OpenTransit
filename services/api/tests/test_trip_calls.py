"""Pure tests for lossless trip-call projection and dated engine parity."""

from datetime import UTC, date, datetime

import pytest

from opentransit.core.trip_calls import (
    EngineCall,
    EngineProfile,
    ExpectedUtcEvent,
    ReconciliationError,
    TripCallError,
    project_profile,
    reconcile_profile,
    source_profile_from_rows,
)

FULL_TRIP_ID = "Trip-2026-route_07-source-trip-900123"
SERVICE_ID = "weekday-service-2026"
SERVICE_DATE = date(2026, 9, 30)


def profile(rows):
    return source_profile_from_rows(FULL_TRIP_ID, SERVICE_ID, rows)


def raw_call(sequence, stop, *, arrival=None, departure=None, pickup=0, dropoff=0):
    row = {
        "stop_sequence": str(sequence),
        "stop_id": stop,
        "pickup_type": str(pickup),
        "drop_off_type": str(dropoff),
    }
    if arrival is not None:
        row["arrival_time"] = arrival
    if departure is not None:
        row["departure_time"] = departure
    return row


def test_same_minute_raw_regression_is_diagnosed_and_projected_with_bounds():
    source = profile(
        [
            raw_call(1, "origin", departure="08:00:50"),
            raw_call(5, "middle", arrival="08:01:20", departure="08:01:30"),
            raw_call(9, "destination", arrival="08:01:25"),
        ]
    )
    result = project_profile(source)
    assert source.trip_id == FULL_TRIP_ID
    assert [event.effective_seconds for event in result.events] == [28800, 28860, 28860, 28860]
    assert len(result.raw_chronology_diagnostics) == 1
    assert result.raw_chronology_clean is False
    assert result.raw_events[-1].raw_seconds == 28885
    assert result.raw_events[-1].effective_seconds == 28860
    assert result.policy.motis_source_commit == "061857d38a375248ae62b4ce722753368a75e474"
    assert result.policy.nigiri_source_commit == "0a08a1c09dad25c5d892b2fd7166b03e82d62970"
    assert result.policy.resolution_seconds == 60


def test_exact_minute_clamp_that_breaks_event_interval_is_rejected():
    source = profile(
        [
            raw_call(1, "origin", departure="08:02:00"),
            raw_call(2, "destination", arrival="08:01:00"),
        ]
    )
    with pytest.raises(TripCallError, match="escapes its raw minute bounds"):
        project_profile(source)


def test_sixty_one_second_interval_distortion_is_rejected():
    source = profile(
        [
            raw_call(1, "origin", departure="08:01:59"),
            raw_call(2, "destination", arrival="08:00:58"),
        ]
    )
    with pytest.raises(TripCallError, match="distorts by 61 seconds"):
        project_profile(source)


def test_cumulative_overbucket_regression_is_rejected_even_when_calls_are_distinct():
    source = profile(
        [
            raw_call(1, "origin", departure="08:00:01"),
            raw_call(5, "loop", arrival="08:00:59", departure="08:01:59"),
            raw_call(9, "destination", arrival="08:00:59"),
        ]
    )
    with pytest.raises(TripCallError, match="distorts by 60 seconds"):
        project_profile(source)


def test_after_midnight_feed_times_keep_service_day_seconds_without_wrap():
    source = profile(
        [
            raw_call(1, "origin", departure="25:10:01"),
            raw_call(2, "destination", arrival="25:40:59"),
        ]
    )
    result = project_profile(source)
    assert [event.raw_seconds for event in result.events] == [90601, 92459]
    assert [event.effective_seconds for event in result.events] == [90600, 92400]


def test_loop_calls_with_identical_stops_and_clocks_remain_distinct_by_sequence():
    source = profile(
        [
            raw_call(1, "loop-stop", departure="08:00:00"),
            raw_call(5, "loop-stop", arrival="08:00:00", departure="08:00:00"),
            raw_call(9, "loop-stop", arrival="08:00:00", departure="08:00:00"),
            raw_call(17, "loop-stop", arrival="08:00:00"),
        ]
    )
    result = project_profile(source)
    assert [(event.sequence, event.ordinal) for event in result.events] == [
        (1, 0),
        (5, 1),
        (5, 1),
        (9, 2),
        (9, 2),
        (17, 3),
    ]
    assert {event.stop_id for event in result.events} == {"loop-stop"}
    assert {event.effective_seconds for event in result.events} == {28800}


@pytest.mark.parametrize(
    "rows",
    [
        [raw_call(1, "a", departure="08:00:00"), raw_call(1, "b", arrival="08:01:00")],
        [raw_call(2, "a", departure="08:00:00"), raw_call(1, "b", arrival="08:01:00")],
        [raw_call(1, "a", departure="-01:00:00"), raw_call(2, "b", arrival="08:01:00")],
        [
            raw_call(1, "a", arrival="08:00:30", departure="08:00:29"),
            raw_call(2, "b", arrival="08:01:00"),
        ],
    ],
)
def test_malformed_sequence_negative_clock_and_same_call_regression_fail(rows):
    with pytest.raises(TripCallError):
        profile(rows)


@pytest.mark.parametrize("pickup,dropoff", [(4, 0), (0, 4), (-1, 0), (0, -1)])
def test_pickup_and_dropoff_rules_preserve_only_gtfs_values_zero_through_three(pickup, dropoff):
    with pytest.raises(TripCallError):
        profile(
            [
                raw_call(1, "a", departure="08:00:00", pickup=pickup),
                raw_call(2, "b", arrival="08:01:00", dropoff=dropoff),
            ]
        )


def _reconcilable_profile():
    source = profile(
        [
            raw_call(5, "stop-a", departure="08:00:00", pickup=2),
            raw_call(9, "stop-b", arrival="08:05:00", dropoff=3),
        ]
    )
    expected = (
        ExpectedUtcEvent(5, 0, "departure", 28800, datetime(2026, 9, 30, 5, 0, tzinfo=UTC)),
        ExpectedUtcEvent(9, 1, "arrival", 29100, datetime(2026, 9, 30, 5, 5, tzinfo=UTC)),
    )
    engine = EngineProfile(
        engine_trip_id="20260930_08:00_mot60day_Trip-2026-route_07-source-trip-900123",
        source_trip_id=FULL_TRIP_ID,
        service_id=SERVICE_ID,
        service_date=SERVICE_DATE,
        calls=(
            EngineCall("stop-a", None, expected[0].at_utc),
            EngineCall("stop-b", expected[1].at_utc, None),
        ),
    )
    return source, engine, expected


def test_reconciliation_matches_exact_full_dated_identity_stop_vector_and_verified_clocks():
    source, engine, expected = _reconcilable_profile()
    result = reconcile_profile(
        source,
        engine,
        expected_engine_trip_id=engine.engine_trip_id,
        expected_service_date=SERVICE_DATE,
        expected_utc_events=expected,
    )
    assert result.profile_id == FULL_TRIP_ID
    assert result.service_id == SERVICE_ID
    assert result.service_date == SERVICE_DATE
    assert result.stop_vector == ("stop-a", "stop-b")
    assert result.structural_match is True
    assert result.raw_chronology_clean is True


def test_reconciliation_rejects_mismatched_whole_stop_vector():
    source, engine, expected = _reconcilable_profile()
    wrong = EngineProfile(
        engine.engine_trip_id,
        engine.source_trip_id,
        engine.service_id,
        engine.service_date,
        (engine.calls[0], EngineCall("other-stop", engine.calls[1].arrival_utc, None)),
    )
    with pytest.raises(ReconciliationError, match="ordered stop-call vectors differ"):
        reconcile_profile(
            source,
            wrong,
            expected_engine_trip_id=engine.engine_trip_id,
            expected_service_date=SERVICE_DATE,
            expected_utc_events=expected,
        )


def test_reconciliation_rejects_wrong_engine_clock_or_missing_required_field():
    source, engine, expected = _reconcilable_profile()
    shifted = EngineProfile(
        engine.engine_trip_id,
        engine.source_trip_id,
        engine.service_id,
        engine.service_date,
        (EngineCall("stop-a", None, datetime(2026, 9, 30, 5, 1, tzinfo=UTC)), engine.calls[1]),
    )
    with pytest.raises(ReconciliationError, match="differs from verified expected"):
        reconcile_profile(
            source,
            shifted,
            expected_engine_trip_id=engine.engine_trip_id,
            expected_service_date=SERVICE_DATE,
            expected_utc_events=expected,
        )
    missing = EngineProfile(
        engine.engine_trip_id,
        engine.source_trip_id,
        engine.service_id,
        engine.service_date,
        (EngineCall("stop-a", None, None), engine.calls[1]),
    )
    with pytest.raises(ReconciliationError, match="missing, extra or unknown"):
        reconcile_profile(
            source,
            missing,
            expected_engine_trip_id=engine.engine_trip_id,
            expected_service_date=SERVICE_DATE,
            expected_utc_events=expected,
        )


@pytest.mark.parametrize(
    "engine_id,source_id,service_date",
    [
        ("wrong-engine-id", FULL_TRIP_ID, SERVICE_DATE),
        (
            "20260930_08:00_mot60day_Trip-2026-route_07-source-trip-900123",
            "normalized-trip-900123",
            SERVICE_DATE,
        ),
        (
            "20260930_08:00_mot60day_Trip-2026-route_07-source-trip-900123",
            FULL_TRIP_ID,
            date(2026, 10, 1),
        ),
    ],
)
def test_reconciliation_rejects_full_trip_or_service_date_identity_mismatch(
    engine_id, source_id, service_date
):
    source, engine, expected = _reconcilable_profile()
    wrong = EngineProfile(engine_id, source_id, engine.service_id, service_date, engine.calls)
    with pytest.raises(ReconciliationError):
        reconcile_profile(
            source,
            wrong,
            expected_engine_trip_id=engine.engine_trip_id,
            expected_service_date=SERVICE_DATE,
            expected_utc_events=expected,
        )


def test_reconciliation_rejects_expected_clock_not_bound_to_projected_seconds():
    source, engine, expected = _reconcilable_profile()
    wrong = (expected[0], ExpectedUtcEvent(9, 1, "arrival", 29099, expected[1].at_utc))
    with pytest.raises(ReconciliationError, match="not bound to projected"):
        reconcile_profile(
            source,
            engine,
            expected_engine_trip_id=engine.engine_trip_id,
            expected_service_date=SERVICE_DATE,
            expected_utc_events=wrong,
        )
