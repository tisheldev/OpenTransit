"""Operator-run generation publisher for the H-1 private ECS preview (LOCAL part only).

Turns one built generation (``opentransit build-generation``) into a release candidate:

1. **verify**: manifest, artifact hashes (``verify_artifacts``), slot-free graph, coverage and
   *current* source freshness (the new-candidate rule shared with local activation), the probe
   corpus (``opentransit probe``'s own parser, every probe departure inside coverage) and, for
   address generations, the Photon tree against its sealed attestation checkpoint;
2. **stage**: ``stage_bundle.stage`` builds the data-image context (``--build`` only);
3. **build**: the H-0 ``docker build`` commands for the API, data and Photon images, then
   ``docker image inspect`` records each local image ID (``--build`` only; heavy Docker lane);
4. **render**: the ECS task definition from ``render_drafts`` with every image pinned by digest
   and the generation ID, verifier-config hash, probe-corpus hash and source-check time as
   task-definition tags, checked by ``validate_drafts.validate_candidate``;
5. **retention / rollback plans**: which ECR digests must never be deleted, and whether the
   previous release could be rolled back to now. Nothing is ever deleted.

The default is a dry run: it verifies, plans and renders, and runs no Docker or AWS command.
``push`` and ``rollback --execute-aws`` are the only code paths that talk to AWS. ``push``
prints its steps unless ``--execute-aws`` is given; both shell out to the ``aws`` and
``docker`` CLIs. First executed on 31 October 2026 against the H-1 preview service.

    uv run --project services/api --locked python deploy/aws/tools/publish_generation.py \\
        publish --generation <gen> --probe-queries <corpus> [--photon-data <checkpoint>] \\
        --output <new dir> [--image-id api=sha256:... ...] [--previous-release <file>] \\
        [--pin sha256:...=<reason>] [--build --photon-jar-dir <dir>]
    ... publish_generation.py retention --current <file> [--previous <file>] [--pin ...] \\
        [--registry-images <aws ecr describe-images output>]
    ... publish_generation.py rollback --current <file> --previous <file> [--now <iso>] \\
        [--execute-aws --region ... --cluster ... --service ... [--profile ...] [--wait]]
    ... publish ... --local-image api=<ref> --local-image data=<ref> [--source-check <record>]
    ... publish_generation.py push --plan <release-plan.json> --region ... --registry ... \\
        --cluster ... --service ... --execution-role-arn ... --vpc-cidr ... [--execute-aws]

See deploy/aws/README.md, "H-1 generation publisher".
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import render_drafts  # noqa: E402
import stage_bundle  # noqa: E402
import validate_drafts  # noqa: E402
from opentransit.build.local_operator import currency_reasons  # noqa: E402
from opentransit.build.probe import _journeys as parse_probe_corpus  # noqa: E402
from opentransit.core.artifacts import (  # noqa: E402
    PHOTON_130_JAR_SHA256,
    file_sha256,
    verify_artifacts,
)
from opentransit.core.generation import Generation  # noqa: E402
from opentransit.runtime import apply_source_check  # noqa: E402

AWS_DIR = TOOLS.parent
REPO = AWS_DIR.parents[1]
SCHEMA_VERSION = 1
DIGEST = re.compile(r"sha256:[a-f0-9]{64}")
IMAGE_PLACEHOLDERS = {"api": "API_DIGEST", "data": "DATA_DIGEST", "photon": "PHOTON_DIGEST"}
REPOSITORIES = {
    "api": "opentransit-api",
    "data": "opentransit-data",
    "photon": "opentransit-photon",
    "motis": "opentransit-motis",
}
MANIFEST_SUMMARY_KEYS = (
    "schemaVersion",
    "state",
    "generationId",
    "builtAt",
    "validatedAt",
    "coverage",
    "engineDigest",
    "mode",
    "sourceCheckedAt",
)
# In the task the verifier writes the inline record here; the API reads it at startup.
SOURCE_CHECK_ENV = "OPENTRANSIT_SOURCE_CHECK_RECORD"
SOURCE_CHECK_IN_TASK = "/run/opentransit/source-check.json"
SOURCE_CHECK_KEYS = ("status", "sha256", "checkedAt")
PUSHABLE_MODES = {"build", "existing-images"}
LABEL = (
    "LOCAL PUBLISH PLAN. No AWS call, push, registration or deployment was made. Local image "
    "IDs are not registry manifest digests; only `push --execute-aws` produces a deployable "
    "revision."
)


class PublishRefused(ValueError):
    """The candidate must not be published; ``reasons`` are stable machine-readable codes."""

    def __init__(self, reasons: list[str], detail: dict | None = None) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons
        self.detail = detail or {}


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


# --- 1. verify --------------------------------------------------------------------------------


def verify_candidate(
    generation_dir: Path,
    probe_queries: Path,
    *,
    now: datetime,
    photon_data: Path | None = None,
    source_check: Path | None = None,
) -> dict:
    """Verify a built generation is publishable as a new candidate at ``now``.

    ``source_check`` is a later successful same-hash paired check (``opentransit fetch``
    record): it renews an unchanged generation's freshness without rebuilding it, by the same
    ``apply_source_check`` rule the API and the in-task verifier apply.

    Raises :class:`PublishRefused` with every reason found. Reuses the serving-side
    verification code; nothing here re-implements hashing or the freshness rule.
    """
    if now.utcoffset() is None:
        raise ValueError("The publisher clock needs an explicit timezone")
    generation_dir = Path(generation_dir).resolve(strict=True)
    manifest = json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("state") != "ready":
        raise PublishRefused(["generation_not_ready"])
    try:
        verified = verify_artifacts(generation_dir, manifest)
        stage_bundle.check_serving_port(generation_dir / "motis")
        generation = Generation.from_manifest(manifest)
    except (OSError, KeyError, ValueError) as exc:
        raise PublishRefused([f"artifacts_invalid:{exc}"]) from exc
    manifest_checked_at = _iso(generation.freshness_checked_at())
    renewal = None
    if source_check is not None:
        try:
            generation = apply_source_check(generation, manifest, Path(source_check))
            renewal = source_check_summary(Path(source_check))
        except (OSError, KeyError, ValueError) as exc:
            raise PublishRefused([f"source_check_invalid:{exc}"]) from exc

    reasons = currency_reasons(generation, now, rollback=False)
    detail: dict = {
        "generationId": generation.id,
        "checkedAt": now.astimezone(UTC).isoformat(),
        "coverage": {
            "from": generation.coverage_from.isoformat(),
            "until": generation.coverage_until.isoformat(),
        },
        "freshness": generation.freshness(now),
        "freshnessBasis": generation.freshness_basis,
        "sourceCheckedAt": _iso(generation.freshness_checked_at()),
        "rule": "new candidate: coverage contains now and source freshness is current",
    }

    try:
        cases, corpus_sha256 = parse_probe_corpus(Path(probe_queries).resolve(strict=True))
    except (OSError, KeyError, ValueError) as exc:
        reasons.append(f"probe_corpus_invalid:{exc}")
        cases, corpus_sha256 = [], None
    outside = [case["id"] for case in cases if not generation.contains(case["departAt"])]
    if outside:
        # H-0 run-02: a corpus without per-generation probeTime failed the in-task verifier.
        reasons.append("probe_outside_coverage:" + ",".join(outside))
    detail["probe"] = {"corpusSha256": corpus_sha256, "caseCount": len(cases)}

    addresses = manifest.get("addressSearch") is not None
    photon_tree = None
    if addresses:
        if photon_data is None:
            reasons.append("photon_data_missing")
        else:
            entries = stage_bundle.tree_entries(Path(photon_data).resolve(strict=True))
            attestation = json.loads(
                (generation_dir / "photon-import-attestation.json").read_text(encoding="utf-8")
            )
            sealed = attestation["checkpoint"]
            photon_tree = stage_bundle.tree_digest(entries)
            if (
                photon_tree != sealed["treeSha256"]
                or len(entries) != sealed["files"]
                or sum(e["bytes"] for e in entries) != sealed["bytes"]
            ):
                reasons.append("photon_tree_mismatch")
    elif photon_data is not None:
        reasons.append("photon_data_without_address_search")
    if reasons:
        raise PublishRefused(reasons, detail)

    summary = {k: manifest[k] for k in MANIFEST_SUMMARY_KEYS if k in manifest}
    if renewal is not None:
        # Rollback reads freshness from this summary, so it carries the renewed check time.
        summary["sourceCheckedAt"] = detail["sourceCheckedAt"]
    return {
        **detail,
        "manifestSourceCheckedAt": manifest_checked_at,
        "sourceCheck": renewal,
        "scheduleComponentGenerationId": manifest.get("scheduleComponentGenerationId"),
        "addressSearch": addresses,
        "artifacts": {k: v for k, v in verified.items() if isinstance(v, str | None)},
        "photonTreeSha256": photon_tree,
        "manifestSummary": summary,
        "generationDir": str(generation_dir),
        "probeQueries": str(Path(probe_queries).resolve()),
        "photonData": str(Path(photon_data).resolve()) if photon_data else None,
    }


def source_check_summary(path: Path) -> dict:
    """The fields ``apply_source_check`` reads, small enough for a task environment value."""
    raw = Path(path).read_bytes()
    evidence = json.loads(raw)
    return {
        "pairedValidation": evidence["pairedValidation"],
        "validation": {"valid": evidence["validation"]["valid"]},
        "validatedAt": evidence["validatedAt"],
        "sources": {
            key: {field: evidence["sources"][key][field] for field in SOURCE_CHECK_KEYS}
            for key in ("gtfs", "trip_id_to_date")
        },
        "record": {"name": Path(path).name, "sha256": hashlib.sha256(raw).hexdigest()},
    }


# --- 2./3. stage and build (local Docker; only with --build) ---------------------------------


def local_tags(generation_id: str, prefix: str = "ot-h1-") -> dict[str, str]:
    return {name: f"{prefix}{name}:gen-{generation_id[:12]}" for name in IMAGE_PLACEHOLDERS}


def build_commands(
    stage_dir: Path,
    tags: dict[str, str],
    *,
    generation_id: str,
    addresses: bool,
    photon_jar_dir: Path | None,
) -> list[dict]:
    """The H-0 build commands (deploy/aws/README.md, "Local commands" step 2) as argv lists."""
    commands = [
        {
            "image": "api",
            "argv": ["docker", "build", "-t", tags["api"], str(REPO / "services/api")],
        },
        {
            "image": "data",
            "argv": [
                "docker",
                "build",
                "--build-context",
                f"bundle={stage_dir}",
                "--label",
                f"org.opentransit.generation-id={generation_id}",
                "-t",
                tags["data"],
                str(AWS_DIR / "data-image"),
            ],
        },
    ]
    if addresses:
        commands.append(
            {
                "image": "photon",
                "argv": [
                    "docker",
                    "build",
                    "--build-context",
                    f"photon_jar={photon_jar_dir or '<photon jar dir>'}",
                    "-t",
                    tags["photon"],
                    str(AWS_DIR / "photon-image"),
                ],
            }
        )
    return commands


def inspect_command(reference: str) -> list[str]:
    return ["docker", "image", "inspect", "--format", "{{.Id}}", reference]


def check_photon_jar(photon_jar_dir: Path) -> str:
    jar = Path(photon_jar_dir) / "photon-1.3.0.jar"
    digest = file_sha256(jar)
    if digest != PHOTON_130_JAR_SHA256:
        raise PublishRefused(["photon_jar_hash_mismatch"])
    return digest


def _run(argv: list[str], env: dict | None = None) -> str:
    """Run one local command; only reached with --build, existing images or push."""
    completed = subprocess.run(
        argv, check=True, capture_output=True, text=True, encoding="utf-8", env=env
    )
    return completed.stdout.strip()


# --- 4. render -------------------------------------------------------------------------------


def _replace_strings(value, replacements: dict[str, str]):
    if isinstance(value, str):
        for old, new in replacements.items():
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [_replace_strings(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_strings(item, replacements) for key, item in value.items()}
    return value


def verifier_config_sha256(task: dict) -> str:
    """Hash of the rendered verifier container (image digest, command, env, mounts, order)."""
    verifier = next(c for c in task["containerDefinitions"] if c["name"] == "verifier")
    return _canonical_sha256(verifier)


def render_candidate(
    variant: str,
    digests: dict[str, str],
    verified: dict,
    *,
    digest_kind: str,
    registry: str | None = None,
    execution_role_arn: str | None = None,
    vpc_cidr: str | None = None,
    family: str | None = None,
    log_group: str | None = None,
) -> dict:
    """Render the task definition with every image pinned and the release identity tagged."""
    spec = render_drafts.VARIANTS[variant]
    if spec["addresses"] != verified["addressSearch"]:
        raise PublishRefused([f"variant_mismatch:{variant} addresses={spec['addresses']}"])
    if digest_kind not in {"local-image-id", "registry-manifest"}:
        raise ValueError(f"Unknown digest kind {digest_kind}")
    required = {"api", "data"} | ({"photon"} if spec["addresses"] else set())
    missing = sorted(required - set(digests))
    if missing:
        raise PublishRefused([f"digest_missing:{name}" for name in missing])
    replacements = {}
    for name in sorted(required):
        if not DIGEST.fullmatch(digests[name]):
            raise PublishRefused([f"digest_malformed:{name}"])
        replacements["{{" + IMAGE_PLACEHOLDERS[name] + "}}"] = digests[name]
    if registry is not None:
        if not validate_drafts.ECR_REGISTRY.fullmatch(registry):
            raise ValueError("registry must look like <account>.dkr.ecr.<region>.amazonaws.com")
        replacements["{{ECR_REGISTRY}}"] = registry
    if execution_role_arn is not None:
        if not validate_drafts.ROLE_ARN.fullmatch(execution_role_arn):
            raise ValueError("execution role must be an IAM role ARN")
        replacements["{{EXECUTION_ROLE_ARN}}"] = execution_role_arn
    if vpc_cidr is not None:
        if "{{" in vpc_cidr or validate_drafts.trusted_proxies_error(vpc_cidr):
            raise ValueError("vpc_cidr must be a CIDR list with prefix lengths, not a catch-all")
        replacements["{{VPC_CIDR}}"] = vpc_cidr
    task = _replace_strings(render_drafts.render_task_definition(variant), replacements)
    if family or log_group:
        task = render_drafts.retarget(
            task,
            family=family or task["family"],
            log_group=log_group or render_drafts.LOG_GROUP,
        )
    if verified.get("sourceCheck"):
        record = json.dumps(verified["sourceCheck"], sort_keys=True, separators=(",", ":"))
        for container in task["containerDefinitions"]:
            if container["name"] == "verifier":
                container["environment"].append({"name": SOURCE_CHECK_ENV, "value": record})
            elif container["name"] == "api":
                container["environment"].append(
                    {"name": "OPENTRANSIT_SOURCE_CHECK", "value": SOURCE_CHECK_IN_TASK}
                )
    tags = [t for t in task["tags"] if t["key"] != "purpose"]
    tags += [
        {"key": "purpose", "value": "h1-candidate"},
        {"key": "generation-id", "value": verified["generationId"]},
        {"key": "probe-corpus-sha256", "value": verified["probe"]["corpusSha256"]},
        {"key": "verifier-config-sha256", "value": verifier_config_sha256(task)},
        {"key": "source-checked-at", "value": verified["sourceCheckedAt"]},
        {"key": "coverage-until", "value": verified["coverage"]["until"]},
        {"key": "digest-kind", "value": digest_kind},
    ]
    if verified.get("scheduleComponentGenerationId"):
        tags.append(
            {"key": "schedule-component-id", "value": verified["scheduleComponentGenerationId"]}
        )
    task["tags"] = tags
    return task


def release_record(
    verified: dict, digests: dict[str, str], task: dict, *, variant: str, digest_kind: str
) -> dict:
    """The record retention and rollback read back (later completed by ``push``)."""
    return {
        "generationId": verified["generationId"],
        "scheduleComponentGenerationId": verified.get("scheduleComponentGenerationId"),
        "addressSearch": verified["addressSearch"],
        "coverage": verified["coverage"],
        "sourceCheckedAt": verified["sourceCheckedAt"],
        "freshnessBasis": verified["freshnessBasis"],
        "sourceCheck": verified.get("sourceCheck"),
        "manifestSummary": verified["manifestSummary"],
        "probeCorpusSha256": verified["probe"]["corpusSha256"],
        "verifierConfigSha256": verifier_config_sha256(task),
        "variant": variant,
        "taskDefinitionFamily": task["family"],
        "taskDefinitionArn": None,
        "digestKind": digest_kind,
        "images": {name: digests[name] for name in sorted(digests)},
        "motisDigest": render_drafts.MOTIS_DIGEST,
    }


# --- 5. retention and rollback ---------------------------------------------------------------


def load_release(path: Path) -> dict:
    """Accept a release-plan.json (its ``release``) or a bare release record."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    release = data.get("release", data)
    if not isinstance(release, dict) or "generationId" not in release:
        raise ValueError(f"{path} holds no release record")
    return release


