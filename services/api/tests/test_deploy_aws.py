"""Structural tests for the AWS H-0 drafts under deploy/aws (no cloud access, no Docker).

These prove the drafts agree with the written plan and the repository's own pins. They do not
prove Fargate behavior; that remains the bounded H-0 test.
"""

import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
AWS = REPO / "deploy" / "aws"
pytestmark = pytest.mark.skipif(not AWS.is_dir(), reason="deploy/aws is not part of this checkout")


def _load(name: str, relative: str):
    path = AWS / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validate = _load("aws_validate_drafts", "tools/validate_drafts.py") if AWS.is_dir() else None
render = _load("aws_render_drafts", "tools/render_drafts.py") if AWS.is_dir() else None
init = _load("aws_init_generation", "data-image/init_generation.py") if AWS.is_dir() else None
stage = _load("aws_stage_bundle", "tools/stage_bundle.py") if AWS.is_dir() else None


def _digest() -> str:
    return validate.compose_motis_digest(REPO / "compose.yaml")


def _task(variant="recommended") -> dict:
    return json.loads((AWS / render.VARIANTS[variant]["file"]).read_text(encoding="utf-8"))


def _container(task: dict, name: str) -> dict:
    return next(c for c in task["containerDefinitions"] if c["name"] == name)


# --- committed drafts ---------------------------------------------------------------------


def test_committed_drafts_validate_cleanly():
    errors, _warnings, budgets = validate.validate_tree()
    assert errors == []
    assert set(budgets) == {
        "ecs/task-definition.json",
        "ecs/variants/task-definition.1vcpu-4gib.json",
        "ecs/variants/task-definition.no-addresses.json",
    }


def test_committed_drafts_match_the_renderer():
    for relative, text in render.render_all().items():
        assert (AWS / relative).read_text(encoding="utf-8") == text, relative


def test_recommended_budget_and_overlap_numbers():
    item = validate.budget(_task())
    assert item["taskMemoryMiB"] == 3072 and item["cpuUnits"] == 1024
    assert item["containerLimitSumMiB"] == 2944 and item["unallocatedMiB"] == 128
    assert item["replacementOverlapMiB"] == 6144 and item["overlapHeadroomMiB"] == 2048
    four = validate.budget(_task("1vcpu-4gib"))
    assert four["replacementOverlapMiB"] == validate.CEILING_MIB  # equals, never exceeds
    assert four["overlapHeadroomMiB"] == 0


def test_dependency_graph_is_exactly_the_specified_order():
    task = _task()
    deps = {
        c["name"]: {d["containerName"]: d["condition"] for d in c.get("dependsOn", [])}
        for c in task["containerDefinitions"]
    }
    assert deps == {
        "init": {},
        "motis": {"init": "SUCCESS"},
        "photon": {"init": "SUCCESS"},
        "verifier": {"init": "SUCCESS", "motis": "HEALTHY"},
        "api": {"verifier": "SUCCESS", "motis": "HEALTHY", "photon": "HEALTHY"},
    }
    essential = {c["name"]: c["essential"] for c in task["containerDefinitions"]}
    assert essential == {
        "init": False,
        "motis": True,
        "photon": True,
        "verifier": False,
        "api": True,
    }
    assert validate._topological({k: set(v) for k, v in deps.items()}) == [
        "init",
        "motis",
        "photon",
        "verifier",
        "api",
    ]


def test_only_port_8000_is_published_and_no_secrets_anywhere():
    for variant in render.VARIANTS:
        task = _task(variant)
        ports = [
            (c["name"], p["containerPort"])
            for c in task["containerDefinitions"]
            for p in c.get("portMappings", [])
        ]
        assert ports == [("api", 8000)]
        text = json.dumps(task)
        assert '"secrets"' not in text and "taskRoleArn" not in text
    api = _container(_task(), "api")
    env = {e["name"]: e["value"] for e in api["environment"]}
    assert env["OPENTRANSIT_MOTIS_URL"] == "http://127.0.0.1:8080"
    assert "--no-access-log" in api["command"] and "--workers" not in api["command"]


