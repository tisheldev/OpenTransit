"""Tests for the cloud build host additions (deploy/aws/tools/daily_refresh.py, build_host.py).

Synthetic fixtures only: no Docker, no network, no AWS.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "deploy" / "aws" / "tools"
pytestmark = pytest.mark.skipif(
    not TOOLS.is_dir(), reason="deploy/aws is not part of this checkout"
)


def _load(name: str):
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(f"aws_{name}", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


daily = _load("daily_refresh")
host = _load("build_host")


def test_serving_pair_prefers_manifest_then_release_source_check():
    manifest = {"inputs": {daily.GTFS: {"sha256": "g1"}, daily.TRIPS: {"sha256": "t1"}}}
    release = {
        "sourceCheck": {"sources": {"gtfs": {"sha256": "g2"}, "trip_id_to_date": {"sha256": "t2"}}}
    }
    assert daily.serving_pair(release, manifest) == {daily.GTFS: "g1", daily.TRIPS: "t1"}
    assert daily.serving_pair(release, None) == {daily.GTFS: "g2", daily.TRIPS: "t2"}
    assert daily.serving_pair({}, None) is None


def test_empty_profile_uses_the_environment_credentials(tmp_path):
    ns = daily.argparse.Namespace(profile="", archive_bucket="b", logs=tmp_path / "logs")
    job = daily.Job.__new__(daily.Job)
    job.args = ns
    assert job.aws("s3", "ls") == ["aws", "--region", daily.REGION, "s3", "ls"]
    assert job.s3("runs/x.json") == "s3://b/runs/x.json"
    ns.profile = "opentransit"
    assert job.aws("s3", "ls")[:3] == ["aws", "--profile", "opentransit"]


def test_upload_summary_writes_one_line(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        daily.subprocess,
        "run",
        lambda argv, **kw: calls.append(argv) or daily.subprocess.CompletedProcess(argv, 0, "", ""),
    )
    job = daily.Job.__new__(daily.Job)
    job.args = daily.argparse.Namespace(profile="", archive_bucket="b")
    job.stamp, job.work = "20261101T0330Z", tmp_path
    job.log_path, job.summary_path = tmp_path / "d.log", tmp_path / "d.json"
    job.summary = {
        "outcome": "failed",
        "mode": "unchanged",
        "failure": "push exited 1",
        "startedAt": "s",
        "finishedAt": "f",
        "steps": [{"step": "fetch", "ok": True}, {"step": "push", "ok": False}],
    }
    daily.upload_summary(job)
    line = (tmp_path / "run-summary.json").read_text(encoding="utf-8")
    assert line.count("\n") == 1
    assert json.loads(line)["failedStep"] == "push"
    assert [c[-1] for c in calls] == [
        "s3://b/runs/20261101T0330Z.json",
        "s3://b/runs/20261101T0330Z/summary.json",
        "s3://b/runs/20261101T0330Z/daily.log",
    ]


def test_build_host_estimate_within_guard_and_policy_is_scoped(monkeypatch):
    estimate = host.monthly_estimate()
    assert estimate["withinGuard"] and estimate["monthlyTotalUsd"] <= host.MONTHLY_GUARD_USD
    net = {"service": "arn:svc", "executionRole": "arn:role"}
    monkeypatch.setattr(host.h0, "DRY_RUN", True)
    monkeypatch.setattr(host.h0, "_ACCOUNT", None)
    policy = host.instance_policy(net, "bucket")
    star = [s for s in policy["Statement"] if s["Resource"] == "*"]
    assert {
        a for s in star for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])
    } == {
        "ecr:GetAuthorizationToken",
        "ecs:RegisterTaskDefinition",
        "ecs:DescribeTaskDefinition",
        "ec2:DescribeNetworkInterfaces",
    }
    passrole = next(s for s in policy["Statement"] if s["Action"] == "iam:PassRole")
    assert passrole["Resource"] == "arn:role"


def test_task_env_check_flags_a_lost_template_variable():
    template = json.loads(daily.TASK_TEMPLATE.read_text(encoding="utf-8"))
    assert daily.missing_template_env(template, template) == {}
    api = next(c for c in template["containerDefinitions"] if c["name"] == "api")
    lost = api["environment"][0]["name"]
    stripped = json.loads(json.dumps(template))
    for c in stripped["containerDefinitions"]:
        if c["name"] == "api":
            c["environment"] = [e for e in c["environment"] if e["name"] != lost]
            c["environment"].append({"name": "OPENTRANSIT_SOURCE_CHECK", "value": "x"})
    assert daily.missing_template_env(template, stripped) == {"api": [lost]}


def test_unchanged_renewal_rebuilds_the_api_image_only_when_its_source_changed(
    tmp_path, monkeypatch
):
    tag = daily.api_source_tag()
    assert tag.startswith("ot-h1-api:src-") and len(tag) == len("ot-h1-api:src-") + 12
    monkeypatch.setattr(daily, "api_source_tag", lambda: tag)
    calls = []
    monkeypatch.setattr(
        daily.subprocess,
        "run",
        lambda argv, **kw: calls.append(argv) or daily.subprocess.CompletedProcess(argv, 1, "", ""),
    )
    job = daily.Job.__new__(daily.Job)
    job.summary = {"steps": []}
    job.log_path, job.summary_path = tmp_path / "d.log", tmp_path / "d.json"
    assert daily.api_image(job, tag) == tag and calls == []
    built = []
    monkeypatch.setattr(job, "run", lambda name, argv, **kw: built.append(argv), raising=False)
    assert daily.api_image(job, "ot-h1-api:gen-old") == tag
    assert built[0][:4] == ["docker", "build", "--build-context", f"web={daily.REPO / 'apps/web'}"]
    assert job.summary["apiImage"] == {"tag": tag, "replaces": "ot-h1-api:gen-old", "built": True}
