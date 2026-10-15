"""Tests for the local H-1 generation publisher (deploy/aws/tools/publish_generation.py).

Synthetic fixtures only: no Docker, no network, no AWS. The push path is never executed; the
tests only check that dry runs cannot reach it and what it would do.
"""

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from opentransit.build.local_operator import currency_reasons
from opentransit.core.generation import Generation

REPO = Path(__file__).resolve().parents[3]
AWS = REPO / "deploy" / "aws"
pytestmark = pytest.mark.skipif(not AWS.is_dir(), reason="deploy/aws is not part of this checkout")


def _load():
    path = AWS / "tools" / "publish_generation.py"
    spec = importlib.util.spec_from_file_location("aws_publish_generation", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["aws_publish_generation"] = module
    spec.loader.exec_module(module)
    return module


pub = _load() if AWS.is_dir() else None

CHECKED = datetime.fromisoformat("2026-10-01T09:19:50+00:00")
NOW = CHECKED + timedelta(hours=24)  # current
COVERAGE = {"from": "2026-10-01T00:00:00+03:00", "until": "2026-11-01T00:00:00+02:00"}
UNTIL = datetime.fromisoformat(COVERAGE["until"])
IDS = {"api": "sha256:" + "a" * 64, "data": "sha256:" + "b" * 64, "photon": "sha256:" + "e" * 64}
ARN = "arn:aws:ecs:il-central-1:111122223333:task-definition/opentransit-h0:7"


def _write(path: Path, data: bytes) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _generation(tmp_path: Path, **overrides) -> Path:
    root = tmp_path / "generation"
    reference = _write(root / "reference.sqlite", b"reference-bytes")
    config = _write(root / "config.yml", b"osm: /input/x\n")
    files = [
        {"path": rel, **_write(root / "motis" / rel, data)}
        for rel, data in (("config.yml", b"osm: x\n"), ("tt.bin", b"timetable"))
    ]
    digest = hashlib.sha256()
    for item in files:
        digest.update(f"{item['path']}\0{item['bytes']}\0{item['sha256']}\n".encode())
    manifest = {
        "schemaVersion": 1,
        "state": "ready",
        "generationId": "c" * 64,
        "builtAt": "2026-10-01T12:41:32+00:00",
        "validatedAt": "2026-10-01T12:24:55+00:00",
        "sourceCheckedAt": CHECKED.isoformat(),
        "coverage": COVERAGE,
        "engineDigest": "sha256:" + "d" * 64,
        "mode": "real",
        "artifacts": {
            "reference": {"path": "reference.sqlite", "sha256": reference["sha256"]},
            "config": {"path": "config.yml", "sha256": config["sha256"]},
            "motis": {"path": "motis", "files": files, "sha256": digest.hexdigest()},
        },
        **overrides,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def _corpus(tmp_path: Path, when="2026-10-05T08:00:00+03:00") -> Path:
    path = tmp_path / "probe-queries.json"
    case = {"fromPlace": "32.0836,34.7981", "toPlace": "32.0838,34.8044", "time": when}
    path.write_text(json.dumps({"cases": [{"id": "J01", "params": case}]}), encoding="utf-8")
    return path


@pytest.fixture
def no_subprocess(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError(f"a dry run must not run commands: {args!r}")

    monkeypatch.setattr(subprocess, "run", refuse)


def _publish(tmp_path, **kwargs):
    if "generation" not in kwargs:  # built lazily so a caller's tampered fixture survives
        kwargs["generation"] = _generation(tmp_path)
    defaults = {
        "probe_queries": _corpus(tmp_path),
        "output": tmp_path / "plan",
        "now": NOW,
        "variant": "no-addresses",
        "image_ids": {"api": IDS["api"], "data": IDS["data"]},
    }
    return pub.publish(**{**defaults, **kwargs})


def _container(task, name):
    return next(c for c in task["containerDefinitions"] if c["name"] == name)


def _release(**overrides) -> dict:
    manifest = {
        "schemaVersion": 1,
        "state": "ready",
        "generationId": "f" * 64,
        "builtAt": "2026-10-01T12:41:32+00:00",
        "validatedAt": "2026-10-01T12:24:55+00:00",
        "sourceCheckedAt": CHECKED.isoformat(),
        "coverage": COVERAGE,
        "engineDigest": "sha256:" + "d" * 64,
    }
    release = {
        "generationId": "f" * 64,
        "manifestSummary": manifest,
        "digestKind": "registry-manifest",
        "taskDefinitionArn": ARN,
        "images": {"api": "sha256:" + "1" * 64, "data": "sha256:" + "2" * 64},
        "motisDigest": pub.render_drafts.MOTIS_DIGEST,
    }
    release.update(overrides)
    return release


# --- dry-run rendering and digest pinning ------------------------------------------------------


def test_dry_run_renders_a_digest_pinned_candidate_without_commands(tmp_path, no_subprocess):
    code, plan = _publish(tmp_path)
    assert code == 0 and plan["outcome"] == "ok" and plan["mode"] == "dry-run"
    assert plan["awsCallsMade"] is False
    assert plan["stages"]["stage"]["executed"] is False
    assert plan["stages"]["build"]["executed"] is False
    assert plan["stages"]["push-and-deploy"]["executed"] is False
    assert plan["stages"]["render"]["validation"]["errors"] == []
    task = json.loads((tmp_path / "plan" / "task-definition.candidate.json").read_text("utf-8"))
    assert _container(task, "init")["image"].endswith("/opentransit-data@" + IDS["data"])
    assert _container(task, "api")["image"].endswith("/opentransit-api@" + IDS["api"])
    assert _container(task, "verifier")["image"] == _container(task, "api")["image"]
    motis = pub.render_drafts.MOTIS_DIGEST
    assert _container(task, "motis")["image"].endswith("@" + motis)
    assert "_DIGEST}}" not in json.dumps(task)
    tags = {t["key"]: t["value"] for t in task["tags"]}
    corpus_sha = hashlib.sha256(_corpus(tmp_path).read_bytes()).hexdigest()
    assert tags["generation-id"] == "c" * 64 and tags["purpose"] == "h1-candidate"
    assert tags["probe-corpus-sha256"] == corpus_sha
    assert tags["verifier-config-sha256"] == pub.verifier_config_sha256(task)
    assert tags["source-checked-at"] == CHECKED.isoformat()
    assert tags["digest-kind"] == "local-image-id"
    release = plan["release"]
    assert release["images"] == {"api": IDS["api"], "data": IDS["data"]}
    assert release["taskDefinitionArn"] is None and release["motisDigest"] == motis
    saved = json.loads((tmp_path / "plan" / "release-plan.json").read_text("utf-8"))
    assert saved["release"] == release
    build = plan["stages"]["build"]["commands"]
    assert [c[:2] for c in build] == [["docker", "build"], ["docker", "build"]]
    assert any("bundle=" in arg for arg in build[1])


def test_dry_run_without_digests_renders_nothing_unpinned(tmp_path, no_subprocess):
    code, plan = _publish(tmp_path, image_ids={})
    assert code == 0 and plan["stages"]["render"]["status"] == "skipped"
    assert not (tmp_path / "plan" / "task-definition.candidate.json").exists()
    assert "release" not in plan


def test_plan_never_overwrites_an_existing_plan(tmp_path, no_subprocess):
    _publish(tmp_path)
    with pytest.raises(FileExistsError):
        _publish(tmp_path)


def test_verifier_config_hash_tracks_the_api_digest(tmp_path):
    generation = _generation(tmp_path)
    verified = pub.verify_candidate(generation, _corpus(tmp_path), now=NOW)
    first = pub.render_candidate("no-addresses", IDS, verified, digest_kind="local-image-id")
    other = dict(IDS, api="sha256:" + "9" * 64)
    second = pub.render_candidate("no-addresses", other, verified, digest_kind="local-image-id")
    assert pub.verifier_config_sha256(first) != pub.verifier_config_sha256(second)


def test_render_refuses_missing_malformed_digests_and_variant_mismatch(tmp_path):
    verified = pub.verify_candidate(_generation(tmp_path), _corpus(tmp_path), now=NOW)
    with pytest.raises(pub.PublishRefused, match="digest_missing:data"):
        pub.render_candidate(
            "no-addresses", {"api": IDS["api"]}, verified, digest_kind="local-image-id"
        )
    with pytest.raises(pub.PublishRefused, match="digest_malformed:api"):
        pub.render_candidate(
            "no-addresses", {**IDS, "api": "latest"}, verified, digest_kind="local-image-id"
        )
    with pytest.raises(pub.PublishRefused, match="variant_mismatch"):
        pub.render_candidate("recommended", IDS, verified, digest_kind="local-image-id")
    with_photon = {**verified, "addressSearch": True}
    with pytest.raises(pub.PublishRefused, match="digest_missing:photon"):
        pub.render_candidate(
            "recommended",
            {"api": IDS["api"], "data": IDS["data"]},
            with_photon,
            digest_kind="local-image-id",
        )


def test_recommended_candidate_with_registry_and_role_validates(tmp_path):
    verified = pub.verify_candidate(_generation(tmp_path), _corpus(tmp_path), now=NOW)
    verified = {**verified, "addressSearch": True, "scheduleComponentGenerationId": "8" * 64}
    task = pub.render_candidate(
        "recommended",
        IDS,
        verified,
        digest_kind="registry-manifest",
        registry="111122223333.dkr.ecr.il-central-1.amazonaws.com",
        execution_role_arn="arn:aws:iam::111122223333:role/opentransit-h0-execution",
    )
    errors, _ = pub.validate_drafts.validate_candidate(task, "c", pub.render_drafts.MOTIS_DIGEST)
    assert errors == []
    assert _container(task, "photon")["image"].endswith("/opentransit-photon@" + IDS["photon"])
    assert "{{" not in json.dumps(task)
    tags = {t["key"]: t["value"] for t in task["tags"]}
    assert tags["schedule-component-id"] == "8" * 64


def _candidate(tmp_path) -> dict:
    verified = pub.verify_candidate(_generation(tmp_path), _corpus(tmp_path), now=NOW)
    return pub.render_candidate("no-addresses", IDS, verified, digest_kind="local-image-id")


@pytest.mark.parametrize(
    "mutation",
    [
        "placeholder_digest",
        "verifier_image",
        "missing_tag",
        "bad_generation_tag",
        "draft_purpose",
        "public_registry",
        "bad_role",
        "secret",
    ],
)
def test_candidate_validator_rejects(tmp_path, mutation):
    task = copy.deepcopy(_candidate(tmp_path))
    api = _container(task, "api")
    if mutation == "placeholder_digest":
        _container(task, "init")["image"] = "{{ECR_REGISTRY}}/opentransit-data@{{DATA_DIGEST}}"
    elif mutation == "verifier_image":
        _container(task, "verifier")["image"] = api["image"][:-1] + "0"
    elif mutation == "missing_tag":
        task["tags"] = [t for t in task["tags"] if t["key"] != "probe-corpus-sha256"]
    elif mutation == "bad_generation_tag":
        next(t for t in task["tags"] if t["key"] == "generation-id")["value"] = "oct1b"
    elif mutation == "draft_purpose":
        next(t for t in task["tags"] if t["key"] == "purpose")["value"] = "h0-draft"
    elif mutation == "public_registry":
        api["image"] = "docker.io/library/api@" + IDS["api"]
    elif mutation == "bad_role":
        task["executionRoleArn"] = "arn:aws:iam::111122223333:user/someone"
    elif mutation == "secret":
        api["environment"].append({"name": "X", "value": "AKIA" + "A" * 16})
    errors, _ = pub.validate_drafts.validate_candidate(task, "t", pub.render_drafts.MOTIS_DIGEST)
    assert errors, mutation


def test_committed_drafts_are_not_release_candidates():
    task = json.loads((AWS / "ecs" / "task-definition.json").read_text(encoding="utf-8"))
    errors, _ = pub.validate_drafts.validate_candidate(task, "d", pub.render_drafts.MOTIS_DIGEST)
    assert any("concrete sha256 digest" in e for e in errors)
    assert any("purpose must be h1-candidate" in e for e in errors)


# --- verification refusals ---------------------------------------------------------------------


def test_new_candidate_requires_current_freshness_and_coverage(tmp_path):
    generation, corpus = _generation(tmp_path), _corpus(tmp_path)
    with pytest.raises(pub.PublishRefused) as aging:
        pub.verify_candidate(generation, corpus, now=CHECKED + timedelta(hours=31))
    assert aging.value.reasons == ["source_aging"]
    with pytest.raises(pub.PublishRefused) as lapsed:
        pub.verify_candidate(generation, corpus, now=UNTIL + timedelta(minutes=1))
    assert "coverage_expired" in lapsed.value.reasons
    assert "source_expired" in lapsed.value.reasons


def test_probe_departures_must_fall_inside_coverage(tmp_path):
    corpus = _corpus(tmp_path, when="2026-12-01T08:00:00+02:00")
    with pytest.raises(pub.PublishRefused, match="probe_outside_coverage:J01"):
        pub.verify_candidate(_generation(tmp_path), corpus, now=NOW)


def test_tampered_or_unready_generation_is_refused_and_plan_kept(tmp_path, no_subprocess):
    generation = _generation(tmp_path)
    (generation / "reference.sqlite").write_bytes(b"changed")
    code, plan = _publish(tmp_path, generation=generation)
    assert code == 1 and plan["outcome"] == "refused"
    assert plan["stages"]["verify"]["status"] == "refused"
    assert plan["stages"]["verify"]["reasons"][0].startswith("artifacts_invalid")
    assert (tmp_path / "plan" / "release-plan.json").is_file()
    assert not (tmp_path / "plan" / "task-definition.candidate.json").exists()
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(pub.PublishRefused, match="generation_not_ready"):
        pub.verify_candidate(_generation(other, state="building"), _corpus(other), now=NOW)


def test_photon_data_for_a_schedule_only_generation_is_refused(tmp_path):
    with pytest.raises(pub.PublishRefused, match="photon_data_without_address_search"):
        pub.verify_candidate(
            _generation(tmp_path), _corpus(tmp_path), now=NOW, photon_data=tmp_path
        )


def test_build_mode_runs_only_local_docker_commands_in_order(tmp_path):
    calls = []

    def fake_runner(argv):
        calls.append(argv)
        return IDS["api"] if "ot-h1-api" in argv[-1] else IDS["data"]

    code, plan = _publish(tmp_path, image_ids=None, build=True, runner=fake_runner)
    assert code == 0, plan
    assert plan["stages"]["stage"]["executed"] is True
    assert (tmp_path / "plan" / "stage" / "payload-manifest.json").is_file()
    assert {argv[0] for argv in calls} == {"docker"}
    assert [argv[1] for argv in calls] == ["build", "build", "image", "image"]
    assert plan["stages"]["build"]["imageIds"] == {"api": IDS["api"], "data": IDS["data"]}
    assert plan["release"]["localTags"]["data"] == "ot-h1-data:gen-" + "c" * 12


# --- retention ---------------------------------------------------------------------------------


def test_retention_protects_active_previous_and_pins_and_never_deletes():
    current = _release(generationId="a" * 64, images={"api": "sha256:" + "3" * 64})
    previous = _release()
    pin = "sha256:" + "4" * 64
    listing = [
        {"repositoryName": "opentransit-api", "imageDigest": "sha256:" + "3" * 64},
        {"repositoryName": "opentransit-data", "imageDigest": "sha256:" + "2" * 64},
        {"repositoryName": "opentransit-data", "imageDigest": pin, "imageTags": ["gen-x"]},
        {"repositoryName": "opentransit-data", "imageDigest": "sha256:" + "5" * 64},
    ]
    plan = pub.retention_plan(
        current=current, previous=previous, pins={pin: "h0-evidence"}, registry_images=listing
    )
    assert plan["automaticDeletion"] is False and plan["deletionPerformed"] is False
    protected = {item["digest"]: item["reasons"] for item in plan["protectedDigests"]}
    assert "active:api:aaaaaaaaaaaa" in protected["sha256:" + "3" * 64]
    assert "previous:data:ffffffffffff" in protected["sha256:" + "2" * 64]
    assert protected[pin] == ["evidence:h0-evidence"]
    assert pub.render_drafts.MOTIS_DIGEST in protected
    assert [i["digest"] for i in plan["unprotectedForHumanReview"]] == ["sha256:" + "5" * 64]
    # The previous API image is protected but missing from the listing: rollback would fail.
    assert any("1111" in w and "absent" in w for w in plan["warnings"])


def test_retention_warns_for_local_ids_and_missing_previous():
    plan = pub.retention_plan(current=_release(digestKind="local-image-id"), previous=None)
    assert any("local image IDs" in w for w in plan["warnings"])
    assert any("no previous release" in w for w in plan["warnings"])
    with pytest.raises(ValueError):
        pub.parse_pins(["latest"])


def test_push_plan_never_deletes_or_deregisters():
    release = _release(localTags={"api": "ot-h1-api:x", "data": "ot-h1-data:x"})
    steps = pub.push_steps(
        release,
        region="il-central-1",
        registry="111122223333.dkr.ecr.il-central-1.amazonaws.com",
        cluster="c",
        service="s",
    )
    text = json.dumps(steps)
    for forbidden in ("delete", "deregister", "batch-delete", "lifecycle", "--force"):
        assert forbidden not in text
    assert steps[-1][:3] == ["aws", "ecs", "update-service"]
    assert steps[-2][:3] == ["aws", "ecs", "register-task-definition"]


def test_push_cli_without_execute_flag_only_prints(tmp_path, no_subprocess, capsys):
    plan = {
        "mode": "build",
        "outcome": "ok",
        "release": _release(localTags={"api": "ot-h1-api:x", "data": "ot-h1-data:x"}),
    }
    path = tmp_path / "release-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    args = ["push", "--plan", str(path), "--region", "il-central-1"]
    args += ["--registry", "111122223333.dkr.ecr.il-central-1.amazonaws.com"]
    args += ["--cluster", "c", "--service", "s", "--execution-role-arn", "r"]
    assert pub.main(args) == 0
    assert json.loads(capsys.readouterr().out)["executed"] is False
    path.write_text(json.dumps({**plan, "mode": "dry-run"}), encoding="utf-8")
    assert pub.main(args + ["--execute-aws"]) == 1  # refused before any command


# --- rollback ----------------------------------------------------------------------------------


def test_rollback_accepts_a_stale_but_covered_previous_release():
    plan = pub.rollback_plan(
        _release(generationId="a" * 64, images={"api": "sha256:" + "3" * 64}),
        _release(),
        CHECKED + timedelta(days=3),
    )
    assert plan["allowed"] is True and plan["freshness"] == "stale"
    assert plan["executed"] is False and plan["command"][-1] == ARN


def test_rollback_refuses_expired_coverage_and_expired_freshness():
    lapsed = pub.rollback_plan(None, _release(), UNTIL + timedelta(seconds=1))
    assert lapsed["allowed"] is False and "coverage_expired" in lapsed["reasons"]
    assert "command" not in lapsed
    expired = pub.rollback_plan(None, _release(), CHECKED + timedelta(days=7, minutes=1))
    assert expired["reasons"] == ["source_expired"]


def test_rollback_refuses_unregistered_or_identical_or_missing_previous():
    local = pub.rollback_plan(
        None, _release(digestKind="local-image-id", taskDefinitionArn=None), NOW
    )
    assert set(local["reasons"]) == {"previous_not_registry_pinned", "previous_revision_unknown"}
    same = pub.rollback_plan(_release(), _release(), NOW)
    assert same["reasons"] == ["previous_equals_current"]
    assert pub.rollback_plan(None, None, NOW)["reasons"] == ["no_previous_release"]


def test_rollback_cli_exit_code_reflects_refusal(tmp_path, capsys):
    path = tmp_path / "previous.json"
    path.write_text(json.dumps({"release": _release()}), encoding="utf-8")
    assert pub.main(["rollback", "--previous", str(path), "--now", NOW.isoformat()]) == 0
    late = (UNTIL + timedelta(days=1)).isoformat()
    assert pub.main(["rollback", "--previous", str(path), "--now", late]) == 1
    out = capsys.readouterr().out
    assert '"allowed": true' in out and '"coverage_expired"' in out


# --- shared rule ---------------------------------------------------------------------------------


def test_shared_currency_rule_and_manifest_parsing():
    generation = Generation.from_manifest(_release()["manifestSummary"])
    stale = CHECKED + timedelta(days=3)
    assert currency_reasons(generation, stale, rollback=True) == []
    assert currency_reasons(generation, stale, rollback=False) == ["source_stale"]
    with pytest.raises(ValueError):
        currency_reasons(generation, stale.replace(tzinfo=None), rollback=True)