def test_no_addresses_variant_has_no_photon_anywhere():
    task = _task("no-addresses")
    assert {c["name"] for c in task["containerDefinitions"]} == {
        "init",
        "motis",
        "verifier",
        "api",
    }
    assert "photon" not in json.dumps(task).lower()


def test_pins_match_the_repository():
    from opentransit.core.artifacts import JAVA_21_IMAGE_DIGEST, PHOTON_130_JAR_SHA256

    assert render.MOTIS_DIGEST == _digest()
    photon = (AWS / "photon-image" / "Dockerfile").read_text(encoding="utf-8")
    assert JAVA_21_IMAGE_DIGEST in photon and PHOTON_130_JAR_SHA256 in photon
    api_base = re.search(
        r"^FROM (python:\S+@sha256:[a-f0-9]{64})$",
        (REPO / "services" / "api" / "Dockerfile").read_text(encoding="utf-8"),
        re.MULTILINE,
    ).group(1)
    assert api_base in (AWS / "data-image" / "Dockerfile").read_text(encoding="utf-8")


def test_local_compose_uses_the_task_definition_limits():
    text = (AWS / "local" / "compose.yaml").read_text(encoding="utf-8")
    for container in _task()["containerDefinitions"]:
        block = text.split(f"\n  {container['name']}:\n", 1)[1].split("\n  ", 1)[0]
        assert (
            f"mem_limit: {container['memory']}m"
            in text.split(f"container_name: ot-t5-{container['name']}", 1)[1].split(
                "container_name", 1
            )[0]
        )
        assert block  # block found


# --- the validator rejects the violations it exists to catch -------------------------------


def _mutations():
    def api(task):
        return _container(task, "api")

    def add_port(task):
        _container(task, "motis")["portMappings"] = [{"containerPort": 8080, "protocol": "tcp"}]

    def second_api_port(task):
        api(task)["portMappings"].append({"containerPort": 9201, "protocol": "tcp"})

    def cycle(task):
        _container(task, "init")["dependsOn"] = [{"containerName": "api", "condition": "SUCCESS"}]

    def success_on_essential(task):
        _container(task, "verifier")["dependsOn"][1]["condition"] = "SUCCESS"

    def missing_edge(task):
        api(task)["dependsOn"] = [
            d for d in api(task)["dependsOn"] if d["containerName"] != "photon"
        ]

    def overflow(task):
        _container(task, "motis")["memory"] += 1024

    def invalid_size(task):
        task["memory"] = "3000"

    def invalid_combination(task):
        task["cpu"], task["memory"] = "512", "8192"

    def secrets(task):
        api(task)["secrets"] = [{"name": "X", "valueFrom": "arn:aws:ssm:::parameter/x"}]

    def secret_env(task):
        api(task)["environment"].append({"name": "SERVICE_TOKEN", "value": "x"})

    def api_root(task):
        api(task)["user"] = "0"

    def writable_root(task):
        api(task)["readonlyRootFilesystem"] = False

    def rw_generation(task):
        _container(task, "motis")["mountPoints"][0]["readOnly"] = False

    def motis_url(task):
        for env in api(task)["environment"]:
            if env["name"] == "OPENTRANSIT_MOTIS_URL":
                env["value"] = "http://motis:8080"

    def access_log(task):
        api(task)["command"].remove("--no-access-log")

    def task_role(task):
        task["taskRoleArn"] = "{{EXECUTION_ROLE_ARN}}"

    def unpinned(task):
        _container(task, "motis")["image"] = "ghcr.io/motis-project/motis:latest"

    def wrong_motis_digest(task):
        _container(task, "motis")["image"] = "{{ECR_REGISTRY}}/opentransit-motis@sha256:" + "0" * 64

    def no_health(task):
        del _container(task, "motis")["healthCheck"]

    def photon_heap(task):
        command = _container(task, "photon")["command"]
        command[command.index("-Xmx512m")] = "-Xmx700m"

    def photon_public(task):
        command = _container(task, "photon")["command"]
        command[command.index("127.0.0.1")] = "0.0.0.0"

    def host_volume(task):
        task["volumes"][0] = {"name": "generation", "host": {"sourcePath": "/data"}}

    def logs_group(task):
        api(task)["logConfiguration"]["options"]["awslogs-group"] = "/other"

    def init_caps(task):
        _container(task, "init")["linuxParameters"]["capabilities"]["drop"] = []

    def ecs_retry_limit(task):
        _container(task, "motis")["healthCheck"]["retries"] = 12

    def api_check_shorter_than_startup(task):
        api(task)["healthCheck"].update(interval=10, retries=3, startPeriod=30)

    return {
        "extra-engine-port": add_port,
        "second-api-port": second_api_port,
        "dependency-cycle": cycle,
        "success-on-essential": success_on_essential,
        "missing-photon-edge": missing_edge,
        "memory-overflow": overflow,
        "invalid-task-size": invalid_size,
        "invalid-cpu-memory-combination": invalid_combination,
        "secrets-block": secrets,
        "secret-looking-env": secret_env,
        "api-root": api_root,
        "writable-root-fs": writable_root,
        "writable-generation-mount": rw_generation,
        "motis-url": motis_url,
        "access-log-enabled": access_log,
        "task-role-attached": task_role,
        "unpinned-image": unpinned,
        "wrong-motis-digest": wrong_motis_digest,
        "healthy-dependency-without-check": no_health,
        "photon-heap-too-large": photon_heap,
        "photon-public-listener": photon_public,
        "host-volume": host_volume,
        "wrong-log-group": logs_group,
        "init-keeps-capabilities": init_caps,
        "health-check-beyond-ecs-limits": ecs_retry_limit,
        "api-check-shorter-than-measured-startup": api_check_shorter_than_startup,
    }