def parse_pins(values: list[str]) -> dict[str, str]:
    pins = {}
    for value in values:
        digest, _, reason = value.partition("=")
        if not DIGEST.fullmatch(digest):
            raise ValueError(f"pin {value!r} must be sha256:<64 hex>[=reason]")
        pins[digest] = reason or "evidence"
    return pins


def retention_plan(
    *,
    current: dict | None,
    previous: dict | None,
    pins: dict[str, str] | None = None,
    registry_images: list[dict] | None = None,
) -> dict:
    """List protected digests (active, previous, evidence-pinned). Never deletes anything.

    ``registry_images`` is the ``imageDetails`` list of ``aws ecr describe-images`` output
    (run by the operator); digests not protected are listed for human review only.
    """
    protected: dict[str, set[str]] = {}
    warnings: list[str] = []

    def protect(digest: str, reason: str) -> None:
        protected.setdefault(digest, set()).add(reason)

    for role, release in (("active", current), ("previous", previous)):
        if release is None:
            continue
        short = release["generationId"][:12]
        for name, digest in release["images"].items():
            protect(digest, f"{role}:{name}:{short}")
        protect(release["motisDigest"], f"{role}:motis:{short}")
        if release.get("digestKind") != "registry-manifest":
            warnings.append(
                f"{role} release {short} records local image IDs, which differ from ECR "
                "manifest digests; it protects nothing in a registry until pushed"
            )
    for digest, reason in (pins or {}).items():
        protect(digest, f"evidence:{reason}")
    if previous is None:
        warnings.append("no previous release: rollback has no retained target")

    listed: list[dict] = []
    review: list[dict] = []
    seen = set()
    for image in registry_images or []:
        digest = image.get("imageDigest")
        seen.add(digest)
        entry = {
            "repository": image.get("repositoryName"),
            "digest": digest,
            "tags": sorted(image.get("imageTags", [])),
        }
        if digest in protected:
            listed.append({**entry, "reasons": sorted(protected[digest])})
        else:
            review.append(entry)
    if registry_images is not None:
        for digest in sorted(set(protected) - seen):
            warnings.append(f"protected digest {digest} is absent from the registry listing")
    return {
        "automaticDeletion": False,
        "deletionPerformed": False,
        "protectedDigests": [
            {"digest": digest, "reasons": sorted(reasons)}
            for digest, reasons in sorted(protected.items())
        ],
        "registryProtected": listed,
        "unprotectedForHumanReview": review,
        "warnings": warnings,
        "rule": "never delete active, previous or evidence-pinned digests; no lifecycle rule",
    }


