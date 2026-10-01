"""Unit tests for generation packaging; Docker is replaced with an injected runner."""

import csv
import hashlib
import json
import subprocess
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from opentransit.build import generations
from opentransit.build.generations import CANONICAL_INPUTS, build_generation, verify_artifacts
from opentransit.build.validation import validate_feed
from opentransit.core.trip_calls import POLICY_ID
from opentransit.reference import SCHEMA_VERSION, ReferenceStore


def _zip(path, members):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, (fields, rows) in members.items():
            from io import StringIO

            stream = StringIO()
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(fields)
            writer.writerows(rows)
            archive.writestr(name, stream.getvalue())


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path / "inputs"
    root.mkdir()
    _zip(
        root / CANONICAL_INPUTS["gtfs"],
        {
            "agency.txt": (
                ["agency_id", "agency_name", "agency_url", "agency_timezone"],
                [["op", "Synthetic operator", "https://example.test", "Asia/Jerusalem"]],
            ),
            "routes.txt": (
                ["route_id", "agency_id", "route_short_name", "route_type"],
                [["bus_7", "op", "7", "3"]],
            ),
            "stops.txt": (
                ["stop_id", "stop_name", "stop_lat", "stop_lon"],
                [["s1", "One", "32.08", "34.78"], ["s2", "Two", "32.09", "34.79"]],
            ),
            "trips.txt": (
                ["route_id", "service_id", "trip_id", "trip_headsign"],
                [["bus_7", "wk", "trip_1", "Two"]],
            ),
            "stop_times.txt": (
                ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
                [
                    ["trip_1", "08:00:00", "08:00:00", "s1", "1"],
                    ["trip_1", "08:20:00", "08:20:00", "s2", "2"],
                ],
            ),
            "calendar.txt": (
                [
                    "service_id",
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                    "start_date",
                    "end_date",
                ],
                [["wk", "1", "1", "1", "1", "1", "1", "1", "20260928", "20261031"]],
            ),
        },
    )
    _zip(
        root / CANONICAL_INPUTS["trip_id_to_date"],
        {
            "TripIdToDate.txt": (
                ["TripId", "FromDate", "ToDate", "DayInWeek"],
                [["trip", "28/09/2026", "31/10/2026", day_in_week] for day_in_week in range(1, 8)],
            )
        },
    )
    (root / CANONICAL_INPUTS["osm"]).write_bytes(b"synthetic osm snapshot")
    provenance = {
        "mode": "fixture",
        "inputs": {
            name: {
                "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
                "bytes": (root / name).stat().st_size,
                "acquiredAt": None,
                "checkedAt": None,
            }
            for name in CANONICAL_INPUTS.values()
        },
    }
    (root / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    return root


def successful_runner(commands, *, write_graph=True):
    def run(command, stdout, stderr, check, timeout):
        commands.append(command)
        assert stderr is not None
        assert check is False
        if command[1] == "run" and "--entrypoint" in command:
            assert timeout == 30
            assert command[command.index("--entrypoint") + 1] == "/bin/sh"
            assert 'test "$(id -u)" = 100' in command[-1]
            assert "volume-nocopy" not in " ".join(command)
            stdout.write("uid=100(motis) gid=101(motis) writable /data\n")
        elif command[1] == "run":
            assert timeout == 600
            stdout.write("synthetic import success\n")
        elif command[1] == "cp":
            assert timeout == 600
            stdout.write("synthetic volume export success\n")
            if write_graph:
                (Path(command[-1]) / "timetable.bin").write_bytes(b"synthetic graph")
        else:
            raise AssertionError(f"Unexpected Docker command: {command}")
        return SimpleNamespace(returncode=0)

    return run


def make_validation_evidence(inputs, path):
    report = validate_feed(
        inputs / CANONICAL_INPUTS["gtfs"], inputs / CANONICAL_INPUTS["trip_id_to_date"]
    )
    validator_path = Path(generations.__file__).with_name("validation.py")
    policy_path = Path(generations.__file__).parents[1] / "core" / "trip_calls.py"
    validator_hash = hashlib.sha256(validator_path.read_bytes()).hexdigest()
    policy_hash = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    evidence = {
        "createdAtUtc": "2026-09-30T10:00:00+00:00",
        "validatorSha256": validator_hash,
        "validatorVersion": validator_hash[:16],
        "policyCodeSha256": policy_hash,
        "policyId": POLICY_ID,
        "inputSha256": {
            "gtfs": hashlib.sha256((inputs / CANONICAL_INPUTS["gtfs"]).read_bytes()).hexdigest(),
            "tripIdToDate": hashlib.sha256(
                (inputs / CANONICAL_INPUTS["trip_id_to_date"]).read_bytes()
            ).hexdigest(),
        },
        "error": None,
        "report": report.as_dict(),
    }
    path.write_text(json.dumps(evidence), encoding="utf-8")
    return evidence


def test_build_generation_validates_pins_and_writes_manifest(inputs, tmp_path):
    commands = []
    output = build_generation(
        inputs,
        tmp_path / "generation",
        date(2026, 9, 30),
        days=31,
        memory_gib=4,
        geocoding=True,
        runner=successful_runner(commands),
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "ready"
    assert manifest["mode"] == "fixture"
    assert manifest["parserVersion"] == 2
    assert manifest["referenceSchemaVersion"] == SCHEMA_VERSION == 3
    assert manifest["identity"]["timingPolicy"] == manifest["timingPolicy"]
    assert manifest["timingPolicy"]["policy_id"] == "motis-minute-bracket-v1"
    assert manifest["build"]["importMemoryCapBytes"] == 4 * 1024**3
    assert manifest["build"]["exitCode"] == 0
    assert manifest["build"]["volumePreflightExitCode"] == 0
    assert manifest["build"]["volumeWritableAsImageUser"] is True
    assert manifest["build"]["exportExitCode"] == 0
    assert manifest["build"]["volumeName"].startswith("opentransit-graph-")
    assert manifest["sourceCheckedAt"] is None
    assert manifest["validatedAt"] == manifest["validationRunAt"]
    assert manifest["coverage"]["from"].startswith("2026-09-30T00:00:00+03:00")
    assert manifest["coverage"]["until"].startswith("2026-10-31T00:00:00+02:00")
    assert manifest["artifacts"]["reference"]["sha256"]
    assert manifest["artifacts"]["motis"]["fileCount"] == 1
    assert manifest["artifacts"]["motis"]["files"][0]["path"] == "timetable.bin"
    assert manifest["preflight"]["tripCount"] == 1
    assert manifest["preflight"]["stopTimeCount"] == 2
    assert len(manifest["preflight"]["importServiceDates"]) == 31
    assert len(manifest["generationId"]) == 64
    assert manifest["identity"]["inputs"][CANONICAL_INPUTS["osm"]]
    config_text = (output / "config.yml").read_text(encoding="utf-8")
    assert "geocoding: true" in config_text
    assert "server:" not in config_text
    assert manifest["localEngineSlot"] is None
    assert manifest["engineOrigin"] is None
    assert "localEngineSlot" not in manifest["identity"]
    assert (output / "import.log").read_text(encoding="utf-8") == "synthetic import success\n"
    assert (output / "export.log").read_text(encoding="utf-8") == (
        "synthetic volume export success\n"
    )
    assert ReferenceStore(output / "reference.sqlite", manifest["generationId"]).stop("s1")
    verified = verify_artifacts(output)
    assert verified["graphTreeSha256"] == manifest["artifacts"]["motis"]["sha256"]
    command = commands[1]
    assert command[command.index("--memory") + 1] == "4g"
    volume_mount = next(value for value in command if value.startswith("type=volume,"))
    assert volume_mount.endswith("dst=/data")
    assert "volume-nocopy" not in volume_mount
    assert commands[0][1] == "run" and "--entrypoint" in commands[0]
    assert commands[2][1:3] == ["cp", f"{manifest['build']['containerName']}:/data/."]
    assert command[-6:] == ["/motis", "import", "-c", "/config.yml", "-d", "/data"]


def test_reference_reuse_requires_exact_generation_and_verifies_copy(inputs, tmp_path, monkeypatch):
    source = build_generation(
        inputs, tmp_path / "reference-source", date(2026, 9, 30), runner=successful_runner([])
    )
    source_bytes = (source / "reference.sqlite").read_bytes()

    def unexpected_build(*args, **kwargs):
        raise AssertionError("reference rebuild must be skipped")

    monkeypatch.setattr(generations, "build_reference", unexpected_build)
    output = build_generation(
        inputs,
        tmp_path / "reference-reuse",
        date(2026, 9, 30),
        runner=successful_runner([]),
        reference_reuse_generation_path=source,
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["generationId"] == source_manifest["generationId"]
    assert manifest["referenceReuse"]["generationId"] == manifest["generationId"]
    assert (
        manifest["artifacts"]["reference"]["sha256"]
        == source_manifest["artifacts"]["reference"]["sha256"]
    )
    assert (output / "reference.sqlite").read_bytes() == source_bytes
    assert ReferenceStore(output / "reference.sqlite", manifest["generationId"]).stop("s1")


def test_reference_reuse_rejects_mismatched_identity_before_import(inputs, tmp_path):
    source = build_generation(
        inputs,
        tmp_path / "reference-source-mismatch",
        date(2026, 9, 30),
        runner=successful_runner([]),
    )
    calls = []
    output = tmp_path / "reference-reuse-mismatch"
    with pytest.raises(ValueError, match="identity differs"):
        build_generation(
            inputs,
            output,
            date(2026, 9, 30),
            geocoding=True,
            runner=lambda *args, **kwargs: calls.append(args),
            reference_reuse_generation_path=source,
        )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
    assert not calls
    assert not (output / "motis").exists()


def test_failed_volume_export_keeps_import_and_export_evidence(inputs, tmp_path):
    commands = []

    def fail_export(command, stdout, stderr, check, timeout):
        commands.append(command)
        if "--entrypoint" in command:
            stdout.write("uid=100 gid=101 writable /data\n")
            return SimpleNamespace(returncode=0)
        if command[1] == "run":
            stdout.write("synthetic import success\n")
            return SimpleNamespace(returncode=0)
        stdout.write("synthetic export failure\n")
        return SimpleNamespace(returncode=3)

    output = tmp_path / "failed-volume-export"
    with pytest.raises(RuntimeError, match="graph export failed"):
        build_generation(inputs, output, date(2026, 9, 30), runner=fail_export)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
    assert manifest["build"]["volumeName"].startswith("opentransit-graph-")
    assert manifest["build"]["exportExitCode"] == 3
    assert (output / "import.log").read_text(encoding="utf-8") == "synthetic import success\n"
    assert (output / "export.log").read_text(encoding="utf-8") == "synthetic export failure\n"
    assert not (output / "reference.sqlite").is_symlink()


def test_generation_id_is_deterministic_for_same_content_and_configuration(inputs, tmp_path):
    runner = successful_runner([])
    first = build_generation(inputs, tmp_path / "first", date(2026, 9, 30), runner=runner)
    second = build_generation(inputs, tmp_path / "second", date(2026, 9, 30), runner=runner)
    one = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    two = json.loads((second / "manifest.json").read_text(encoding="utf-8"))
    assert one["generationId"] == two["generationId"]


def test_local_engine_slots_bind_server_config_before_import_and_change_identity(inputs, tmp_path):
    outputs = {}
    for slot, port in (("blue", 59081), ("green", 59082)):
        commands = []
        delegate = successful_runner(commands)

        def runner(
            command,
            stdout,
            stderr,
            check,
            timeout,
            *,
            expected_port=port,
            delegate_runner=delegate,
        ):
            if command[1] == "run" and "/motis" in command:
                config_mount = next(
                    arg
                    for arg in command
                    if arg.startswith("type=bind,") and "dst=/config.yml" in arg
                )
                config_path = config_mount.split("src=", 1)[1].split(",dst=/config.yml", 1)[0]
                config = Path(config_path).read_text(encoding="utf-8")
                assert "server:\n  host: 127.0.0.1\n" in config
                assert f"  port: {expected_port}\n" in config
            return delegate_runner(command, stdout, stderr, check, timeout)

        outputs[slot] = build_generation(
            inputs,
            tmp_path / slot,
            date(2026, 9, 30),
            runner=runner,
            local_engine_slot=slot,
        )

    blue = json.loads((outputs["blue"] / "manifest.json").read_text(encoding="utf-8"))
    green = json.loads((outputs["green"] / "manifest.json").read_text(encoding="utf-8"))
    assert blue["localEngineSlot"] == "blue"
    assert green["localEngineSlot"] == "green"
    assert blue["identity"]["localEngineSlot"] == "blue"
    assert green["identity"]["localEngineSlot"] == "green"
    assert blue["engineOrigin"] == "http://127.0.0.1:59081"
    assert green["engineOrigin"] == "http://127.0.0.1:59082"
    assert blue["configSha256"] == blue["artifacts"]["config"]["sha256"]
    assert green["configSha256"] == green["artifacts"]["config"]["sha256"]
    assert blue["generationId"] != green["generationId"]
    assert blue["configSha256"] != green["configSha256"]


def test_matching_validation_evidence_is_reused_without_renewing_source_freshness(
    inputs, tmp_path, monkeypatch
):
    evidence_path = tmp_path / "full-feed-validation.json"
    evidence = make_validation_evidence(inputs, evidence_path)
    commands = []

    def unexpected_validation(*args, **kwargs):
        pytest.fail("build reran validation despite matching validation evidence")

    monkeypatch.setattr(generations, "validate_feed", unexpected_validation)
    output = build_generation(
        inputs,
        tmp_path / "evidence-generation",
        date(2026, 9, 30),
        runner=successful_runner(commands),
        validation_evidence_path=evidence_path,
    )

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    validation_artifact = json.loads((output / "validation.json").read_text(encoding="utf-8"))
    provenance = manifest["validationEvidence"]
    assert provenance["path"] == str(evidence_path.resolve())
    assert provenance["sha256"] == hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    assert provenance["validatorSha256"] == evidence["validatorSha256"]
    assert provenance["policyCodeSha256"] == evidence["policyCodeSha256"]
    assert validation_artifact["evidenceProvenance"] == provenance
    assert manifest["validatedAt"] == manifest["validationRunAt"] == evidence["createdAtUtc"]
    assert manifest["sourceCheckedAt"] is None
    assert manifest["identity"]["validationEvidenceSha256"] == provenance["sha256"]
    assert manifest["state"] == "ready"


@pytest.mark.parametrize(
    ("mutation", "error_match"),
    [
        ("source", "input hashes"),
        ("validator", "validator code hash"),
        ("policy", "policy code hash"),
        ("missing-check", "missing required checks"),
        ("failed-check", "contains a failure"),
        ("audit-error", "unsuccessful validator run"),
    ],
)
def test_stale_or_incomplete_validation_evidence_fails_before_import(
    inputs, tmp_path, monkeypatch, mutation, error_match
):
    evidence_path = tmp_path / f"{mutation}.json"
    evidence = make_validation_evidence(inputs, evidence_path)
    if mutation == "source":
        evidence["inputSha256"]["gtfs"] = "0" * 64
    elif mutation == "validator":
        evidence["validatorSha256"] = "0" * 64
    elif mutation == "policy":
        evidence["policyCodeSha256"] = "0" * 64
    elif mutation == "missing-check":
        evidence["report"]["checks"] = [
            item for item in evidence["report"]["checks"] if item["id"] != "E10"
        ]
    elif mutation == "failed-check":
        next(item for item in evidence["report"]["checks"] if item["id"] == "V04")["status"] = (
            "fail"
        )
    elif mutation == "audit-error":
        evidence["error"] = "prior failure"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    output = tmp_path / f"candidate-{mutation}"
    runner_calls = []
    with pytest.raises(ValueError, match=error_match):
        build_generation(
            inputs,
            output,
            date(2026, 9, 30),
            runner=lambda *args, **kwargs: runner_calls.append(args),
            validation_evidence_path=evidence_path,
        )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
    assert not runner_calls
    assert not (output / "reference.sqlite").exists()
    assert not (output / "motis").exists()


def test_missing_validation_evidence_preserves_failed_candidate_without_import(inputs, tmp_path):
    output = tmp_path / "missing-evidence"
    runner_calls = []
    with pytest.raises(ValueError, match="Unable to read validation evidence"):
        build_generation(
            inputs,
            output,
            date(2026, 9, 30),
            runner=lambda *args, **kwargs: runner_calls.append(args),
            validation_evidence_path=tmp_path / "absent.json",
        )
    assert json.loads((output / "manifest.json").read_text())["state"] == "failed"
    assert not runner_calls


@pytest.mark.parametrize("slot", ["orange", 59081])
def test_invalid_local_engine_slot_fails_before_output_creation(inputs, tmp_path, slot):
    output = tmp_path / "unsupported-slot"
    with pytest.raises(ValueError, match="local_engine_slot"):
        build_generation(
            inputs,
            output,
            date(2026, 9, 30),
            runner=successful_runner([]),
            local_engine_slot=slot,
        )
    assert not output.exists()


def test_source_checked_at_uses_oldest_successful_paired_check(inputs, tmp_path):
    provenance_path = inputs / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["inputs"][CANONICAL_INPUTS["gtfs"]].update(
        status="unchanged", checkedAt="2026-09-30T10:05:00+00:00"
    )
    provenance["inputs"][CANONICAL_INPUTS["trip_id_to_date"]].update(
        status="changed", checkedAt="2026-09-30T10:02:00+00:00"
    )
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    output = build_generation(
        inputs, tmp_path / "checked-generation", date(2026, 9, 30), runner=successful_runner([])
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sourceCheckedAt"] == "2026-09-30T10:02:00+00:00"


def test_source_provenance_reuses_parent_m1_manifest_without_rewriting_it(inputs, tmp_path):
    provenance_path = inputs / "provenance.json"
    provenance_path.unlink()
    parent_manifest_path = inputs.parent / "manifest.json"
    parent_manifest = {
        "generation": {
            "inputs": {
                CANONICAL_INPUTS["gtfs"]: {
                    "sha256": hashlib.sha256(
                        (inputs / CANONICAL_INPUTS["gtfs"]).read_bytes()
                    ).hexdigest(),
                    "acquiredAt": "2026-09-30T09:33:07.260277+00:00",
                    "lastModified": "Tue, 29 Sep 2026 16:59:05 GMT",
                    "url": "https://gtfs.mot.gov.il/gtfsfiles/israel-public-transportation.zip",
                },
                CANONICAL_INPUTS["trip_id_to_date"]: {
                    "sha256": hashlib.sha256(
                        (inputs / CANONICAL_INPUTS["trip_id_to_date"]).read_bytes()
                    ).hexdigest(),
                    "acquiredAt": "2026-09-30T09:33:11.146493+00:00",
                    "lastModified": "Tue, 29 Sep 2026 16:59:18 GMT",
                    "url": "https://gtfs.mot.gov.il/gtfsfiles/TripIdToDate.zip",
                },
                CANONICAL_INPUTS["osm"]: {
                    "sha256": hashlib.sha256(
                        (inputs / CANONICAL_INPUTS["osm"]).read_bytes()
                    ).hexdigest(),
                    "acquiredAt": None,
                    "note": "Existing M1 snapshot; no fresh download",
                },
            }
        }
    }
    parent_manifest_path.write_text(json.dumps(parent_manifest), encoding="utf-8")
    original_bytes = parent_manifest_path.read_bytes()

    output = build_generation(
        inputs,
        tmp_path / "parent-m1-provenance",
        date(2026, 9, 30),
        runner=successful_runner([]),
    )

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sourceCheckedAt"] == "2026-09-30T09:33:07.260277+00:00"
    assert manifest["inputs"][CANONICAL_INPUTS["gtfs"]]["url"].endswith(
        "israel-public-transportation.zip"
    )
    assert manifest["inputs"][CANONICAL_INPUTS["gtfs"]]["lastModified"] == (
        "Tue, 29 Sep 2026 16:59:05 GMT"
    )
    assert parent_manifest_path.read_bytes() == original_bytes


def test_failed_engine_import_preserves_manifest_and_log_without_overwrite(inputs, tmp_path):
    def failed(command, stdout, stderr, check, timeout):
        if "--entrypoint" in command:
            stdout.write("uid=100 gid=101 writable /data\n")
            return SimpleNamespace(returncode=0)
        stdout.write("synthetic import failure\n")
        return SimpleNamespace(returncode=42)

    output = tmp_path / "failed-generation"
    with pytest.raises(RuntimeError, match="exit code 42"):
        build_generation(inputs, output, date(2026, 9, 30), runner=failed)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
    assert manifest["build"]["exitCode"] == 42
    assert "failure" in (output / "import.log").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        build_generation(inputs, output, date(2026, 9, 30), runner=successful_runner([]))


def test_corrupt_input_hash_fails_before_import_and_keeps_candidate(inputs, tmp_path):
    with (inputs / CANONICAL_INPUTS["osm"]).open("ab") as stream:
        stream.write(b"changed")
    output = tmp_path / "bad-input"
    with pytest.raises(ValueError, match="differs from recorded provenance"):
        build_generation(inputs, output, date(2026, 9, 30), runner=successful_runner([]))
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
    assert "hash differs" in manifest["failure"]


def test_zero_exit_without_graph_files_is_failed(inputs, tmp_path):
    output = tmp_path / "empty-graph"
    with pytest.raises(ValueError, match="without any non-empty graph artifacts"):
        build_generation(
            inputs,
            output,
            date(2026, 9, 30),
            runner=successful_runner([], write_graph=False),
        )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
    assert (output / "import.log").is_file()


def test_import_timeout_stops_only_its_unique_candidate_container(inputs, tmp_path):
    commands = []

    def timed_out(command, stdout, stderr, check, timeout):
        commands.append(command)
        if "--entrypoint" in command:
            stdout.write("uid=100 gid=101 writable /data\n")
            return SimpleNamespace(returncode=0)
        if command[1] == "run":
            raise subprocess.TimeoutExpired(command, timeout)
        return SimpleNamespace(returncode=0)

    output = tmp_path / "timed-out"
    with pytest.raises(subprocess.TimeoutExpired):
        build_generation(inputs, output, date(2026, 9, 30), runner=timed_out)
    assert commands[0][1] == "run" and "--entrypoint" in commands[0]
    assert commands[1][1] == "run"
    assert commands[1][commands[1].index("--name") + 1].startswith("opentransit-builder-")
    assert commands[2] == [
        "docker",
        "stop",
        "--time",
        "5",
        commands[1][commands[1].index("--name") + 1],
    ]
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
    assert manifest["build"]["containerName"] == commands[2][-1]
    assert (output / "import.log").is_file()


def test_invalid_feed_keeps_validation_report_and_never_calls_runner(inputs, tmp_path):
    gtfs_path = inputs / CANONICAL_INPUTS["gtfs"]
    gtfs_path.write_bytes(b"not a zip")
    provenance_path = inputs / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["inputs"][CANONICAL_INPUTS["gtfs"]]["sha256"] = hashlib.sha256(
        gtfs_path.read_bytes()
    ).hexdigest()
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    output = tmp_path / "invalid-feed"
    with pytest.raises(zipfile.BadZipFile):
        build_generation(inputs, output, date(2026, 9, 30), runner=successful_runner([]))
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
