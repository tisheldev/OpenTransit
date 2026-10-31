"""Daily H-1 refresh on the operator machine (Windows Task Scheduler, 06:30 local).

Steps, in order, stopping at the first failure; everything goes to a dated log and summary
under ``--logs`` (default ``D:/ot/logs``):

1. ``fetch``: ``opentransit fetch`` into the source store (append-only; writes a check record);
2. ``validate``: ``opentransit validate`` on the fetched GTFS/TripIdToDate pair;
3. ``build-generation`` (only when the pair differs from the serving generation's inputs):
   ``--addresses`` into a new dated directory under ``--generations-root``;
4. ``probe`` (new builds only): the generation's own MOTIS graph in a local container, probed
   with the corpus redated into its coverage;
5. ``publish``: the generation publisher. A changed feed builds and pushes new images; an
   unchanged feed reuses the serving images and renews freshness with today's paired check
   (``--source-check``): a new task-definition revision, no rebuild;
6. ``push --execute-aws --wait``: register, update the service and wait for convergence;
7. ``alb-probe``: ``/readyz``, ``/v1/status``, the ten probe journeys and the demo through the
   ALB from this machine;
8. ``retention``: ``opentransit prune --dry-run`` records candidates; nothing is deleted.

The serving release is tracked in ``<releases>/current.json`` (``release`` and ``previous``
paths); it moves only after a converged deployment. Exit 0 only if every step passed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[2]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO / "services/api"))

import h0_bounded_test as h0  # noqa: E402
from tools.acceptance_run import parse_instant, redate_probe_corpus  # noqa: E402

PROFILE = "opentransit"
REGION = "eu-north-1"
CLUSTER = SERVICE = "opentransit-h1"
VPC_CIDR = "10.80.0.0/16"
GTFS, TRIPS = "israel-public-transportation.zip", "TripIdToDate.zip"
MOTIS_IMAGE = "ghcr.io/motis-project/motis@" + h0.render_drafts.MOTIS_DIGEST
CODEX_RT = Path.home() / ".codex/worktrees/8007/OpenTransit/.runtime"


class StepFailed(RuntimeError):
    pass


class Job:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
        self.local_date = datetime.now().astimezone().date()
        args.logs.mkdir(parents=True, exist_ok=True)
        self.log_path = args.logs / f"daily-{self.stamp}.log"
        self.summary_path = args.logs / f"daily-{self.stamp}.json"
        self.work = args.logs / f"daily-{self.stamp}"
        self.work.mkdir()
        self.summary: dict = {
            "kind": "h1-daily-refresh",
            "startedAt": now(),
            "log": str(self.log_path),
            "steps": [],
        }

    def log(self, text: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(text if text.endswith("\n") else text + "\n")

    def save(self) -> None:
        self.summary_path.write_text(json.dumps(self.summary, indent=2) + "\n", encoding="utf-8")

    def run(self, name: str, argv: list[str], *, env: dict | None = None, ok=(0,)) -> str:
        """Run one command, log it, record the step; raise StepFailed on a bad exit code."""
        started = time.monotonic()
        self.log(f"\n=== {now()} {name}: {' '.join(map(str, argv))}")
        done = subprocess.run(
            [str(a) for a in argv],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        self.log(done.stdout)
        if done.stderr.strip():
            self.log("--- stderr\n" + done.stderr)
        self.log(f"=== exit {done.returncode} after {time.monotonic() - started:.1f} s")
        self.record(name, done.returncode in ok, seconds=time.monotonic() - started)
        if done.returncode not in ok:
            raise StepFailed(f"{name} exited {done.returncode}")
        return done.stdout

    def record(self, name: str, ok: bool, **detail) -> None:
        if "seconds" in detail:
            detail["seconds"] = round(detail["seconds"], 1)
        self.summary["steps"].append({"step": name, "at": now(), "ok": ok, **detail})
        self.save()

    def opentransit(self, *args) -> list[str]:
        return ["uv", "run", "--project", REPO / "services/api", "--locked", "opentransit", *args]

    def publisher(self, *args) -> list[str]:
        script = TOOLS / "publish_generation.py"
        return [
            "uv",
            "run",
            "--project",
            REPO / "services/api",
            "--locked",
            "python",
            script,
            *args,
        ]


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha_pair(manifest: dict) -> dict:
    return {name: manifest["inputs"][name]["sha256"] for name in (GTFS, TRIPS)}


def load_current(releases: Path) -> tuple[dict, dict, Path, Path | None]:
    pointer = json.loads((releases / "current.json").read_text(encoding="utf-8"))
    current_path = Path(pointer["release"])
    current = json.loads(current_path.read_text(encoding="utf-8"))
    plan = json.loads((current_path.parent / "release-plan.json").read_text(encoding="utf-8"))
    previous = Path(pointer["previous"]) if pointer.get("previous") else None
    return current, plan, current_path, previous


def alb_url(repo: Path) -> str:
    evidence = json.loads(
        (repo / "services/api/results/h1-preview-20261031-01.json").read_text(encoding="utf-8")
    )
    lbs = [r for r in evidence["resources"] if r["type"] == "load-balancer" and not r["deletedAt"]]
    return "http://" + lbs[-1]["dnsName"]


def alb_probe(job: Job, base: str, corpus_path: Path) -> dict:
    """The H-0 probe through the ALB (readiness, status, ten journeys, latency, demo)."""
    result: dict = {"base": base, "from": "operator machine (Israel)"}
    status, ms, payload = h0.http("GET", base + "/readyz")
    result["readyz"] = {"status": status, "ms": round(ms, 1)}
    status, ms, payload = h0.http("GET", base + "/v1/status")
    body = json.loads(payload) if status == 200 else {}
    result["status"] = {"status": status, "ms": round(ms, 1), "body": body}
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    journeys = []
    for case in corpus["cases"]:
        params = case["params"]
        (flat, flon), (tlat, tlon) = (
            map(float, params[k].split(",")) for k in ("fromPlace", "toPlace")
        )
        request = {
            "from": {"kind": "coordinate", "latitude": flat, "longitude": flon},
            "to": {"kind": "coordinate", "latitude": tlat, "longitude": tlon},
            "departAt": case.get("probeTime") or params["time"],
            "results": 1,
        }
        status, ms, payload = h0.http("POST", base + "/v1/journeys", request, timeout=60)
        count = len(json.loads(payload)["data"].get("journeys", [])) if status == 200 else None
        expected = case.get("expect", {}).get("outcome")
        passed = status == 200 and (
            expected == "either" or ((count or 0) > 0) == (expected == "route")
        )
        journeys.append({"id": case["id"], "status": status, "ms": round(ms, 1), "pass": passed})
    result["journeys"] = journeys
    result["journeysPassed"] = sum(j["pass"] for j in journeys)
    demo = subprocess.run(
        [str(a) for a in job.opentransit("demo", "--api-url", base)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    job.log("--- demo\n" + demo.stdout[-1500:] + demo.stderr[-500:])
    result["demoExit"] = demo.returncode
    result["ok"] = (
        result["readyz"]["status"] == 200
        and demo.returncode == 0
        and all(j["pass"] for j in journeys)
    )
    return result


def local_probe(job: Job, generation: Path, corpus: Path) -> None:
    """Probe the new generation's MOTIS graph in a local container (own name and port)."""
    name, port = f"ot-daily-motis-{job.stamp.lower()}", job.args.probe_port
    job.run(
        "probe-engine-start",
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "--read-only",
            "--tmpfs",
            "/tmp",
            "-p",
            f"127.0.0.1:{port}:8080",
            "-v",
            f"{generation}:/generation:ro",
            "--entrypoint",
            "/motis",
            MOTIS_IMAGE,
            "server",
            "-d",
            "/generation/motis",
        ],
    )
    try:
        engine = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            status, _, _ = h0.http(
                "GET",
                engine + "/api/v6/plan?fromPlace=32.0836,34.7981&toPlace=32.0838,34.8044",
                timeout=10,
            )
            if status == 200:
                break
            time.sleep(10)
        job.run(
            "probe",
            job.opentransit(
                "probe",
                "--generation",
                generation,
                "--engine-url",
                engine,
                "--queries",
                corpus,
                "--output",
                job.work / "probe.json",
            ),
        )
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source-root", type=Path, default=Path("D:/ot/src"))
    parser.add_argument("--generations-root", type=Path, default=Path("D:/ot/generations"))
    parser.add_argument("--logs", type=Path, default=Path("D:/ot/logs"))
    parser.add_argument("--releases", type=Path, default=Path("D:/ot/releases"))
    parser.add_argument(
        "--photon-jar", type=Path, default=CODEX_RT / "m4-photon-spike-20260930/photon-1.3.0.jar"
    )
    parser.add_argument("--osm-reader-path", type=Path, default=CODEX_RT / "osm-reader-20260930")
    parser.add_argument(
        "--corpus", type=Path, default=REPO / "services/api/tools/acceptance-probe-corpus.json"
    )
    parser.add_argument("--probe-port", type=int, default=59380)
    parser.add_argument("--profile", default=PROFILE)
    args = parser.parse_args(argv)
    job = Job(args)
    code = 1
    try:
        code = refresh(job)
    except StepFailed as exc:
        job.summary["failure"] = str(exc)
    except Exception as exc:  # recorded, never swallowed silently
        job.summary["failure"] = f"{type(exc).__name__}: {exc}"
        job.log(f"!!! {job.summary['failure']}")
    job.summary["finishedAt"] = now()
    job.summary["outcome"] = "ok" if code == 0 else "failed"
    job.save()
    job.log(f"\n=== {now()} outcome {job.summary['outcome']}")
    return code