def rollback_plan(current: dict | None, previous: dict | None, now: datetime) -> dict:
    """Decide whether the retained previous release may be rolled back to at ``now``.

    Uses the shared rollback rule (``currency_reasons(..., rollback=True)``): any serviceable
    freshness (current, aging, stale) is accepted; expired freshness or coverage that has
    lapsed or not started is refused. The plan is never executed here.
    """
    if now.utcoffset() is None:
        raise ValueError("The rollback clock needs an explicit timezone")
    if previous is None:
        return {"allowed": False, "reasons": ["no_previous_release"], "executed": False}
    reasons = []
    if current is not None and current.get("images") == previous.get("images"):
        reasons.append("previous_equals_current")
    if previous.get("digestKind") != "registry-manifest":
        reasons.append("previous_not_registry_pinned")
    if not previous.get("taskDefinitionArn"):
        reasons.append("previous_revision_unknown")
    generation = Generation.from_manifest(previous["manifestSummary"])
    if generation.id != previous["generationId"]:
        reasons.append("previous_record_inconsistent")
    reasons += currency_reasons(generation, now, rollback=True)
    plan = {
        "allowed": not reasons,
        "reasons": reasons,
        "checkedAt": now.astimezone(UTC).isoformat(),
        "previousGenerationId": previous["generationId"],
        "coverage": {
            "from": generation.coverage_from.isoformat(),
            "until": generation.coverage_until.isoformat(),
        },
        "freshness": generation.freshness(now),
        "rule": "rollback: serviceable freshness (current/aging/stale) and coverage contains now",
        "executed": False,
    }
    if not reasons:
        plan["command"] = [
            "aws",
            "ecs",
            "update-service",
            "--cluster",
            "<cluster>",
            "--service",
            "<service>",
            "--task-definition",
            previous["taskDefinitionArn"],
        ]
    return plan


