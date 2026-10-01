import zipfile
from datetime import date

import pytest

from opentransit.build.identity import compare_ids


def test_full_trip_ids_and_daily_provenance(tmp_path):
    paths = [tmp_path / "old.zip", tmp_path / "new.zip"]
    for path, trip in zip(paths, ("12_300926", "12_011026"), strict=True):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("stops.txt", "stop_id\n1\n2\n")
            archive.writestr("routes.txt", "route_id\n7\n")
            archive.writestr("trips.txt", "trip_id\n" + trip + "\n")
    report = compare_ids(*paths, date(2026, 9, 30), date(2026, 10, 1))
    assert report["consecutiveDailyFeeds"]
    assert report["counts"]["stops"]["retained"] == 2
    assert report["counts"]["trips"]["retained"] == 0
    assert len(report["previous"]["sha256"]) == 64
    historical = compare_ids(*paths, date(2026, 9, 4), date(2026, 10, 1))
    assert not historical["consecutiveDailyFeeds"]
    with pytest.raises(ValueError):
        compare_ids(*paths, date(2026, 10, 1), date(2026, 9, 30))
