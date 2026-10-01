"""Dry-run retention tests preserve all protected and unproven generations."""

import hashlib
import json
import os

import pytest

from opentransit.build.retention import plan_prune


def _generation(root, generation_id, built_at):
    directory = root / generation_id
    (directory / "motis").mkdir(parents=True)
    graph = b"graph-" + generation_id.encode()
    (directory / "motis" / "graph.bin").write_bytes(graph)
    config = b"config\n"
    (directory / "config.yml").write_bytes(config)
    reference = b"reference-" + generation_id.encode()
    (directory / "reference.sqlite").write_bytes(reference)
    graph_hash = hashlib.sha256(graph).hexdigest()
    ref_hash = hashlib.sha256(reference).hexdigest()
    config_hash = hashlib.sha256(config).hexdigest()
    graph_tree_hash = hashlib.sha256(
        f"graph.bin\0{len(graph)}\0{graph_hash}\n".encode()
    ).hexdigest()
    manifest = {
        "schemaVersion": 1,
        "generationId": generation_id,
        "state": "ready",
        "builtAt": built_at,
        "engineDigest": "sha256:" + "a" * 64,
        "artifacts": {
            "motis": {
                "path": "motis",
                "sha256": graph_tree_hash,
                "files": [{"path": "graph.bin", "bytes": len(graph), "sha256": graph_hash}],
            },
            "config": {"path": "config.yml", "sha256": config_hash},
            "reference": {"path": "reference.sqlite", "sha256": ref_hash},
        },
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def test_retention_lists_only_verified_older_unprotected_generation(tmp_path):
    root = tmp_path / "generations"
    root.mkdir()
    old = _generation(root, "old", "2026-09-01T00:00:00+00:00")
    active = _generation(root, "active", "2026-09-29T00:00:00+00:00")
    previous = _generation(root, "previous", "2026-09-28T00:00:00+00:00")
    pinned = _generation(root, "pinned", "2026-09-02T00:00:00+00:00")
    draining = _generation(root, "draining", "2026-09-03T00:00:00+00:00")
    plan = plan_prune(root, "active", "previous", {"pinned"}, {"draining"})
    assert [item["generationId"] for item in plan.candidates] == ["old"]
    retained = {item["generationId"] for item in plan.retained}
    assert {"active", "previous", "pinned", "draining"} <= retained
    assert plan.as_dict()["deletionPerformed"] is False
    assert all(path.exists() for path in (old, active, previous, pinned, draining))


def test_retention_keeps_everything_when_previous_boundary_missing(tmp_path):
    root = tmp_path / "generations"
    root.mkdir()
    _generation(root, "old", "2026-09-01T00:00:00+00:00")
    plan = plan_prune(root, "active", "missing")
    assert plan.candidates == ()
    assert any(item["generationId"] == "old" for item in plan.retained)


def test_retention_keeps_unverified_generation(tmp_path):
    root = tmp_path / "generations"
    root.mkdir()
    broken = root / "broken"
    broken.mkdir()
    (broken / "manifest.json").write_text('{"generationId":"broken"}', encoding="utf-8")
    plan = plan_prune(root, "active", "previous")
    assert plan.candidates == ()
    assert "unverified" in plan.retained[0]["reason"]


def test_retention_keeps_all_when_active_identity_is_unknown(tmp_path):
    root = tmp_path / "generations"
    root.mkdir()
    _generation(root, "old", "2026-09-01T00:00:00+00:00")
    _generation(root, "previous", "2026-09-28T00:00:00+00:00")
    plan = plan_prune(root, "missing-active", "previous")
    assert plan.candidates == ()
    assert {item["generationId"] for item in plan.retained} == {"old", "previous"}


def test_retention_keeps_duplicate_generation_ids(tmp_path):
    root = tmp_path / "generations"
    root.mkdir()
    first = _generation(root, "duplicate-one", "2026-09-01T00:00:00+00:00")
    second = _generation(root, "duplicate-two", "2026-09-02T00:00:00+00:00")
    previous = _generation(root, "previous", "2026-09-28T00:00:00+00:00")
    for directory in (first, second):
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["generationId"] = "same-id"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    plan = plan_prune(root, "previous", "previous")
    assert plan.candidates == ()
    collisions = [item for item in plan.retained if item["generationId"] == "same-id"]
    assert len(collisions) == 2
    assert all("duplicate generation identity" in item["reason"] for item in collisions)
    assert previous.exists()


def test_retention_never_traverses_or_lists_external_symlink_candidate(tmp_path):
    root = tmp_path / "generations"
    external = tmp_path / "external"
    root.mkdir()
    external.mkdir()
    _generation(root, "previous", "2026-09-28T00:00:00+00:00")
    linked = _generation(external, "outside", "2026-09-01T00:00:00+00:00")
    try:
        os.symlink(linked, root / "outside-link", target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")
    plan = plan_prune(root, "previous", "previous")
    assert all(item["path"] != str(linked) for item in plan.candidates)
    assert any("symlink or junction" in item["reason"] for item in plan.retained)