# --- push (the only AWS code path; never run by tests) ----------------------------------------


def motis_mirror_command(registry: str, digest: str) -> list[str]:
    """Digest-preserving copy of the pinned public MOTIS image into private ECR (U7)."""
    return [
        "docker",
        "buildx",
        "imagetools",
        "create",
        "--tag",
        f"{registry}/{REPOSITORIES['motis']}:motis-{digest.removeprefix('sha256:')[:12]}",
        f"ghcr.io/motis-project/motis@{digest}",
    ]


def remote_tag(release: dict, name: str) -> str:
    """One immutable tag per (generation, local image): a rebuilt API never reuses a tag."""
    image_id = release["images"][name].removeprefix("sha256:")
    return f"gen-{release['generationId'][:12]}-{image_id[:12]}"


def push_steps(release: dict, *, region: str, registry: str, cluster: str, service: str) -> list:
    """Human-readable plan of what ``execute_push`` would do. Pure; used for dry runs/tests."""
    steps = [
        ["aws", "ecr", "get-login-password", "--region", region],
        ["<write a throwaway DOCKER_CONFIG with the ECR token>"],
        ["aws", "ecr", "describe-images", "--repository-name", REPOSITORIES["motis"]],
        motis_mirror_command(registry, release["motisDigest"]),
    ]
    for name in sorted(release["images"]):
        remote = f"{registry}/{REPOSITORIES[name]}:{remote_tag(release, name)}"
        steps += [
            ["aws", "ecr", "describe-images", "--repository-name", REPOSITORIES[name]],
            ["docker", "tag", release["localTags"][name], remote],
            ["docker", "push", remote],
        ]
    steps += [
        [
            "aws",
            "ecs",
            "register-task-definition",
            "--region",
            region,
            "--cli-input-json",
            "file://task-definition.registered.json",
        ],
        [
            "aws",
            "ecs",
            "update-service",
            "--region",
            region,
            "--cluster",
            cluster,
            "--service",
            service,
            "--task-definition",
            "<taskDefinitionArn from register-task-definition>",
        ],
    ]
    return steps