@pytest.mark.parametrize("name", sorted(_mutations()) if AWS.is_dir() else [])
def test_validator_rejects_violation(name):
    task = copy.deepcopy(_task())
    _mutations()[name](task)
    errors, _ = validate.validate_task_definition(task, "t", _digest())
    assert errors, f"{name} was not detected"


def test_validator_rejects_four_gib_overlap_beyond_ceiling():
    task = copy.deepcopy(_task("1vcpu-4gib"))
    task["memory"] = "5120"
    assert validate.budget(task)["overlapHeadroomMiB"] < 0


def test_service_target_group_and_edge_rules():
    service = json.loads((AWS / "ecs" / "service.json").read_text(encoding="utf-8"))
    assert validate.validate_service(service) == []
    for mutate in (
        lambda s: s["deploymentConfiguration"].update(maximumPercent=100),
        lambda s: s["deploymentConfiguration"].update(minimumHealthyPercent=50),
        lambda s: s["deploymentConfiguration"]["deploymentCircuitBreaker"].update(rollback=False),
        lambda s: s.update(desiredCount=2),
        lambda s: s["loadBalancers"][0].update(containerName="motis", containerPort=8080),
        lambda s: s.update(
            capacityProviderStrategy=[{"capacityProvider": "FARGATE_SPOT", "weight": 1}]
        ),
        # Shorter than the measured local cold start (717 s to /readyz 200).
        lambda s: s.update(healthCheckGracePeriodSeconds=600),
    ):
        broken = copy.deepcopy(service)
        mutate(broken)
        assert validate.validate_service(broken)
    group = json.loads((AWS / "alb" / "target-group.json").read_text(encoding="utf-8"))
    assert validate.validate_target_group(group) == []
    group["HealthCheckPath"] = "/healthz"
    assert validate.validate_target_group(group)
    balancer = json.loads((AWS / "alb" / "load-balancer.json").read_text(encoding="utf-8"))
    balancer["loadBalancer"]["Attributes"][0]["Value"] = "true"
    assert validate.validate_load_balancer(balancer)


