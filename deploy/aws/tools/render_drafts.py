"""Render the ECS task-definition drafts and the matching local emulation from one source.

DRAFT ONLY: nothing here talks to AWS. ``{{TOKENS}}`` are placeholders that a future,
explicitly authorized deployment step must replace; the validator allows only the tokens in
``PLACEHOLDERS``. Run ``python deploy/aws/tools/render_drafts.py --write`` after editing, and
the unit tests fail if the committed files drift from this renderer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AWS_DIR = Path(__file__).resolve().parents[1]
REGION = "il-central-1"
LOG_GROUP = "/opentransit/h0"
MOTIS_DIGEST = "sha256:6055f51eec43eeed28524037ca0161b96efe9cd05728eaa9ac04c20c2826d330"
API_PORT = 8000
MOTIS_PORT = 8080
PHOTON_PORT = 2322
PHOTON_ADMIN_PORT = 9201
SERVICE_UID = "10001"

PLACEHOLDERS = {
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
    "VPC_CIDR",
    "TASK_DEFINITION_REVISION",
}

# Docker's default capability set minus CHOWN, DAC_OVERRIDE and FOWNER, which init needs.
INIT_DROPPED_CAPS = [
    "AUDIT_WRITE",
    "FSETID",
    "KILL",
    "MKNOD",
    "NET_BIND_SERVICE",
    "NET_RAW",
    "SETFCAP",
    "SETGID",
    "SETPCAP",
    "SETUID",
    "SYS_CHROOT",
]

PHOTON_COMMAND = [
    "java",
    "-Xms256m",
    "-Xmx512m",
    "-jar",
    "/opt/photon/photon-1.3.0.jar",
    "-data-dir",
    "/photon_data",
    "serve",
    "-listen-ip",
    "127.0.0.1",
    "-listen-port",
    str(PHOTON_PORT),
]

# MiB hard limits per container. Evidence: engine-only MOTIS peak 941 MB (September), Photon
# provider peak 429-448 MB at -Xmx512m under a 1 GiB cap, API 122-148 MB RSS (its cgroup peak
# equals the 512 MiB cap because SQLite page cache counts). None is a full-stack measurement.
VARIANTS = {
    "recommended": {
        "file": "ecs/task-definition.json",
        "family": "opentransit-h0",
        "cpu": "1024",
        "memory": "3072",
        "addresses": True,
        "limits": {"init": 192, "motis": 1280, "photon": 768, "verifier": 192, "api": 512},
    },
    "1vcpu-4gib": {
        "file": "ecs/variants/task-definition.1vcpu-4gib.json",
        "family": "opentransit-h0-4gib",
        "cpu": "1024",
        "memory": "4096",
        "addresses": True,
        "limits": {"init": 256, "motis": 1536, "photon": 1024, "verifier": 256, "api": 768},
    },
    "no-addresses": {
        "file": "ecs/variants/task-definition.no-addresses.json",
        "family": "opentransit-h0-no-addresses",
        "cpu": "512",
        "memory": "2048",
        "addresses": False,
        "limits": {"init": 128, "motis": 1280, "verifier": 128, "api": 512},
    },
}
COMPOSE_FILE = "local/compose.yaml"
# The local emulation has no ALB: the API sees the real TCP peer, so the proxy-trust token
# (which only a deployment step can resolve) is left out rather than rendered unparseable.
LOCAL_OMITTED_ENV = "OPENTRANSIT_TRUSTED_PROXIES"


def _logging(prefix: str) -> dict:
    return {
        "logDriver": "awslogs",
        "options": {
            "awslogs-group": LOG_GROUP,
            "awslogs-region": REGION,
            "awslogs-stream-prefix": prefix,
            "mode": "non-blocking",
            "max-buffer-size": "4m",
        },
    }


def _mount(volume: str, path: str, read_only: bool) -> dict:
    return {"sourceVolume": volume, "containerPath": path, "readOnly": read_only}


def _healthcheck(command: str, *, interval=15, timeout=5, retries=10, start_period=60) -> dict:
    """ECS bounds: interval 5-300 s, retries 1-10, startPeriod 0-300 s."""
    return {
        "command": ["CMD-SHELL", command],
        "interval": interval,
        "timeout": timeout,
        "retries": retries,
        "startPeriod": start_period,
    }


def _container(name: str, image: str, user: str, limit: int, **fields) -> dict:
    caps = {"drop": ["ALL"]} if name != "init" else {"drop": INIT_DROPPED_CAPS}
    container = {
        "name": name,
        "image": image,
        "essential": False,
        "user": user,
        "memory": limit,
        "readonlyRootFilesystem": True,
        "linuxParameters": {"capabilities": caps, "initProcessEnabled": True},
        "logConfiguration": _logging(name),
    }
    container.update(fields)
    head = ("name", "image", "essential", "user", "memory")
    return {
        **{key: container[key] for key in head},
        **dict(sorted((k, v) for k, v in container.items() if k not in head)),
    }


def render_task_definition(variant: str) -> dict:
    spec = VARIANTS[variant]
    limits = spec["limits"]
    addresses = spec["addresses"]
    motis_url = f"http://127.0.0.1:{MOTIS_PORT}"
    writable = ["/run/opentransit", "/scratch/api", "/scratch/motis"]
    init_mounts = [
        _mount("generation", "/generation", False),
        _mount("probe", "/run/opentransit", False),
        _mount("tmp-api", "/scratch/api", False),
        _mount("tmp-motis", "/scratch/motis", False),
    ]
    volumes = ["generation", "probe", "tmp-api", "tmp-motis"]
    init_args = [
        "--payload",
        "/payload",
        "--generation-dir",
        "/generation",
        "--uid",
        SERVICE_UID,
        "--gid",
        SERVICE_UID,
    ]
    if addresses:
        init_args += ["--photon-dir", "/photon_data"]
        writable.append("/scratch/photon")
        init_mounts += [
            _mount("photon-data", "/photon_data", False),
            _mount("tmp-photon", "/scratch/photon", False),
        ]
        volumes += ["photon-data", "tmp-photon"]
    for path in writable:
        init_args += ["--writable-dir", path]

    ecr = "{{ECR_REGISTRY}}"
    containers = [
        _container(
            "init",
            f"{ecr}/opentransit-data@{{{{DATA_DIGEST}}}}",
            "0",
            limits["init"],
            command=init_args,
            mountPoints=init_mounts,
        ),
        _container(
            "motis",
            f"{ecr}/opentransit-motis@{MOTIS_DIGEST}",
            SERVICE_UID,
            limits["motis"],
            essential=True,
            command=["/motis", "server", "-d", "/generation/motis"],
            dependsOn=[{"containerName": "init", "condition": "SUCCESS"}],
            startTimeout=900,
            stopTimeout=30,
            mountPoints=[
                _mount("generation", "/generation", True),
                _mount("tmp-motis", "/tmp", False),
            ],
            healthCheck=_healthcheck(
                f"wget -qO- 'http://127.0.0.1:{MOTIS_PORT}/api/v6/plan"
                "?fromPlace=32.0836,34.7981&toPlace=32.0838,34.8044' >/dev/null 2>&1 || exit 1"
            ),
        ),
    ]
    if addresses:
        containers.append(
            _container(
                "photon",
                f"{ecr}/opentransit-photon@{{{{PHOTON_DIGEST}}}}",
                SERVICE_UID,
                limits["photon"],
                essential=True,
                command=PHOTON_COMMAND,
                dependsOn=[{"containerName": "init", "condition": "SUCCESS"}],
                startTimeout=900,
                stopTimeout=30,
                mountPoints=[
                    _mount("photon-data", "/photon_data", False),
                    _mount("tmp-photon", "/tmp", False),
                ],
                healthCheck=_healthcheck(
                    f"curl -fsS http://127.0.0.1:{PHOTON_PORT}/status >/dev/null || exit 1",
                    interval=20,
                    retries=9,
                    start_period=120,
                ),
            )
        )
    api_image = f"{ecr}/opentransit-api@{{{{API_DIGEST}}}}"
    containers.append(
        _container(
            "verifier",
            api_image,
            SERVICE_UID,
            limits["verifier"],
            command=[
                "/app/.venv/bin/opentransit",
                "probe",
                "--generation",
                "/generation",
                "--engine-url",
                motis_url,
                "--queries",
                "/generation/probe-queries.json",
                "--output",
                "/run/opentransit/probe.json",
            ],
            dependsOn=[
                {"containerName": "init", "condition": "SUCCESS"},
                {"containerName": "motis", "condition": "HEALTHY"},
            ],
            startTimeout=600,
            environment=[
                {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"},
                {"name": "TMPDIR", "value": "/run/opentransit"},
            ],
            mountPoints=[
                _mount("generation", "/generation", True),
                _mount("probe", "/run/opentransit", False),
            ],
        )
    )
    api_env = [
        {"name": "OPENTRANSIT_MANIFEST", "value": "/generation/manifest.json"},
        {"name": "OPENTRANSIT_MOTIS_URL", "value": motis_url},
        {"name": "OPENTRANSIT_PROBE", "value": "/run/opentransit/probe.json"},
        # Explicit even though 1 is the default. The ALB is the only peer, so its VPC range is
        # trusted for X-Forwarded-For; the deployment step substitutes the real CIDR for the token.
        {"name": "OPENTRANSIT_RATE_LIMIT_ENABLED", "value": "1"},
        {"name": "OPENTRANSIT_TRUSTED_PROXIES", "value": "{{VPC_CIDR}}"},
    ]
    api_depends = [
        {"containerName": "verifier", "condition": "SUCCESS"},
        {"containerName": "motis", "condition": "HEALTHY"},
    ]
    if addresses:
        api_env += [
            {
                "name": "OPENTRANSIT_PHOTON_ADMIN_URL",
                "value": f"http://127.0.0.1:{PHOTON_ADMIN_PORT}",
            },
            {"name": "OPENTRANSIT_PHOTON_URL", "value": f"http://127.0.0.1:{PHOTON_PORT}"},
        ]
        api_depends.append({"containerName": "photon", "condition": "HEALTHY"})
    api_env.append({"name": "PYTHONDONTWRITEBYTECODE", "value": "1"})
    containers.append(
        _container(
            "api",
            api_image,
            SERVICE_UID,
            limits["api"],
            essential=True,
            command=[
                "/app/.venv/bin/uvicorn",
                "opentransit.api.app:create_app",
                "--factory",
                "--host",
                "0.0.0.0",
                "--port",
                str(API_PORT),
                "--no-access-log",
                "--log-level",
                "info",
                "--timeout-graceful-shutdown",
                "25",
            ],
            dependsOn=api_depends,
            startTimeout=900,
            stopTimeout=60,
            environment=api_env,
            portMappings=[{"containerPort": API_PORT, "protocol": "tcp", "name": "api"}],
            mountPoints=[
                _mount("generation", "/generation", True),
                _mount("probe", "/run/opentransit", True),
                _mount("tmp-api", "/tmp", False),
            ],
            healthCheck=_healthcheck(
                '/app/.venv/bin/python -c "import urllib.request;'
                f"urllib.request.urlopen('http://127.0.0.1:{API_PORT}/healthz',timeout=2)\" "
                "|| exit 1",
                # Lifespan (reference hash + integrity check) measured 338 s on one core;
                # 300 s start period (ECS maximum) + 10 x 30 s tolerates 600 s.
                interval=30,
                retries=10,
                start_period=300,
            ),
        )
    )
    return {
        "family": spec["family"],
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["FARGATE"],
        "cpu": spec["cpu"],
        "memory": spec["memory"],
        "runtimePlatform": {"cpuArchitecture": "X86_64", "operatingSystemFamily": "LINUX"},
        "ephemeralStorage": {"sizeInGiB": 20},
        "executionRoleArn": "{{EXECUTION_ROLE_ARN}}",
        "containerDefinitions": containers,
        "volumes": [{"name": name} for name in volumes],
        "tags": [
            {"key": "project", "value": "opentransit"},
            {"key": "purpose", "value": "h0-draft"},
        ],
    }


def _yaml_scalar(value: object) -> str:
    return json.dumps(value)  # JSON strings/numbers/lists are valid YAML flow scalars


def render_local_compose(variant: str = "recommended") -> str:
    """Docker Compose emulation of one task definition (shared netns, same limits and mounts)."""
    task = render_task_definition(variant)
    spec = VARIANTS[variant]
    one_cpu = spec["cpu"] == "1024"
    lines = [
        "# GENERATED by deploy/aws/tools/render_drafts.py from",
        f"# {spec['file']} -- do not edit by hand. Local emulation only: not a Fargate test.",
        "# Images are local tags (see deploy/aws/README.md); MOTIS keeps its pinned digest.",
        f"name: ot-t5-h0-{variant}",
        "services:",
    ]
    local_image = {
        "init": "ot-t5-data:local",
        "photon": "ot-t5-photon:local",
        "verifier": "ot-t5-api:local",
        "api": "ot-t5-api:local",
    }
    for container in task["containerDefinitions"]:
        name = container["name"]
        image = (
            container["image"].replace(
                "{{ECR_REGISTRY}}/opentransit-motis", "ghcr.io/motis-project/motis"
            )
            if name == "motis"
            else local_image[name]
        )
        limit = f"{container['memory']}m"
        lines.append(f"  {name}:")
        lines.append(f"    container_name: ot-t5-{name}")
        lines.append(f"    image: {image}")
        lines.append(f"    user: {_yaml_scalar(container['user'])}")
        lines.append("    read_only: true")
        lines.append(f"    mem_limit: {limit}")
        lines.append(f"    memswap_limit: {limit}")
        if one_cpu:
            lines.append('    cpuset: "0"')
        drops = container["linuxParameters"]["capabilities"]["drop"]
        lines.append(f"    cap_drop: {_yaml_scalar(drops)}")
        lines.append("    init: true")
        lines.append(f"    command: {_yaml_scalar(container['command'])}")
        if name == "init":
            lines.append("    network_mode: none")
        elif name == "motis":
            lines.append('    ports: ["127.0.0.1:58500:8000"]')
        else:
            lines.append('    network_mode: "service:motis"')
        if "environment" in container:
            lines.append("    environment:")
            for item in container["environment"]:
                if item["name"] == LOCAL_OMITTED_ENV:
                    continue
                lines.append(f"      {item['name']}: {_yaml_scalar(item['value'])}")
        lines.append("    volumes:")
        for mount in container["mountPoints"]:
            suffix = ":ro" if mount["readOnly"] else ""
            lines.append(f"      - {mount['sourceVolume']}:{mount['containerPath']}{suffix}")
        if "healthCheck" in container:
            check = container["healthCheck"]
            lines.append("    healthcheck:")
            lines.append(f"      test: {_yaml_scalar(check['command'])}")
            lines.append(f"      interval: {check['interval']}s")
            lines.append(f"      timeout: {check['timeout']}s")
            lines.append(f"      retries: {check['retries']}")
            lines.append(f"      start_period: {check['startPeriod']}s")
        if "stopTimeout" in container:
            lines.append(f"    stop_grace_period: {container['stopTimeout']}s")
        if "dependsOn" in container:
            lines.append("    depends_on:")
            for dependency in container["dependsOn"]:
                condition = {
                    "SUCCESS": "service_completed_successfully",
                    "HEALTHY": "service_healthy",
                }[dependency["condition"]]
                lines.append(f"      {dependency['containerName']}:")
                lines.append(f"        condition: {condition}")
    lines.append("volumes:")
    for volume in task["volumes"]:
        lines.append(f"  {volume['name']}: {{}}")
    return "\n".join(lines) + "\n"


def render_all() -> dict[str, str]:
    """Relative path -> file text for every generated draft."""
    outputs = {
        spec["file"]: json.dumps(render_task_definition(name), indent=2) + "\n"
        for name, spec in VARIANTS.items()
    }
    outputs[COMPOSE_FILE] = render_local_compose("recommended")
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite the committed drafts")
    parser.add_argument(
        "--print-compose",
        choices=sorted(VARIANTS),
        help="print the local Compose emulation of one variant and exit",
    )
    args = parser.parse_args(argv)
    if args.print_compose:
        sys.stdout.write(render_local_compose(args.print_compose))
        return 0
    outputs = render_all()
    stale = []
    for relative, text in outputs.items():
        path = AWS_DIR / relative
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        elif not path.is_file() or path.read_text(encoding="utf-8") != text:
            stale.append(relative)
    if stale:
        print("drafts differ from the renderer: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