class AwsSession:
    """``aws``/``docker`` calls for push and rollback: one profile and Region, and an ECR login
    kept in a throwaway Docker config (the Windows credential store rejects ECR tokens)."""

    def __init__(self, region: str, profile: str | None = None, runner=_run) -> None:
        self.region, self.profile, self.runner = region, profile, runner
        self.docker_env: dict | None = None
        self._config: Path | None = None

    def _profile(self) -> list[str]:
        return ["--profile", self.profile] if self.profile else []

    def aws(self, *args: str) -> dict:
        argv = ["aws", *self._profile(), "--region", self.region, "--output", "json", *args]
        out = self.runner(argv)
        return json.loads(out) if out else {}

    def login(self, registry: str) -> None:
        password = self.runner(
            ["aws", *self._profile(), "--region", self.region, "ecr", "get-login-password"]
        )
        self._config = Path(tempfile.mkdtemp(prefix="ot-publish-"))
        auth = base64.b64encode(f"AWS:{password.strip()}".encode()).decode()
        (self._config / "config.json").write_text(
            json.dumps({"auths": {registry: {"auth": auth}}}), encoding="utf-8"
        )
        self.docker_env = {**os.environ, "DOCKER_CONFIG": str(self._config)}

    def docker(self, *args: str) -> str:
        return self.runner(["docker", *args], env=self.docker_env)

    def close(self) -> None:
        if self._config is not None:
            shutil.rmtree(self._config, ignore_errors=True)

    def image_digest(self, repository: str, key: str, value: str) -> str | None:
        try:
            out = self.aws(
                "ecr",
                "describe-images",
                "--repository-name",
                repository,
                "--image-ids",
                f"{key}={value}",
            )
        except subprocess.CalledProcessError:
            return None  # ImageNotFoundException
        details = out.get("imageDetails") or []
        return details[0]["imageDigest"] if details else None

    def wait_for_deployment(self, cluster: str, service: str, timeout: float) -> dict:
        """Poll until the service has one COMPLETED deployment with its desired tasks running."""
        started = time.monotonic()
        state: dict = {}
        while time.monotonic() - started < timeout:
            svc = self.aws("ecs", "describe-services", "--cluster", cluster, "--services", service)
            svc = (svc.get("services") or [{}])[0]
            deployments = svc.get("deployments", [])
            primary = next((d for d in deployments if d["status"] == "PRIMARY"), {})
            state = {
                "seconds": round(time.monotonic() - started, 1),
                "deployments": len(deployments),
                "rolloutState": primary.get("rolloutState"),
                "taskDefinition": primary.get("taskDefinition"),
                "runningCount": svc.get("runningCount"),
                "desiredCount": svc.get("desiredCount"),
                "events": [e["message"] for e in svc.get("events", [])[:5]],
            }
            if state["rolloutState"] == "FAILED":
                break
            if (
                state["deployments"] == 1
                and state["rolloutState"] == "COMPLETED"
                and state["runningCount"] == state["desiredCount"]
            ):
                break
            time.sleep(15)
        state["converged"] = (
            state.get("deployments") == 1
            and state.get("rolloutState") == "COMPLETED"
            and state.get("runningCount") == state.get("desiredCount")
        )
        return state


