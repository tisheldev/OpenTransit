"""Run the bounded H-0 Fargate test (user approval, 31 October 2026) and record its evidence.

Every AWS call goes through ``aws --profile opentransit --region eu-north-1``. Each created
resource is written to the evidence file the moment it exists, so ``cleanup`` can never miss
one; the 12-digit account ID is stored as ``{{ACCOUNT_ID}}`` (public repository) and restored
from ``sts get-caller-identity`` on read. ``--dry-run`` prints the AWS/Docker commands and
changes nothing (no AWS calls at all, not even reads).

Limits enforced here: at most two desired tasks; ``service`` refuses to start when the recorded
task running time would exceed the two-hour budget. Cost stays a recorded estimate.

    P="uv run --project services/api --locked python deploy/aws/tools/h0_bounded_test.py"
    $P setup                       # ECR, logs, IAM, VPC, ALB, cluster (no tasks)
    $P push --image api=ot-h0-api:local --image photon=ot-t5-photon:local --mirror-motis
    $P register                    # digest-pinned task definition from render_drafts
    $P service --desired 1         # create/update the service; 0 stops every task
    $P wait-ready                  # time to ALB target healthy and /readyz 200
    $P probe --queries <corpus>    # demo, ten journeys and latency through the ALB
    $P tasks                       # record task start/stop times and running time
    $P cleanup                     # delete everything except ECR repositories and images
    $P inventory --label after     # list what remains in the Region
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_drafts  # noqa: E402

AWS_DIR = Path(__file__).resolve().parents[1]
REPO = AWS_DIR.parents[1]
DEFAULT_EVIDENCE = REPO / "services/api/results/h0-fargate-20261031-01.json"
EVIDENCE = DEFAULT_EVIDENCE
PROFILE = "opentransit"
REGION = render_drafts.REGION
NAME = "opentransit-h0"
LOG_GROUP = render_drafts.LOG_GROUP
VPC_CIDR = render_drafts.VPC_CIDR
SUBNETS = {"a": ("10.80.0.0/24", f"{REGION}a"), "b": ("10.80.1.0/24", f"{REGION}b")}
REPOSITORIES = ("opentransit-api", "opentransit-data", "opentransit-photon", "opentransit-motis")
MOTIS_SOURCE = f"ghcr.io/motis-project/motis@{render_drafts.MOTIS_DIGEST}"
TAGS = {"Project": "OpenTransit", "Purpose": "H0"}
MAX_TASKS = 2
MAX_TASK_SECONDS = 2 * 3600

DRY_RUN = False


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# --- evidence ledger -------------------------------------------------------------------------

_ACCOUNT: str | None = None


def account() -> str:
    global _ACCOUNT
    if _ACCOUNT is None:
        _ACCOUNT = "111122223333" if DRY_RUN else aws("sts", "get-caller-identity")["Account"]
    return _ACCOUNT


def load() -> dict:
    if not EVIDENCE.exists():
        return {
            "schemaVersion": 1,
            "kind": "h0-fargate",
            "label": (
                "BOUNDED PRIVATE AWS TEST in eu-north-1 (user approval 31 October 2026). "
                "Measured values are marked as such; costs are estimates from list prices."
            ),
            "task": "H0-IMG",
            "region": REGION,
            "accountId": "{{ACCOUNT_ID}}",
            "resources": [],
            "steps": [],
            "measurements": {},
        }
    text = EVIDENCE.read_text(encoding="utf-8")
    return json.loads(text.replace("{{ACCOUNT_ID}}", account()) if not DRY_RUN else text)


def save(evidence: dict) -> None:
    if DRY_RUN and EVIDENCE == DEFAULT_EVIDENCE:
        return  # a dry run may write only a scratch ledger passed with --evidence
    text = json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    text = text.replace(account(), "{{ACCOUNT_ID}}")
    EVIDENCE.write_text(text, encoding="utf-8", newline="\n")


def step(evidence: dict, name: str, ok: bool, **detail) -> None:
    evidence["steps"].append({"step": name, "at": now(), "ok": ok, **detail})
    save(evidence)
    print(f"[{'ok' if ok else 'FAIL'}] {name} {json.dumps(detail, ensure_ascii=False)[:300]}")


def resource(evidence: dict, kind: str, ident: str, arn: str | None = None, **extra) -> None:
    evidence["resources"].append(
        {"type": kind, "id": ident, "arn": arn, "createdAt": now(), "deletedAt": None, **extra}
    )
    save(evidence)


def find(evidence: dict, kind: str, live: bool = True) -> list[dict]:
    return [
        r
        for r in evidence["resources"]
        if r["type"] == kind and (not live or r["deletedAt"] is None)
    ]


def one(evidence: dict, kind: str) -> dict:
    found = find(evidence, kind)
    if len(found) != 1:
        raise SystemExit(f"expected one live {kind} in the evidence, found {len(found)}")
    return found[0]


# --- command runners -------------------------------------------------------------------------


def _print(argv: list[str]) -> None:
    print("DRY-RUN:", " ".join(argv))


def aws(*args: str, region: str = REGION, check: bool = True) -> dict:
    argv = ["aws", "--profile", PROFILE, "--region", region, "--output", "json", *map(str, args)]
    if DRY_RUN:
        _print(argv)
        return {}
    done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        if check:
            raise RuntimeError(f"{' '.join(args[:2])} failed: {done.stderr.strip()[:800]}")
        return {"_error": done.stderr.strip()[:800]}
    return json.loads(done.stdout) if done.stdout.strip() else {}


def run(argv: list[str], *, stdin: str | None = None) -> str:
    if DRY_RUN:
        _print(argv)
        return ""
    env = {**os.environ, "DOCKER_CONFIG": str(_DOCKER_CONFIG)} if argv[0] == "docker" else None
    done = subprocess.run(
        argv, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env
    )
    if done.returncode != 0:
        raise RuntimeError(f"{argv[0]} {argv[1]} failed: {done.stderr.strip()[:800]}")
    return done.stdout


_TMP = Path(tempfile.mkdtemp(prefix="ot-h0-"))
# Windows Credential Manager rejects ECR tokens ("The stub received bad data"), so ECR logins
# go to a throwaway Docker config that push() deletes; the token never leaves this process tree.
_DOCKER_CONFIG = _TMP / "docker"


def file_arg(document: object, name: str) -> str:
    path = _TMP / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return "file://" + path.as_posix()


def tag_list(key: str = "Key", value: str = "Value") -> list[str]:
    return [f"{key}={k},{value}={v}" for k, v in TAGS.items()]


def ec2_tags(kind: str, name: str) -> str:
    tags = ",".join(f"{{Key={k},Value={v}}}" for k, v in {**TAGS, "Name": name}.items())
    return f"ResourceType={kind},Tags=[{tags}]"


def draft(path: str) -> dict:
    text = (AWS_DIR / path).read_text(encoding="utf-8").replace("{{ACCOUNT_ID}}", account())
    return json.loads(text)


# --- setup -----------------------------------------------------------------------------------


def setup(args: argparse.Namespace) -> int:
    ev = load()
    if find(ev, "vpc"):
        raise SystemExit("setup already recorded; run cleanup first or continue with push")
    step(ev, "setup-start", True, reviewerCidr=args.reviewer_cidr)

    for repo in REPOSITORIES:
        out = aws(
            "ecr",
            "create-repository",
            "--repository-name",
            repo,
            "--image-tag-mutability",
            "IMMUTABLE",
            "--tags",
            *tag_list(),
        )
        arn = out.get("repository", {}).get("repositoryArn")
        resource(ev, "ecr-repository", repo, arn, keep=True)

    aws(
        "logs",
        "create-log-group",
        "--log-group-name",
        LOG_GROUP,
        "--tags",
        ",".join(f"{k}={v}" for k, v in TAGS.items()),
    )
    aws("logs", "put-retention-policy", "--log-group-name", LOG_GROUP, "--retention-in-days", "7")
    resource(
        ev,
        "log-group",
        LOG_GROUP,
        f"arn:aws:logs:{REGION}:{account()}:log-group:{LOG_GROUP}",
        retentionDays=7,
    )

    role = f"{NAME}-execution"
    out = aws(
        "iam",
        "create-role",
        "--role-name",
        role,
        "--assume-role-policy-document",
        file_arg(draft("iam/execution-role-trust.json"), "t.json"),
        "--description",
        "OpenTransit H-0 task execution role: pull 4 repos, write 1 log group",
        "--tags",
        *tag_list(),
    )
    resource(ev, "iam-role", role, out.get("Role", {}).get("Arn"))
    aws(
        "iam",
        "put-role-policy",
        "--role-name",
        role,
        "--policy-name",
        f"{NAME}-execution",
        "--policy-document",
        file_arg(draft("iam/execution-role-policy.json"), "p.json"),
    )
    resource(ev, "iam-inline-policy", f"{role}/{NAME}-execution")

    vpc = (
        aws(
            "ec2",
            "create-vpc",
            "--cidr-block",
            VPC_CIDR,
            "--tag-specifications",
            ec2_tags("vpc", NAME),
        )
        .get("Vpc", {})
        .get("VpcId", "vpc-DRY")
    )
    resource(ev, "vpc", vpc, cidr=VPC_CIDR)
    aws("ec2", "modify-vpc-attribute", "--vpc-id", vpc, "--enable-dns-hostnames", '{"Value":true}')
    igw = (
        aws(
            "ec2",
            "create-internet-gateway",
            "--tag-specifications",
            ec2_tags("internet-gateway", NAME),
        )
        .get("InternetGateway", {})
        .get("InternetGatewayId", "igw-DRY")
    )
    resource(ev, "internet-gateway", igw, vpcId=vpc)
    aws("ec2", "attach-internet-gateway", "--internet-gateway-id", igw, "--vpc-id", vpc)
    rtb = (
        aws(
            "ec2",
            "create-route-table",
            "--vpc-id",
            vpc,
            "--tag-specifications",
            ec2_tags("route-table", NAME),
        )
        .get("RouteTable", {})
        .get("RouteTableId", "rtb-DRY")
    )
    resource(ev, "route-table", rtb, vpcId=vpc)
    aws(
        "ec2",
        "create-route",
        "--route-table-id",
        rtb,
        "--destination-cidr-block",
        "0.0.0.0/0",
        "--gateway-id",
        igw,
    )
    subnets = []
    for key, (cidr, zone) in SUBNETS.items():
        sid = (
            aws(
                "ec2",
                "create-subnet",
                "--vpc-id",
                vpc,
                "--cidr-block",
                cidr,
                "--availability-zone",
                zone,
                "--tag-specifications",
                ec2_tags("subnet", f"{NAME}-{key}"),
            )
            .get("Subnet", {})
            .get("SubnetId", f"subnet-DRY{key}")
        )
        resource(ev, "subnet", sid, cidr=cidr, zone=zone)
        assoc = aws("ec2", "associate-route-table", "--route-table-id", rtb, "--subnet-id", sid)
        resource(
            ev,
            "route-table-association",
            assoc.get("AssociationId", "rtbassoc-DRY"),
            routeTableId=rtb,
            subnetId=sid,
        )
        subnets.append(sid)

    groups = draft("network/security-groups.json")
    ids = {}
    for key in ("albSecurityGroup", "taskSecurityGroup"):
        spec = groups[key]
        gid = aws(
            "ec2",
            "create-security-group",
            "--group-name",
            spec["GroupName"],
            "--description",
            spec["Description"],
            "--vpc-id",
            vpc,
            "--tag-specifications",
            ec2_tags("security-group", spec["GroupName"]),
        ).get("GroupId", f"sg-DRY{key[:3]}")
        resource(ev, "security-group", gid, name=spec["GroupName"], vpcId=vpc)
        ids[key] = gid
        # Replace the default allow-all egress with the draft's explicit rules.
        aws(
            "ec2",
            "revoke-security-group-egress",
            "--group-id",
            gid,
            "--ip-permissions",
            '[{"IpProtocol":"-1","IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]',
        )
    for key, spec in groups.items():
        for direction in ("ingress", "egress"):
            for rule in spec[direction]:
                perm = {
                    "IpProtocol": rule["protocol"],
                    "FromPort": rule["fromPort"],
                    "ToPort": rule["toPort"],
                }
                if "cidr" in rule:
                    cidr = rule["cidr"].replace("{{REVIEWER_CIDR}}", args.reviewer_cidr)
                    perm["IpRanges"] = [{"CidrIp": cidr}]
                else:
                    perm["UserIdGroupPairs"] = [{"GroupId": ids[rule["securityGroup"]]}]
                aws(
                    "ec2",
                    f"authorize-security-group-{direction}",
                    "--group-id",
                    ids[key],
                    "--ip-permissions",
                    json.dumps([perm]),
                )

    tg_spec = draft("alb/target-group.json")
    tg = (
        aws(
            "elbv2",
            "create-target-group",
            "--name",
            tg_spec["Name"],
            "--protocol",
            "HTTP",
            "--protocol-version",
            "HTTP1",
            "--port",
            "8000",
            "--vpc-id",
            vpc,
            "--target-type",
            "ip",
            "--health-check-protocol",
            "HTTP",
            "--health-check-path",
            tg_spec["HealthCheckPath"],
            "--health-check-interval-seconds",
            str(tg_spec["HealthCheckIntervalSeconds"]),
            "--health-check-timeout-seconds",
            str(tg_spec["HealthCheckTimeoutSeconds"]),
            "--healthy-threshold-count",
            str(tg_spec["HealthyThresholdCount"]),
            "--unhealthy-threshold-count",
            str(tg_spec["UnhealthyThresholdCount"]),
            "--matcher",
            "HttpCode=200",
            "--tags",
            *tag_list(),
        )
        .get("TargetGroups", [{}])[0]
        .get("TargetGroupArn", "arn:tg-DRY")
    )
    resource(ev, "target-group", tg_spec["Name"], tg)
    aws(
        "elbv2",
        "modify-target-group-attributes",
        "--target-group-arn",
        tg,
        "--attributes",
        *[f"Key={a['Key']},Value={a['Value']}" for a in tg_spec["Attributes"]],
    )

    lb_spec = draft("alb/load-balancer.json")
    lb = aws(
        "elbv2",
        "create-load-balancer",
        "--name",
        NAME,
        "--type",
        "application",
        "--scheme",
        "internet-facing",
        "--ip-address-type",
        "ipv4",
        "--subnets",
        *subnets,
        "--security-groups",
        ids["albSecurityGroup"],
        "--tags",
        *tag_list(),
    ).get("LoadBalancers", [{}])[0]
    lb_arn = lb.get("LoadBalancerArn", "arn:lb-DRY")
    resource(ev, "load-balancer", NAME, lb_arn, dnsName=lb.get("DNSName"))
    aws(
        "elbv2",
        "modify-load-balancer-attributes",
        "--load-balancer-arn",
        lb_arn,
        "--attributes",
        *[f"Key={a['Key']},Value={a['Value']}" for a in lb_spec["loadBalancer"]["Attributes"]],
    )
    listener = lb_spec["listeners"][0]
    out = aws(
        "elbv2",
        "create-listener",
        "--load-balancer-arn",
        lb_arn,
        "--protocol",
        listener["Protocol"],
        "--port",
        str(listener["Port"]),
        "--default-actions",
        f"Type=forward,TargetGroupArn={tg}",
        "--tags",
        *tag_list(),
    )
    resource(
        ev,
        "listener",
        f"{listener['Protocol']}:{listener['Port']}",
        out.get("Listeners", [{}])[0].get("ListenerArn"),
    )

    out = aws(
        "ecs",
        "create-cluster",
        "--cluster-name",
        NAME,
        "--settings",
        "name=containerInsights,value=disabled",
        "--tags",
        *tag_list("key", "value"),
    )
    resource(ev, "ecs-cluster", NAME, out.get("cluster", {}).get("clusterArn"))
    step(ev, "setup-complete", True, albDns=lb.get("DNSName"))
    return 0


# --- images ----------------------------------------------------------------------------------


def registry() -> str:
    return f"{account()}.dkr.ecr.{REGION}.amazonaws.com"


def ecr_login() -> None:
    """Write the ECR auth into the throwaway config (``docker login`` insists on wincred)."""
    _DOCKER_CONFIG.mkdir(exist_ok=True)
    if DRY_RUN:
        _print(["aws", "ecr", "get-login-password", "->", str(_DOCKER_CONFIG / "config.json")])
        return
    password = run(["aws", "--profile", PROFILE, "--region", REGION, "ecr", "get-login-password"])
    auth = base64.b64encode(f"AWS:{password.strip()}".encode()).decode()
    config = {"auths": {registry(): {"auth": auth}}}
    (_DOCKER_CONFIG / "config.json").write_text(json.dumps(config), encoding="utf-8")


def push(args: argparse.Namespace) -> int:
    ev = load()
    ecr_login()
    try:
        push_images(ev, args)
    finally:
        shutil.rmtree(_DOCKER_CONFIG, ignore_errors=True)
    return 0


def push_images(ev: dict, args: argparse.Namespace) -> None:
    for item in args.image:
        name, local = item.split("=", 1)
        image_id = run(["docker", "image", "inspect", "--format", "{{.Id}}", local]).strip()
        target = f"{registry()}/opentransit-{name}:{args.tag}"
        started = time.monotonic()
        run(["docker", "tag", local, target])
        run(["docker", "push", target])
        seconds = round(time.monotonic() - started, 1)
        record_image(
            ev, name, args.tag, localImage=local, localImageId=image_id, pushSeconds=seconds
        )
    if args.mirror_motis:
        target = f"{registry()}/opentransit-motis:{args.tag}"
        started = time.monotonic()
        run(["docker", "buildx", "imagetools", "create", "--tag", target, MOTIS_SOURCE])
        record_image(
            ev,
            "motis",
            args.tag,
            source=MOTIS_SOURCE,
            pushSeconds=round(time.monotonic() - started, 1),
        )


def record_image(ev: dict, name: str, tag: str, **extra) -> None:
    out = aws(
        "ecr",
        "describe-images",
        "--repository-name",
        f"opentransit-{name}",
        "--image-ids",
        f"imageTag={tag}",
    )
    detail = (out.get("imageDetails") or [{}])[0]
    image = {
        "repository": f"opentransit-{name}",
        "tag": tag,
        "digest": detail.get("imageDigest"),
        "compressedBytes": detail.get("imageSizeInBytes"),
        "pushedAt": now(),
        **extra,
    }
    ev.setdefault("images", []).append(image)
    step(
        ev,
        f"push-{name}",
        bool(image["digest"]),
        digest=image["digest"],
        compressedBytes=image["compressedBytes"],
    )


def digest(ev: dict, name: str, tag: str | None) -> str:
    images = [i for i in ev.get("images", []) if i["repository"] == f"opentransit-{name}"]
    if tag:
        images = [i for i in images if i["tag"] == tag]
    if not images or not images[-1]["digest"]:
        raise SystemExit(f"no pushed {name} image{' tagged ' + tag if tag else ''} in the evidence")
    return images[-1]["digest"]


# --- task definition and service -------------------------------------------------------------


def register(args: argparse.Namespace) -> int:
    ev = load()
    task = render_drafts.render_task_definition(args.variant)
    text = json.dumps(task)
    motis = digest(ev, "motis", args.motis_tag) if not DRY_RUN else render_drafts.MOTIS_DIGEST
    if motis != render_drafts.MOTIS_DIGEST:
        raise SystemExit(f"mirrored MOTIS digest {motis} differs from the pinned digest")
    values = {
        "ECR_REGISTRY": registry(),
        "API_DIGEST": "sha256:DRY" if DRY_RUN else digest(ev, "api", args.api_tag),
        "DATA_DIGEST": "sha256:DRY" if DRY_RUN else digest(ev, "data", args.data_tag),
        "PHOTON_DIGEST": "sha256:DRY" if DRY_RUN else digest(ev, "photon", args.photon_tag),
        "EXECUTION_ROLE_ARN": f"arn:aws:iam::{account()}:role/{NAME}-execution",
    }
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    task = json.loads(text)
    task["tags"] = [{"key": k, "value": v} for k, v in TAGS.items()]
    if "{{" in json.dumps(task):
        raise SystemExit("unreplaced placeholder in the task definition")
    out = aws("ecs", "register-task-definition", "--cli-input-json", file_arg(task, "td.json"))
    arn = out.get("taskDefinition", {}).get("taskDefinitionArn", "arn:td-DRY")
    resource(
        ev,
        "task-definition",
        arn.rsplit("/", 1)[-1],
        arn,
        images={c["name"]: c["image"] for c in task["containerDefinitions"]},
    )
    step(ev, "register-task-definition", True, arn=arn)
    return 0


def task_seconds(ev: dict) -> float:
    total = 0.0
    for task in ev["measurements"].get("tasks", {}).values():
        start = task.get("startedAt") or task.get("createdAt")
        if not start:
            continue
        end = task.get("stoppedAt") or now()
        total += (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    return total


def service(args: argparse.Namespace) -> int:
    if not 0 <= args.desired <= MAX_TASKS:
        raise SystemExit(f"desired count must be 0..{MAX_TASKS} (approved limit)")
    ev = load()
    if args.desired and not DRY_RUN:
        refresh_tasks(ev)
        used = task_seconds(ev)
        if used >= MAX_TASK_SECONDS - 15 * 60:
            raise SystemExit(f"{used:.0f} s of task time used; the two-hour budget is exhausted")
    cluster = one(ev, "ecs-cluster")["arn"] if not DRY_RUN else "arn:cluster-DRY"
    existing = find(ev, "ecs-service")
    if existing:
        aws(
            "ecs",
            "update-service",
            "--cluster",
            cluster,
            "--service",
            NAME,
            "--desired-count",
            str(args.desired),
        )
        step(ev, "service-desired-count", True, desired=args.desired)
        return 0
    spec = json.loads((AWS_DIR / "ecs/service.json").read_text(encoding="utf-8"))
    td = find(ev, "task-definition")[-1]["arn"] if not DRY_RUN else "arn:td-DRY"
    subnets = [r["id"] for r in find(ev, "subnet")] or ["subnet-DRYa", "subnet-DRYb"]
    groups = {r["name"]: r["id"] for r in find(ev, "security-group")}
    spec.update(
        cluster=cluster,
        taskDefinition=td,
        desiredCount=args.desired,
        tags=[{"key": k, "value": v} for k, v in TAGS.items()],
    )
    spec["networkConfiguration"]["awsvpcConfiguration"].update(
        subnets=subnets, securityGroups=[groups.get(f"{NAME}-task", "sg-DRYtask")]
    )
    tg = find(ev, "target-group")
    spec["loadBalancers"][0]["targetGroupArn"] = tg[0]["arn"] if tg else "arn:tg-DRY"
    out = aws("ecs", "create-service", "--cli-input-json", file_arg(spec, "svc.json"))
    resource(ev, "ecs-service", NAME, out.get("service", {}).get("serviceArn"))
    step(ev, "service-create", True, desired=args.desired, taskDefinition=td)
    return 0


def refresh_tasks(ev: dict) -> dict:
    cluster = one(ev, "ecs-cluster")["arn"]
    arns: list[str] = []
    for status in ("RUNNING", "STOPPED"):
        arns += aws("ecs", "list-tasks", "--cluster", cluster, "--desired-status", status).get(
            "taskArns", []
        )
    tasks = ev["measurements"].setdefault("tasks", {})
    if arns:
        described = aws("ecs", "describe-tasks", "--cluster", cluster, "--tasks", *arns)
        for task in described.get("tasks", []):
            tasks[task["taskArn"].rsplit("/", 1)[-1]] = {
                key: task.get(key)
                for key in (
                    "createdAt",
                    "pullStartedAt",
                    "pullStoppedAt",
                    "startedAt",
                    "stoppingAt",
                    "stoppedAt",
                    "lastStatus",
                    "healthStatus",
                    "stopCode",
                    "stoppedReason",
                    "taskDefinitionArn",
                )
            } | {
                "containers": {
                    c["name"]: {
                        k: c.get(k) for k in ("lastStatus", "exitCode", "reason", "healthStatus")
                    }
                    for c in task.get("containers", [])
                }
            }
    ev["measurements"]["taskRunningSecondsSoFar"] = round(task_seconds(ev), 1)
    save(ev)
    return tasks


def tasks_cmd(args: argparse.Namespace) -> int:
    ev = load()
    tasks = refresh_tasks(ev)
    for tid, task in tasks.items():
        print(
            tid[:12],
            task["lastStatus"],
            task.get("healthStatus"),
            task.get("startedAt"),
            {
                n: (c["lastStatus"], c["exitCode"], c["healthStatus"])
                for n, c in task["containers"].items()
            },
        )
    print("task running seconds so far:", ev["measurements"]["taskRunningSecondsSoFar"])
    return 0


# --- measurements through the ALB -------------------------------------------------------------


def alb_url(ev: dict) -> str:
    return "http://" + one(ev, "load-balancer")["dnsName"]


def http(method: str, url: str, body: dict | None = None, timeout: float = 30) -> tuple:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url, data=data, method=method, headers={"content-type": "application/json"}
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        payload, status = exc.read(), exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, (time.perf_counter() - started) * 1000, type(exc).__name__
    return status, (time.perf_counter() - started) * 1000, payload


def wait_ready(args: argparse.Namespace) -> int:
    ev = load()
    url = alb_url(ev) + "/readyz"
    tg = one(ev, "target-group")["arn"]
    started, wait_started = time.monotonic(), now()
    first_healthy = None
    seen: dict[str, str] = {}
    while time.monotonic() - started < args.timeout:
        health = aws("elbv2", "describe-target-health", "--target-group-arn", tg)
        states = {
            t["Target"]["Id"]: t["TargetHealth"]["State"]
            for t in health.get("TargetHealthDescriptions", [])
        }
        if states != seen:
            print(now(), states)
            seen = states
        healthy = [ip for ip, state in states.items() if state == "healthy"]
        if len(healthy) >= args.targets:
            status, ms, payload = http("GET", url)
            if status == 200:
                first_healthy = now()
                break
        time.sleep(10)
    tasks = refresh_tasks(ev)
    ok = first_healthy is not None
    ev["measurements"].setdefault("readiness", []).append(
        {
            "label": args.label,
            "waitStartedAt": wait_started,
            "readyz200At": first_healthy,
            "targets": seen,
            "taskTimes": tasks,
        }
    )
    step(ev, f"wait-ready-{args.label}", ok, readyz200At=first_healthy, targets=seen)
    return 0 if ok else 1


def probe(args: argparse.Namespace) -> int:
    ev = load()
    base = alb_url(ev)
    result: dict = {"label": args.label, "startedAt": now(), "from": "developer machine (Israel)"}

    status, ms, payload = http("GET", base + "/readyz")
    result["readyz"] = {
        "status": status,
        "ms": round(ms, 1),
        "body": json.loads(payload) if status else payload,
    }
    status, ms, payload = http("GET", base + "/v1/status")
    result["status"] = {
        "status": status,
        "ms": round(ms, 1),
        "body": json.loads(payload) if status == 200 else None,
    }

    demo = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(REPO / "services/api"),
            "--locked",
            "opentransit",
            "demo",
            "--api-url",
            base,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    result["demo"] = {
        "exit": demo.returncode,
        "stdoutTail": demo.stdout[-1500:],
        "stderrTail": demo.stderr[-500:],
    }

    corpus = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    journeys = []
    for case in corpus["cases"]:
        params = case["params"]
        (flat, flon), (tlat, tlon) = (
            map(float, params[k].split(",")) for k in ("fromPlace", "toPlace")
        )
        body = {
            "from": {"kind": "coordinate", "latitude": flat, "longitude": flon},
            "to": {"kind": "coordinate", "latitude": tlat, "longitude": tlon},
            "departAt": case.get("probeTime") or params["time"],
            "results": 1,
        }
        status, ms, payload = http("POST", base + "/v1/journeys", body, timeout=60)
        count, outcome = None, None
        if status == 200:
            answer = json.loads(payload)
            count = len(answer.get("journeys", []))
            outcome = answer.get("outcome")
        expected = case.get("expect", {}).get("outcome")
        # Structural check, as in the probe: "either" accepts both outcomes.
        passed = status == 200 and (
            expected == "either" or ((count or 0) > 0) == (expected == "route")
        )
        journeys.append(
            {
                "id": case["id"],
                "status": status,
                "ms": round(ms, 1),
                "journeys": count,
                "outcome": outcome,
                "expected": expected,
                "pass": passed,
            }
        )
    result["journeys"] = journeys

    samples = []
    for _ in range(args.latency_samples):
        status, ms, _payload = http("GET", base + "/healthz", timeout=10)
        if status == 200:
            samples.append(ms)
    if samples:
        samples.sort()
        result["healthzLatencyMs"] = {
            "n": len(samples),
            "min": round(samples[0], 1),
            "median": round(statistics.median(samples), 1),
            "p95": round(samples[int(0.95 * (len(samples) - 1))], 1),
            "max": round(samples[-1], 1),
            "note": "HTTP round trip from this machine through the ALB (new connection each)",
        }
    journey_ms = sorted(j["ms"] for j in journeys if j["status"] == 200)
    if journey_ms:
        result["journeyLatencyMs"] = {
            "n": len(journey_ms),
            "median": round(statistics.median(journey_ms), 1),
            "max": journey_ms[-1],
        }
    result["finishedAt"] = now()
    ev["measurements"].setdefault("probes", []).append(result)
    ok = demo.returncode == 0 and all(j["pass"] for j in journeys)
    step(
        ev,
        f"probe-{args.label}",
        ok,
        demoExit=demo.returncode,
        journeysPassed=sum(j["pass"] for j in journeys),
        journeysTotal=len(journeys),
        healthzMedianMs=result.get("healthzLatencyMs", {}).get("median"),
    )
    return 0 if ok else 1


def metrics(args: argparse.Namespace) -> int:
    ev = load()
    end = datetime.now(UTC)
    start = datetime.fromisoformat(args.since)
    out = {}
    for metric in ("CPUUtilization", "MemoryUtilization"):
        data = aws(
            "cloudwatch",
            "get-metric-statistics",
            "--namespace",
            "AWS/ECS",
            "--metric-name",
            metric,
            "--dimensions",
            f"Name=ClusterName,Value={NAME}",
            f"Name=ServiceName,Value={NAME}",
            "--start-time",
            start.isoformat(),
            "--end-time",
            end.isoformat(),
            "--period",
            "60",
            "--statistics",
            "Average",
            "Maximum",
        )
        points = sorted(data.get("Datapoints", []), key=lambda p: p["Timestamp"])
        out[metric] = [
            {"t": p["Timestamp"], "avg": round(p["Average"], 2), "max": round(p["Maximum"], 2)}
            for p in points
        ]
    ev["measurements"]["serviceMetrics"] = {
        "source": "CloudWatch AWS/ECS service metrics (percent of task CPU/memory reservation, "
        "averaged over running tasks; no per-container breakdown without Container Insights)",
        **out,
    }
    step(ev, "metrics", True, points={k: len(v) for k, v in out.items()})
    return 0


def export_logs(args: argparse.Namespace) -> int:
    ev = load()
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    streams = aws("logs", "describe-log-streams", "--log-group-name", LOG_GROUP).get(
        "logStreams", []
    )
    count = 0
    for stream in streams:
        name = stream["logStreamName"]
        events, token = [], None
        while True:
            extra = ["--next-token", token] if token else []
            page = aws(
                "logs",
                "get-log-events",
                "--log-group-name",
                LOG_GROUP,
                "--log-stream-name",
                name,
                "--start-from-head",
                *extra,
            )
            events += page.get("events", [])
            if page.get("nextForwardToken") in (None, token):
                break
            token = page["nextForwardToken"]
        path = folder / (name.replace("/", "_") + ".log")
        path.write_text(
            "".join(f"{e['timestamp']} {e['message']}\n" for e in events),
            encoding="utf-8",
            newline="\n",
        )
        count += len(events)
    sentinels = {}
    for needle in args.sentinel or []:
        sentinels[needle] = sum(
            p.read_text(encoding="utf-8").count(needle) for p in folder.glob("*.log")
        )
    ev["measurements"]["logExport"] = {
        "folder": folder.relative_to(REPO).as_posix(),
        "streams": len(streams),
        "events": count,
        "sentinelHits": sentinels,
    }
    step(ev, "export-logs", True, streams=len(streams), events=count, sentinels=sentinels)
    return 0


# --- cleanup and inventory ------------------------------------------------------------------


def mark_deleted(ev: dict, r: dict) -> None:
    r["deletedAt"] = now()
    save(ev)


def cleanup(args: argparse.Namespace) -> int:
    ev = load()
    step(ev, "cleanup-start", True)
    cluster = find(ev, "ecs-cluster")
    for svc in find(ev, "ecs-service"):
        aws(
            "ecs",
            "update-service",
            "--cluster",
            cluster[0]["arn"],
            "--service",
            NAME,
            "--desired-count",
            "0",
            check=False,
        )
        aws(
            "ecs",
            "delete-service",
            "--cluster",
            cluster[0]["arn"],
            "--service",
            NAME,
            "--force",
            check=False,
        )
        aws(
            "ecs",
            "wait",
            "services-inactive",
            "--cluster",
            cluster[0]["arn"],
            "--services",
            NAME,
            check=False,
        )
        mark_deleted(ev, svc)
    if cluster and not DRY_RUN:
        refresh_tasks(ev)
    for r in find(ev, "listener"):
        aws("elbv2", "delete-listener", "--listener-arn", r["arn"], check=False)
        mark_deleted(ev, r)
    for r in find(ev, "load-balancer"):
        aws("elbv2", "delete-load-balancer", "--load-balancer-arn", r["arn"], check=False)
        aws(
            "elbv2", "wait", "load-balancers-deleted", "--load-balancer-arns", r["arn"], check=False
        )
        mark_deleted(ev, r)
    for r in find(ev, "target-group"):
        aws("elbv2", "delete-target-group", "--target-group-arn", r["arn"], check=False)
        mark_deleted(ev, r)
    for r in find(ev, "task-definition"):
        aws("ecs", "deregister-task-definition", "--task-definition", r["arn"], check=False)
        aws("ecs", "delete-task-definitions", "--task-definitions", r["arn"], check=False)
        mark_deleted(ev, r)
    for r in cluster:
        aws("ecs", "delete-cluster", "--cluster", r["arn"], check=False)
        mark_deleted(ev, r)
    # ALB and task ENIs are released asynchronously; security groups fail until they are gone.
    vpcs = find(ev, "vpc")
    for _ in range(30 if vpcs and not DRY_RUN else 1):
        enis = aws(
            "ec2",
            "describe-network-interfaces",
            "--filters",
            f"Name=vpc-id,Values={vpcs[0]['id'] if vpcs else 'vpc-DRY'}",
        ).get("NetworkInterfaces", [])
        if not enis:
            break
        print("waiting for", len(enis), "network interfaces to be released")
        time.sleep(20)
    groups = find(ev, "security-group")
    for r in groups:  # drop the cross-references first
        sg = aws("ec2", "describe-security-groups", "--group-ids", r["id"], check=False)
        for group in sg.get("SecurityGroups", []):
            if group.get("IpPermissions"):
                aws(
                    "ec2",
                    "revoke-security-group-ingress",
                    "--group-id",
                    r["id"],
                    "--ip-permissions",
                    json.dumps(group["IpPermissions"]),
                    check=False,
                )
            if group.get("IpPermissionsEgress"):
                aws(
                    "ec2",
                    "revoke-security-group-egress",
                    "--group-id",
                    r["id"],
                    "--ip-permissions",
                    json.dumps(group["IpPermissionsEgress"]),
                    check=False,
                )
    for r in groups:
        out = aws("ec2", "delete-security-group", "--group-id", r["id"], check=False)
        if "_error" not in out:
            mark_deleted(ev, r)
    for r in find(ev, "route-table-association"):
        aws("ec2", "disassociate-route-table", "--association-id", r["id"], check=False)
        mark_deleted(ev, r)
    for r in find(ev, "subnet"):
        if "_error" not in aws("ec2", "delete-subnet", "--subnet-id", r["id"], check=False):
            mark_deleted(ev, r)
    for r in find(ev, "route-table"):
        if "_error" not in aws(
            "ec2", "delete-route-table", "--route-table-id", r["id"], check=False
        ):
            mark_deleted(ev, r)
    for r in find(ev, "internet-gateway"):
        aws(
            "ec2",
            "detach-internet-gateway",
            "--internet-gateway-id",
            r["id"],
            "--vpc-id",
            r["vpcId"],
            check=False,
        )
        if "_error" not in aws(
            "ec2", "delete-internet-gateway", "--internet-gateway-id", r["id"], check=False
        ):
            mark_deleted(ev, r)
    for r in vpcs:
        if "_error" not in aws("ec2", "delete-vpc", "--vpc-id", r["id"], check=False):
            mark_deleted(ev, r)
    for r in find(ev, "log-group"):
        if not args.keep_logs:
            aws("logs", "delete-log-group", "--log-group-name", r["id"], check=False)
            mark_deleted(ev, r)
    for r in find(ev, "iam-inline-policy"):
        role, policy = r["id"].split("/", 1)
        aws("iam", "delete-role-policy", "--role-name", role, "--policy-name", policy, check=False)
        mark_deleted(ev, r)
    for r in find(ev, "iam-role"):
        if "_error" not in aws("iam", "delete-role", "--role-name", r["id"], check=False):
            mark_deleted(ev, r)
    left = [
        f"{r['type']}:{r['id']}"
        for r in ev["resources"]
        if r["deletedAt"] is None and not r.get("keep")
    ]
    step(
        ev,
        "cleanup-complete",
        not left,
        remaining=left,
        kept=[r["id"] for r in find(ev, "ecr-repository")],
    )
    return 0 if not left else 1


def inventory(args: argparse.Namespace) -> int:
    ev = load()
    q = {
        "ecsClusters": aws("ecs", "list-clusters").get("clusterArns"),
        "taskDefinitionsActive": aws("ecs", "list-task-definitions", "--status", "ACTIVE").get(
            "taskDefinitionArns"
        ),
        "loadBalancers": [
            lb["LoadBalancerArn"]
            for lb in aws("elbv2", "describe-load-balancers").get("LoadBalancers", [])
        ],
        "targetGroups": [
            t["TargetGroupArn"]
            for t in aws("elbv2", "describe-target-groups").get("TargetGroups", [])
        ],
        "vpcs": [
            (v["VpcId"], v["CidrBlock"], v["IsDefault"])
            for v in aws("ec2", "describe-vpcs").get("Vpcs", [])
        ],
        "nonDefaultSecurityGroups": [
            (g["GroupId"], g["GroupName"])
            for g in aws("ec2", "describe-security-groups").get("SecurityGroups", [])
            if g["GroupName"] != "default"
        ],
        "networkInterfaces": [
            (n["NetworkInterfaceId"], n.get("Description"))
            for n in aws("ec2", "describe-network-interfaces").get("NetworkInterfaces", [])
        ],
        "elasticIps": [
            a.get("PublicIp") for a in aws("ec2", "describe-addresses").get("Addresses", [])
        ],
        "natGateways": [
            n["NatGatewayId"]
            for n in aws("ec2", "describe-nat-gateways").get("NatGateways", [])
            if n["State"] not in ("deleted",)
        ],
        "logGroups": [
            g["logGroupName"] for g in aws("logs", "describe-log-groups").get("logGroups", [])
        ],
        "logGroupsUsEast1": [
            g["logGroupName"]
            for g in aws("logs", "describe-log-groups", region="us-east-1", check=False).get(
                "logGroups", []
            )
        ],
        "iamRolesOpenTransit": [
            r["RoleName"]
            for r in aws("iam", "list-roles").get("Roles", [])
            if r["RoleName"].startswith("opentransit")
        ],
        "ecrRepositories": {},
        "taggedResources": [
            r["ResourceARN"]
            for r in aws(
                "resourcegroupstaggingapi",
                "get-resources",
                "--tag-filters",
                "Key=Project,Values=OpenTransit",
            ).get("ResourceTagMappingList", [])
        ],
    }
    for repo in aws("ecr", "describe-repositories").get("repositories", []):
        images = aws("ecr", "describe-images", "--repository-name", repo["repositoryName"]).get(
            "imageDetails", []
        )
        q["ecrRepositories"][repo["repositoryName"]] = [
            {"tags": i.get("imageTags"), "digest": i["imageDigest"], "bytes": i["imageSizeInBytes"]}
            for i in images
        ]
    ev.setdefault("inventory", {})[args.label] = {"at": now(), **q}
    save(ev)
    print(json.dumps(q, indent=1, default=str)[:4000])
    return 0


def main(argv: list[str] | None = None) -> int:
    global DRY_RUN, EVIDENCE
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="print commands, change nothing")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("setup")
    p.add_argument("--reviewer-cidr", default="93.173.37.36/32")
    p = sub.add_parser("push")
    p.add_argument("--image", action="append", default=[], help="name=local-ref (api/data/photon)")
    p.add_argument("--mirror-motis", action="store_true")
    p.add_argument("--tag", default="h0-20261031")
    p = sub.add_parser("register")
    p.add_argument("--variant", default="recommended", choices=sorted(render_drafts.VARIANTS))
    for name in ("api", "data", "photon", "motis"):
        p.add_argument(f"--{name}-tag")
    p = sub.add_parser("service")
    p.add_argument("--desired", type=int, required=True)
    p = sub.add_parser("wait-ready")
    p.add_argument("--label", required=True)
    p.add_argument("--targets", type=int, default=1)
    p.add_argument("--timeout", type=float, default=1800)
    p = sub.add_parser("probe")
    p.add_argument("--label", required=True)
    p.add_argument("--queries", required=True)
    p.add_argument("--latency-samples", type=int, default=50)
    p = sub.add_parser("metrics")
    p.add_argument("--since", required=True, help="ISO instant with offset")
    p = sub.add_parser("export-logs")
    p.add_argument("--output", required=True)
    p.add_argument("--sentinel", action="append")
    sub.add_parser("tasks")
    p = sub.add_parser("cleanup")
    p.add_argument("--keep-logs", action="store_true")
    p = sub.add_parser("inventory")
    p.add_argument("--label", required=True)
    args = parser.parse_args(argv)
    DRY_RUN, EVIDENCE = args.dry_run, args.evidence
    if shutil.which("aws") is None:
        raise SystemExit("aws CLI not found")
    handlers = {
        "setup": setup,
        "push": push,
        "register": register,
        "service": service,
        "wait-ready": wait_ready,
        "probe": probe,
        "metrics": metrics,
        "export-logs": export_logs,
        "tasks": tasks_cmd,
        "cleanup": cleanup,
        "inventory": inventory,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
