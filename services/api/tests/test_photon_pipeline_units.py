"""Unit checks for the Photon preparation, import log and sealing helpers (no Docker, no osmium)."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from opentransit.build import photon, photon_source, select_generation
from opentransit.build.address_catalog import build_address_catalog


def _tag(**tags):
    return [SimpleNamespace(k=key.replace("__", ":"), v=value) for key, value in tags.items()]


def _location(lon, lat, valid=True):
    return SimpleNamespace(lon=lon, lat=lat, valid=lambda: valid)


class FakeOsmium:
    """Minimal pyosmium stand-in: feeds fixed nodes, ways and areas to a SimpleHandler."""

    def __init__(self, nodes=(), ways=(), areas=()):
        class SimpleHandler:
            def apply_file(self, path, locations=False, idx=None):
                for kind, items in (("node", nodes), ("way", ways), ("area", areas)):
                    for item in items:
                        handler = getattr(self, kind, None)
                        if handler is not None:
                            handler(item)

        self.SimpleHandler = SimpleHandler
        self.geom = SimpleNamespace(
            GeoJSONFactory=lambda: SimpleNamespace(
                create_multipolygon=lambda area: json.dumps(area.geometry)
            )
        )


def fake_world():
    nodes = [
        SimpleNamespace(
            id=11,
            tags=_tag(addr__housenumber="7", addr__street="Herzl", addr__city="Tel Aviv"),
            location=_location(34.78, 32.08),
        ),
        SimpleNamespace(  # no street: not an address document
            id=12, tags=_tag(addr__housenumber="9"), location=_location(34.78, 32.08)
        ),
        SimpleNamespace(  # unlocated node is skipped
            id=13,
            tags=_tag(addr__housenumber="1", addr__street="Herzl"),
            location=_location(0, 0, valid=False),
        ),
    ]
    ways = [
        SimpleNamespace(
            id=500,
            tags=_tag(highway="residential", name="Herzl", name__en="Herzl St"),
            nodes=[
                SimpleNamespace(location=_location(34.7799, 32.0799)),
                SimpleNamespace(location=_location(34.7801, 32.0801)),
            ],
        ),
        SimpleNamespace(  # unnamed highway is not context
            id=501,
            tags=_tag(highway="service"),
            nodes=[
                SimpleNamespace(location=_location(34.7, 32.0)),
                SimpleNamespace(location=_location(34.71, 32.01)),
            ],
        ),
    ]
    square = [[[34.7, 32.0], [34.9, 32.0], [34.9, 32.2], [34.7, 32.2], [34.7, 32.0]]]
    areas = [
        SimpleNamespace(
            tags=_tag(boundary="administrative", admin_level="8", name="Tel Aviv"),
            geometry={"type": "MultiPolygon", "coordinates": [square]},
            from_way=lambda: False,
            orig_id=lambda: 9001,
        ),
        SimpleNamespace(  # wrong admin level: not a locality
            tags=_tag(boundary="administrative", admin_level="4", name="District"),
            geometry={"type": "MultiPolygon", "coordinates": [square]},
            from_way=lambda: False,
            orig_id=lambda: 9002,
        ),
    ]
    return FakeOsmium(nodes, ways, areas)


def test_source_scans_feed_the_real_enrichment_and_catalog(tmp_path):
    from tools.enrich_photon_addresses import transform_dump

    pbf = tmp_path / "source.osm.pbf"
    pbf.write_bytes(b"synthetic pbf")
    pbf_sha = hashlib.sha256(pbf.read_bytes()).hexdigest()
    world = fake_world()
    houses = photon_source.export_house_dump(pbf, tmp_path / "houses.jsonl", osmium=world)
    context = photon_source.extract_context(pbf, tmp_path / "context.jsonl", osmium=world)
    assert houses["houseRecords"] == 1 and houses["sourcePbfSha256"] == pbf_sha
    assert context["counts"]["streetRecordsWritten"] == 1
    assert context["counts"]["localityRecordsWritten"] == 1
    assert context["counts"]["areasProducedByOsmium"] == 2
    header = json.loads((tmp_path / "houses.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert header["content"]["database_version"].endswith(pbf_sha)
    first = json.loads((tmp_path / "context.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert first == {"type": "ContextHeader", "sourceSha256": pbf_sha, "schemaVersion": 1}

    # The unmodified enrichment accepts these files with the supplied PBF hash (no pins).
    result = transform_dump(
        tmp_path / "houses.jsonl",
        tmp_path / "context.jsonl",
        tmp_path / "enriched.jsonl",
        tmp_path / "enriched.provenance.json",
        expected_source_sha256=pbf_sha,
        expected_house_dump_sha256=None,
        expected_house_count=None,
    )
    counts = result["counts"]
    assert counts["houseRecords"] == 1 and counts["streetDocumentsAdded"] == 1
    catalog = build_address_catalog(tmp_path / "enriched.jsonl", tmp_path / "catalog.sqlite")
    assert int(catalog["record_count"]) == 2
    assert catalog["source_pbf_sha256"] == pbf_sha

    probes = photon.pick_probe_documents(tmp_path / "enriched.jsonl")
    assert [p["kind"] for p in probes] == ["house", "street"]
    assert probes[0]["osmType"] == "N" and probes[0]["housenumber"] == "7"
    assert probes[1]["osmType"] == "W" and probes[1]["osmId"] == "500"


def test_source_scans_refuse_to_overwrite_and_missing_reader(tmp_path):
    pbf = tmp_path / "source.osm.pbf"
    pbf.write_bytes(b"x")
    existing = tmp_path / "houses.jsonl"
    existing.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        photon_source.export_house_dump(pbf, existing, osmium=fake_world())
    assert existing.read_text(encoding="utf-8") == "keep"
    with pytest.raises(RuntimeError, match="--osm-reader-path"):
        photon_source.load_osmium(tmp_path / "no-such-reader-dir")


def test_import_log_requires_marker_exact_count_and_no_fatal_markers():
    good = (
        f"{photon.SETUP_MARKER}\n"
        "Finished import of 5 photon documents. (Total processing time: 1s)\n"
    )
    assert photon.check_import_log(good, 5)["indexedDocuments"] == 5
    for bad in (
        good.replace("5 photon", "4 photon"),
        good.replace(photon.SETUP_MARKER, "x"),
        good + "Import error.\n",
        good + good,
        "",
    ):
        with pytest.raises(ValueError, match="unverified"):
            photon.check_import_log(bad, 5)


def test_photon_memory_caps_never_exceed_two_gib():
    caps, heap = photon.photon_memory_args(2)
    assert caps == ["--memory=2g", "--memory-swap=2g"] and heap == "1g"
    assert photon.photon_memory_args(1)[1] == "512m"
    for bad in (0, 3, True, "2"):
        with pytest.raises(ValueError):
            photon.photon_memory_args(bad)


def test_photon_tree_checkpoint_matches_staging_and_init_algorithms(tmp_path):
    import importlib.util
    import sys

    root = tmp_path / "tree"
    (root / "photon_data" / "node_1").mkdir(parents=True)
    (root / "photon_data" / "node_1" / "a.bin").write_bytes(b"a")
    (root / "photon_data" / "node_1" / "write.lock").write_bytes(b"")
    checkpoint = photon.tree_checkpoint(root)
    assert checkpoint["files"] == 2 and checkpoint["bytes"] == 1
    path = Path(__file__).resolve().parents[3] / "deploy" / "aws" / "tools" / "stage_bundle.py"
    if path.is_file():
        spec = importlib.util.spec_from_file_location("units_stage_bundle", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["units_stage_bundle"] = module
        spec.loader.exec_module(module)
        entries = module.tree_entries(root)
        assert module.tree_digest(entries) == checkpoint["treeSha256"]


def test_sealing_refuses_missing_http_client_and_preserves_the_container(tmp_path):
    jar = tmp_path / "photon.jar"
    jar.write_bytes(b"jar")
    commands = []

    def runner(command, stdout, stderr, check, timeout):
        commands.append(command)
        if command[1] == "exec":
            return SimpleNamespace(returncode=1)  # neither curl nor wget
        if command[1] == "inspect":
            stdout.write(json.dumps({"Status": "exited", "ExitCode": 143, "OOMKilled": False}))
        return SimpleNamespace(returncode=0)

    logs = tmp_path / "logs"
    logs.mkdir()
    original = photon.PHOTON_130_JAR_SHA256
    photon.PHOTON_130_JAR_SHA256 = hashlib.sha256(b"jar").hexdigest()
    try:
        with pytest.raises(RuntimeError, match="neither curl nor wget"):
            photon.seal_photon(
                "volume", jar, [], 1, logs, tmp_path / "photon", runner=runner, sleep=lambda _: None
            )
    finally:
        photon.PHOTON_130_JAR_SHA256 = original
    assert any(command[1] == "stop" for command in commands)  # stopped, never removed
    assert not any(command[1] == "rm" for command in commands)
    assert not (tmp_path / "photon").exists()


def test_select_generation_requires_a_passed_probe_and_uses_existing_activation(
    tmp_path, monkeypatch
):
    root = tmp_path / "generations"
    generation = root / "one"
    generation.mkdir(parents=True)
    (generation / "manifest.json").write_text(
        json.dumps({"state": "ready", "generationId": "g" * 64}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="probe is required"):
        select_generation.select_generation(generation, root, "http://127.0.0.1:59081")
    (generation / "probe.json").write_text(
        json.dumps({"status": "failed", "generationId": "g" * 64}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="did not pass"):
        select_generation.select_generation(generation, root, "http://127.0.0.1:59081")
    (generation / "probe.json").write_text(
        json.dumps({"status": "passed", "generationId": "g" * 64}), encoding="utf-8"
    )
    seen = {}

    def fake_write(path, data, generations_root):
        seen["binding"] = (path, data, generations_root)
        return SimpleNamespace(
            generation_id=data["generationId"], engine_origin=data["engineOrigin"]
        )

    def fake_activate(generations_root, current, binding):
        seen["activate"] = (generations_root, current, binding)
        return "bindings/previous.json"

    monkeypatch.setattr(select_generation, "write_binding", fake_write)
    monkeypatch.setattr(select_generation, "activate_current", fake_activate)
    result = select_generation.select_generation(
        generation, root, "http://127.0.0.1:59081", operation_token="t" * 32
    )
    path, data, _ = seen["binding"]
    assert path.parent == root.resolve() / "bindings" and data["activationToken"] == "t" * 32
    assert data["probePath"] == str((generation / "probe.json").resolve())
    assert seen["activate"] == (root.resolve(), root.resolve() / "current", path)
    assert result["previousTarget"] == "bindings/previous.json"
    with pytest.raises(ValueError, match="inside the generations root"):
        select_generation.select_generation(tmp_path, root, "http://127.0.0.1:59081")