def test_iam_and_network_rules():
    def read(path):
        return json.loads((AWS / path).read_text(encoding="utf-8"))

    execution, task_policy = (
        read("iam/execution-role-policy.json"),
        read("iam/task-role-policy.json"),
    )
    trusts = [read("iam/execution-role-trust.json"), read("iam/task-role-trust.json")]
    assert validate.validate_iam(execution, task_policy, trusts) == []
    wide = copy.deepcopy(execution)
    wide["Statement"][1]["Action"].append("ecr:*")
    assert validate.validate_iam(wide, task_policy, trusts)
    granted = copy.deepcopy(task_policy)
    granted["Statement"].append({"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"})
    assert validate.validate_iam(execution, granted, trusts)
    groups = read("network/security-groups.json")
    assert validate.validate_security_groups(groups) == []
    open_engine = copy.deepcopy(groups)
    open_engine["taskSecurityGroup"]["ingress"].append(
        {"protocol": "tcp", "fromPort": 8080, "toPort": 8080, "cidr": "0.0.0.0/0"}
    )
    assert validate.validate_security_groups(open_engine)
    assert validate.validate_log_group(read("logs/log-group.json")) == []


def test_scan_flags_secret_like_text_and_unknown_placeholders(tmp_path):
    path = tmp_path / "x.json"
    assert validate.scan_text(path, '{"a": "AKIAABCDEFGHIJKLMNOP"}')
    assert validate.scan_text(path, '{"a": "123456789012"}')
    assert validate.scan_text(path, '{"a": "{{NOT_A_TOKEN}}"}')
    assert (
        validate.scan_text(path, '{"a": "{{ACCOUNT_ID}}", "b": "sha256:' + "ab" * 32 + '"}') == []
    )


# --- data-initialization image logic ------------------------------------------------------


def _write(path: Path, data: bytes) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _payload(tmp_path, *, photon=False, graph_config=b"osm: x\n"):
    payload = tmp_path / "payload"
    files = []

    def add(src, root, dst, data):
        info = _write(payload / src, data)
        files.append({"src": src, "root": root, "dst": dst, **info})

    add(
        "small/manifest.json",
        "generation",
        "manifest.json",
        json.dumps({"generationId": "a" * 64}).encode(),
    )
    add("reference/reference.sqlite", "generation", "reference.sqlite", b"sqlite" * 100)
    add("graph/tt.bin", "generation", "motis/tt.bin", b"graph" * 50)
    add("graph/config.yml", "generation", "motis/config.yml", graph_config)
    attestation = {}
    if photon:
        entries = []
        for rel, data in (("photon_data/node_1/a", b"index"), ("photon_data/node_1/empty", b"")):
            add(f"photon/{rel}", "photon", rel, data)
            entries.append(files[-1])
        attestation = {
            "checkpoint": {
                "treeSha256": init.tree_sha256(
                    [
                        {"path": e["dst"], "bytes": e["bytes"], "sha256": e["sha256"]}
                        for e in entries
                    ]
                ),
                "files": len(entries),
                "bytes": sum(e["bytes"] for e in entries),
            }
        }
        add(
            "small/photon-import-attestation.json",
            "generation",
            "photon-import-attestation.json",
            json.dumps(attestation).encode(),
        )
    (payload / "payload-manifest.json").write_text(
        json.dumps({"schemaVersion": 1, "generationId": "a" * 64, "files": files}),
        encoding="utf-8",
    )
    return payload, attestation


def _args(tmp_path, payload):
    generation, photon, scratch = tmp_path / "gen", tmp_path / "photon", tmp_path / "scratch"
    for directory in (generation, photon, scratch):
        directory.mkdir()
    argv = [
        "--payload", str(payload),
        "--generation-dir", str(generation),
        "--photon-dir", str(photon),
        "--writable-dir", str(scratch),
    ]  # fmt: skip
    return argv, generation, photon


def test_init_copies_and_verifies_a_schedule_only_generation(tmp_path):
    payload, _ = _payload(tmp_path)
    argv, generation, photon = _args(tmp_path, payload)
    assert init.main(argv) == 0
    assert (generation / "motis" / "tt.bin").read_bytes() == b"graph" * 50
    assert list(photon.iterdir()) == []


