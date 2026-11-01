"""Stand up, check and (later) clean up the continuous H-1 private preview in eu-north-1.

Reuses the bounded H-0 runner (``h0_bounded_test.py``) with H-1 names: cluster, service, ALB
and task family ``opentransit-h1``, log group ``/opentransit/h1`` (14 days), tags
``Project=OpenTransit, Purpose=H1``. The four ECR repositories from H-0 are reused, never
created or deleted here. Every created resource is written to the evidence file as it exists;
the account ID is stored as ``{{ACCOUNT_ID}}``. ``--dry-run`` prints commands only.

    P="uv run --project services/api --locked python deploy/aws/tools/h1_preview.py"
    $P estimate                    # weekly cost projection (recorded; refuses above the guard)
    $P setup                       # logs, IAM, VPC, ALB, cluster; adopts the ECR repositories
    $P adopt-images --tag h0-20261031
    $P register && $P service --desired 1 && $P wait-ready --label first
    $P probe --label first --queries <corpus>
    $P converge --label <label>    # wait for one COMPLETED deployment with one running task
    $P pause / $P resume           # desired count 0 / 1 (the ALB keeps costing while paused)
    $P --dry-run cleanup           # print the full teardown; without --dry-run it deletes
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import h0_bounded_test as h0  # noqa: E402

EVIDENCE = h0.REPO / "services/api/results/h1-preview-20261031-01.json"
NAME = "opentransit-h1"
WEEKLY_GUARD_USD = 30.0
# eu-north-1 list prices read from the AWS Price List API on 31 October 2026 (pre-tax USD).
PRICES = {
    "fargateVcpuHour": 0.0445,
    "fargateGbHour": 0.0049,
    "albHour": 0.02394,
    "albLcuHour": 0.0076,
    "publicIpv4Hour": 0.005,
    "ecrGbMonth": 0.10,
    "logsIngestGb": 0.54,
    "logsStorageGbMonth": 0.028,
}


def configure() -> None:
    h0.EVIDENCE = h0.DEFAULT_EVIDENCE = EVIDENCE
    h0.NAME = NAME
    h0.LOG_GROUP = "/opentransit/h1"
    h0.TAGS = {"Project": "OpenTransit", "Purpose": "H1"}
    h0.RETENTION_DAYS = 14
    h0.CREATE_REPOSITORIES = False
    h0.MAX_TASK_SECONDS = float("inf")  # continuous service; the two-task ceiling still holds
    h0.RENAMES = {"opentransit-h0": NAME, "/opentransit/h0": "/opentransit/h1", "H-0": "H-1"}


def ensure_evidence() -> None:
    if EVIDENCE.exists():
        return
    EVIDENCE.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "h1-preview",
                "label": (
                    "H-1 PRIVATE PREVIEW in eu-north-1, left running (task 31 October 2026). "
                    "Measured values are marked as such; costs are estimates from list prices."
                ),
                "task": "H-1",
                "region": h0.REGION,
                "accountId": "{{ACCOUNT_ID}}",
                "resources": [],
                "steps": [],
                "measurements": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def weekly_estimate() -> dict:
    p, week = PRICES, 168.0
    task_hour = p["fargateVcpuHour"] * 1 + p["fargateGbHour"] * 3
    rollouts = 7 + 4  # one daily rollout plus drills; each overlaps a second task ~15 minutes
    lines = {
        "fargateOneTask": task_hour * week,
        "alb": p["albHour"] * week,
        "albLcuUpperBound": p["albLcuHour"] * 1.0 * week,
        "publicIpv4TaskAndTwoAlbNodes": p["publicIpv4Hour"] * 3 * week,
        "secondTaskDuringRollouts": rollouts * 0.25 * (task_hour + p["publicIpv4Hour"]),
        # 1.18 GB kept from H-0 plus up to seven new 0.76 GB data images in a changing week.
        "ecrStorage": (1.18 + 7 * 0.76) * p["ecrGbMonth"] * week / 730,
        "logs": 0.1 * p["logsIngestGb"] + 0.1 * p["logsStorageGbMonth"],
    }
    total = sum(lines.values())
    return {
        "basis": "eu-north-1 on-demand list prices (AWS Price List API, 31 Oct 2026), pre-tax",
        "prices": p,
        "weeklyUsd": {k: round(v, 2) for k, v in lines.items()},
        "weeklyTotalUsd": round(total, 2),
        "guardUsd": WEEKLY_GUARD_USD,
        "withinGuard": total <= WEEKLY_GUARD_USD,
        "notIncluded": "data transfer out (small JSON responses, free tier), tax",
    }


def estimate(_args) -> int:
    ev = h0.load()
    ev["costEstimate"] = weekly_estimate()
    h0.step(ev, "cost-estimate", ev["costEstimate"]["withinGuard"], **ev["costEstimate"])
    return 0 if ev["costEstimate"]["withinGuard"] else 1


def adopt_images(args) -> int:
    """Record the already-pushed images (no push): describe-images by tag for each repository."""
    ev = h0.load()
    for repo in h0.REPOSITORIES:
        if not any(r["id"] == repo for r in h0.find(ev, "ecr-repository")):
            out = h0.aws("ecr", "describe-repositories", "--repository-names", repo)
            arn = (out.get("repositories") or [{}])[0].get("repositoryArn")
            h0.resource(ev, "ecr-repository", repo, arn, keep=True, preExisting="H-0")
        h0.record_image(ev, repo.removeprefix("opentransit-"), args.tag, source="pushed in H-0")
    return 0


def service_state() -> dict:
    ev = h0.load()
    cluster = h0.one(ev, "ecs-cluster")["arn"]
    svc = h0.aws("ecs", "describe-services", "--cluster", cluster, "--services", NAME)
    return (svc.get("services") or [{}])[0]


def converge(args) -> int:
    """Wait until the service has one COMPLETED deployment and exactly one running task."""
    started = time.monotonic()
    ev = h0.load()
    seen = None
    while time.monotonic() - started < args.timeout:
        svc = service_state()
        deployments = [
            (d["status"], d.get("rolloutState"), d["taskDefinition"].rsplit("/", 1)[-1])
            for d in svc.get("deployments", [])
        ]
        state = (svc.get("runningCount"), svc.get("pendingCount"), tuple(deployments))
        if state != seen:
            print(h0.now(), state)
            seen = state
        if any(d[1] == "FAILED" for d in deployments):
            break
        if (
            len(deployments) == 1
            and deployments[0][1] == "COMPLETED"
            and svc.get("runningCount") == svc.get("desiredCount") == 1
        ):
            break
        time.sleep(15)
    ok = seen is not None and len(seen[2]) == 1 and seen[2][0][1] == "COMPLETED"
    ev = h0.load()
    ev["measurements"].setdefault("convergence", []).append(
        {
            "label": args.label,
            "seconds": round(time.monotonic() - started, 1),
            "finalState": {"running": seen[0], "pending": seen[1], "deployments": seen[2]}
            if seen
            else None,
            "at": h0.now(),
        }
    )
    h0.save(ev)
    h0.step(ev, f"converge-{args.label}", ok, seconds=round(time.monotonic() - started, 1))
    return 0 if ok else 1


def set_desired(count: int) -> int:
    return h0.main(["service", "--desired", str(count)])


def cleanup(argv: list[str]) -> int:
    """Add every family revision the publisher registered to the ledger, then tear down."""
    ev = h0.load()
    if not h0.DRY_RUN:
        listed = h0.aws("ecs", "list-task-definitions", "--family-prefix", NAME).get(
            "taskDefinitionArns", []
        )
        known = {r["arn"] for r in h0.find(ev, "task-definition", live=False)}
        for arn in listed:
            if arn not in known:
                h0.resource(ev, "task-definition", arn.rsplit("/", 1)[-1], arn, via="publisher")
    return h0.main(argv)


def main(argv: list[str] | None = None) -> int:
    configure()
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv
    h0.DRY_RUN = dry
    rest = [a for a in argv if a != "--dry-run"]
    if not dry:
        ensure_evidence()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command")
    known, extra = parser.parse_known_args(rest)
    command = known.command
    if command == "estimate":
        return estimate(None)
    if command == "adopt-images":
        p = argparse.ArgumentParser()
        p.add_argument("--tag", required=True)
        return adopt_images(p.parse_args(extra))
    if command == "converge":
        p = argparse.ArgumentParser()
        p.add_argument("--label", required=True)
        p.add_argument("--timeout", type=float, default=2700)
        return converge(p.parse_args(extra))
    if command in ("pause", "resume"):
        return set_desired(0 if command == "pause" else 1)
    passthrough = (["--dry-run"] if dry else []) + rest
    if command == "cleanup":
        return cleanup(passthrough)
    if command == "push":
        raise SystemExit("H-1 images go through publish_generation.py push, not this tool")
    return h0.main(passthrough)


if __name__ == "__main__":
    sys.exit(main())
