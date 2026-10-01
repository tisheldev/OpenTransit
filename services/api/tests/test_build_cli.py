import json
from datetime import UTC, datetime

import pytest
from test_feed_validation import make_inputs

from opentransit.build import cli
from opentransit.build.fetch import FetchReport, FetchResult
from opentransit.build.prepare import sha256


def test_validation_command_preserves_failed_evidence_and_existing_output(tmp_path):
    gtfs, mapping = make_inputs(tmp_path)
    output = tmp_path / "result.json"
    args = ["validate", "--gtfs", str(gtfs), "--mapping", str(mapping), "--output", str(output)]
    assert cli.main(args) == 0
    original = output.read_bytes()
    assert json.loads(original)["valid"]
    assert cli.main(args) == 1
    assert output.read_bytes() == original


@pytest.mark.parametrize("slot", ["blue", "green"])
def test_build_command_forwards_local_engine_slot(tmp_path, monkeypatch, slot):
    from opentransit.build import generations

    captured = {}

    def fake_build(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return tmp_path / "candidate"

    monkeypatch.setattr(generations, "build_generation", fake_build)
    result = cli.main(
        [
            "build",
            "--inputs",
            str(tmp_path / "inputs"),
            "--output",
            str(tmp_path / "candidate"),
            "--first-day",
            "2026-09-30",
            "--local-engine-slot",
            slot,
            "--validation-evidence",
            str(tmp_path / "validation.json"),
            "--reference-reuse-generation",
            str(tmp_path / "prior-generation"),
        ]
    )

    assert result == 0
    assert captured["kwargs"]["local_engine_slot"] == slot
    assert captured["kwargs"]["validation_evidence_path"] == tmp_path / "validation.json"
    assert captured["kwargs"]["reference_reuse_generation_path"] == tmp_path / "prior-generation"


def test_fetch_snapshot_requires_complete_valid_pair_and_preserves_sources(tmp_path, monkeypatch):
    gtfs, mapping = make_inputs(tmp_path)
    osm = tmp_path / "osm.pbf"
    osm.write_bytes(b"synthetic osm")
    timestamp = datetime(2026, 9, 30, tzinfo=UTC).isoformat()
    results = {}
    for key, name, path in (
        ("gtfs", "israel-public-transportation.zip", gtfs),
        ("trip_id_to_date", "TripIdToDate.zip", mapping),
        ("osm", "israel-and-palestine-latest.osm.pbf", osm),
    ):
        results[key] = FetchResult(
            key, name, "new", path, sha256(path), path.stat().st_size, timestamp, timestamp
        )
    monkeypatch.setattr(cli, "fetch_sources", lambda *a, **kw: FetchReport(tmp_path, results))
    root = tmp_path / "archive"
    snapshot = cli.fetch_snapshot(root)
    provenance = json.loads((snapshot / "provenance.json").read_text())
    assert provenance["inputs"]["israel-public-transportation.zip"]["sha256"] == sha256(gtfs)
    assert (snapshot / "TripIdToDate.zip").read_bytes() == mapping.read_bytes()
    check = next((root / "checks").glob("*.json"))
    assert json.loads(check.read_text())["pairedValidation"] == "passed"
    results["trip_id_to_date"] = FetchResult(
        "trip_id_to_date", "TripIdToDate.zip", "failed", None, None, None, None, timestamp
    )
    with pytest.raises(ValueError):
        cli.fetch_snapshot(root)
    assert len(list((root / "snapshots").iterdir())) == 1
    events = [json.loads(path.read_text()) for path in (root / "checks").glob("*.json")]
    assert {item["pairedValidation"] for item in events} == {"passed", "not_run"}


def test_unknown_source_freshness_does_not_renew_with_local_validation(manifest):
    from opentransit.core.generation import Generation

    value = json.loads(manifest.read_text())
    value["sourceCheckedAt"] = None
    manifest.write_text(json.dumps(value))
    generation = Generation.load(manifest)
    assert generation.freshness(datetime(2026, 9, 30, tzinfo=UTC)) == "expired"
    value["sourceCheckedAt"] = "2026-09-01T00:00:00+00:00"
    manifest.write_text(json.dumps(value))
    assert Generation.load(manifest).freshness(datetime(2026, 9, 30, tzinfo=UTC)) == "expired"