def test_init_copies_photon_tree_bound_to_the_attestation(tmp_path):
    payload, _ = _payload(tmp_path, photon=True)
    argv, generation, photon = _args(tmp_path, payload)
    assert init.main(argv) == 0
    assert (photon / "photon_data" / "node_1" / "a").read_bytes() == b"index"
    assert (photon / "photon_data" / "node_1" / "empty").exists()


def test_init_rejects_a_corrupt_source_without_leaving_success(tmp_path, capsys):
    payload, _ = _payload(tmp_path)
    (payload / "graph" / "tt.bin").write_bytes(b"tampered")
    argv, _, _ = _args(tmp_path, payload)
    assert init.main(argv) == 3
    assert "init_failed" in capsys.readouterr().out


def test_init_refuses_non_empty_targets_and_never_overwrites(tmp_path):
    payload, _ = _payload(tmp_path)
    argv, generation, _ = _args(tmp_path, payload)
    (generation / "stale").write_text("x", encoding="utf-8")
    assert init.main(argv) == 4
    assert (generation / "stale").read_text(encoding="utf-8") == "x"


def test_init_rejects_a_local_engine_slot_graph_config(tmp_path):
    config = b"server:\n  host: 127.0.0.1\n  port: 59081\nosm: x\n"
    payload, _ = _payload(tmp_path, graph_config=config)
    argv, _, _ = _args(tmp_path, payload)
    assert init.main(argv) == 5
    ok = b"server:\n  host: 127.0.0.1\n  port: 8080\nosm: x\n"
    other = tmp_path / "second"
    other.mkdir()
    payload, _ = _payload(other, graph_config=ok)
    argv, _, _ = _args(other, payload)
    assert init.main(argv) == 0


def test_init_rejects_photon_data_that_differs_from_the_sealed_checkpoint(tmp_path):
    payload, _ = _payload(tmp_path, photon=True)
    manifest_path = payload / "payload-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    attestation_entry = next(f for f in manifest["files"] if f["dst"].endswith("attestation.json"))
    attestation = json.loads((payload / attestation_entry["src"]).read_text(encoding="utf-8"))
    attestation["checkpoint"]["treeSha256"] = "0" * 64
    info = _write(payload / attestation_entry["src"], json.dumps(attestation).encode())
    attestation_entry.update(info)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    argv, _, _ = _args(tmp_path, payload)
    assert init.main(argv) == 5


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m.update(schemaVersion=2),
        lambda m: m.update(generationId="short"),
        lambda m: m["files"][0].update(dst="../escape"),
        lambda m: m["files"][0].update(src="/abs"),
        lambda m: m["files"][0].update(root="elsewhere"),
        lambda m: m["files"].append(dict(m["files"][0])),
        lambda m: m.update(files=[]),
    ],
)
def test_init_rejects_malformed_payload_manifests(tmp_path, mutate):
    payload, _ = _payload(tmp_path)
    manifest_path = payload / "payload-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    argv, _, _ = _args(tmp_path, payload)
    assert init.main(argv) == 2


def test_init_requires_the_manifest_generation_to_match(tmp_path):
    payload, _ = _payload(tmp_path)
    manifest_path = payload / "payload-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generationId"] = "b" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    argv, _, _ = _args(tmp_path, payload)
    assert init.main(argv) == 5


# --- host-side staging ---------------------------------------------------------------------


