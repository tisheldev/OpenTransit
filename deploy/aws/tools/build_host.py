"""Create, run, watch and (later) tear down the H-1 cloud build host in eu-north-1.

One EC2 instance in the H-1 VPC, started daily at 03:30 UTC by EventBridge Scheduler; on boot it
runs ``deploy/aws/build-host/run-refresh.sh`` (the daily refresh) and powers itself off. Tags
``Project=OpenTransit, Purpose=H1-build``. Every resource is written to the evidence file as it
is created, with the account ID stored as ``{{ACCOUNT_ID}}``. ``--dry-run`` prints commands only.

    B="uv run --project services/api --locked python deploy/aws/tools/build_host.py"
    $B estimate                    # monthly projection (recorded; refuses above the $8 guard)
    $B setup --ref <commit>        # bucket, logs, alarm, topic, IAM, SG, instance, schedule
    $B seed                        # serving release record from D:/ot/releases into the bucket
    $B mode refresh|maintenance    # instance tag read at boot (maintenance: no run, no power-off)
    $B set-ref <commit>            # pinned repository commit, read at the next boot
    $B trigger                     # one-off schedule with the daily target, two minutes out
    $B watch [--stamp <stamp>]     # follow the run in CloudWatch Logs until the instance stops
    $B pause | resume              # disable / enable the daily schedule
    $B --dry-run teardown          # print the teardown; without --dry-run it deletes (not S3)
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import h0_bounded_test as h0  # noqa: E402

EVIDENCE = h0.REPO / "services/api/results/h1-build-host-20261101-01.json"
H1_EVIDENCE = h0.REPO / "services/api/results/h1-preview-20261031-01.json"
NAME = "opentransit-build-host"
LOG_GROUP = "/opentransit/build-host"
LOG_RETENTION_DAYS = 90
REF_PARAMETER = "/opentransit/build-host/repo-ref"
REPO_URL = "https://github.com/tisheldev/OpenTransit.git"
SCHEDULE = "opentransit-build-host-daily"
CRON = "cron(30 3 * * ? *)"
TOPIC = "opentransit-build-host-alerts"
ALARM = "opentransit-build-host-no-success-26h"
METRIC_NAMESPACE, METRIC = "OpenTransit/BuildHost", "RefreshSucceeded"
INSTANCE_TYPE = (
    "t3.large"  # 2 vCPU, 8 GiB; burstable, credits kept 7 days while stopped
)
ROOT_GIB = 30
AMI_PARAMETER = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
MONTHLY_GUARD_USD = 8.0
# eu-north-1 list prices from the AWS Price List API on 1 November 2026 (pre-tax USD).
PRICES = {
    "t3.largeHour": 0.0864,
    "t3UnlimitedVcpuHour": 0.05,
    "gp3GbMonth": 0.0836,
    "snapshotFree": 0.0,
    "publicIpv4Hour": 0.005,
    "logsIngestGb": 0.54,
    "logsStorageGbMonth": 0.028,
    "s3GbMonth": 0.023,
    "alarmMonth": 0.10,
}


def configure() -> None:
    h0.EVIDENCE = h0.DEFAULT_EVIDENCE = EVIDENCE
    h0.TAGS = {"Project": "OpenTransit", "Purpose": "H1-build"}
    if not EVIDENCE.exists() and not h0.DRY_RUN:
        EVIDENCE.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "kind": "h1-build-host",
                    "label": (
                        "H-1 CLOUD BUILD HOST in eu-north-1 (task 1 November 2026): one EC2 "
                        "instance started daily by EventBridge Scheduler, stopping itself. "
                        "Measured values are marked as such; costs are list-price estimates."
                    ),
                    "task": "H1-BUILD",
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


def h1() -> dict:
    """The live H-1 resources this host joins (VPC, subnet, ALB and its group, service)."""
    text = H1_EVIDENCE.read_text(encoding="utf-8").replace(
        "{{ACCOUNT_ID}}", h0.account()
    )
    ev = json.loads(text)
    live = {r["type"] + ":" + (r.get("name") or r["id"]): r for r in ev["resources"]}
    subnets = [
        r for r in ev["resources"] if r["type"] == "subnet" and not r["deletedAt"]
    ]
    return {
        "vpc": live[
            "vpc:" + next(r["id"] for r in ev["resources"] if r["type"] == "vpc")
        ]["id"],
        "subnet": subnets[0]["id"],
        "albSg": live["security-group:opentransit-h1-alb"]["id"],
        "alb": next(r for r in ev["resources"] if r["type"] == "load-balancer"),
        "cluster": live["ecs-cluster:opentransit-h1"]["arn"],
        "service": live["ecs-service:opentransit-h1"]["arn"],
        "executionRole": live["iam-role:opentransit-h1-execution"]["arn"],
    }


def bucket_name() -> str:
    return f"opentransit-archive-{h0.account()}"


def monthly_estimate(hours_per_day: float = 1.5) -> dict:
    p, hours = PRICES, hours_per_day * 30
    lines = {
        "instance": p["t3.largeHour"] * hours,
        # One busy vCPU for the whole run: 0.4 vCPU above the 2 x 30% baseline, charged as
        # surplus credits (credits do not accrue while stopped).
        "t3UnlimitedSurplus": p["t3UnlimitedVcpuHour"] * 0.4 * hours,
        "rootVolume": p["gp3GbMonth"] * ROOT_GIB,
        "publicIpv4WhileRunning": p["publicIpv4Hour"] * hours,
        "logs": 0.05 * p["logsIngestGb"] + 0.3 * p["logsStorageGbMonth"],
        # Content-addressed sources: a changed GTFS (143 MB) about every other day, OSM weekly.
        "s3ArchiveFirstMonth": (15 * 0.15 + 4 * 0.12) * p["s3GbMonth"],
        "alarm": p["alarmMonth"],
    }
    total = sum(lines.values())
    return {
        "basis": "eu-north-1 on-demand list prices (AWS Price List API, 1 Nov 2026), pre-tax",
        "instanceType": INSTANCE_TYPE,
        "hoursPerDay": hours_per_day,
        "prices": p,
        "monthlyUsd": {k: round(v, 2) for k, v in lines.items()},
        "monthlyTotalUsd": round(total, 2),
        "guardUsd": MONTHLY_GUARD_USD,
        "withinGuard": total <= MONTHLY_GUARD_USD,
        "notIncluded": (
            "ECR storage of new images pushed by the refresh (pipeline cost, ~$0.08 per changed "
            "generation per month, never pruned), data transfer in (free), tax; SNS and "
            "Scheduler are within their free tiers"
        ),
    }


def estimate(args) -> int:
    ev = h0.load()
    ev["costEstimate"] = monthly_estimate(args.hours_per_day)
    h0.step(
        ev, "cost-estimate", ev["costEstimate"]["withinGuard"], **ev["costEstimate"]
    )
    return 0 if ev["costEstimate"]["withinGuard"] else 1


def instance_policy(net: dict, bucket: str) -> dict:
    acct, region = h0.account(), h0.REGION
    repos = [f"arn:aws:ecr:{region}:{acct}:repository/{r}" for r in h0.REPOSITORIES]
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "EcrLogin",
                "Effect": "Allow",
                "Action": "ecr:GetAuthorizationToken",
                "Resource": "*",
            },
            {
                "Sid": "EcrPushPull",
                "Effect": "Allow",
                "Resource": repos,
                "Action": [
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:BatchGetImage",
                    "ecr:CompleteLayerUpload",
                    "ecr:DescribeImages",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:InitiateLayerUpload",
                    "ecr:PutImage",
                    "ecr:UploadLayerPart",
                ],
            },
            # RegisterTaskDefinition takes no resource ARN; TagResource covers its tags.
            {
                "Sid": "EcsRegister",
                "Effect": "Allow",
                "Resource": "*",
                "Action": ["ecs:RegisterTaskDefinition", "ecs:DescribeTaskDefinition"],
            },
            {
                "Sid": "EcsTagTaskDefinition",
                "Effect": "Allow",
                "Action": "ecs:TagResource",
                "Resource": f"arn:aws:ecs:{region}:{acct}:task-definition/opentransit-h1:*",
            },
            {
                "Sid": "EcsPreviewService",
                "Effect": "Allow",
                "Resource": net["service"],
                "Action": ["ecs:UpdateService", "ecs:DescribeServices"],
            },
            {
                "Sid": "PassExecutionRole",
                "Effect": "Allow",
                "Action": "iam:PassRole",
                "Resource": net["executionRole"],
                "Condition": {
                    "StringEquals": {"iam:PassedToService": "ecs-tasks.amazonaws.com"}
                },
            },
            {
                "Sid": "Logs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogStreams",
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{acct}:log-group:{LOG_GROUP}",
                    f"arn:aws:logs:{region}:{acct}:log-group:{LOG_GROUP}:*",
                ],
            },
            {
                "Sid": "ArchiveList",
                "Effect": "Allow",
                "Action": "s3:ListBucket",
                "Resource": f"arn:aws:s3:::{bucket}",
            },
            {
                "Sid": "ArchiveObjects",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject"],
                "Resource": f"arn:aws:s3:::{bucket}/*",
            },
            {
                "Sid": "RepoRef",
                "Effect": "Allow",
                "Action": "ssm:GetParameter",
                "Resource": f"arn:aws:ssm:{region}:{acct}:parameter{REF_PARAMETER}",
            },
            # The ALB's private address for the post-deploy probe (read-only, no resource ARN).
            {
                "Sid": "FindAlbAddress",
                "Effect": "Allow",
                "Action": "ec2:DescribeNetworkInterfaces",
                "Resource": "*",
            },
        ],
    }


def trust(service: str, **condition) -> dict:
    statement: dict = {
        "Effect": "Allow",
        "Principal": {"Service": service},
        "Action": "sts:AssumeRole",
    }
    if condition:
        statement["Condition"] = {"StringEquals": condition}
    return {"Version": "2012-10-17", "Statement": [statement]}


def render_user_data(net: dict, bucket: str) -> str:
    alb_id = net["alb"]["arn"].split(":loadbalancer/")[1]  # app/<name>/<id>
    values = {
        "REGION": h0.REGION,
        "BUCKET": bucket,
        "LOG_GROUP": LOG_GROUP,
        "REF_PARAMETER": REF_PARAMETER,
        "REPO_URL": REPO_URL,
        "ALB_ENI_DESCRIPTION": f"ELB {alb_id}",
    }
    text = (h0.AWS_DIR / "build-host/user-data.sh").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    assert "{{" not in text, "unrendered user-data placeholder"
    return text


def setup(args) -> int:
    ev = h0.load()
    if not (ev.get("costEstimate") or {}).get("withinGuard"):
        raise SystemExit(
            "run `estimate` first; setup refuses without a recorded estimate in guard"
        )
    net, acct, region = h1(), h0.account(), h0.REGION
    tags_kv = [f"Key={k},Value={v}" for k, v in h0.TAGS.items()]
    have = {r["type"] for r in h0.find(ev, "s3-bucket") + h0.find(ev, "iam-role")}

    # Archive bucket: adopt the portability session's bucket if it exists, else create it.
    bucket = bucket_name()
    if not h0.find(ev, "s3-bucket"):
        exists = "_error" not in h0.aws(
            "s3api", "head-bucket", "--bucket", bucket, check=False
        )
        if not exists:
            h0.aws(
                "s3api",
                "create-bucket",
                "--bucket",
                bucket,
                "--create-bucket-configuration",
                f"LocationConstraint={region}",
            )
            h0.aws(
                "s3api",
                "put-public-access-block",
                "--bucket",
                bucket,
                "--public-access-block-configuration",
                "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,"
                "RestrictPublicBuckets=true",
            )
            h0.aws(
                "s3api",
                "put-bucket-versioning",
                "--bucket",
                bucket,
                "--versioning-configuration",
                "Status=Enabled",
            )
            h0.aws(
                "s3api",
                "put-bucket-tagging",
                "--bucket",
                bucket,
                "--tagging",
                json.dumps(
                    {"TagSet": [{"Key": k, "Value": v} for k, v in h0.TAGS.items()]}
                ),
            )
        h0.resource(
            ev, "s3-bucket", bucket, f"arn:aws:s3:::{bucket}", adopted=exists, keep=True
        )

    if not h0.find(ev, "log-group"):
        h0.aws(
            "logs",
            "create-log-group",
            "--log-group-name",
            LOG_GROUP,
            "--tags",
            ",".join(f"{k}={v}" for k, v in h0.TAGS.items()),
        )
        h0.aws(
            "logs",
            "put-retention-policy",
            "--log-group-name",
            LOG_GROUP,
            "--retention-in-days",
            str(LOG_RETENTION_DAYS),
        )
        h0.resource(
            ev,
            "log-group",
            LOG_GROUP,
            f"arn:aws:logs:{region}:{acct}:log-group:{LOG_GROUP}",
            retentionDays=LOG_RETENTION_DAYS,
        )
        h0.aws(
            "logs",
            "put-metric-filter",
            "--log-group-name",
            LOG_GROUP,
            "--filter-name",
            "refresh-succeeded",
            "--filter-pattern",
            '"OPENTRANSIT_REFRESH_RESULT outcome=ok"',
            "--metric-transformations",
            f"metricName={METRIC},metricNamespace={METRIC_NAMESPACE},metricValue=1",
        )
        h0.resource(
            ev,
            "metric-filter",
            f"{LOG_GROUP}/refresh-succeeded",
            metric=f"{METRIC_NAMESPACE}/{METRIC}",
        )

    if not h0.find(ev, "sns-topic"):
        topic = h0.aws("sns", "create-topic", "--name", TOPIC, "--tags", *tags_kv)[
            "TopicArn"
        ]
        h0.resource(
            ev, "sns-topic", TOPIC, topic, subscriptions="none (user adds email later)"
        )
    topic = h0.one(ev, "sns-topic")["arn"]
    if not h0.find(ev, "cloudwatch-alarm"):
        # 26 consecutive hours without one success line (missing data counts as breaching).
        h0.aws(
            "cloudwatch",
            "put-metric-alarm",
            "--alarm-name",
            ALARM,
            "--alarm-description",
            "No successful OpenTransit build-host refresh in 26 hours (see docs/operations.md)",
            "--namespace",
            METRIC_NAMESPACE,
            "--metric-name",
            METRIC,
            "--statistic",
            "Sum",
            "--period",
            "3600",
            "--evaluation-periods",
            "26",
            "--datapoints-to-alarm",
            "26",
            "--threshold",
            "1",
            "--comparison-operator",
            "LessThanThreshold",
            "--treat-missing-data",
            "breaching",
            "--alarm-actions",
            topic,
            "--tags",
            *tags_kv,
        )
        h0.resource(
            ev,
            "cloudwatch-alarm",
            ALARM,
            f"arn:aws:cloudwatch:{region}:{acct}:alarm:{ALARM}",
            topic=topic,
        )

    if not h0.find(ev, "ssm-parameter"):
        h0.aws(
            "ssm",
            "put-parameter",
            "--name",
            REF_PARAMETER,
            "--type",
            "String",
            "--value",
            args.ref,
            "--description",
            "OpenTransit commit the build host runs",
            "--tags",
            *tags_kv,
        )
        h0.resource(
            ev,
            "ssm-parameter",
            REF_PARAMETER,
            f"arn:aws:ssm:{region}:{acct}:parameter{REF_PARAMETER}",
            value=args.ref,
        )

    if "iam-role" not in have:
        role = h0.aws(
            "iam",
            "create-role",
            "--role-name",
            NAME,
            "--assume-role-policy-document",
            h0.file_arg(trust("ec2.amazonaws.com"), "trust-ec2.json"),
            "--tags",
            *tags_kv,
        )["Role"]["Arn"]
        h0.resource(ev, "iam-role", NAME, role)
        h0.aws(
            "iam",
            "put-role-policy",
            "--role-name",
            NAME,
            "--policy-name",
            NAME,
            "--policy-document",
            h0.file_arg(instance_policy(net, bucket), "instance.json"),
        )
        h0.resource(ev, "iam-inline-policy", f"{NAME}/{NAME}")
        ssm_core = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
        h0.aws(
            "iam", "attach-role-policy", "--role-name", NAME, "--policy-arn", ssm_core
        )
        h0.resource(
            ev, "iam-attached-policy", f"{NAME}/AmazonSSMManagedInstanceCore", ssm_core
        )
        profile = h0.aws(
            "iam",
            "create-instance-profile",
            "--instance-profile-name",
            NAME,
            "--tags",
            *tags_kv,
        )["InstanceProfile"]["Arn"]
        h0.aws(
            "iam",
            "add-role-to-instance-profile",
            "--instance-profile-name",
            NAME,
            "--role-name",
            NAME,
        )
        h0.resource(ev, "iam-instance-profile", NAME, profile)
        sched = h0.aws(
            "iam",
            "create-role",
            "--role-name",
            f"{NAME}-scheduler",
            "--assume-role-policy-document",
            h0.file_arg(
                trust("scheduler.amazonaws.com", **{"aws:SourceAccount": acct}),
                "trust-scheduler.json",
            ),
            "--tags",
            *tags_kv,
        )["Role"]["Arn"]
        h0.resource(ev, "iam-role", f"{NAME}-scheduler", sched)
        time.sleep(12)  # IAM propagation before the instance profile is used

    if not h0.find(ev, "security-group"):
        sg = h0.aws(
            "ec2",
            "create-security-group",
            "--group-name",
            NAME,
            "--vpc-id",
            net["vpc"],
            "--description",
            "OpenTransit build host: no inbound; HTTPS/HTTP out",
            "--tag-specifications",
            h0.ec2_tags("security-group", NAME),
        )["GroupId"]
        h0.resource(ev, "security-group", sg, name=NAME, inbound="none")
        h0.aws(
            "ec2",
            "revoke-security-group-egress",
            "--group-id",
            sg,
            "--ip-permissions",
            json.dumps([{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}]),
        )
        h0.aws(
            "ec2",
            "authorize-security-group-egress",
            "--group-id",
            sg,
            "--ip-permissions",
            json.dumps(
                [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": port,
                        "ToPort": port,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    }
                    for port in (80, 443)
                ]
            ),
        )
        rule = h0.aws(
            "ec2",
            "authorize-security-group-ingress",
            "--group-id",
            net["albSg"],
            "--ip-permissions",
            json.dumps(
                [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 80,
                        "ToPort": 80,
                        "UserIdGroupPairs": [
                            {
                                "GroupId": sg,
                                "Description": "OpenTransit build host post-deploy probe",
                            }
                        ],
                    }
                ]
            ),
        )
        rule_id = rule["SecurityGroupRules"][0]["SecurityGroupRuleId"]
        h0.resource(
            ev,
            "security-group-rule",
            rule_id,
            group=net["albSg"],
            rule="ALB tcp/80 from the build host group",
        )
    sg = h0.one(ev, "security-group")["id"]

    if not h0.find(ev, "ec2-instance"):
        ami = h0.aws("ssm", "get-parameter", "--name", AMI_PARAMETER)["Parameter"][
            "Value"
        ]
        image = h0.aws("ec2", "describe-images", "--image-ids", ami)["Images"][0]
        user_data = base64.b64encode(render_user_data(net, bucket).encode()).decode()
        tags = {**h0.TAGS, "Name": NAME, "OpenTransitMode": "maintenance"}
        spec = ",".join(f"{{Key={k},Value={v}}}" for k, v in tags.items())
        out = h0.aws(
            "ec2",
            "run-instances",
            "--image-id",
            ami,
            "--instance-type",
            INSTANCE_TYPE,
            "--subnet-id",
            net["subnet"],
            "--security-group-ids",
            sg,
            "--associate-public-ip-address",
            "--iam-instance-profile",
            f"Name={NAME}",
            "--metadata-options",
            "HttpTokens=required,HttpEndpoint=enabled,HttpPutResponseHopLimit=1,"
            "InstanceMetadataTags=enabled",
            "--block-device-mappings",
            json.dumps(
                [
                    {
                        "DeviceName": image["RootDeviceName"],
                        "Ebs": {
                            "VolumeSize": ROOT_GIB,
                            "VolumeType": "gp3",
                            "Encrypted": True,
                            "DeleteOnTermination": True,
                        },
                    }
                ]
            ),
            "--instance-initiated-shutdown-behavior",
            "stop",
            "--credit-specification",
            "CpuCredits=unlimited",
            "--user-data",
            user_data,
            "--count",
            "1",
            "--tag-specifications",
            f"ResourceType=instance,Tags=[{spec}]",
            f"ResourceType=volume,Tags=[{spec}]",
        )
        inst = out["Instances"][0]
        h0.resource(
            ev,
            "ec2-instance",
            inst["InstanceId"],
            f"arn:aws:ec2:{region}:{acct}:instance/{inst['InstanceId']}",
            instanceType=INSTANCE_TYPE,
            ami=ami,
            amiName=image["Name"],
            amiCreated=image["CreationDate"],
            rootGiB=ROOT_GIB,
            subnet=net["subnet"],
        )
    instance = h0.one(ev, "ec2-instance")

    if not h0.find(ev, "scheduler-schedule"):
        sched_role = next(
            r for r in h0.find(ev, "iam-role") if r["id"].endswith("-scheduler")
        )
        h0.aws(
            "iam",
            "put-role-policy",
            "--role-name",
            sched_role["id"],
            "--policy-name",
            "start-build-host",
            "--policy-document",
            h0.file_arg(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "ec2:StartInstances",
                            "Resource": instance["arn"],
                        }
                    ],
                },
                "scheduler.json",
            ),
        )
        h0.resource(ev, "iam-inline-policy", f"{sched_role['id']}/start-build-host")
        out = h0.aws(
            "scheduler",
            "create-schedule",
            "--name",
            SCHEDULE,
            "--schedule-expression",
            CRON,
            "--schedule-expression-timezone",
            "UTC",
            "--flexible-time-window",
            "Mode=OFF",
            "--state",
            "ENABLED",
            "--description",
            "Start the OpenTransit build host (daily refresh)",
            "--target",
            json.dumps(target(instance, sched_role)),
        )
        h0.resource(
            ev,
            "scheduler-schedule",
            SCHEDULE,
            out["ScheduleArn"],
            expression=CRON,
            timezone="UTC",
        )
    h0.step(ev, "setup", True, instance=instance["id"], bucket=bucket)
    return 0


def target(instance: dict, role: dict) -> dict:
    return {
        "Arn": "arn:aws:scheduler:::aws-sdk:ec2:startInstances",
        "RoleArn": role["arn"],
        "Input": json.dumps({"InstanceIds": [instance["id"]]}),
        "RetryPolicy": {"MaximumRetryAttempts": 3, "MaximumEventAgeInSeconds": 3600},
    }


def seed(args) -> int:
    """Put the serving release record (and its plan) where the host's first run finds it."""
    ev = h0.load()
    pointer = json.loads((args.releases / "current.json").read_text(encoding="utf-8"))
    release = Path(pointer["release"])
    name = release.parent.name
    bucket = h0.one(ev, "s3-bucket")["id"]
    for file in ("release-registered.json", "release-plan.json"):
        h0.aws(
            "s3",
            "cp",
            "--only-show-errors",
            str(release.parent / file),
            f"s3://{bucket}/bootstrap/releases/{name}/{file}",
        )
    current = {
        "release": f"/srv/ot/releases/{name}/release-registered.json",
        "previous": None,
        "at": h0.now(),
        "seededFrom": str(release),
    }
    path = h0._TMP / "current.json"
    path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    h0.aws(
        "s3",
        "cp",
        "--only-show-errors",
        str(path),
        f"s3://{bucket}/bootstrap/releases/current.json",
    )
    h0.step(ev, "seed-release", True, release=name, bucket=bucket)
    return 0