def execute_push(
    plan: dict,
    plan_dir: Path,
    *,
    region,
    registry,
    cluster,
    service,
    role,
    vpc_cidr,
    profile: str | None = None,
    family: str = render_drafts.H1_FAMILY,
    log_group: str = render_drafts.H1_LOG_GROUP,
    wait: bool = False,
    timeout: float = 2700,
    runner=_run,
) -> dict:
    """Push, register and deploy (``push --execute-aws``; first run 31 October 2026, H-1).

    It never deregisters, deletes or prunes anything, so a failed push/registration leaves the
    current revision serving, and the service's circuit breaker (``ecs/service.json``) rolls a
    failed deployment back to it. An image whose tag already holds it is not pushed again.
    """
    release = dict(plan["release"])
    for name, image_id in release["images"].items():
        if runner(inspect_command(release["localTags"][name])) != image_id:
            raise PublishRefused([f"local_image_changed:{name}"])
    session = AwsSession(region, profile, runner)
    pushes = {}
    try:
        session.login(registry)
        motis = session.image_digest(REPOSITORIES["motis"], "imageDigest", release["motisDigest"])
        if motis is None:
            session.docker(*motis_mirror_command(registry, release["motisDigest"])[1:])
        pushes["motis"] = {"digest": release["motisDigest"], "pushed": motis is None}
        digests = {}
        for name in sorted(release["images"]):
            tag = remote_tag(release, name)
            remote = f"{registry}/{REPOSITORIES[name]}:{tag}"
            existing = session.image_digest(REPOSITORIES[name], "imageTag", tag)
            started = time.monotonic()
            if existing is None:
                session.docker("tag", release["localTags"][name], remote)
                session.docker("push", remote)
            digests[name] = session.image_digest(REPOSITORIES[name], "imageTag", tag)
            if not digests[name]:
                raise PublishRefused([f"pushed_digest_unknown:{name}"])
            pushes[name] = {
                "tag": tag,
                "digest": digests[name],
                "pushed": existing is None,
                "seconds": round(time.monotonic() - started, 1),
            }
    finally:
        session.close()
    task = render_candidate(
        release["variant"],
        digests,
        plan["verify"],
        digest_kind="registry-manifest",
        registry=registry,
        execution_role_arn=role,
        vpc_cidr=vpc_cidr,
        family=family,
        log_group=log_group,
    )
    errors, _ = validate_drafts.validate_candidate(task, "registered", render_drafts.MOTIS_DIGEST)
    leftover = sorted(set(validate_drafts.PLACEHOLDER.findall(json.dumps(task))))
    if leftover:
        errors.append(f"registered: unresolved placeholders {leftover}")
    if errors:
        raise PublishRefused(errors)
    task_path = plan_dir / "task-definition.registered.json"
    task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    registered = session.aws(
        "ecs", "register-task-definition", "--cli-input-json", f"file://{task_path.as_posix()}"
    )
    arn = registered["taskDefinition"]["taskDefinitionArn"]
    release.update(
        images=digests,
        localImageIds=plan["release"]["images"],
        digestKind="registry-manifest",
        taskDefinitionArn=arn,
        taskDefinitionFamily=family,
        registeredAt=datetime.now(UTC).isoformat(timespec="seconds"),
        pushes=pushes,
    )
    record = plan_dir / "release-registered.json"
    record.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    session.aws(
        "ecs",
        "update-service",
        "--cluster",
        cluster,
        "--service",
        service,
        "--task-definition",
        arn,
    )
    release["deployment"] = {"startedAt": datetime.now(UTC).isoformat(timespec="seconds")}
    if wait:
        release["deployment"].update(session.wait_for_deployment(cluster, service, timeout))
    record.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    return release