def refresh(job: Job) -> int:
    args = job.args
    current, current_plan, current_path, _ = load_current(args.releases)
    serving_dir = Path(current_plan["verify"]["generationDir"])
    serving_manifest = json.loads((serving_dir / "manifest.json").read_text(encoding="utf-8"))
    job.summary["serving"] = {
        "generationId": current["generationId"],
        "taskDefinitionArn": current["taskDefinitionArn"].rsplit("/", 1)[-1],
        "release": str(current_path),
    }

    # 1-2. fetch and validate
    out = job.run("fetch", job.opentransit("fetch", "--output", args.source_root))
    snapshot = Path(out.strip().splitlines()[-1])
    check = args.source_root / "checks" / f"{snapshot.name}.json"
    record = json.loads(check.read_text(encoding="utf-8"))
    job.run(
        "validate",
        job.opentransit(
            "validate",
            "--gtfs",
            snapshot / GTFS,
            "--mapping",
            snapshot / TRIPS,
            "--output",
            job.work / "validate.json",
        ),
    )
    fetched = {
        GTFS: record["sources"]["gtfs"]["sha256"],
        TRIPS: record["sources"]["trip_id_to_date"]["sha256"],
    }
    changed = fetched != sha_pair(serving_manifest)
    job.summary["source"] = {
        "snapshot": str(snapshot),
        "check": str(check),
        "pairedValidation": record.get("pairedValidation"),
        "changedFromServing": changed,
        "sha256": {k: v[:12] for k, v in fetched.items()},
    }
    job.save()

    output = args.releases / job.stamp
    common = ["--output", output, "--previous-release", current_path]
    if changed:
        # 3-4. new dated generation, then its own local probe
        name = job.local_date.strftime("%Y%m%d")
        generation = args.generations_root / name
        suffix = ord("b")
        while generation.exists():
            generation = args.generations_root / f"{name}{chr(suffix)}"
            suffix += 1
        job.run(
            "build-generation",
            job.opentransit(
                "build-generation",
                "--snapshot",
                snapshot,
                "--output",
                generation,
                "--first-day",
                job.local_date.isoformat(),
                "--days",
                "31",
                "--memory-gib",
                "6",
                "--addresses",
                "--photon-jar",
                args.photon_jar,
                "--photon-memory-gib",
                "2",
                "--osm-reader-path",
                args.osm_reader_path,
            ),
        )
        manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
        coverage = manifest["coverage"]
        corpus, _ = redate_probe_corpus(
            json.loads(args.corpus.read_text(encoding="utf-8")),
            parse_instant(coverage["from"]),
            parse_instant(coverage["until"]),
        )
        corpus_path = job.work / "probe-queries.json"
        corpus_path.write_text(
            json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        local_probe(job, generation, corpus_path)
        publish = [
            "publish",
            "--generation",
            generation,
            "--probe-queries",
            corpus_path,
            "--photon-data",
            generation / "photon",
            "--photon-jar-dir",
            args.photon_jar.parent,
            "--build",
            *common,
        ]
    else:
        # Unchanged pair: renew freshness of the serving generation with today's check.
        job.record("build-generation", True, skipped="feed pair unchanged since the serving build")
        job.record("probe", True, skipped="no new generation; the in-task verifier probes it")
        corpus_path = Path(current_plan["verify"]["probeQueries"])
        publish = [
            "publish",
            "--generation",
            serving_dir,
            "--probe-queries",
            corpus_path,
            "--photon-data",
            current_plan["verify"]["photonData"],
            "--source-check",
            check,
            *[f"--local-image={n}={ref}" for n, ref in sorted(current["localTags"].items())],
            *common,
        ]
    job.run("publish", job.publisher(*publish))

    # 6. push, register, update and wait
    registry = current["taskDefinitionArn"].split(":")[4] + f".dkr.ecr.{REGION}.amazonaws.com"
    role = f"arn:aws:iam::{registry.split('.')[0]}:role/{SERVICE}-execution"
    job.run(
        "push",
        job.publisher(
            "push",
            "--plan",
            output / "release-plan.json",
            "--region",
            REGION,
            "--registry",
            registry,
            "--cluster",
            CLUSTER,
            "--service",
            SERVICE,
            "--execution-role-arn",
            role,
            "--vpc-cidr",
            VPC_CIDR,
            "--profile",
            args.profile,
            "--execute-aws",
            "--wait",
        ),
    )
    registered = output / "release-registered.json"
    (args.releases / "current.json").write_text(
        json.dumps(
            {"release": str(registered), "previous": str(current_path), "at": now()}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    new_release = json.loads(registered.read_text(encoding="utf-8"))
    job.summary["deployed"] = {
        "taskDefinition": new_release["taskDefinitionArn"].rsplit("/", 1)[-1],
        "generationId": new_release["generationId"],
        "sourceCheckedAt": new_release["sourceCheckedAt"],
        "deployment": new_release.get("deployment"),
        "pushes": new_release.get("pushes"),
    }
    job.save()

    # 7. post-deploy probe through the ALB
    started = time.monotonic()
    probe = alb_probe(job, alb_url(REPO), corpus_path)
    job.record("alb-probe", probe["ok"], seconds=time.monotonic() - started, **probe)
    if not probe["ok"]:
        raise StepFailed("post-deploy ALB probe failed (previous release: see current.json)")

    # 8. retention: candidates only
    job.run(
        "retention",
        job.opentransit(
            "prune",
            "--generations-root",
            args.generations_root,
            "--active",
            new_release["generationId"],
            "--previous",
            current["generationId"],
            "--dry-run",
            "--output",
            job.work / "prune.json",
        ),
    )
    prune = json.loads((job.work / "prune.json").read_text(encoding="utf-8"))
    job.summary["retentionCandidates"] = prune.get("candidates", prune)
    return 0


if __name__ == "__main__":
    sys.exit(main())
