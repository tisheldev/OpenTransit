import csv
import zipfile
from pathlib import Path

import pytest

from opentransit.build.validation import FeedValidationError, validate_feed

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "gtfs"


def make_zip(path: Path, files: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def fixture_files() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in FIXTURE_DIR.iterdir()}


def make_inputs(tmp_path: Path, *, files=None, mapping=None):
    gtfs = make_zip(tmp_path / "gtfs.zip", files or fixture_files())
    mapping = mapping or (
        "LineDetailRecordId,OfficeLineId,Direction,LineAlternative,FromDate,ToDate,TripId,DayInWeek,DepartureTime\n"
        "1,2,1,0,28/09/2026,28/09/2026,101,2,23:50,\n"
        "2,2,1,0,29/09/2026,29/09/2026,101,3,23:50,\n"
        "3,2,1,0,30/09/2026,30/09/2026,101,4,23:50,\n"
        "4,2,1,0,02/10/2026,02/10/2026,101,6,23:50,\n"
        "5,2,1,0,03/10/2026,03/10/2026,101,7,23:50,\n"
    )
    mapping_zip = make_zip(tmp_path / "mapping.zip", {"TripIdToDate.txt": mapping})
    return gtfs, mapping_zip


def test_fixture_validates_calendar_dates_only_compatible_pair_and_loop(tmp_path):
    files = fixture_files()
    del files["calendar.txt"]
    gtfs, mapping = make_inputs(tmp_path, files=files)

    report = validate_feed(gtfs, mapping)

    assert report.valid
    assert report.coverage == {"from": "2026-09-29", "through": "2026-10-03", "activeDateCount": 4}
    assert report.pairing["feedTripCount"] == 1
    assert report.pairing["tripsWithoutMappedServiceDates"] == 0
    assert report.pairing["tripDateEvidenceSamples"][0]["tripId"] == "101_280926"
    assert report.integrity["time_integrity"]["afterMidnightRows"] == 6
    assert report.integrity["time_integrity"]["maxTimeRoundTrip"]["matches"]
    assert next(item for item in report.checks if item["id"] == "E02")["status"] == "pass"
    assert [item["id"] for item in report.checks if item["id"].startswith("E")] == [
        f"E{i:02d}" for i in range(1, 11)
    ]
    assert next(item for item in report.checks if item["id"] == "E01")["status"] == "not_observed"


def test_rejects_foreign_key_and_coordinate_corruption(tmp_path):
    files = fixture_files()
    files["trips.txt"] = files["trips.txt"].replace("r1,weekday", "missing,weekday")
    files["stops.txt"] = files["stops.txt"].replace("32.0080,34.0080", "91,34.0080")
    gtfs, mapping = make_inputs(tmp_path, files=files)

    with pytest.raises(FeedValidationError) as raised:
        validate_feed(gtfs, mapping)

    checks = {item["id"]: item for item in raised.value.report.checks}
    assert checks["E08"]["status"] == "fail"
    assert checks["V02"]["status"] == "fail"


def test_rejects_reversed_trip_mapping_range_and_full_service_date_gap(tmp_path):
    gtfs, mapping = make_inputs(
        tmp_path,
        mapping=("TripId,FromDate,ToDate,DayInWeek\n101,03/10/2026,28/09/2026,7\n"),
    )

    with pytest.raises(FeedValidationError) as raised:
        validate_feed(gtfs, mapping)

    assert raised.value.report.pairing["reversedRanges"]
    assert raised.value.report.pairing["tripsWithoutMappedServiceDates"] == 1


def test_static_pairing_rejects_incomplete_key_coverage(tmp_path):
    gtfs, mapping = make_inputs(
        tmp_path,
        mapping=("TripId,FromDate,ToDate,DayInWeek\n999,28/09/2026,03/10/2026,2\n"),
    )

    with pytest.raises(FeedValidationError) as raised:
        validate_feed(gtfs, mapping)

    checks = {item["id"]: item for item in raised.value.report.checks}
    assert checks["E05"]["status"] == "fail"
    assert checks["V09"]["status"] == "fail"


def test_static_pairing_rejects_disjoint_mapping_window(tmp_path):
    gtfs, mapping = make_inputs(
        tmp_path,
        mapping=("TripId,FromDate,ToDate,DayInWeek\n101,01/01/2025,07/01/2025,2\n"),
    )

    with pytest.raises(FeedValidationError) as raised:
        validate_feed(gtfs, mapping)

    assert raised.value.report.pairing["dateWindowsOverlap"] is False
    assert raised.value.report.pairing["staticPairingVerdict"] == "REJECTED"


def test_partial_service_date_coverage_is_static_pass_with_diagnostic(tmp_path):
    gtfs, mapping = make_inputs(
        tmp_path,
        mapping=("TripId,FromDate,ToDate,DayInWeek\n101,30/09/2026,30/09/2026,4\n"),
    )

    report = validate_feed(gtfs, mapping)

    assert report.valid
    assert report.pairing["fullTripIdentityCount"] == 1
    assert report.pairing["tripSamplesWithoutMappedDates"] == ["101_280926"]
    assert report.pairing["unmappedActiveServiceDateCount"] > 0
    assert report.pairing["staticPairingVerdict"] == "ACCEPTED"
    assert report.pairing["serviceDateCoverageDiagnostic"] == "warning_only_not_realtime_proof"


def test_rejects_duplicate_identifiers_and_invalid_gtfs_time(tmp_path):
    files = fixture_files()
    files["routes.txt"] += "r1,agency,2,Duplicate,3\n"
    files["stop_times.txt"] = files["stop_times.txt"].replace("24:02:00", "25:99:00")
    gtfs, mapping = make_inputs(tmp_path, files=files)

    with pytest.raises(ValueError, match="invalid GTFS time"):
        validate_feed(gtfs, mapping)


