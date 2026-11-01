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
8. ``archive`` (with ``--archive-bucket``): source files content-addressed by SHA-256, the check
   record, the generation manifest, pipeline record and probe, and the release records;
9. ``retention``: ``opentransit prune --dry-run`` records candidates; nothing is deleted;
10. ``host-cleanup`` (cloud build host only, ``--host-cleanup``): frees the host's bounded disk
    of copies that are archived elsewhere (see ``host_cleanup``).

The serving release is tracked in ``<releases>/current.json`` (``release`` and ``previous``
paths); it moves only after a converged deployment. When the serving generation is not on this
machine (the cloud build host's first run), the feed counts as changed and a new generation is
built ("bootstrap"). Exit 0 only if every step passed; the log's last line is
``OPENTRANSIT_REFRESH_RESULT outcome=<ok|failed> mode=<built|bootstrap|unchanged|->`` and with
``--archive-bucket`` a one-line summary goes to ``runs/<stamp>.json``.
"""

from __future__ import annotations

import argparse
import json
import shutil
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
        self.summary_path.write_text(
            json.dumps(self.summary, indent=2) + "\n", encoding="utf-8"
        )

    def run(
        self, name: str, argv: list[str], *, env: dict | None = None, ok=(0,)
    ) -> str:
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
        return [
            "uv",
            "run",
            "--project",
            REPO / "services/api",
            "--locked",
            "opentransit",
            *args,
        ]

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

    def aws(self, *args) -> list[str]:
        profile = ["--profile", self.args.profile] if self.args.profile else []
        return ["aws", *profile, "--region", REGION, *args]

    def s3_has(self, key: str) -> bool:
        done = subprocess.run(
            self.aws(
                "s3api",
                "head-object",
                "--bucket",
                self.args.archive_bucket,
                "--key",
                key,
            ),
            capture_output=True,
        )
        return done.returncode == 0

    def s3_put(self, path: Path, key: str) -> None:
        argv = self.aws("s3", "cp", "--only-show-errors", str(path), self.s3(key))
        done = subprocess.run(argv, capture_output=True, text=True)
        self.log(
            f"--- s3 cp {path} {key}: exit {done.returncode} {done.stderr.strip()}"
        )
        if done.returncode != 0:
            raise StepFailed(f"archive upload {key} failed")

    def s3(self, key: str) -> str:
        return f"s3://{self.args.archive_bucket}/{key}"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha_pair(manifest: dict) -> dict:
    return {name: manifest["inputs"][name]["sha256"] for name in (GTFS, TRIPS)}


def serving_pair(release: dict, manifest: dict | None) -> dict | None:
    """The serving pair from its manifest, else from the release's renewing source check."""
    if manifest is not None:
        return sha_pair(manifest)
    sources = (release.get("sourceCheck") or {}).get("sources") or {}
    if not {"gtfs", "trip_id_to_date"} <= sources.keys():
        return None
    return {
        GTFS: sources["gtfs"]["sha256"],
        TRIPS: sources["trip_id_to_date"]["sha256"],
    }


def load_current(releases: Path) -> tuple[dict, dict, Path, Path | None]:
    pointer = json.loads((releases / "current.json").read_text(encoding="utf-8"))
    current_path = Path(pointer["release"])
    current = json.loads(current_path.read_text(encoding="utf-8"))
    plan = json.loads(
        (current_path.parent / "release-plan.json").read_text(encoding="utf-8")
    )
    previous = Path(pointer["previous"]) if pointer.get("previous") else None
    return current, plan, current_path, previous


def alb_url(repo: Path) -> str:
    evidence = json.loads(
        (repo / "services/api/results/h1-preview-20261031-01.json").read_text(
            encoding="utf-8"
        )
    )
    lbs = [
        r
        for r in evidence["resources"]
        if r["type"] == "load-balancer" and not r["deletedAt"]
    ]
    return "http://" + lbs[-1]["dnsName"]


def alb_probe(job: Job, base: str, corpus_path: Path) -> dict:
    """The H-0 probe through the ALB (readiness, status, ten journeys, latency, demo)."""
    origin = (
        "cloud build host (H-1 VPC)"
        if job.args.alb_url
        else "operator machine (Israel)"
    )
    result: dict = {"base": base, "from": origin}
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
        status, ms, payload = h0.http(
            "POST", base + "/v1/journeys", request, timeout=60
        )
        count = (
            len(json.loads(payload)["data"].get("journeys", []))
            if status == 200
            else None
        )
        expected = case.get("expect", {}).get("outcome")
        passed = status == 200 and (
            expected == "either" or ((count or 0) > 0) == (expected == "route")
        )
        journeys.append(
            {"id": case["id"], "status": status, "ms": round(ms, 1), "pass": passed}
        )
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
                engine
                + "/api/v6/plan?fromPlace=32.0836,34.7981&toPlace=32.0838,34.8044",
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
    parser.add_argument(
        "--generations-root", type=Path, default=Path("D:/ot/generations")
    )
    parser.add_argument("--logs", type=Path, default=Path("D:/ot/logs"))
    parser.add_argument("--releases", type=Path, default=Path("D:/ot/releases"))
    parser.add_argument(
        "--photon-jar",
        type=Path,
        default=CODEX_RT / "m4-photon-spike-20260930/photon-1.3.0.jar",
    )
    parser.add_argument(
        "--osm-reader-path", type=Path, default=CODEX_RT / "osm-reader-20260930"
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=REPO / "services/api/tools/acceptance-probe-corpus.json",
    )
    parser.add_argument("--probe-port", type=int, default=59380)
    parser.add_argument(
        "--profile",
        default=PROFILE,
        help="AWS CLI profile; '' uses the environment's credentials",
    )
    parser.add_argument(
        "--alb-url", help="post-deploy probe base URL (default: the H-1 evidence)"
    )
    parser.add_argument(
        "--archive-bucket", help="S3 bucket for sources, records and summaries"
    )
    parser.add_argument(
        "--min-free-gib",
        type=float,
        default=0,
        help="refuse to start below this much free disk",
    )
    parser.add_argument(
        "--host-cleanup",
        action="store_true",
        help="cloud build host: remove archived local copies after a successful run",
    )
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
    job.log(
        f"OPENTRANSIT_REFRESH_RESULT outcome={job.summary['outcome']} "
        f"mode={job.summary.get('mode', '-')} stamp={job.stamp}"
    )
    if args.archive_bucket:
        upload_summary(job)
    return code


def upload_summary(job: Job) -> None:
    """One-line summary at ``runs/<stamp>.json``, the full summary and log beside it."""
    s = job.summary
    line = {
        "stamp": job.stamp,
        "outcome": s["outcome"],
        "mode": s.get("mode"),
        "failure": s.get("failure"),
        "failedStep": next((x["step"] for x in s["steps"] if not x["ok"]), None),
        "startedAt": s["startedAt"],
        "finishedAt": s["finishedAt"],
        "generationId": (s.get("deployed") or {}).get("generationId"),
        "taskDefinition": (s.get("deployed") or {}).get("taskDefinition"),
        "sourceSha256": (s.get("source") or {}).get("sha256"),
    }
    one = job.work / "run-summary.json"
    one.write_text(json.dumps(line, separators=(",", ":")) + "\n", encoding="utf-8")
    for path, key in (
        (one, f"runs/{job.stamp}.json"),
        (job.summary_path, f"runs/{job.stamp}/summary.json"),
        (job.log_path, f"runs/{job.stamp}/daily.log"),
    ):
        done = subprocess.run(
            job.aws("s3", "cp", "--only-show-errors", str(path), job.s3(key)),
            capture_output=True,
            text=True,
        )
        if done.returncode != 0:  # the run's own outcome is already decided; log loudly
            job.log(f"!!! summary upload {key} failed: {done.stderr.strip()}")


def archive(
    job: Job, snapshot: Path, check: Path, generation: Path | None, release_dir: Path
) -> None:
    """Upload this run's sources and records; source files are keyed by SHA-256, so an
    unchanged feed is stored once."""
    started = time.monotonic()
    provenance = json.loads((snapshot / "provenance.json").read_text(encoding="utf-8"))
    uploaded, present = [], []
    for name, item in sorted(provenance["inputs"].items()):
        key = f"sources/sha256/{item['sha256']}/{name}"
        if job.s3_has(key):
            present.append(key)
        else:
            job.s3_put(snapshot / name, key)
            uploaded.append(key)
    records = [
        (snapshot / "provenance.json", f"snapshots/{snapshot.name}/provenance.json"),
        (check, f"checks/{check.name}"),
    ]
    if generation is not None:
        prefix = f"generations/{generation.name}"
        records += [
            (generation / "manifest.json", f"{prefix}/manifest.json"),
            (generation / "pipeline/pipeline.json", f"{prefix}/pipeline.json"),
            (job.work / "probe.json", f"{prefix}/probe.json"),
        ]
    for name in (
        "release-registered.json",
        "release-plan.json",
        "task-definition.registered.json",
    ):
        records.append((release_dir / name, f"releases/{release_dir.name}/{name}"))
    for path, key in records:
        if path.is_file():
            job.s3_put(path, key)
            uploaded.append(key)
    job.record(
        "archive",
        True,
        seconds=time.monotonic() - started,
        bucket=job.args.archive_bucket,
        uploaded=uploaded,
        alreadyPresent=present,
    )


def host_cleanup(job: Job, keep_releases: list[Path], latest_snapshot: Path) -> dict:
    """Free the build host's bounded disk after a successful run.

    Only copies that exist elsewhere are removed: generation directories other than the
    serving and previous ones whose manifest is in the archive (their data images are in ECR
    by digest), staging trees of older releases, local Docker images other than those two
    releases' (registry copies stay; ECR is never pruned) and source snapshot copies whose
    every file is in the archive under its SHA-256, except the newest (the fetch store's own
    objects, which change detection reads, stay)."""
    args = job.args
    keep_dirs, keep_tags = set(), set()
    for record_path in keep_releases:
        record_path = Path(record_path)
        plan_path = record_path.parent / "release-plan.json"
        if record_path.is_file():
            record = json.loads(record_path.read_text(encoding="utf-8"))
            keep_tags |= set(record["localTags"].values())
        if plan_path.is_file():
            gen = Path(
                json.loads(plan_path.read_text(encoding="utf-8"))["verify"][
                    "generationDir"
                ]
            )
            keep_dirs.add(gen.name)
    removed: dict = {
        "generations": [],
        "stages": [],
        "images": [],
        "snapshots": [],
        "kept": [],
    }
    for gen in sorted(p for p in args.generations_root.iterdir() if p.is_dir()):
        if gen.name in keep_dirs:
            continue
        if job.s3_has(f"generations/{gen.name}/manifest.json"):
            shutil.rmtree(gen)
            removed["generations"].append(gen.name)
        else:
            removed["kept"].append(f"generation {gen.name}: manifest not archived")
    keep_release_dirs = {Path(p).parent.name for p in keep_releases}
    for release in sorted(p for p in args.releases.iterdir() if p.is_dir()):
        if release.name not in keep_release_dirs and (release / "stage").exists():
            shutil.rmtree(release / "stage")
            removed["stages"].append(release.name)
    listing = subprocess.run(
        ["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True,
        text=True,
    ).stdout.split()
    for ref in listing:
        repo = ref.rsplit(":", 1)[0]
        ours = repo.startswith("ot-h1-") or ".dkr.ecr." in repo
        if ours and ref not in keep_tags:
            subprocess.run(["docker", "rmi", ref], capture_output=True)
            removed["images"].append(ref)
    subprocess.run(["docker", "image", "prune", "-f"], capture_output=True)
    subprocess.run(["docker", "builder", "prune", "-f"], capture_output=True)
    for snap in sorted((args.source_root / "snapshots").iterdir()):
        if snap == latest_snapshot or not (snap / "provenance.json").is_file():
            continue
        inputs = json.loads((snap / "provenance.json").read_text(encoding="utf-8"))[
            "inputs"
        ]
        keys = [f"sources/sha256/{i['sha256']}/{n}" for n, i in inputs.items()]
        keys.append(f"snapshots/{snap.name}/provenance.json")
        if all(job.s3_has(k) for k in keys):
            shutil.rmtree(snap)
            removed["snapshots"].append(snap.name)
        else:
            removed["kept"].append(f"snapshot {snap.name}: not fully archived")
    removed["freeGiB"] = round(disk_free_gib(args.generations_root), 1)
    return removed


def disk_free_gib(path: Path) -> float:
    path.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(path).free / 2**30


def refresh(job: Job) -> int:
    args = job.args
    if args.min_free_gib:
        free = disk_free_gib(args.generations_root)
        job.record("disk", free >= args.min_free_gib, freeGiB=round(free, 1))
        if free < args.min_free_gib:
            raise StepFailed(f"disk: {free:.1f} GiB free, need {args.min_free_gib:g}")
    current, current_plan, current_path, _ = load_current(args.releases)
    serving_dir = Path(current_plan["verify"]["generationDir"])
    on_host = (serving_dir / "manifest.json").is_file()
    serving_manifest = (
        json.loads((serving_dir / "manifest.json").read_text(encoding="utf-8"))
        if on_host
        else None
    )
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
    if on_host:
        changed = fetched != sha_pair(serving_manifest)
        job.summary["mode"] = "built" if changed else "unchanged"
    else:
        # The serving generation and its images are not on this machine, so freshness cannot
        # be renewed from here: build a new generation instead.
        changed = True
        job.summary["mode"] = "bootstrap"
    job.summary["source"] = {
        "snapshot": str(snapshot),
        "check": str(check),
        "pairedValidation": record.get("pairedValidation"),
        "changedFromServing": fetched != serving_pair(current, serving_manifest),
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
        manifest = json.loads(
            (generation / "manifest.json").read_text(encoding="utf-8")
        )
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
        job.record(
            "build-generation",
            True,
            skipped="feed pair unchanged since the serving build",
        )
        job.record(
            "probe", True, skipped="no new generation; the in-task verifier probes it"
        )
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
            *[
                f"--local-image={n}={ref}"
                for n, ref in sorted(current["localTags"].items())
            ],
            *common,
        ]
    job.run("publish", job.publisher(*publish))

    # 6. push, register, update and wait
    registry = (
        current["taskDefinitionArn"].split(":")[4] + f".dkr.ecr.{REGION}.amazonaws.com"
    )
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
            *(["--profile", args.profile] if args.profile else []),
            "--execute-aws",
            "--wait",
        ),
    )
    registered = output / "release-registered.json"
    (args.releases / "current.json").write_text(
        json.dumps(
            {"release": str(registered), "previous": str(current_path), "at": now()},
            indent=2,
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
    probe = alb_probe(job, args.alb_url or alb_url(REPO), corpus_path)
    passed = probe.pop("ok")
    job.record("alb-probe", passed, seconds=time.monotonic() - started, **probe)
    if not passed:
        raise StepFailed(
            "post-deploy ALB probe failed (previous release: see current.json)"
        )

    # 8. archive: sources by content hash, then the records of this run
    if args.archive_bucket:
        archive(job, snapshot, check, generation if changed else None, output)

    # 9. retention: candidates only
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
    job.save()

    if args.host_cleanup:
        keep = [registered, current_path]
        job.record("host-cleanup", True, **host_cleanup(job, keep, snapshot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