def _generation(tmp_path, *, port=None):
    root = tmp_path / "generation"
    reference = _write(root / "reference.sqlite", b"reference-bytes")
    config = _write(root / "config.yml", b"osm: /input/x\n")
    graph_config = b"osm: x\n" if port is None else f"server:\n  port: {port}\n".encode()
    files = []
    for rel, data in (
        ("config.yml", graph_config),
        ("tt.bin", b"timetable"),
        ("adr/a.bin", b"adr"),
    ):
        files.append({"path": rel, **_write(root / "motis" / rel, data)})
    files.sort(key=lambda item: item["path"])
    digest = hashlib.sha256()
    for item in files:
        digest.update(f"{item['path']}\0{item['bytes']}\0{item['sha256']}\n".encode())
    manifest = {
        "schemaVersion": 1,
        "state": "ready",
        "generationId": "c" * 64,
        "engineDigest": "sha256:" + "d" * 64,
        "artifacts": {
            "reference": {"path": "reference.sqlite", "sha256": reference["sha256"]},
            "config": {"path": "config.yml", "sha256": config["sha256"]},
            "motis": {"path": "motis", "files": files, "sha256": digest.hexdigest()},
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_stage_bundle_lists_every_artifact_once(tmp_path):
    generation = _generation(tmp_path)
    queries = tmp_path / "probe.json"
    queries.write_text("[]", encoding="utf-8")
    out = tmp_path / "staged"
    result = stage.stage(generation, out, probe_queries=queries, force_copy=True)
    assert result["generationId"] == "c" * 64 and result["addressSearch"] is False
    assert (out / "payload" / "photon" / ".keep").exists()
    destinations = [f["dst"] for f in result["files"]]
    assert len(destinations) == len(set(destinations))
    assert {"manifest.json", "reference.sqlite", "probe-queries.json", "motis/tt.bin"} <= set(
        destinations
    )


def test_stage_keeps_zero_byte_graph_files_the_manifest_omits(tmp_path):
    """The graph digest skips empty files, but MOTIS opens them (routed_shapes_* on oct1b)."""
    generation = _generation(tmp_path)
    (generation / "motis" / "routed_shapes_data.bin").write_bytes(b"")
    result = stage.stage(generation, tmp_path / "staged", force_copy=True)
    entry = next(f for f in result["files"] if f["dst"] == "motis/routed_shapes_data.bin")
    assert entry["bytes"] == 0 and entry["sha256"] == hashlib.sha256(b"").hexdigest()
    assert (tmp_path / "staged" / "payload" / "graph" / "routed_shapes_data.bin").is_file()


def test_stage_layout_matches_the_dockerfile_copies(tmp_path):
    """payload/* plus payload-manifest.json land together under /payload in the image."""
    generation = _generation(tmp_path)
    out = tmp_path / "staged"
    stage.stage(generation, out, force_copy=True)
    image = tmp_path / "image-payload"
    for name in ("reference", "graph", "photon", "small"):
        source = out / "payload" / name
        target = image / name
        target.mkdir(parents=True)
        for path in source.rglob("*"):
            if path.is_file():
                destination = target / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(path.read_bytes())
    (image / "payload-manifest.json").write_bytes((out / "payload-manifest.json").read_bytes())
    gen, photon, scratch = tmp_path / "g", tmp_path / "p", tmp_path / "s"
    for directory in (gen, photon, scratch):
        directory.mkdir()
    assert (
        init.main(
            [
                "--payload",
                str(image),
                "--generation-dir",
                str(gen),
                "--photon-dir",
                str(photon),
                "--writable-dir",
                str(scratch),
            ]
        )  # fmt: skip
        == 0
    )
    assert (gen / "motis" / "adr" / "a.bin").read_bytes() == b"adr"
    dockerfile = (AWS / "data-image" / "Dockerfile").read_text(encoding="utf-8")
    for name in ("reference", "graph", "photon", "small"):
        assert f"payload/{name}/ /payload/{name}/" in dockerfile


def test_stage_refuses_slot_graph_existing_output_and_mismatched_photon(tmp_path):
    slot = _generation(tmp_path, port=59081)
    with pytest.raises(ValueError, match="local-engine-slot"):
        stage.stage(slot, tmp_path / "o1", force_copy=True)
    plain = tmp_path / "plain"
    plain.mkdir()
    generation = _generation(plain)
    with pytest.raises(ValueError, match="without address search"):
        stage.stage(generation, plain / "o2", photon_data=plain, force_copy=True)
    (plain / "exists").mkdir()
    with pytest.raises(FileExistsError):
        stage.stage(generation, plain / "exists", force_copy=True)


def test_stage_refuses_a_tampered_generation(tmp_path):
    generation = _generation(tmp_path)
    (generation / "reference.sqlite").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        stage.stage(generation, tmp_path / "o", force_copy=True)
    assert not (tmp_path / "o").exists()