def test_fixture_csv_files_are_well_formed():
    for path in FIXTURE_DIR.iterdir():
        with path.open(encoding="utf-8", newline="") as stream:
            assert list(csv.reader(stream))


def test_stop_time_chronology_uses_stop_sequence_not_file_order(tmp_path):
    files = fixture_files()
    header, *rows = files["stop_times.txt"].splitlines()
    files["stop_times.txt"] = "\n".join([header, *reversed(rows)]) + "\n"
    gtfs, mapping = make_inputs(tmp_path, files=files)

    assert validate_feed(gtfs, mapping).valid


def test_small_raw_regression_is_retained_but_bounded_projection_passes(tmp_path):
    files = fixture_files()
    files["stop_times.txt"] = files["stop_times.txt"].replace(
        "101_280926,24:20:00,24:21:00,s3,3",
        "101_280926,24:02:30,24:03:00,s3,3",
    )
    gtfs, mapping = make_inputs(tmp_path, files=files)

    report = validate_feed(gtfs, mapping)

    time_integrity = report.integrity["time_integrity"]
    assert report.valid
    assert next(item for item in report.checks if item["id"] == "V04")["status"] == "pass"
    assert time_integrity["cross_call_chronology"]["count"] == 1
    assert time_integrity["cross_call_chronology"]["verdict"] == "diagnostic_fail"
    assert time_integrity["cross_call_chronology"]["blocking"] is False
    effective = time_integrity["effective_chronology"]
    assert effective["policyId"] == "motis-minute-bracket-v1"
    assert effective["status"] == "pass"
    assert effective["validatedProfileCount"] == 1
    assert effective["effectiveEventCount"] == 6


@pytest.mark.parametrize(
    "sequence_three_times",
    ["24:02:00,24:03:00", "24:01:59,24:02:00"],
    ids=["exact-minute-clamp", "sixty-one-second-reversal"],
)
def test_projection_rejects_event_outside_its_raw_minute(tmp_path, sequence_three_times):
    files = fixture_files()
    files["stop_times.txt"] = files["stop_times.txt"].replace(
        "24:20:00,24:21:00,s3,3", f"{sequence_three_times},s3,3"
    )
    gtfs, mapping = make_inputs(tmp_path, files=files)

    with pytest.raises(FeedValidationError) as raised:
        validate_feed(gtfs, mapping)

    report = raised.value.report
    effective = report.integrity["time_integrity"]["effective_chronology"]
    assert next(item for item in report.checks if item["id"] == "V04")["status"] == "fail"
    assert effective["status"] == "fail"
    assert effective["profileErrorCount"] == 1
    assert "escapes its raw minute bounds" in effective["samples"][0]["error"]


def test_missing_effective_clock_is_blocked_without_interpolation(tmp_path):
    files = fixture_files()
    files["stop_times.txt"] = files["stop_times.txt"].replace(
        "101_280926,24:02:00,24:03:00,s2,2", "101_280926,24:02:00,,s2,2"
    )
    gtfs, mapping = make_inputs(tmp_path, files=files)

    with pytest.raises(FeedValidationError) as raised:
        validate_feed(gtfs, mapping)

    effective = raised.value.report.integrity["time_integrity"]["effective_chronology"]
    assert effective["status"] == "fail"
    assert "Required effective clock event is missing" in effective["samples"][0]["error"]


def test_rejects_non_chronological_calls_and_invalid_pickup_dropoff(tmp_path):
    files = fixture_files()
    files["stop_times.txt"] = files["stop_times.txt"].replace(
        "101_280926,24:20:00,24:21:00,s3,3",
        "101_280926,23:20:00,23:21:00,s3,3",
    )
    files["stop_times.txt"] = (
        files["stop_times.txt"]
        .replace(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence",
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type",
        )
        .replace(
            "101_280926,23:50:00,23:50:00,s1,1",
            "101_280926,23:50:00,23:50:00,s1,1,9,0",
        )
    )
    gtfs, mapping = make_inputs(tmp_path, files=files)

    with pytest.raises(FeedValidationError) as raised:
        validate_feed(gtfs, mapping)

    checks = {item["id"]: item for item in raised.value.report.checks}
    assert checks["E02"]["status"] == "pass"
    assert checks["V04"]["status"] == "fail"
    assert raised.value.report.integrity["time_integrity"]["non_chronological_stop_times"] > 0
    assert raised.value.report.integrity["time_integrity"]["pickup_dropoff_rule_errors"] == 1
    chronology = raised.value.report.integrity["time_integrity"]["cross_call_chronology"]
    assert chronology["count"] == 1
    assert chronology["affectedTripCount"] == 1
    assert len(chronology["samples"]) == 1
    sample = chronology["samples"][0]
    assert sample["tripId"] == "101_280926"
    assert sample["previousSequence"] == 2
    assert sample["sequence"] == 3
    assert sample["previousSourceLine"] == 3
    assert sample["sourceLine"] == 4
    assert sample["activeServiceDateCount"] == 5
    assert sample["activeInImportWindow"] is True


def test_same_stop_departure_before_arrival_is_not_cross_call_regression(tmp_path):
    files = fixture_files()
    files["stop_times.txt"] = files["stop_times.txt"].replace(
        "101_280926,23:50:00,23:50:00,s1,1",
        "101_280926,23:51:00,23:50:00,s1,1",
    )
    gtfs, mapping = make_inputs(tmp_path, files=files)

    with pytest.raises(FeedValidationError) as raised:
        validate_feed(gtfs, mapping)

    time_integrity = raised.value.report.integrity["time_integrity"]
    assert time_integrity["departure_before_arrival"] == 1
    assert time_integrity["cross_call_chronology"]["count"] == 0