def execute_rollback(
    plan: dict,
    *,
    region: str,
    cluster: str,
    service: str,
    profile: str | None = None,
    wait: bool = False,
    timeout: float = 2700,
    runner=_run,
) -> dict:
    """Deploy the retained previous revision that ``rollback_plan`` allowed. Deletes nothing."""
    if not plan.get("allowed"):
        raise PublishRefused(plan.get("reasons") or ["rollback_not_allowed"])
    session = AwsSession(region, profile, runner)
    arn = plan["command"][-1]
    session.aws(
        "ecs",
        "update-service",
        "--cluster",
        cluster,
        "--service",
        service,
        "--task-definition",
        arn,
    )
    result = {
        **plan,
        "executed": True,
        "startedAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if wait:
        result["deployment"] = session.wait_for_deployment(cluster, service, timeout)
    return result


# --- orchestration ---------------------------------------------------------------------------


def publish(
    *,
    generation: Path,
    probe_queries: Path,
    output: Path,
    now: datetime,
    clock_overridden: bool = False,
    variant: str = "recommended",
    photon_data: Path | None = None,
    photon_jar_dir: Path | None = None,
    image_ids: dict[str, str] | None = None,
    previous_release: dict | None = None,
    pins: dict[str, str] | None = None,
    registry_images: list[dict] | None = None,
    build: bool = False,
    tag_prefix: str = "ot-h1-",
    source_check: Path | None = None,
    local_images: dict[str, str] | None = None,
    runner=_run,
) -> tuple[int, dict]:
    """Run the local stages and write ``release-plan.json`` (+ the candidate) to ``output``.

    Returns (exit code, plan). A refusal is still written, so it can be kept as evidence.
    """
    output = Path(output).resolve()
    if (output / "release-plan.json").exists():
        raise FileExistsError(output / "release-plan.json")
    output.mkdir(parents=True, exist_ok=True)
    plan: dict = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "h1-generation-publish-plan",
        "label": LABEL,
        "mode": "build" if build else "existing-images" if local_images else "dry-run",
        "clock": {"now": now.astimezone(UTC).isoformat(), "overridden": clock_overridden},
        "variant": variant,
        "stages": {},
        "awsCallsMade": False,
    }

    def finish(code: int) -> tuple[int, dict]:
        plan["outcome"] = "ok" if code == 0 else "refused"
        (output / "release-plan.json").write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return code, plan

    try:
        verified = verify_candidate(
            generation,
            probe_queries,
            now=now,
            photon_data=photon_data,
            source_check=source_check,
        )
        if photon_jar_dir is not None and verified["addressSearch"]:
            verified["photonJarSha256"] = check_photon_jar(photon_jar_dir)
    except PublishRefused as exc:
        plan["stages"]["verify"] = {"status": "refused", "reasons": exc.reasons, **exc.detail}
        return finish(1)
    plan["verify"] = verified
    plan["stages"]["verify"] = {"status": "passed"}

    tags = local_tags(verified["generationId"], tag_prefix)
    if not verified["addressSearch"]:
        tags.pop("photon")
    stage_dir = output / "stage"
    commands = build_commands(
        stage_dir,
        tags,
        generation_id=verified["generationId"],
        addresses=verified["addressSearch"],
        photon_jar_dir=photon_jar_dir,
    )
    plan["stages"]["stage"] = {"executed": False, "output": str(stage_dir)}
    plan["stages"]["build"] = {
        "executed": False,
        "localTags": tags,
        "commands": [c["argv"] for c in commands],
    }
    digests = dict(image_ids or {})
    digest_source = "--image-id" if digests else None
    if local_images:
        # Images already built (and possibly already in ECR): inspect them, build nothing.
        missing = sorted(set(tags) - set(local_images))
        if missing or build:
            plan["stages"]["build"].update(
                status="refused",
                reasons=[f"local_image_missing:{n}" for n in missing] or ["build_and_local_images"],
            )
            return finish(1)
        tags = {name: local_images[name] for name in tags}
        try:
            digests = {name: runner(inspect_command(ref)) for name, ref in tags.items()}
        except subprocess.CalledProcessError:
            plan["stages"]["build"].update(status="failed", reasons=["local_image_not_found"])
            return finish(1)
        plan["stages"]["build"].update(status="existing-images", localTags=tags, imageIds=digests)
        digest_source = "docker image inspect (existing local images)"
    if build:
        if verified["addressSearch"] and photon_jar_dir is None:
            plan["stages"]["build"]["status"] = "refused"
            plan["stages"]["build"]["reasons"] = ["photon_jar_dir_missing"]
            return finish(1)
        try:
            staged = stage_bundle.stage(
                Path(generation),
                stage_dir,
                photon_data=photon_data,
                probe_queries=probe_queries,
            )
        except (OSError, ValueError, KeyError) as exc:
            plan["stages"]["stage"].update(status="failed", reasons=[f"{type(exc).__name__}"])
            return finish(1)
        plan["stages"]["stage"].update(
            executed=True,
            files=len(staged["files"]),
            bytes=sum(f["bytes"] for f in staged["files"]),
        )
        try:
            for command in commands:
                runner(command["argv"])
            digests = {name: runner(inspect_command(tag)) for name, tag in tags.items()}
        except subprocess.CalledProcessError as exc:
            plan["stages"]["build"].update(
                executed=True, status="failed", reasons=[f"command_failed:{exc.cmd[:3]}"]
            )
            return finish(1)
        plan["stages"]["build"].update(executed=True, status="passed", imageIds=digests)
        digest_source = "docker image inspect"

    if not digests:
        plan["stages"]["render"] = {
            "status": "skipped",
            "reason": "no image digests: pass --image-id api=... data=... [photon=...] or --build",
        }
        # Nothing new to protect yet: the serving release (if given) stays the active one.
        plan["retention"] = retention_plan(
            current=previous_release, previous=None, pins=pins, registry_images=registry_images
        )
        return finish(0)
    try:
        task = render_candidate(variant, digests, verified, digest_kind="local-image-id")
    except PublishRefused as exc:
        plan["stages"]["render"] = {"status": "refused", "reasons": exc.reasons}
        return finish(1)
    errors, warnings = validate_drafts.validate_candidate(
        task, "candidate", render_drafts.MOTIS_DIGEST
    )
    candidate_path = output / "task-definition.candidate.json"
    candidate_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    plan["stages"]["render"] = {
        "status": "passed" if not errors else "invalid",
        "taskDefinition": str(candidate_path),
        "digestSource": digest_source,
        "validation": {"errors": errors, "warnings": warnings},
    }
    release = release_record(verified, digests, task, variant=variant, digest_kind="local-image-id")
    release["localTags"] = tags
    plan["release"] = release
    plan["stages"]["push-and-deploy"] = {
        "executed": False,
        "how": "publish_generation.py push --plan <this file> ... --execute-aws",
    }
    # The new release becomes active; the currently serving one becomes previous.
    plan["retention"] = retention_plan(
        current=release, previous=previous_release, pins=pins, registry_images=registry_images
    )
    if previous_release is not None:
        plan["rollbackIfCandidateFails"] = rollback_plan(release, previous_release, now)
    return finish(1 if errors else 0)


