"""Structural checks for the AWS H-0 drafts. Pure local file inspection; no cloud access.

    python deploy/aws/tools/validate_drafts.py [--aws-dir deploy/aws]

A pass means the drafts are internally consistent with the written plan. It is not a Fargate
acceptance test: startup ordering, permissions, memory and draining are proven only by H-0.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AWS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = AWS_DIR.parents[1]

CEILING_MIB = 8192
REGION = "il-central-1"
LOG_GROUP = "/opentransit/h0"
PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
KNOWN_PLACEHOLDERS = {
    "ACCOUNT_ID",
    "ECR_REGISTRY",
    "EXECUTION_ROLE_ARN",
    "API_DIGEST",
    "DATA_DIGEST",
    "PHOTON_DIGEST",
    "CLUSTER_ARN",
    "SUBNET_A",
    "SUBNET_B",
    "TASK_SECURITY_GROUP",
    "ALB_SECURITY_GROUP",
    "TARGET_GROUP_ARN",
    "VPC_ID",
    "CERTIFICATE_ARN",
    "REVIEWER_CIDR",
    "TASK_DEFINITION_REVISION",
}
# Valid Fargate Linux vCPU units -> allowed memory (MiB).
FARGATE_COMBINATIONS = {
    256: {512, 1024, 2048},
    512: {1024, 2048, 3072, 4096},
    1024: set(range(2048, 8192 + 1, 1024)),
    2048: set(range(4096, 16384 + 1, 1024)),
    4096: set(range(8192, 30720 + 1, 1024)),
}
SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)aws_secret_access_key"),
    re.compile(r"(?i)\b(password|passwd|api[_-]?key|secret[_-]?key|bearer)\b\s*[:=]"),
    re.compile(r"(?<![0-9a-z])[0-9]{12}(?![0-9a-z])"),  # a literal AWS account ID
)
SECRET_NAME = re.compile(r"(?i)(secret|token|password|passwd|credential|api[_-]?key)")
IMAGE_DIGEST = re.compile(r"@(sha256:[a-f0-9]{64}|\{\{[A-Z_]+_DIGEST\}\})$")
# ECS container health-check bounds (HealthCheck API reference).
ECS_HEALTH_LIMITS = {"interval": (5, 300), "timeout": (2, 120), "retries": (1, 10)}
ECS_MAX_START_PERIOD = 300
# Local one-core emulation (services/api/results/h0-local-images-20261001-01.json): API
# lifespan 338 s, task start to /readyz 200 717 s. Both bounds keep roughly 1.7x headroom.
MIN_API_HEALTH_TOLERANCE_SECONDS = 600
MIN_START_GRACE_SECONDS = 1200
HEAP = re.compile(r"^-Xmx(\d+)([mMgG])$")

# Rendered release candidates (deploy/aws/tools/publish_generation.py): every image pinned by a
# concrete digest, account-specific values either still placeholders or well-formed, and the
# release identity carried as task-definition tags.
CANDIDATE_PLACEHOLDERS = {"ECR_REGISTRY", "EXECUTION_ROLE_ARN"}
CONCRETE_DIGEST = re.compile(r"@sha256:[a-f0-9]{64}$")
ROLE_ARN = re.compile(r"arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]{1,512}")
ECR_REGISTRY = re.compile(r"[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com")
RELEASE_TAGS = {
    "generation-id": re.compile(r"[a-f0-9]{64}"),
    "probe-corpus-sha256": re.compile(r"[a-f0-9]{64}"),
    "verifier-config-sha256": re.compile(r"[a-f0-9]{64}"),
    "source-checked-at": re.compile(r"\d{4}-\d{2}-\d{2}T[0-9:.]+(Z|[+-]\d{2}:\d{2})"),
    "coverage-until": re.compile(r"\d{4}-\d{2}-\d{2}T[0-9:.]+(Z|[+-]\d{2}:\d{2})"),
    "digest-kind": re.compile(r"local-image-id|registry-manifest"),
}
# ECS tag limits: at most 50 tags, key <= 128 and value <= 256 characters from this set.
ECS_TAG_VALUE = re.compile(r"[\w\s+\-=.:/@]{0,256}")

REQUIRED_EDGES = {
    # container -> {dependency: condition}
    "motis": {"init": "SUCCESS"},
    "photon": {"init": "SUCCESS"},
    "verifier": {"init": "SUCCESS", "motis": "HEALTHY"},
    "api": {"verifier": "SUCCESS", "motis": "HEALTHY", "photon": "HEALTHY"},
}
ESSENTIAL = {"init": False, "verifier": False, "motis": True, "photon": True, "api": True}


def _walk(value):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _topological(dependencies: dict[str, set[str]]) -> list[str] | None:
    order: list[str] = []
    remaining = {name: set(deps) for name, deps in dependencies.items()}
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if not deps)
        if not ready:
            return None  # a cycle
        order.extend(ready)
        for name in ready:
            del remaining[name]
        for deps in remaining.values():
            deps.difference_update(ready)
    return order


def budget(task: dict) -> dict:
    """Allocation arithmetic, in MiB, used by the validator and the README tables."""
    memory = int(task["memory"])
    limits = {c["name"]: c.get("memory") for c in task["containerDefinitions"]}
    allocated = sum(v for v in limits.values() if isinstance(v, int))
    return {
        "cpuUnits": int(task["cpu"]),
        "taskMemoryMiB": memory,
        "containerLimitsMiB": limits,
        "containerLimitSumMiB": allocated,
        "unallocatedMiB": memory - allocated,
        "replacementOverlapMiB": 2 * memory,
        "ceilingMiB": CEILING_MIB,
        "overlapHeadroomMiB": CEILING_MIB - 2 * memory,
    }


def validate_task_definition(
    task: dict, label: str, motis_digest: str | None = None, *, candidate: bool = False
):
    """Return (errors, warnings) for one task-definition draft.

    ``candidate=True`` is used by :func:`validate_candidate` for a rendered release revision,
    which may carry a concrete execution-role ARN instead of the draft placeholder.
    """
    errors: list[str] = []
    warnings: list[str] = []

    def fail(message: str) -> None:
        errors.append(f"{label}: {message}")

    if task.get("networkMode") != "awsvpc":
        fail("networkMode must be awsvpc")
    if task.get("requiresCompatibilities") != ["FARGATE"]:
        fail("requiresCompatibilities must be exactly [FARGATE]")
    if task.get("runtimePlatform") != {
        "cpuArchitecture": "X86_64",
        "operatingSystemFamily": "LINUX",
    }:
        fail("runtimePlatform must be Linux/X86_64")
    if task.get("ephemeralStorage", {}).get("sizeInGiB", 0) < 20:
        fail("ephemeralStorage must be at least the 20 GiB Fargate default")
    if "taskRoleArn" in task:
        fail("the serving task has no task role (no AWS permissions)")
    role = str(task.get("executionRoleArn", ""))
    if candidate:
        if role != "{{EXECUTION_ROLE_ARN}}" and not ROLE_ARN.fullmatch(role):
            fail("executionRoleArn must be the placeholder or an IAM role ARN")
    elif not role.startswith("{{"):
        fail("executionRoleArn must be a placeholder in the draft")
    for key in ("pidMode", "ipcMode", "proxyConfiguration", "placementConstraints"):
        if key in task:
            fail(f"{key} is not allowed")

    try:
        cpu, memory = int(task["cpu"]), int(task["memory"])
    except KeyError, ValueError:
        fail("cpu and memory must be numeric strings")
        return errors, warnings
    if memory not in FARGATE_COMBINATIONS.get(cpu, set()):
        fail(f"{cpu} CPU units / {memory} MiB is not a valid Fargate combination")

    containers = task.get("containerDefinitions", [])
    by_name = {c.get("name"): c for c in containers}
    if len(by_name) != len(containers):
        fail("container names must be unique")
    addresses = "photon" in by_name
    expected = {"init", "motis", "verifier", "api"} | ({"photon"} if addresses else set())
    if set(by_name) != expected:
        fail(f"containers must be exactly {sorted(expected)}, found {sorted(by_name)}")
        return errors, warnings

    volume_names = {v.get("name") for v in task.get("volumes", [])}
    for volume in task.get("volumes", []):
        if set(volume) != {"name"}:
            fail(f"volume {volume.get('name')} must be a plain task-local ephemeral volume")
    if addresses != ("photon-data" in volume_names):
        fail("photon-data volume must exist exactly when Photon is present")

    total = 0
    for name, c in by_name.items():
        if c.get("essential") is not ESSENTIAL[name]:
            fail(f"{name}: essential must be {ESSENTIAL[name]}")
        limit = c.get("memory")
        if type(limit) is not int or limit <= 0:
            fail(f"{name}: a hard memory limit in MiB is required")
        else:
            total += limit
        if "memoryReservation" in c and c["memoryReservation"] > (limit or 0):
            fail(f"{name}: memoryReservation exceeds the hard limit")
        user = str(c.get("user", ""))
        if not user:
            fail(f"{name}: user must be explicit")
        elif user.split(":")[0] in {"0", "root"} and name != "init":
            fail(f"{name}: only the short-lived init container may run as root")
        if name == "init":
            if user != "0":
                fail("init: runs as root solely to chown task-local volumes")
            if "portMappings" in c:
                fail("init: must not publish ports")
            caps = c.get("linuxParameters", {}).get("capabilities", {})
            kept = {"CHOWN", "DAC_OVERRIDE", "FOWNER"}
            if kept & set(caps.get("drop", [])) or "add" in caps:
                fail("init: may keep only CHOWN, DAC_OVERRIDE and FOWNER (never add)")
            if "NET_RAW" not in caps.get("drop", []) or "SETUID" not in caps.get("drop", []):
                fail("init: other default capabilities must be dropped")
        else:
            caps = c.get("linuxParameters", {}).get("capabilities", {})
            if caps.get("drop") != ["ALL"] or "add" in caps:
                fail(f"{name}: capabilities must drop ALL and add none")
        if c.get("readonlyRootFilesystem") is not True:
            fail(f"{name}: readonlyRootFilesystem must be true")
        for key in ("privileged", "secrets", "environmentFiles", "repositoryCredentials"):
            if key in c:
                fail(f"{name}: {key} is not allowed")
        if c.get("linuxParameters", {}).get("devices"):
            fail(f"{name}: devices are not allowed")
        image = c.get("image", "")
        if not IMAGE_DIGEST.search(image):
            fail(f"{name}: image must be pinned by digest or a *_DIGEST placeholder")
        if name == "motis" and motis_digest and not image.endswith(f"@{motis_digest}"):
            fail("motis: image digest differs from compose.yaml")
        log = c.get("logConfiguration", {})
        options = log.get("options", {})
        if (
            log.get("logDriver") != "awslogs"
            or options.get("awslogs-group") != LOG_GROUP
            or options.get("awslogs-region") != REGION
            or not options.get("awslogs-stream-prefix")
            or options.get("awslogs-create-group", "false") != "false"
        ):
            fail(f"{name}: awslogs must use the pre-created {LOG_GROUP} group in {REGION}")
        for env in c.get("environment", []):
            if SECRET_NAME.search(env.get("name", "")):
                fail(f"{name}: environment name {env.get('name')} looks like a secret")
        for mount in c.get("mountPoints", []):
            if mount["sourceVolume"] not in volume_names:
                fail(f"{name}: mount of undefined volume {mount['sourceVolume']}")

    if total > memory:
        fail(f"container memory limits sum to {total} MiB, above the {memory} MiB task")
    elif memory - total < 128:
        warnings.append(f"{label}: only {memory - total} MiB of the task memory is unallocated")

    # Ports: only the API publishes one, and only 8000.
    for name, c in by_name.items():
        ports = c.get("portMappings", [])
        if name == "api":
            if [(p.get("containerPort"), p.get("protocol")) for p in ports] != [(8000, "tcp")]:
                fail("api: must publish exactly container port 8000/tcp")
            if any("hostPort" in p and p["hostPort"] != 8000 for p in ports):
                fail("api: hostPort must be absent or 8000")
        elif ports:
            fail(f"{name}: must not publish ports")

    # Dependency graph: complete, acyclic, and exactly the intended startup ordering.
    graph: dict[str, set[str]] = {}
    conditions: dict[str, dict[str, str]] = {}
    for name, c in by_name.items():
        deps = c.get("dependsOn", [])
        graph[name] = {d["containerName"] for d in deps}
        conditions[name] = {d["containerName"]: d["condition"] for d in deps}
        for d in deps:
            if d["containerName"] not in by_name:
                fail(f"{name}: depends on unknown container {d['containerName']}")
            elif d["condition"] == "SUCCESS" and by_name[d["containerName"]]["essential"]:
                fail(f"{name}: SUCCESS dependency {d['containerName']} must be nonessential")
            elif d["condition"] == "HEALTHY" and "healthCheck" not in by_name[d["containerName"]]:
                fail(f"{name}: HEALTHY dependency {d['containerName']} has no health check")
            elif d["condition"] not in {"SUCCESS", "HEALTHY"}:
                fail(f"{name}: unsupported dependency condition {d['condition']}")
        if deps and "startTimeout" not in c:
            fail(f"{name}: startTimeout must be set explicitly for its dependency chain")
    if _topological({k: {x for x in v if x in by_name} for k, v in graph.items()}) is None:
        fail("container dependency graph has a cycle")
    for name, wanted in REQUIRED_EDGES.items():
        if name not in by_name:
            continue
        for dependency, condition in wanted.items():
            if dependency not in by_name:
                continue
            if conditions[name].get(dependency) != condition:
                fail(f"{name}: must depend on {dependency} with condition {condition}")
    if graph["init"]:
        fail("init must not depend on anything")
    extras = set(conditions["api"]) - set(REQUIRED_EDGES["api"])
    if extras:
        fail(f"api: unexpected dependencies {sorted(extras)}")

    # Volume access policy.
    def mounts(name: str) -> dict[str, tuple[str, bool]]:
        return {
            m["sourceVolume"]: (m["containerPath"], m["readOnly"])
            for m in by_name[name].get("mountPoints", [])
        }

    for name in ("motis", "verifier", "api"):
        generation = mounts(name).get("generation")
        if generation != ("/generation", True):
            fail(f"{name}: /generation must be mounted read-only")
    if mounts("init").get("generation") != ("/generation", False):
        fail("init: must be the only writer of /generation")
    if mounts("api").get("probe") != ("/run/opentransit", True):
        fail("api: probe evidence must be read-only")
    if mounts("verifier").get("probe") != ("/run/opentransit", False):
        fail("verifier: must write probe evidence to /run/opentransit")
    for name in ("motis", "verifier", "api", "photon"):
        if name in by_name and name != "init":
            for volume, (path, read_only) in mounts(name).items():
                if volume.startswith("tmp-") and (read_only or path != "/tmp"):
                    fail(f"{name}: scratch volume {volume} must be a writable /tmp")
    if addresses and mounts("photon").get("photon-data") != ("/photon_data", False):
        fail("photon: /photon_data must be writable (OpenSearch locks and logs)")

    # Environment and commands.
    def env(name: str) -> dict[str, str]:
        return {e["name"]: e["value"] for e in by_name[name].get("environment", [])}

    api_env = env("api")
    if api_env.get("OPENTRANSIT_MOTIS_URL") != "http://127.0.0.1:8080":
        fail("api: OPENTRANSIT_MOTIS_URL must be http://127.0.0.1:8080")
    if api_env.get("OPENTRANSIT_MANIFEST") != "/generation/manifest.json":
        fail("api: OPENTRANSIT_MANIFEST must be /generation/manifest.json")
    if api_env.get("OPENTRANSIT_PROBE") != "/run/opentransit/probe.json":
        fail("api: OPENTRANSIT_PROBE must be the verifier's output")
    if api_env.get("OPENTRANSIT_PLAYGROUND", "0") != "0":
        fail("api: the playground must stay disabled")
    photon_vars = {k for k in api_env if k.startswith("OPENTRANSIT_PHOTON")}
    if addresses:
        if (
            api_env.get("OPENTRANSIT_PHOTON_URL") != "http://127.0.0.1:2322"
            or api_env.get("OPENTRANSIT_PHOTON_ADMIN_URL") != "http://127.0.0.1:9201"
        ):
            fail("api: Photon query/admin origins must be the task-local loopback origins")
    elif photon_vars:
        fail("api: Photon variables must be absent without a Photon container")
    api_command = by_name["api"].get("command", [])
    if "--no-access-log" not in api_command:
        fail("api: Uvicorn access logging must be disabled")
    if "--workers" in api_command:
        fail("api: exactly one Uvicorn worker is required")
    if "--timeout-graceful-shutdown" not in api_command or (
        api_command[api_command.index("--timeout-graceful-shutdown") + 1] != "25"
    ):
        fail("api: graceful shutdown must be 25 seconds")
    if by_name["api"].get("stopTimeout") != 60:
        fail("api: stopTimeout must be 60 seconds")
    port_flags = [
        api_command[i + 1] for i, token in enumerate(api_command[:-1]) if token == "--port"
    ]
    if port_flags != ["8000"]:
        fail("api: must listen on port 8000 only")
    verifier_command = by_name["verifier"].get("command", [])
    if "http://127.0.0.1:8080" not in verifier_command or "probe" not in verifier_command:
        fail("verifier: must probe the task-local engine at http://127.0.0.1:8080")
    if by_name["motis"].get("command", [None])[:3] != ["/motis", "server", "-d"]:
        fail("motis: must run `/motis server -d <graph>` like compose.yaml")
    motis_check = " ".join(by_name["motis"].get("healthCheck", {}).get("command", []))
    if "127.0.0.1:8080" not in motis_check:
        fail("motis: health check must probe the local engine on 8080")
    for name, c in by_name.items():
        check = c.get("healthCheck")
        if check is None:
            continue
        for field, (low, high) in ECS_HEALTH_LIMITS.items():
            if not low <= check.get(field, 0) <= high:
                fail(f"{name}: health check {field} must be within ECS limits {low}-{high}")
        if not 0 <= check.get("startPeriod", 0) <= ECS_MAX_START_PERIOD:
            fail(f"{name}: health check startPeriod must be at most {ECS_MAX_START_PERIOD}")
    api_check = by_name["api"].get("healthCheck", {})
    tolerance = api_check.get("startPeriod", 0) + api_check.get("interval", 0) * api_check.get(
        "retries", 0
    )
    if tolerance < MIN_API_HEALTH_TOLERANCE_SECONDS:
        fail(
            f"api: health check tolerates {tolerance} s of startup; the measured lifespan "
            f"needs at least {MIN_API_HEALTH_TOLERANCE_SECONDS} s"
        )
    if addresses:
        command = by_name["photon"].get("command", [])
        photon_check = " ".join(by_name["photon"].get("healthCheck", {}).get("command", []))
        if "127.0.0.1:2322/status" not in photon_check:
            fail("photon: health check must probe 127.0.0.1:2322/status")
        if command[command.index("-listen-ip") + 1 : command.index("-listen-ip") + 2] != [
            "127.0.0.1"
        ]:
            fail("photon: must listen on loopback")
        heap = next((HEAP.fullmatch(t) for t in command if HEAP.fullmatch(t)), None)
        if heap is None:
            fail("photon: -Xmx must be explicit")
        else:
            heap_mib = int(heap.group(1)) * (1024 if heap.group(2) in "gG" else 1)
            limit = by_name["photon"]["memory"]
            if heap_mib > 0.75 * limit:
                fail("photon: heap must be at most 75% of the container limit")
    for name, c in by_name.items():
        text = json.dumps(c)
        if re.search(r"(?<![0-9])(8080|2322|9201)\b", json.dumps(c.get("portMappings", []))):
            fail(f"{name}: engine/provider ports must not be published")
        if "0.0.0.0" in text and name != "api":
            fail(f"{name}: only the API may bind 0.0.0.0")
    return errors, warnings


def validate_candidate(task: dict, label: str, motis_digest: str | None = None):
    """Return (errors, warnings) for a rendered release candidate task definition.

    Applies every draft rule, then requires concrete image digests (no ``*_DIGEST``
    placeholders), the verifier on the API image, only account-specific placeholders left, and
    the release identity tags. Structural only: it says nothing about Fargate behavior.
    """
    errors, warnings = validate_task_definition(task, label, motis_digest, candidate=True)

    def fail(message: str) -> None:
        errors.append(f"{label}: {message}")

    containers = {c.get("name"): c for c in task.get("containerDefinitions", [])}
    for name, container in containers.items():
        if not CONCRETE_DIGEST.search(container.get("image", "")):
            fail(f"{name}: a release candidate pins a concrete sha256 digest")
    if "verifier" in containers and "api" in containers:
        if containers["verifier"].get("image") != containers["api"].get("image"):
            fail("verifier: must run the API image digest")
    text = json.dumps(task)
    leftover = set(PLACEHOLDER.findall(text)) - CANDIDATE_PLACEHOLDERS
    if leftover:
        fail(f"unresolved placeholders {sorted(leftover)}")
    for image in (c.get("image", "") for c in containers.values()):
        registry = image.split("/", 1)[0]
        if registry != "{{ECR_REGISTRY}}" and not ECR_REGISTRY.fullmatch(registry):
            fail(f"image registry {registry} must be the placeholder or a private ECR registry")
    for pattern in SECRET_PATTERNS[:-1]:  # account IDs are legitimate in a concrete candidate
        if pattern.search(text):
            fail(f"matches secret-like pattern {pattern.pattern[:30]}")
    tags = task.get("tags", [])
    if len(tags) > 50:
        fail("ECS allows at most 50 tags")
    values = {}
    for tag in tags:
        key, value = str(tag.get("key", "")), str(tag.get("value", ""))
        if not 1 <= len(key) <= 128 or not ECS_TAG_VALUE.fullmatch(value):
            fail(f"tag {key!r} violates the ECS tag limits")
        values[key] = value
    if values.get("purpose") != "h1-candidate":
        fail("tag purpose must be h1-candidate")
    for key, pattern in RELEASE_TAGS.items():
        if key not in values:
            fail(f"release tag {key} is required")
        elif not pattern.fullmatch(values[key]):
            fail(f"release tag {key} is malformed")
    return errors, warnings


def validate_service(service: dict) -> list[str]:
    errors: list[str] = []
    config = service.get("deploymentConfiguration", {})
    breaker = config.get("deploymentCircuitBreaker", {})
    checks = {
        "desiredCount must be 1": service.get("desiredCount") == 1,
        "rolling maximumPercent must be 200": config.get("maximumPercent") == 200,
        "rolling minimumHealthyPercent must be 100": config.get("minimumHealthyPercent") == 100,
        "circuit breaker with rollback is required": breaker == {"enable": True, "rollback": True},
        "platformVersion must be 1.4.0": service.get("platformVersion") == "1.4.0",
        "capacity must be on-demand FARGATE": service.get("capacityProviderStrategy")
        == [{"capacityProvider": "FARGATE", "weight": 1}],
        "ECS rolling controller is required": service.get("deploymentController")
        == {"type": "ECS"},
        "exec must be disabled": service.get("enableExecuteCommand") is False,
        f"health-check grace period must be at least {MIN_START_GRACE_SECONDS} s "
        "(measured cold start 717 s)": isinstance(service.get("healthCheckGracePeriodSeconds"), int)
        and service["healthCheckGracePeriodSeconds"] >= MIN_START_GRACE_SECONDS,
        "the only load balancer target is api:8000": [
            (b.get("containerName"), b.get("containerPort"))
            for b in service.get("loadBalancers", [])
        ]
        == [("api", 8000)],
    }
    errors += [f"service: {message}" for message, ok in checks.items() if not ok]
    network = service.get("networkConfiguration", {}).get("awsvpcConfiguration", {})
    if network.get("assignPublicIp") not in {"ENABLED", "DISABLED"}:
        errors.append("service: assignPublicIp must be explicit")
    if len(network.get("securityGroups", [])) != 1:
        errors.append("service: exactly one task security group is expected")
    if "scale" in json.dumps(service).lower():
        errors.append("service: autoscaling is out of scope for H-0")
    return errors


def validate_target_group(group: dict) -> list[str]:
    expected = {
        "Protocol": "HTTP",
        "Port": 8000,
        "TargetType": "ip",
        "HealthCheckPath": "/readyz",
        "HealthCheckIntervalSeconds": 10,
        "HealthCheckTimeoutSeconds": 2,
        "HealthyThresholdCount": 2,
        "UnhealthyThresholdCount": 2,
        "Matcher": {"HttpCode": "200"},
    }
    errors = [f"target group: {k} must be {v!r}" for k, v in expected.items() if group.get(k) != v]
    attributes = {a["Key"]: a["Value"] for a in group.get("Attributes", [])}
    if attributes.get("deregistration_delay.timeout_seconds") != "30":
        errors.append("target group: deregistration delay must be 30 seconds")
    if attributes.get("stickiness.enabled") != "false":
        errors.append("target group: stickiness must be off")
    return errors


def validate_load_balancer(document: dict) -> list[str]:
    errors = []
    balancer = document.get("loadBalancer", {})
    attributes = {a["Key"]: a["Value"] for a in balancer.get("Attributes", [])}
    for key in ("access_logs.s3.enabled", "connection_logs.s3.enabled"):
        if attributes.get(key) != "false":
            errors.append(f"load balancer: {key} must be false (logs carry client IP and URL)")
    listeners = document.get("listeners", [])
    if [(x.get("Protocol"), x.get("Port")) for x in listeners] != [("HTTPS", 443)]:
        errors.append("load balancer: only an HTTPS:443 listener is allowed")
    if balancer.get("Scheme") != "internet-facing" or balancer.get("Type") != "application":
        errors.append("load balancer: must be an internet-facing application balancer")
    return errors


def _statements(policy: dict) -> list[dict]:
    statements = policy.get("Statement", [])
    return statements if isinstance(statements, list) else [statements]


def validate_iam(execution_policy: dict, task_policy: dict, trusts: list[dict]) -> list[str]:
    errors = []
    allowed_ecr = {
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
    }
    for statement in _statements(execution_policy):
        actions = statement["Action"]
        actions = [actions] if isinstance(actions, str) else actions
        resources = statement["Resource"]
        resources = [resources] if isinstance(resources, str) else resources
        if statement.get("Effect") != "Allow":
            errors.append("execution policy: only Allow statements are expected")
        if "*" in resources and actions != ["ecr:GetAuthorizationToken"]:
            errors.append("execution policy: Resource * is only for ecr:GetAuthorizationToken")
        for action in actions:
            if action == "*" or action.endswith(":*"):
                errors.append(f"execution policy: wildcard action {action}")
            elif action.startswith("ecr:") and action not in allowed_ecr | {
                "ecr:GetAuthorizationToken"
            }:
                errors.append(f"execution policy: unexpected ECR action {action}")
            elif not action.startswith(("ecr:", "logs:")):
                errors.append(f"execution policy: unexpected service in {action}")
            elif action.startswith("logs:") and action not in {
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            }:
                errors.append(f"execution policy: unexpected logs action {action}")
        if any(a.startswith("logs:") for a in actions) and any(
            LOG_GROUP not in r or "*:*" in r for r in resources
        ):
            errors.append("execution policy: log permissions must target the draft log group")
        if any(a.startswith("ecr:Batch") for a in actions) and any(
            ":repository/opentransit-" not in r for r in resources
        ):
            errors.append("execution policy: ECR pulls must target named opentransit repositories")
    task_statements = _statements(task_policy)
    if any(s.get("Effect") == "Allow" for s in task_statements):
        errors.append("task policy: the serving task role must grant nothing")
    if not any(s.get("Effect") == "Deny" and s.get("Action") == "*" for s in task_statements):
        errors.append("task policy: expected the explicit deny-all guard")
    for index, trust in enumerate(trusts):
        statement = _statements(trust)[0]
        condition = statement.get("Condition", {})
        if statement.get("Principal") != {"Service": "ecs-tasks.amazonaws.com"}:
            errors.append(f"trust policy {index}: principal must be ecs-tasks.amazonaws.com")
        if "aws:SourceAccount" not in condition.get("StringEquals", {}) or "aws:SourceArn" not in (
            condition.get("ArnLike", {})
        ):
            errors.append(f"trust policy {index}: confused-deputy conditions are required")
    return errors


def validate_security_groups(groups: dict) -> list[str]:
    errors = []
    alb, task = groups["albSecurityGroup"], groups["taskSecurityGroup"]
    if [(r["fromPort"], r["toPort"], r.get("cidr")) for r in alb["ingress"]] != [
        (443, 443, "{{REVIEWER_CIDR}}")
    ]:
        errors.append("network: ALB ingress must be 443 from the reviewer range only")
    if [(r["fromPort"], r["toPort"], r.get("securityGroup")) for r in alb["egress"]] != [
        (8000, 8000, "taskSecurityGroup")
    ]:
        errors.append("network: ALB egress must be 8000 to the task group only")
    if [(r["fromPort"], r["toPort"], r.get("securityGroup")) for r in task["ingress"]] != [
        (8000, 8000, "albSecurityGroup")
    ]:
        errors.append("network: task ingress must be 8000 from the ALB group only")
    if [(r["fromPort"], r["toPort"]) for r in task["egress"]] != [(443, 443)]:
        errors.append("network: task egress is limited to 443")
    for group in (alb, task):
        for rule in group["ingress"] + group["egress"]:
            if rule.get("cidr") in {"0.0.0.0/0", "::/0"} and rule in group["ingress"]:
                errors.append("network: no ingress from the whole internet")
            if rule["protocol"] != "tcp":
                errors.append("network: only tcp rules are expected")
    return errors


def validate_log_group(group: dict) -> list[str]:
    errors = []
    if group.get("logGroupName") != LOG_GROUP:
        errors.append(f"log group: name must be {LOG_GROUP}")
    if group.get("retentionInDays") != 7:
        errors.append("log group: retention must be seven days")
    return errors


def scan_text(path: Path, text: str) -> list[str]:
    errors = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{path.name}: matches secret-like pattern {pattern.pattern[:30]}")
    for name in PLACEHOLDER.findall(text):
        if name not in KNOWN_PLACEHOLDERS:
            errors.append(f"{path.name}: unknown placeholder {{{{{name}}}}}")
    return errors


def compose_motis_digest(compose_path: Path) -> str | None:
    match = re.search(
        r"ghcr\.io/motis-project/motis@(sha256:[a-f0-9]{64})", compose_path.read_text("utf-8")
    )
    return match.group(1) if match else None


def validate_tree(aws_dir: Path = AWS_DIR, compose_path: Path | None = None):
    """Validate every committed draft; returns (errors, warnings, budgets)."""
    errors: list[str] = []
    warnings: list[str] = []
    budgets: dict[str, dict] = {}
    compose_path = compose_path or REPO_ROOT / "compose.yaml"
    digest = compose_motis_digest(compose_path) if compose_path.is_file() else None
    if digest is None:
        errors.append("compose.yaml: pinned MOTIS digest not found")

    def load(relative: str) -> dict:
        path = aws_dir / relative
        text = path.read_text(encoding="utf-8")
        errors.extend(scan_text(path, text))
        return json.loads(text)

    task_files = [
        "ecs/task-definition.json",
        *sorted(
            str(p.relative_to(aws_dir)).replace("\\", "/")
            for p in (aws_dir / "ecs" / "variants").glob("*.json")
        ),
    ]
    for relative in task_files:
        task = load(relative)
        task_errors, task_warnings = validate_task_definition(task, relative, digest)
        errors += task_errors
        warnings += task_warnings
        if not task_errors:
            budgets[relative] = budget(task)
        if budget(task)["replacementOverlapMiB"] > CEILING_MIB:
            errors.append(f"{relative}: two overlapping tasks exceed the 8 GiB ceiling")
        elif budget(task)["overlapHeadroomMiB"] < 1024:
            warnings.append(
                f"{relative}: overlap allocation leaves {budget(task)['overlapHeadroomMiB']} MiB "
                "of the 8 GiB ceiling for any task-hosted edge component"
            )
    errors += validate_service(load("ecs/service.json"))
    load("ecs/cluster.json")
    errors += validate_target_group(load("alb/target-group.json"))
    errors += validate_load_balancer(load("alb/load-balancer.json"))
    errors += validate_iam(
        load("iam/execution-role-policy.json"),
        load("iam/task-role-policy.json"),
        [load("iam/execution-role-trust.json"), load("iam/task-role-trust.json")],
    )
    errors += validate_security_groups(load("network/security-groups.json"))
    errors += validate_log_group(load("logs/log-group.json"))
    for relative in ("data-image/Dockerfile", "photon-image/Dockerfile", "local/compose.yaml"):
        path = aws_dir / relative
        if path.is_file():
            errors += scan_text(path, path.read_text(encoding="utf-8"))
    return errors, warnings, budgets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aws-dir", type=Path, default=AWS_DIR)
    args = parser.parse_args(argv)
    errors, warnings, budgets = validate_tree(args.aws_dir)
    for name, item in budgets.items():
        print(
            f"{name}: task {item['taskMemoryMiB']} MiB, containers {item['containerLimitSumMiB']}"
            f" MiB, overlap {item['replacementOverlapMiB']} MiB of {item['ceilingMiB']}"
        )
    for message in warnings:
        print(f"warning: {message}")
    for message in errors:
        print(f"error: {message}", file=sys.stderr)
    print("FAIL" if errors else "PASS (structural only; not a Fargate acceptance test)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
