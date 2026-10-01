"""One-command generation pipeline with every Docker/osmium/enrichment boundary mocked.

The schedule half runs the real ``build_generation`` (validation, reference SQLite, hashing,
manifest) against the synthetic fixture feed; only Docker is replaced. The address half uses the
real address catalog, attestation, composite identity and artifact verification; only osmium, the
Photon container and the long enrichment are replaced. No result here is real-engine evidence.
"""

import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_generation_build import inputs, successful_runner  # noqa: F401

from opentransit.build import cli, generations, photon, pipeline
from opentransit.build.pipeline import Boundaries, build_complete_generation, stage_order
from opentransit.core.artifacts import (
    JAVA_21_IMAGE_DIGEST,
    PHOTON_130_JAR_SHA256,
    canonical_sha256,
    verify_artifacts,
)
from opentransit.reference import ReferenceStore

FIRST_DAY = date(2026, 9, 30)
PBF_SHA = "a" * 64


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_digest(root: Path) -> dict:
    return {
        path.relative_to(root).as_posix(): _sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _house(identity: int, lon=34.77, lat=32.08):
    return {
        "type": "Place",
        "content": [
            {
                "place_id": f"N{identity}",
                "object_type": "N",
                "object_id": identity,
                "osm_key": "addr:housenumber",
                "osm_value": "7",
                "address_type": "house",
                "housenumber": "7",
                "address": {"street": "Synthetic"},
                "extra": {"addr:street": "Synthetic"},
                "centroid": [lon, lat],
            }
        ],
    }


def _street(identity: int):
    return {
        "type": "Place",
        "content": [
            {
                "place_id": f"W{identity}",
                "object_type": "W",
                "object_id": identity,
                "osm_key": "highway",
                "address_type": "street",
                "name": {"name": "Synthetic"},
                "address": {},
                "extra": {"highway": "residential"},
                "centroid": [34.78, 32.09],
            }
        ],
    }


def write_enriched_dump(path: Path) -> None:
    header = {
        "type": "NominatimDumpFile",
        "content": {
            "version": "0.1.0",
            "generator": "OpenTransit source-context enrichment",
            "database_version": f"source OSM PBF SHA-256 {PBF_SHA}; test",
        },
    }
    rows = [header, _house(2001), _street(3001)]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class FakeDocker:
    """Answers the pipeline's Docker commands; records every command in order."""

    def __init__(self, dump: Path, *, fail: str | None = None, documents: int = 2):
        self.commands: list[list[str]] = []
        self.dump = dump
        self.fail = fail
        self.documents = documents
        self.blocked = False
        self.motis = successful_runner(self.commands)

    def _source(self, key: str) -> dict:
        for line in self.dump.read_text(encoding="utf-8").splitlines()[1:]:
            place = json.loads(line)["content"][0]
            if place["place_id"] == key:
                lon, lat = place["centroid"]
                return {
                    "_id": key,
                    "found": True,
                    "_source": {
                        "osm_type": place["object_type"],
                        "osm_id": place["object_id"],
                        "type": place["address_type"],
                        "housenumber": place.get("housenumber"),
                        "coordinate": {"lat": lat, "lon": lon},
                    },
                }
        return {"_id": key, "found": False}

    def _http(self, method: str, url: str) -> dict:
        if url.endswith("/status"):
            return {"status": "Ok"}
        if url.endswith(":9201/"):
            return {"cluster_uuid": "cluster-1"}
        if "/_settings" in url and method == "PUT":
            self.blocked = True
            return {"acknowledged": True}
        if "/_settings" in url:
            return {
                "photon": {
                    "settings": {
                        "index.uuid": "index-1",
                        **({"index.blocks.write": "true"} if self.blocked else {}),
                    }
                }
            }
        if "/_flush" in url:
            return {"_shards": {"failed": 0}}
        if "/_count" in url:
            return {"count": self.documents, "_shards": {"failed": 0}}
        if "/_doc/" in url:
            return self._source(url.rsplit("/", 1)[1])
        raise AssertionError(url)

    def __call__(self, command, stdout, stderr, check, timeout):
        assert check is False
        if command[:2] == ["docker", "volume"]:
            return SimpleNamespace(returncode=0)
        if command[1] == "run" and "--entrypoint" in command and "chown" in command[-1]:
            self.commands.append(command)
            return SimpleNamespace(returncode=0)
        if command[1] == "run" and "import" in command and "--detach" not in command:
            if "-jar" in command:
                self.commands.append(command)
                if self.fail == "photon_import":
                    stdout.write("Import error.\n")
                    return SimpleNamespace(returncode=1)
                stdout.write(
                    f"{photon.SETUP_MARKER}\nFinished import of {self.documents} photon "
                    "documents. (Total processing time: 12s)\n"
                )
                return SimpleNamespace(returncode=0)
        if command[1] == "run" and "--detach" in command:
            self.commands.append(command)
            return SimpleNamespace(returncode=0)
        if command[1] == "inspect":
            self.commands.append(command)
            name = command[-1]
            if "import" in name:
                state = {"Status": "exited", "ExitCode": 0, "OOMKilled": False}
                state["FinishedAt"] = "2026-10-01T05:37:07.727099484Z"
            else:
                state = {"Status": "exited", "Running": True, "ExitCode": 143, "OOMKilled": False}
                if "state-final" in stdout.name:
                    state["Running"] = False
            stdout.write(json.dumps(state))
            return SimpleNamespace(returncode=0)
        if command[1] == "exec":
            self.commands.append(command)
            if command[3:5] == ["sh", "-c"]:
                stdout.write("/usr/bin/curl\n")
            else:
                method = command[command.index("-X") + 1]
                stdout.write(json.dumps(self._http(method, command[-1])))
            return SimpleNamespace(returncode=0)
        if command[1] in {"stop", "logs"}:
            self.commands.append(command)
            return SimpleNamespace(returncode=0)
        if command[1] == "cp" and "photon" in command[2]:
            self.commands.append(command)
            target = Path(command[-1]) / "photon_data" / "node_1"
            target.mkdir(parents=True)
            (target / "segment.bin").write_bytes(b"sealed segment")
            (target / "write.lock").write_bytes(b"")
            return SimpleNamespace(returncode=0)
        # MOTIS preflight, import and export.
        if self.fail == "motis_import" and command[1] == "run" and "--entrypoint" not in command:
            self.commands.append(command)
            stdout.write("import failed\n")
            return SimpleNamespace(returncode=1)
        return self.motis(command, stdout, stderr, check, timeout)


def _square(lon0, lat0, lon1, lat1):
    return [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]


def write_context(pbf: Path, output: Path, *, sha: str | None = None) -> dict:
    """A real context file (header + one locality around the fixture stops) for ``pbf``."""
    sha = sha or _sha(pbf)
    rows = [
        {"type": "ContextHeader", "sourceSha256": sha, "schemaVersion": 1},
        {"type": "Street", "osmType": "W", "osmId": "1", "tags": {}, "coordinates": []},
        {
            "type": "Locality",
            "osmType": "R",
            "osmId": "7",
            "tags": {
                "boundary": "administrative",
                "admin_level": "8",
                "name": "Fixture City",
                "name:en": "Fixture City",
            },
            "geometry": {"type": "Polygon", "coordinates": [_square(34.7, 32.0, 34.9, 32.2)]},
        },
    ]
    Path(output).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return {"sourcePbfSha256": sha, "counts": {"streetRecordsWritten": 1}}


def make_boundaries(docker: FakeDocker, calls: list[str], context_sha: str | None = None):
    seen: dict[str, str] = {}

    def export_houses(pbf, output, reader_path=None):
        calls.append("export_houses")
        Path(output).write_text("house dump\n", encoding="utf-8")
        return {"houseRecords": 1, "sourcePbfSha256": seen["sha"]}

    def extract_context(pbf, output, reader_path=None):
        calls.append("extract_context")
        seen["sha"] = _sha(Path(pbf))
        return write_context(Path(pbf), Path(output), sha=context_sha)

    def enrich(houses, context, output, provenance, pbf_sha256):
        calls.append("enrich")
        assert pbf_sha256 == seen["sha"] != PBF_SHA  # the snapshot PBF, shared with localities
        write_enriched_dump(Path(output))
        Path(provenance).write_text("{}\n", encoding="utf-8")
        return {
            "counts": {"houseRecords": 1, "streetDocumentsAdded": 1},
            "outputs": {"photonDumpSha256": _sha(Path(output))},
        }

    def import_photon(*args, **kwargs):
        calls.append("import_photon")
        output = Path(args[0]).parents[2]
        assert not (output / "manifest.json").exists(), "no manifest until composite verifies"
        assert (output / "schedule-component-manifest.json").exists()
        return photon.import_photon(*args, **kwargs)

    return Boundaries(
        runner=docker,
        sleep=lambda _seconds: None,
        load_osmium=lambda _path: object(),
        export_houses=export_houses,
        extract_context=extract_context,
        enrich=enrich,
        import_photon=import_photon,
    )


@pytest.fixture
def jar(tmp_path, monkeypatch):
    path = tmp_path / "photon-1.3.0.jar"
    path.write_bytes(b"synthetic photon jar")
    monkeypatch.setattr(photon, "PHOTON_130_JAR_SHA256", _sha(path))
    return path


def build(*args, **kwargs):
    # The shared fake MOTIS runner asserts the 600 s import timeout of the older build tests.
    kwargs.setdefault("import_timeout_seconds", 600)
    return build_complete_generation(*args, **kwargs)


def stage_names(output: Path) -> list[str]:
    evidence = json.loads((output / "pipeline" / "pipeline.json").read_text(encoding="utf-8"))
    return [entry["name"] for entry in evidence["stages"]]


def test_schedule_only_stage_order_and_evidence(inputs, tmp_path):  # noqa: F811
    docker = FakeDocker(tmp_path / "unused")
    output = build(
        inputs,
        tmp_path / "gen",
        FIRST_DAY,
        boundaries=Boundaries(runner=docker),
        memory_gib=6,
    )
    evidence = json.loads((output / "pipeline" / "pipeline.json").read_text(encoding="utf-8"))
    assert evidence["state"] == "complete"
    assert [s["name"] for s in evidence["stages"]] == list(stage_order(False))
    assert all(
        s["status"] == "passed" and s["elapsedSeconds"] is not None for s in evidence["stages"]
    )
    assert evidence["request"]["engineLimits"] == generations.STREET_ROUTING_LIMITS
    assert evidence["result"]["addresses"] is False
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "ready" and "addressSearch" not in manifest
    assert evidence["result"]["generationId"] == manifest["generationId"]
    # Docker order: volume preflight, capped import, export.
    assert [c[1] for c in docker.commands] == ["run", "run", "cp"]
    import_command = docker.commands[1]
    assert import_command[import_command.index("--memory") + 1] == "6g"
    assert verify_artifacts(output)["generationId"] == manifest["generationId"]


def test_address_stage_order_composite_identity_and_stage_bundle(inputs, tmp_path, jar):  # noqa: F811
    dump = tmp_path / "gen" / "pipeline" / "work" / "photon-enriched.jsonl"
    docker = FakeDocker(dump)
    calls: list[str] = []
    output = build(
        inputs,
        tmp_path / "gen",
        FIRST_DAY,
        addresses=True,
        photon_jar=jar,
        boundaries=make_boundaries(docker, calls),
    )
    # One context scan, before the schedule build, serves localities and the enrichment.
    assert calls == ["extract_context", "export_houses", "enrich", "import_photon"]
    assert stage_names(output) == list(stage_order(True))
    assert stage_names(output)[0] == "osm_context" and "photon_context" not in stage_names(output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    component = json.loads(
        (output / "schedule-component-manifest.json").read_text(encoding="utf-8")
    )
    context_sha = _sha(output / "pipeline" / "work" / "osm-context.jsonl")
    assert component["identity"]["localityContextSha256"] == context_sha
    provenance = component["artifacts"]["reference"]["localityProvenance"]
    assert provenance["contextSha256"] == context_sha and provenance["localityCount"] == 1
    reference = ReferenceStore(output / "reference.sqlite", component["generationId"])
    assert [row["locality_id"] for row in reference.search_localities()] == ["osm:relation:7"]
    evidence = json.loads((output / "pipeline" / "pipeline.json").read_text(encoding="utf-8"))
    assert evidence["request"]["localities"] is True
    scan = next(s for s in evidence["stages"] if s["name"] == "osm_context")
    assert scan["details"]["localities"]["contextSha256"] == context_sha
    assert manifest["scheduleComponentGenerationId"] == component["generationId"]
    assert manifest["generationId"] != component["generationId"]
    attestation = json.loads(
        (output / "photon-import-attestation.json").read_text(encoding="utf-8")
    )
    address_identity = canonical_sha256(
        {
            "scheduleComponentGenerationId": component["generationId"],
            "sourceDumpSha256": attestation["sourceDumpSha256"],
            "catalogSha256": _sha(output / "address-catalog.sqlite"),
            "attestationSha256": _sha(output / "photon-import-attestation.json"),
            "selectionPolicyVersion": "primary-name-house-street-v1",
            "normalizationPolicyVersion": "source-catalog-v1",
            "photonJarSha256": PHOTON_130_JAR_SHA256,
            "javaImageDigest": JAVA_21_IMAGE_DIGEST,
        }
    )
    assert manifest["addressSearch"]["artifactIdentity"] == address_identity
    assert manifest["generationId"] == canonical_sha256(
        {
            "scheduleComponentGenerationId": component["generationId"],
            "addressArtifactIdentity": address_identity,
        }
    )
    assert attestation["indexWriteBlocked"] is True
    assert attestation["documentCount"] == 2 and len(attestation["probes"]) == 2
    assert attestation["checkpoint"]["files"] == 2
    assert (
        attestation["checkpoint"]["treeSha256"]
        == photon.tree_checkpoint(output / "photon")["treeSha256"]
    )
    verified = verify_artifacts(output)
    assert verified["generationId"] == manifest["generationId"]
    assert verified["scheduleComponentGenerationId"] == component["generationId"]

    # Caps: MOTIS import 6 GiB, Photon import 2 GiB (heap 1g), serving a sealed copy 1 GiB.
    motis_import = next(c for c in docker.commands if c[1] == "run" and "--memory" in c)
    assert motis_import[motis_import.index("--memory") + 1] == "6g"
    photon_import = next(c for c in docker.commands if "-import-file" in c)
    assert "--memory=2g" in photon_import and "--memory-swap=2g" in photon_import
    assert "-Xmx1g" in photon_import and "--network" in photon_import
    assert photon_import[photon_import.index("--network") + 1] == "none"
    serve = next(c for c in docker.commands if "--detach" in c)
    assert "--memory=1g" in serve and not any(arg in {"-p", "--publish"} for arg in serve)
    assert (output / "pipeline" / "logs" / "photon-seal-http.json").is_file()

    # The result is consumable by the H-0 staging tool: a sealed Photon tree and a slot-free graph.
    import importlib.util
    import sys

    repo = Path(__file__).resolve().parents[3]
    path = repo / "deploy" / "aws" / "tools" / "stage_bundle.py"
    if path.is_file():
        spec = importlib.util.spec_from_file_location("pipeline_stage_bundle", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["pipeline_stage_bundle"] = module
        spec.loader.exec_module(module)
        staged = module.stage(output, tmp_path / "stage", photon_data=output / "photon")
        assert staged


def test_failed_photon_import_is_isolated_and_attributed(inputs, tmp_path, jar):  # noqa: F811
    before_inputs = _tree_digest(inputs)
    sibling = tmp_path / "earlier-generation"
    sibling.mkdir()
    (sibling / "manifest.json").write_text('{"keep": true}', encoding="utf-8")
    dump = tmp_path / "gen" / "pipeline" / "work" / "photon-enriched.jsonl"
    docker = FakeDocker(dump, fail="photon_import")
    calls: list[str] = []
    with pytest.raises(RuntimeError, match="did not exit cleanly|Photon"):
        build(
            inputs,
            tmp_path / "gen",
            FIRST_DAY,
            addresses=True,
            photon_jar=jar,
            boundaries=make_boundaries(docker, calls),
        )
    output = tmp_path / "gen"
    evidence = json.loads((output / "pipeline" / "pipeline.json").read_text(encoding="utf-8"))
    assert evidence["state"] == "failed"
    assert evidence["failure"]["stage"] == "photon_import"
    statuses = {s["name"]: s["status"] for s in evidence["stages"]}
    assert statuses["motis_export"] == "passed" and statuses["photon_import"] == "failed"
    assert "photon_seal" not in statuses and "compose" not in statuses and "verify" not in statuses
    assert not (output / "manifest.json").exists()  # incomplete generations are never loadable
    assert (output / "schedule-component-manifest.json").is_file()
    assert (output / "pipeline" / "logs" / "photon-import.log").read_text(
        encoding="utf-8"
    ) == "Import error.\n"
    assert _tree_digest(inputs) == before_inputs
    assert json.loads((sibling / "manifest.json").read_text(encoding="utf-8")) == {"keep": True}
    # Preserved containers/volumes are never removed.
    assert not any("rm" in command for command in docker.commands)


def test_failed_motis_import_runs_no_address_stage_and_preserves_evidence(inputs, tmp_path, jar):  # noqa: F811
    docker = FakeDocker(tmp_path / "unused", fail="motis_import")
    calls: list[str] = []
    with pytest.raises(RuntimeError, match="MOTIS import failed"):
        build(
            inputs,
            tmp_path / "gen",
            FIRST_DAY,
            addresses=True,
            photon_jar=jar,
            boundaries=make_boundaries(docker, calls),
        )
    output = tmp_path / "gen"
    assert calls == ["extract_context"]  # no house export, enrichment or Photon stage
    evidence = json.loads((output / "pipeline" / "pipeline.json").read_text(encoding="utf-8"))
    assert evidence["failure"]["stage"] == "motis_import"
    assert stage_names(output) == ["osm_context", "validate", "reference", "motis_import"]
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "failed"
    assert (output / "import.log").read_text(encoding="utf-8") == "import failed\n"


def _localities_boundaries(tmp_path, calls, *, context_sha=None):
    boundaries = make_boundaries(FakeDocker(tmp_path / "unused"), calls, context_sha)
    return boundaries


def _reference(output):
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    return ReferenceStore(output / "reference.sqlite", manifest["generationId"]), manifest


def test_schedule_only_build_gets_localities_when_the_osm_reader_is_given(inputs, tmp_path):  # noqa: F811
    calls: list[str] = []
    output = build(
        inputs,
        tmp_path / "gen",
        FIRST_DAY,
        osm_reader_path=tmp_path / "reader",  # automatic mode: a reader path turns it on
        boundaries=_localities_boundaries(tmp_path, calls),
    )
    assert calls == ["extract_context"]  # no Photon house export or enrichment
    assert stage_names(output) == list(stage_order(False, True))
    assert stage_names(output)[:2] == ["osm_context", "validate"]
    reference, manifest = _reference(output)
    assert [row["locality_id"] for row in reference.search_localities()] == ["osm:relation:7"]
    assert all(
        row["locality_ids"] == ["osm:relation:7"] for row in reference.stop_search_candidates()
    )
    context_sha = _sha(output / "pipeline" / "work" / "osm-context.jsonl")
    assert manifest["identity"]["localityContextSha256"] == context_sha
    assert manifest["artifacts"]["reference"]["localityProvenance"]["osmPbfSha256"] == _sha(
        inputs / generations.CANONICAL_INPUTS["osm"]
    )
    evidence = json.loads((output / "pipeline" / "pipeline.json").read_text(encoding="utf-8"))
    assert evidence["request"]["localities"] is True
    assert evidence["request"]["localitiesRequested"] is None
    assert verify_artifacts(output)["generationId"] == manifest["generationId"]


def test_no_localities_flag_skips_the_scan_even_with_a_reader(inputs, tmp_path):  # noqa: F811
    calls: list[str] = []
    output = build(
        inputs,
        tmp_path / "gen",
        FIRST_DAY,
        osm_reader_path=tmp_path / "reader",
        localities=False,
        boundaries=_localities_boundaries(tmp_path, calls),
    )
    assert calls == [] and stage_names(output) == list(stage_order(False))
    reference, manifest = _reference(output)
    assert reference.search_localities() == []
    assert "localityContextSha256" not in manifest["identity"]
    assert "localityProvenance" not in manifest["artifacts"]["reference"]
    evidence = json.loads((output / "pipeline" / "pipeline.json").read_text(encoding="utf-8"))
    assert evidence["request"]["localities"] is False
    assert evidence["request"]["localitiesRequested"] is False


def test_address_build_without_localities_still_scans_once_for_the_enrichment(
    inputs,  # noqa: F811
    tmp_path,
    jar,
):
    dump = tmp_path / "gen" / "pipeline" / "work" / "photon-enriched.jsonl"
    calls: list[str] = []
    output = build(
        inputs,
        tmp_path / "gen",
        FIRST_DAY,
        addresses=True,
        localities=False,
        photon_jar=jar,
        boundaries=make_boundaries(FakeDocker(dump), calls),
    )
    assert calls == ["extract_context", "export_houses", "enrich", "import_photon"]
    scan = json.loads((output / "pipeline" / "pipeline.json").read_text(encoding="utf-8"))
    details = next(s for s in scan["stages"] if s["name"] == "osm_context")["details"]
    assert details["localities"] is None  # context kept for the enrichment only
    component = json.loads(
        (output / "schedule-component-manifest.json").read_text(encoding="utf-8")
    )
    assert "localityContextSha256" not in component["identity"]
    assert (
        ReferenceStore(output / "reference.sqlite", component["generationId"]).search_localities()
        == []
    )


def test_explicit_localities_fail_before_creating_output_without_the_reader(inputs, tmp_path):  # noqa: F811
    def missing_osmium(_path):
        raise RuntimeError("pyosmium is required")

    with pytest.raises(RuntimeError, match="pyosmium"):
        build(
            inputs,
            tmp_path / "gen",
            FIRST_DAY,
            localities=True,
            boundaries=Boundaries(runner=FakeDocker(tmp_path), load_osmium=missing_osmium),
        )
    assert not (tmp_path / "gen").exists()
    # Automatic mode never probes for pyosmium: no reader path and no addresses means no scan.
    output = build(
        inputs,
        tmp_path / "plain",
        FIRST_DAY,
        boundaries=Boundaries(runner=FakeDocker(tmp_path), load_osmium=missing_osmium),
    )
    assert stage_names(output) == list(stage_order(False))


def test_context_from_another_pbf_fails_the_context_stage_and_builds_nothing(inputs, tmp_path):  # noqa: F811
    calls: list[str] = []
    with pytest.raises(ValueError, match="different PBF"):
        build(
            inputs,
            tmp_path / "gen",
            FIRST_DAY,
            osm_reader_path=tmp_path / "reader",
            boundaries=_localities_boundaries(tmp_path, calls, context_sha="b" * 64),
        )
    output = tmp_path / "gen"
    evidence = json.loads((output / "pipeline" / "pipeline.json").read_text(encoding="utf-8"))
    assert evidence["failure"]["stage"] == "osm_context"
    assert stage_names(output) == ["osm_context"]
    assert not (output / "manifest.json").exists() and not (output / "reference.sqlite").exists()


def test_refuses_existing_output_without_touching_it(inputs, tmp_path):  # noqa: F811
    existing = tmp_path / "gen"
    existing.mkdir()
    (existing / "keep.txt").write_text("preserved", encoding="utf-8")
    docker = FakeDocker(tmp_path / "unused")
    with pytest.raises(FileExistsError):
        build(inputs, existing, FIRST_DAY, boundaries=Boundaries(runner=docker))
    assert [p.name for p in existing.iterdir()] == ["keep.txt"]
    assert docker.commands == []
    assert (
        cli.main(
            [
                "build-generation",
                "--snapshot",
                str(inputs),
                "--output",
                str(existing),
                "--first-day",
                "2026-09-30",
            ]
        )
        == 1
    )


def test_preflight_failures_create_no_output(inputs, tmp_path, jar):  # noqa: F811
    docker = FakeDocker(tmp_path / "unused")
    boundaries = Boundaries(runner=docker, load_osmium=lambda _path: object())
    with pytest.raises(ValueError, match="--photon-jar is required"):
        build(inputs, tmp_path / "a", FIRST_DAY, addresses=True, boundaries=boundaries)
    wrong = tmp_path / "wrong.jar"
    wrong.write_bytes(b"not the pinned jar")
    with pytest.raises(ValueError, match="pinned Photon 1.3.0"):
        build(
            inputs,
            tmp_path / "b",
            FIRST_DAY,
            addresses=True,
            photon_jar=wrong,
            boundaries=boundaries,
        )

    def missing_osmium(_path):
        raise RuntimeError("pyosmium is required")

    with pytest.raises(RuntimeError, match="pyosmium"):
        build(
            inputs,
            tmp_path / "c",
            FIRST_DAY,
            addresses=True,
            photon_jar=jar,
            boundaries=Boundaries(runner=docker, load_osmium=missing_osmium),
        )
    with pytest.raises(ValueError, match="Photon import memory cap"):
        build(
            inputs,
            tmp_path / "d",
            FIRST_DAY,
            addresses=True,
            photon_jar=jar,
            photon_memory_gib=3,
            boundaries=boundaries,
        )
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError, match="Snapshot lacks"):
        build(tmp_path / "empty", tmp_path / "e", FIRST_DAY, boundaries=Boundaries(runner=docker))
    assert not any((tmp_path / name).exists() for name in "abcde")
    assert docker.commands == []


def test_generated_config_is_slot_free_and_pins_walking_caps(inputs, tmp_path):  # noqa: F811
    output = build(
        inputs, tmp_path / "gen", FIRST_DAY, boundaries=Boundaries(runner=FakeDocker(tmp_path))
    )
    config = (output / "config.yml").read_text(encoding="utf-8")
    assert "server:" not in config and "port:" not in config and "host:" not in config
    assert (
        "limits:\n  street_routing_max_prepost_transit_seconds: 1800\n"
        "  street_routing_max_direct_seconds: 1800\n"
    ) in config
    assert "geocoding: true" in config
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["localEngineSlot"] is None and manifest["engineOrigin"] is None
    assert manifest["engineLimits"] == generations.STREET_ROUTING_LIMITS
    assert manifest["identity"]["engineLimits"] == generations.STREET_ROUTING_LIMITS
    assert manifest["configSha256"] == _sha(output / "config.yml")
    evidence = json.loads((output / "pipeline" / "pipeline.json").read_text(encoding="utf-8"))
    verify = next(s for s in evidence["stages"] if s["name"] == "verify")
    assert verify["details"]["engineConfig"]["slotFree"] is True
    # A different cap is a different config hash and generation identity.
    other = generations._config(FIRST_DAY, 31, True).replace("1800", "3600")
    assert hashlib.sha256(other.encode()).hexdigest() != manifest["configSha256"]


def test_walking_caps_cover_exactly_the_api_advertised_maxima():
    from opentransit.api.schemas import JourneyRequest

    maxima = set()
    for name in ("max_access_walk_minutes", "max_egress_walk_minutes", "max_direct_walk_minutes"):
        limits = [m.le for m in JourneyRequest.model_fields[name].metadata if hasattr(m, "le")]
        maxima.add(limits[0] * 60)
    assert maxima == {1800}
    assert set(generations.STREET_ROUTING_LIMITS.values()) == maxima
    assert set(generations.STREET_ROUTING_LIMITS) == {
        "street_routing_max_prepost_transit_seconds",
        "street_routing_max_direct_seconds",
    }


def test_engine_config_check_rejects_slot_ports_and_echoed_mismatches(tmp_path):
    slot = tmp_path / "slot"
    slot.mkdir()
    (slot / "config.yml").write_text(
        generations._config(FIRST_DAY, 31, True, "blue"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="slot-free"):
        pipeline.check_engine_config(slot)
    echoed = tmp_path / "echoed"
    echoed.mkdir()
    (echoed / "config.yml").write_text(generations._config(FIRST_DAY, 31, True), encoding="utf-8")
    (echoed / "import.log").write_text(
        "limits:\n  street_routing_max_direct_seconds: 21600\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="echoed"):
        pipeline.check_engine_config(echoed)
    (echoed / "import.log").write_text(
        "limits:\n  street_routing_max_direct_seconds: 1800\n", encoding="utf-8"
    )
    assert pipeline.check_engine_config(echoed)["engineEchoedLimits"] == {
        "street_routing_max_direct_seconds": 1800
    }
    (echoed / "config.yml").write_text("osm: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pinned street-routing limits"):
        pipeline.check_engine_config(echoed)


def test_interrupt_is_recorded_and_reraised(inputs, tmp_path):  # noqa: F811
    def interrupted(*args, **kwargs):
        kwargs["on_stage"]("validate", "started", {})
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        build(
            inputs,
            tmp_path / "gen",
            FIRST_DAY,
            boundaries=Boundaries(build_schedule=interrupted),
        )
    evidence = json.loads(
        (tmp_path / "gen" / "pipeline" / "pipeline.json").read_text(encoding="utf-8")
    )
    assert evidence["state"] == "failed" and evidence["failure"]["stage"] == "validate"


def test_cli_forwards_build_generation_arguments(tmp_path, monkeypatch):
    captured = {}

    def fake(*args, **kwargs):
        captured["args"], captured["kwargs"] = args, kwargs
        return tmp_path / "gen"

    monkeypatch.setattr(pipeline, "build_complete_generation", fake)
    code = cli.main(
        [
            "build-generation",
            "--snapshot",
            str(tmp_path / "snap"),
            "--output",
            str(tmp_path / "gen"),
            "--first-day",
            "2026-10-01",
            "--days",
            "31",
            "--addresses",
            "--photon-jar",
            str(tmp_path / "photon.jar"),
            "--osm-reader-path",
            str(tmp_path / "reader"),
        ]
    )
    assert code == 0
    assert captured["args"] == (tmp_path / "snap", tmp_path / "gen", date(2026, 10, 1), 31)
    assert captured["kwargs"]["addresses"] is True
    assert captured["kwargs"]["memory_gib"] == 6 and captured["kwargs"]["photon_memory_gib"] == 2
    assert captured["kwargs"]["osm_reader_path"] == tmp_path / "reader"
    assert captured["kwargs"]["localities"] is None  # automatic
    for flag, expected in (("--localities", True), ("--no-localities", False)):
        cli.main(
            ["build-generation", "--snapshot", "s", "--output", "o", "--first-day", "2026-10-01"]
            + [flag]
        )
        assert captured["kwargs"]["localities"] is expected

    def failing(*args, **kwargs):
        raise subprocess.TimeoutExpired("docker", 1)

    monkeypatch.setattr(pipeline, "build_complete_generation", failing)
    assert (
        cli.main(
            ["build-generation", "--snapshot", "s", "--output", "o", "--first-day", "2026-10-01"]
        )
        == 1
    )