def _image_ids(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        name, _, digest = value.partition("=")
        if name not in IMAGE_PLACEHOLDERS or not DIGEST.fullmatch(digest):
            raise ValueError(f"--image-id {value!r} must be api|data|photon=sha256:<64 hex>")
        result[name] = digest
    return result


def _now(value: str | None) -> tuple[datetime, bool]:
    if value is None:
        return datetime.now(UTC), False
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("--now needs an explicit offset")
    return parsed, True


def _registry_images(path: Path | None) -> list[dict] | None:
    if path is None:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["imageDetails"] if isinstance(data, dict) else data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)

    pub = commands.add_parser("publish", help="verify, (build,) render and plan; dry run default")
    pub.add_argument("--generation", type=Path, required=True)
    pub.add_argument("--probe-queries", type=Path, required=True)
    pub.add_argument("--output", type=Path, required=True, help="plan directory (new or empty)")
    pub.add_argument("--photon-data", type=Path, help="never-served sealed Photon checkpoint")
    pub.add_argument("--photon-jar-dir", type=Path, help="directory with photon-1.3.0.jar")
    pub.add_argument("--variant", choices=sorted(render_drafts.VARIANTS), default="recommended")
    pub.add_argument("--image-id", action="append", default=[], help="name=sha256:... (local)")
    pub.add_argument("--previous-release", type=Path, help="currently serving release record")
    pub.add_argument("--pin", action="append", default=[], help="sha256:...=reason")
    pub.add_argument("--registry-images", type=Path, help="aws ecr describe-images JSON")
    pub.add_argument("--now", help="override the clock (ISO with offset; recorded in the plan)")
    pub.add_argument("--tag-prefix", default="ot-h1-")
    pub.add_argument(
        "--source-check",
        type=Path,
        help="later same-hash paired check record that renews freshness",
    )
    pub.add_argument(
        "--local-image",
        action="append",
        default=[],
        help="name=local-ref: use an existing local image (api/data/photon) instead of building",
    )
    mode = pub.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="the default: no Docker, no AWS")
    mode.add_argument("--build", action="store_true", help="stage and docker build (heavy)")

    ret = commands.add_parser("retention", help="list protected digests; never deletes")
    ret.add_argument("--current", type=Path, required=True)
    ret.add_argument("--previous", type=Path)
    ret.add_argument("--pin", action="append", default=[])
    ret.add_argument("--registry-images", type=Path)

    rb = commands.add_parser("rollback", help="check the previous release; never executes")
    rb.add_argument("--current", type=Path)
    rb.add_argument("--previous", type=Path, required=True)
    rb.add_argument("--now")
    rb.add_argument("--execute-aws", action="store_true", help="deploy the previous revision")
    for name in ("--region", "--cluster", "--service", "--profile"):
        rb.add_argument(name)
    rb.add_argument("--wait", action="store_true")

    push = commands.add_parser("push", help="push/register/deploy (only with --execute-aws)")
    push.add_argument("--plan", type=Path, required=True)
    for name in (
        "--region",
        "--registry",
        "--cluster",
        "--service",
        "--execution-role-arn",
        "--vpc-cidr",
    ):
        push.add_argument(name, required=True)
    push.add_argument("--execute-aws", action="store_true", help="really call AWS")
    push.add_argument("--profile", help="AWS CLI profile (default: the environment's)")
    push.add_argument("--family", default=render_drafts.H1_FAMILY)
    push.add_argument("--log-group", default=render_drafts.H1_LOG_GROUP)
    push.add_argument("--wait", action="store_true", help="wait for the deployment to converge")
    push.add_argument("--timeout", type=float, default=2700)

    args = parser.parse_args(argv)
    try:
        if args.command == "publish":
            now, overridden = _now(args.now)
            code, plan = publish(
                generation=args.generation,
                probe_queries=args.probe_queries,
                output=args.output,
                now=now,
                clock_overridden=overridden,
                variant=args.variant,
                photon_data=args.photon_data,
                photon_jar_dir=args.photon_jar_dir,
                image_ids=_image_ids(args.image_id),
                previous_release=load_release(args.previous_release)
                if args.previous_release
                else None,
                pins=parse_pins(args.pin),
                registry_images=_registry_images(args.registry_images),
                build=args.build,
                tag_prefix=args.tag_prefix,
                source_check=args.source_check,
                local_images=dict(v.split("=", 1) for v in args.local_image),
            )
            summary = {
                "outcome": plan["outcome"],
                "mode": plan["mode"],
                "stages": {
                    k: v.get("status", v.get("executed")) for k, v in plan["stages"].items()
                },
                "plan": str(Path(args.output).resolve() / "release-plan.json"),
            }
            print(json.dumps(summary, indent=2))
            return code
        if args.command == "retention":
            result = retention_plan(
                current=load_release(args.current),
                previous=load_release(args.previous) if args.previous else None,
                pins=parse_pins(args.pin),
                registry_images=_registry_images(args.registry_images),
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "rollback":
            now, _ = _now(args.now)
            result = rollback_plan(
                load_release(args.current) if args.current else None,
                load_release(args.previous),
                now,
            )
            if args.execute_aws and result["allowed"]:
                if not (args.region and args.cluster and args.service):
                    raise ValueError("rollback --execute-aws needs --region, --cluster, --service")
                result = execute_rollback(
                    result,
                    region=args.region,
                    cluster=args.cluster,
                    service=args.service,
                    profile=args.profile,
                    wait=args.wait,
                )
            print(json.dumps(result, indent=2))
            converged = result.get("deployment", {}).get("converged", True)
            return 0 if result["allowed"] and converged else 1
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        if (
            "release" not in plan
            or plan.get("outcome") != "ok"
            or plan.get("mode") not in PUSHABLE_MODES
        ):
            raise PublishRefused(["plan_not_a_successful_build"])
        if "{{" in args.vpc_cidr or validate_drafts.trusted_proxies_error(args.vpc_cidr):
            raise PublishRefused(["vpc_cidr_invalid"])
        steps = push_steps(
            plan["release"],
            region=args.region,
            registry=args.registry,
            cluster=args.cluster,
            service=args.service,
        )
        if not args.execute_aws:
            print(json.dumps({"executed": False, "steps": steps}, indent=2))
            return 0
        release = execute_push(
            plan,
            args.plan.resolve().parent,
            region=args.region,
            registry=args.registry,
            cluster=args.cluster,
            service=args.service,
            role=args.execution_role_arn,
            vpc_cidr=args.vpc_cidr,
            profile=args.profile,
            family=args.family,
            log_group=args.log_group,
            wait=args.wait,
            timeout=args.timeout,
        )
        print(json.dumps({"executed": True, "release": release}, indent=2))
        return 0 if release["deployment"].get("converged", True) else 1
    except PublishRefused as exc:
        print(json.dumps({"refused": exc.reasons, **exc.detail}, indent=2), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