def mode(args) -> int:
    ev = h0.load()
    inst = h0.one(ev, "ec2-instance")["id"]
    h0.aws(
        "ec2",
        "create-tags",
        "--resources",
        inst,
        "--tags",
        f"Key=OpenTransitMode,Value={args.mode}",
    )
    h0.step(ev, "mode", True, instance=inst, mode=args.mode)
    return 0


def set_ref(args) -> int:
    ev = h0.load()
    h0.aws(
        "ssm",
        "put-parameter",
        "--name",
        REF_PARAMETER,
        "--value",
        args.ref,
        "--overwrite",
    )
    h0.step(ev, "set-ref", True, ref=args.ref)
    return 0


def trigger(args) -> int:
    """A one-off schedule with the daily schedule's own target and role (deleted after it runs)."""
    ev = h0.load()
    instance = h0.one(ev, "ec2-instance")
    role = next(r for r in h0.find(ev, "iam-role") if r["id"].endswith("-scheduler"))
    at = (datetime.now(UTC) + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%S")
    name = f"{NAME}-manual-{at.replace(':', '').replace('-', '')}"
    h0.aws(
        "scheduler",
        "create-schedule",
        "--name",
        name,
        "--schedule-expression",
        f"at({at})",
        "--schedule-expression-timezone",
        "UTC",
        "--flexible-time-window",
        "Mode=OFF",
        "--action-after-completion",
        "DELETE",
        "--target",
        json.dumps(target(instance, role)),
    )
    h0.step(ev, "trigger", True, schedule=name, at=at + "Z")
    return 0


def instance_state(instance_id: str) -> str:
    out = h0.aws("ec2", "describe-instances", "--instance-ids", instance_id)
    return out["Reservations"][0]["Instances"][0]["State"]["Name"]


def watch(args) -> int:
    """Print the newest run's host and job streams until the instance is stopped again."""
    ev = h0.load()
    instance = h0.one(ev, "ec2-instance")["id"]
    started, seen, stamp = time.monotonic(), {}, args.stamp
    stopped_since = None
    while time.monotonic() - started < args.timeout:
        if stamp is None:
            streams = h0.aws(
                "logs",
                "describe-log-streams",
                "--log-group-name",
                LOG_GROUP,
                "--order-by",
                "LastEventTime",
                "--descending",
                "--max-items",
                "4",
            )
            names = [s["logStreamName"] for s in streams.get("logStreams", [])]
            fresh = [n for n in names if n.split("/")[0] >= (args.after or "")]
            stamp = fresh[0].split("/")[0] if fresh else None
        if stamp:
            for part in ("host", "job"):
                stream = f"{stamp}/{part}"
                cmd = [
                    "logs",
                    "get-log-events",
                    "--log-group-name",
                    LOG_GROUP,
                    "--log-stream-name",
                    stream,
                    "--start-from-head",
                ]
                if stream in seen:
                    cmd += ["--next-token", seen[stream]]
                out = h0.aws(*cmd, check=False)
                for event in out.get("events", []):
                    print(f"[{part}] {event['message']}", flush=True)
                if out.get("nextForwardToken"):
                    seen[stream] = out["nextForwardToken"]
        state = instance_state(instance)
        if state == "stopped":
            stopped_since = stopped_since or time.monotonic()
            if time.monotonic() - stopped_since > 30:
                print(f"instance {instance} stopped", flush=True)
                return 0
        time.sleep(20)
    return 1


def pause(args) -> int:
    ev = h0.load()
    sched = h0.one(ev, "scheduler-schedule")
    current = h0.aws("scheduler", "get-schedule", "--name", sched["id"])
    state = "DISABLED" if args.command == "pause" else "ENABLED"
    h0.aws(
        "scheduler",
        "update-schedule",
        "--name",
        sched["id"],
        "--schedule-expression",
        current["ScheduleExpression"],
        "--schedule-expression-timezone",
        current["ScheduleExpressionTimezone"],
        "--flexible-time-window",
        json.dumps(current["FlexibleTimeWindow"]),
        "--target",
        json.dumps(current["Target"]),
        "--state",
        state,
    )
    h0.step(ev, args.command, True, schedule=sched["id"], state=state)
    return 0


def teardown(_args) -> int:
    """Delete in reverse order; the archive bucket and its objects are kept (delete by hand)."""
    ev = h0.load()
    order = [
        "scheduler-schedule",
        "ec2-instance",
        "security-group-rule",
        "security-group",
        "iam-instance-profile",
        "iam-attached-policy",
        "iam-inline-policy",
        "iam-role",
        "ssm-parameter",
        "cloudwatch-alarm",
        "sns-topic",
        "metric-filter",
        "log-group",
    ]
    net = h1()
    for kind in order:
        for r in reversed(h0.find(ev, kind)):
            ident = r["id"]
            if kind == "scheduler-schedule":
                h0.aws("scheduler", "delete-schedule", "--name", ident)
            elif kind == "ec2-instance":
                h0.aws("ec2", "terminate-instances", "--instance-ids", ident)
                if not h0.DRY_RUN:
                    h0.aws(
                        "ec2", "wait", "instance-terminated", "--instance-ids", ident
                    )
            elif kind == "security-group-rule":
                h0.aws(
                    "ec2",
                    "revoke-security-group-ingress",
                    "--group-id",
                    net["albSg"],
                    "--security-group-rule-ids",
                    ident,
                )
            elif kind == "security-group":
                h0.aws("ec2", "delete-security-group", "--group-id", ident)
            elif kind == "iam-instance-profile":
                h0.aws(
                    "iam",
                    "remove-role-from-instance-profile",
                    "--instance-profile-name",
                    ident,
                    "--role-name",
                    NAME,
                )
                h0.aws(
                    "iam", "delete-instance-profile", "--instance-profile-name", ident
                )
            elif kind == "iam-attached-policy":
                h0.aws(
                    "iam",
                    "detach-role-policy",
                    "--role-name",
                    NAME,
                    "--policy-arn",
                    r["arn"],
                )
            elif kind == "iam-inline-policy":
                role, policy = ident.split("/")
                h0.aws(
                    "iam",
                    "delete-role-policy",
                    "--role-name",
                    role,
                    "--policy-name",
                    policy,
                )
            elif kind == "iam-role":
                h0.aws("iam", "delete-role", "--role-name", ident)
            elif kind == "ssm-parameter":
                h0.aws("ssm", "delete-parameter", "--name", ident)
            elif kind == "cloudwatch-alarm":
                h0.aws("cloudwatch", "delete-alarms", "--alarm-names", ident)
            elif kind == "sns-topic":
                h0.aws("sns", "delete-topic", "--topic-arn", r["arn"])
            elif kind == "metric-filter":
                h0.aws(
                    "logs",
                    "delete-metric-filter",
                    "--log-group-name",
                    LOG_GROUP,
                    "--filter-name",
                    "refresh-succeeded",
                )
            elif kind == "log-group":
                h0.aws("logs", "delete-log-group", "--log-group-name", ident)
            if not h0.DRY_RUN:
                r["deletedAt"] = h0.now()
                h0.save(ev)
    print(
        "kept: the archive bucket",
        h0.find(ev, "s3-bucket")[0]["id"]
        if h0.find(ev, "s3-bucket")
        else "(none recorded)",
        "and the ECR repositories",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--dry-run", action="store_true", help="print commands, change nothing"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("estimate")
    p.add_argument("--hours-per-day", type=float, default=1.5)
    p = sub.add_parser("setup")
    p.add_argument("--ref", required=True, help="repository commit the host checks out")
    p = sub.add_parser("seed")
    p.add_argument("--releases", type=Path, default=Path("D:/ot/releases"))
    p = sub.add_parser("mode")
    p.add_argument("mode", choices=["refresh", "maintenance"])
    p = sub.add_parser("set-ref")
    p.add_argument("ref")
    sub.add_parser("trigger")
    p = sub.add_parser("watch")
    p.add_argument("--stamp", help="run stamp (default: the newest stream)")
    p.add_argument("--after", help="ignore streams older than this stamp")
    p.add_argument("--timeout", type=float, default=4 * 3600)
    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("teardown")
    args = parser.parse_args(argv)
    h0.DRY_RUN = args.dry_run
    configure()
    command = {
        "estimate": estimate,
        "setup": setup,
        "seed": seed,
        "mode": mode,
        "set-ref": set_ref,
        "trigger": trigger,
        "watch": watch,
        "pause": pause,
        "resume": pause,
        "teardown": teardown,
    }[args.command]
    return command(args)


if __name__ == "__main__":
    sys.exit(main())
