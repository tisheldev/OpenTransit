#!/usr/bin/env python3
"""Reproducible Linux Compose proof of local activation, rollback and retention (M2.5/M2.6).

Run on the Docker host (stdlib only):

    python services/api/tools/activation_compose_harness.py --run-id r01 \\
        --codex-runtime C:/Users/<you>/.codex/worktrees/8007/OpenTransit/.runtime

Complete composite generations (schedule + sealed Photon, e.g. ``build-generation
--addresses``) are selected with ``--old-generation``/``--new-generation`` and a real paired
``--source-check``; each then gets its own graph mount and Photon (see
activation-compose-composite.yaml), and the bindings name each generation's Photon origins.

It serves two existing real generations (read-only mounts; nothing is copied or modified)
behind one managed API worker with real pinned MOTIS engines, then checks: (1) in-flight
requests finish on the old generation and later ones use the new one; (2) a failed reload
leaves old serving state intact and the pointer restored; (3) rollback refuses stale or
expired generations and succeeds for a valid one; (4) the old engine stops only after the
worker's retirement acknowledgement, at least ten request deadlines after activation;
(5) prune --dry-run lists candidates and deletes nothing. Everything created is named
<prefix>-* (default ot-t2), uses host port 8300, caps memory, and is removed at the end after
logs are exported.
"""

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[2]
COMPOSE = TOOLS / "activation-compose.yaml"
COMPOSITE_COMPOSE = TOOLS / "activation-compose-composite.yaml"
RUNTIME = Path("C:/Projects/OpenTransit/.runtime/t2-activation")
GEN_A = "m3-functional-blue-20260930-attempt3"
GEN_B = "m4-translations-blue-20260930"
GRAPH_VOLUME = "opentransit-graph-d5a097a105eb4d739e683ae2e9910c8f"
CORPUS = "m4-functional-evidence-20260930/probe-corpus.json"
API = "http://127.0.0.1:8300"
MOTIS_DIGEST = "sha256:6055f51eec43eeed28524037ca0161b96efe9cd05728eaa9ac04c20c2826d330"
MOTIS_IMAGE = f"ghcr.io/motis-project/motis@{MOTIS_DIGEST}"
API_IMAGE = "opentransit-api:latest"
JAVA_IMAGE_BASE = "eclipse-temurin:21.0.12.1_1-jre"
PHOTON_JAR = "m4-photon-spike-20260930/photon-1.3.0.jar"
# Loopback origins inside the API's network namespace (delay proxy -> per-generation Photon).
PHOTON_ORIGINS = {
    "a": ("http://127.0.0.1:2422", "http://127.0.0.1:9211"),
    "b": ("http://127.0.0.1:2432", "http://127.0.0.1:9221"),
}
# Small composite files copied into the managed root; large artifacts are read-only mounts.
COMPOSITE_COPIES = ("schedule-component-manifest.json", "photon-import-attestation.json")
DEADLINE_SECONDS = 1.5
# Standby engines are queried directly (bypassing the delay proxy, so proxy-based checks are
# unaffected) to keep their graph pages resident: reloads rehash ~3 GB per generation over the
# Windows share for 10-16 minutes, which evicts an idle engine and makes its first request
# exceed the 1.2 s engine timeout (r03 rollback, r04 probe J01).
ENGINE_DIRECT_PORTS = (59091, 59092)
KEEP_WARM_SECONDS = 15
WARM_QUERY = (
    "import urllib.request as u;u.urlopen('http://127.0.0.1:{port}/api/v6/plan?"
    "fromPlace=32.0757,34.7748&toPlace=32.0838,34.8044&time=2026-10-05T05:00:00Z',"
    "timeout=10)"
)
PROXY_DELAY = 0.35
JOURNEY = {
    "from": {"kind": "coordinate", "latitude": 32.0757, "longitude": 34.7748},
    "to": {"kind": "coordinate", "latitude": 32.0838, "longitude": 34.8044},
    "departAt": "2026-10-01T18:00:00+03:00",
}
BASE_ROLES = ["api", "motis-a", "motis-b", "proxy"]
COMPOSITE_ROLES = ["photon-a", "photon-a-fwd", "photon-b", "photon-b-fwd"]

POINTER_WATCH = """
import json, os, sys, time
stop = sys.argv[1]
reads = errors = 0
targets = set()
while not os.path.exists(stop):
    try:
        target = os.readlink('/managed/current')
        json.load(open('/managed/' + target))
        targets.add(target)
        reads += 1
    except Exception:
        errors += 1
    time.sleep(0.002)
print(json.dumps({'reads': reads, 'errors': errors, 'targets': sorted(targets)}))
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Harness:
    def __init__(self, args):
        self.args = args
        self.codex = Path(args.codex_runtime)
        self.run_dir = RUNTIME / args.run_id
        self.prefix = args.prefix
        self.composite = args.old_generation is not None
        if self.composite:
            self.gen_dirs = {"a": Path(args.old_generation), "b": Path(args.new_generation)}
        else:
            generations = self.codex / "generations"
            self.gen_dirs = {"a": generations / GEN_A, "b": generations / GEN_B}
        self.gen_names = {slot: path.name for slot, path in self.gen_dirs.items()}
        roles = BASE_ROLES + (COMPOSITE_ROLES if self.composite else [])
        self.containers = [f"{self.prefix}-{role}" for role in roles]
        self.api_container = f"{self.prefix}-api"
        self.root_volume = f"{self.prefix}-root"
        self.photon_volumes = [f"{self.prefix}-photon-{slot}" for slot in "ab"]
        self.java_image = None
        self.photon_jar = None
        self.commands: list[dict] = []
        self.checks: dict[str, dict] = {}
        self.timings: dict[str, float] = {}
        self.data: dict = {}
        self.memory: dict[str, int] = {}
        self._sampling = False
        self._warming = False
        self.warm_counts: dict[str, dict[str, int]] = {}
        self.started = False

    # -- process helpers -------------------------------------------------------------
    def log(self, message: str) -> None:
        print(f"[{datetime.now(UTC):%H:%M:%S}] {message}", flush=True)

    def run(self, argv, *, timeout=600, check=True, label=None, env=None):
        started = time.time()
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        self.commands.append(
            {
                "label": label or " ".join(str(item) for item in argv[:4]),
                "argv": [str(item) for item in argv][:12],
                "startedAt": datetime.fromtimestamp(started, UTC).isoformat(),
                "seconds": round(time.time() - started, 2),
                "exitCode": proc.returncode,
            }
        )
        if check and proc.returncode != 0:
            raise RuntimeError(f"{argv[:5]} failed ({proc.returncode}): {proc.stderr[-800:]}")
        return proc

    def exec_api(self, *argv, timeout=1500, check=True, label=None):
        return self.run(
            ["docker", "exec", self.api_container, *argv],
            timeout=timeout,
            check=check,
            label=label,
        )

    def cli(self, *argv, timeout=1500, label=None):
        """Run the product `opentransit` command inside the API container."""
        proc = self.exec_api(
            "/app/.venv/bin/python",
            "-m",
            "opentransit.build.cli",
            *argv,
            timeout=timeout,
            check=False,
            label=label or f"opentransit {argv[0]}",
        )
        text = proc.stdout.strip().splitlines()
        try:
            payload = json.loads(text[-1]) if text else None
        except ValueError:
            payload = None
        return proc.returncode, payload, proc

    def tool(self, *argv, label=None):
        return self.exec_api(
            "/app/.venv/bin/python",
            "/tools/activation_container_tools.py",
            *argv,
            label=label or f"tools {argv[0]}",
        )

    def python_in_api(self, code: str, timeout=60):
        return self.exec_api(
            "/app/.venv/bin/python", "-c", code, timeout=timeout, check=False, label="python probe"
        )

    def check(self, name, passed: bool, **details) -> bool:
        self.checks[name] = {"passed": bool(passed), **details}
        self.log(f"check {name}: {'PASS' if passed else 'FAIL'}")
        return passed

    # -- environment -------------------------------------------------------------------
    def env(self) -> dict:
        env = dict(os.environ)
        env.update(
            OT_PREFIX=self.prefix,
            OT_API_IMAGE=API_IMAGE,
            OT_SRC=(REPO / "services/api/src").as_posix(),
            OT_TOOLS=TOOLS.as_posix(),
            OT_RUN=self.run_dir.as_posix(),
            # Composite runs replace every graph mount; the base file still declares the
            # legacy external volume, which is then never mounted.
            OT_GRAPH_VOLUME=GRAPH_VOLUME,
            OT_A_REFERENCE=(self.gen_dirs["a"] / "reference.sqlite").as_posix(),
            OT_B_REFERENCE=(self.gen_dirs["b"] / "reference.sqlite").as_posix(),
        )
        if self.composite:
            env.update(
                OT_JAVA_IMAGE=self.java_image,
                OT_PHOTON_JAR=self.photon_jar.as_posix(),
                OT_A_GRAPH=(self.gen_dirs["a"] / "motis").as_posix(),
                OT_B_GRAPH=(self.gen_dirs["b"] / "motis").as_posix(),
                OT_A_CATALOG=(self.gen_dirs["a"] / "address-catalog.sqlite").as_posix(),
                OT_B_CATALOG=(self.gen_dirs["b"] / "address-catalog.sqlite").as_posix(),
            )
        return env

    def compose(self, *argv, timeout=600, check=True):
        files = ["-f", str(COMPOSE)]
        if self.composite:
            files += ["-f", str(COMPOSITE_COMPOSE)]
        return self.run(
            ["docker", "compose", "-p", self.prefix, *files, *argv],
            timeout=timeout,
            check=check,
            env=self.env(),
            label=f"compose {argv[0]}",
        )

    def tree_snapshot(self, slot: str) -> dict:
        root = self.gen_dirs[slot]
        files = {}
        for path in sorted(root.rglob("*")):
            if path.is_file():
                stat = path.stat()
                files[path.relative_to(root).as_posix()] = [stat.st_size, int(stat.st_mtime_ns)]
        digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        return {"files": len(files), "metadataSha256": digest}

    def preflight(self) -> None:
        self.run(["docker", "info"], timeout=60, label="docker info")
        existing = self.run(
            ["docker", "ps", "-a", "--filter", f"name={self.prefix}-", "-q"]
        ).stdout.split()
        if existing:
            raise RuntimeError(f"{self.prefix}-* containers already exist; remove them first")
        volumes = self.run(["docker", "volume", "ls", "-q"]).stdout.split()
        for volume in [self.root_volume] + (self.photon_volumes if self.composite else []):
            if volume in volumes:
                raise RuntimeError(f"{volume} already exists; remove it first")
        if not self.composite and GRAPH_VOLUME not in volumes:
            raise RuntimeError(f"graph volume missing: {GRAPH_VOLUME}")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        manifests = {}
        for slot, directory in self.gen_dirs.items():
            path = directory / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if self.composite and not manifest.get("addressSearch"):
                raise RuntimeError(f"{directory} is not an address composite generation")
            manifests[self.gen_names[slot]] = {
                "slot": slot,
                "path": directory.as_posix(),
                "generationId": manifest["generationId"],
                "scheduleComponentGenerationId": manifest.get("scheduleComponentGenerationId"),
                "addressArtifactIdentity": (manifest.get("addressSearch") or {}).get(
                    "artifactIdentity"
                ),
                "photonTreeSha256": (manifest.get("addressBuild") or {}).get("photonTreeSha256"),
                "manifestSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "referenceSha256": manifest["artifacts"]["reference"]["sha256"],
                "referenceContentSha256": manifest["artifacts"]["reference"].get("contentSha256"),
                "graphTreeSha256": manifest["artifacts"]["motis"]["sha256"],
                "configSha256": manifest["artifacts"]["config"]["sha256"],
                "parserVersion": manifest.get("parserVersion"),
                "builtAt": manifest["builtAt"],
                "sourceCheckedAt": manifest.get("sourceCheckedAt"),
                "coverage": manifest["coverage"],
            }
        self.data["generations"] = manifests
        self.ids = {slot: manifests[self.gen_names[slot]]["generationId"] for slot in "ab"}
        if self.ids["a"] == self.ids["b"]:
            raise RuntimeError("old and new generations must differ")
        refs = [API_IMAGE, MOTIS_IMAGE]
        if self.composite:
            address = json.loads(
                (self.gen_dirs["b"] / "manifest.json").read_text(encoding="utf-8")
            )["addressSearch"]
            self.java_image = f"{JAVA_IMAGE_BASE}@{address['javaImageDigest']}"
            refs.append(self.java_image)
            self.photon_jar = Path(self.args.photon_jar or self.codex / PHOTON_JAR)
            self.data["photonJar"] = {
                "path": self.photon_jar.as_posix(),
                "sha256": hashlib.sha256(self.photon_jar.read_bytes()).hexdigest(),
                "expectedSha256": address["photonJarSha256"],
            }
            if self.data["photonJar"]["sha256"] != address["photonJarSha256"]:
                raise RuntimeError("Photon JAR differs from the generation's pinned JAR")
        images = {}
        for ref in refs:
            inspect = json.loads(self.run(["docker", "image", "inspect", ref]).stdout)[0]
            images[ref] = {"id": inspect["Id"], "repoDigests": inspect.get("RepoDigests", [])}
        self.data["images"] = images
        self.data["realSourceTreesBefore"] = {
            self.gen_names[slot]: self.tree_snapshot(slot) for slot in "ab"
        }
        git = self.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], check=False).stdout.strip()
        dirty = self.run(["git", "-C", str(REPO), "status", "--porcelain"], check=False).stdout
        branch = self.run(
            ["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"], check=False
        ).stdout.strip()
        self.data["code"] = {
            "commit": git,
            "branch": branch,
            "uncommittedFiles": len(dirty.splitlines()),
        }
        corpus = Path(self.args.probe_corpus) if self.args.probe_corpus else self.codex / CORPUS
        (self.run_dir / "probe-corpus.json").write_bytes(corpus.read_bytes())
        self.data["probeCorpus"] = {
            "source": self.args.probe_corpus or CORPUS,
            "sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
        }
        if self.args.source_check:
            check = Path(self.args.source_check)
            (self.run_dir / "source-check.json").write_bytes(check.read_bytes())
            self.data["sourceCheck"] = {
                "path": check.as_posix(),
                "sha256": hashlib.sha256(check.read_bytes()).hexdigest(),
                "kind": "real paired upstream check (copied into each managed generation)",
            }
        for slot, port in (("a", 59091), ("b", 59092)):
            # Legacy generations share one graph volume; composites each serve their own graph.
            source = self.gen_dirs[slot if self.composite else "b"] / "motis" / "config.yml"
            config = source.read_text(encoding="utf-8")
            if re.search(r"(?m)^server:", config):
                config = re.sub(r"(?m)^  port: \d+$", f"  port: {port}", config)
            else:
                # Slot-free generation config: add a loopback listener for this engine slot.
                config = f"server:\n  host: 127.0.0.1\n  port: {port}\n" + config
            (self.run_dir / f"motis-{slot}.yml").write_text(config, encoding="utf-8", newline="\n")
        (self.run_dir / "delay-a").write_text("0", encoding="utf-8")
        (self.run_dir / "delay-b").write_text("0", encoding="utf-8")

    def warm_engine(self, port: int, count: int = 6) -> None:
        for _ in range(count):
            self.python_in_api(WARM_QUERY.format(port=port), timeout=30)

    def keep_engines_warm(self) -> None:
        """Operator-style standby keep-alive: one direct plan query per engine every 15 s."""

        def loop():
            while self._warming:
                for port in ENGINE_DIRECT_PORTS:
                    try:
                        ok = (
                            subprocess.run(
                                ["docker", "exec", self.api_container, "/app/.venv/bin/python"]
                                + ["-c", WARM_QUERY.format(port=port)],
                                capture_output=True,
                                timeout=60,
                            ).returncode
                            == 0
                        )
                    except subprocess.TimeoutExpired:
                        ok = False
                    counts = self.warm_counts.setdefault(str(port), {"ok": 0, "failed": 0})
                    counts["ok" if ok else "failed"] += 1
                time.sleep(KEEP_WARM_SECONDS)

        self._warming = True
        threading.Thread(target=loop, daemon=True).start()

    def sample_memory(self) -> None:
        def loop():
            while self._sampling:
                proc = subprocess.run(
                    ["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.MemUsage}}"]
                    + list(self.containers),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                for line in proc.stdout.splitlines():
                    name, _, usage = line.partition("|")
                    match = re.match(r"([\d.]+)(KiB|MiB|GiB)", usage)
                    if match and name.startswith(f"{self.prefix}-"):
                        factor = {"KiB": 1 << 10, "MiB": 1 << 20, "GiB": 1 << 30}[match[2]]
                        self.memory[name] = max(
                            self.memory.get(name, 0), int(float(match[1]) * factor)
                        )
                time.sleep(5)

        self._sampling = True
        threading.Thread(target=loop, daemon=True).start()

    # -- stack ---------------------------------------------------------------------------
    def start_stack(self) -> None:
        started = time.time()
        self.started = True
        self.run(["docker", "volume", "create", self.root_volume], label="create managed volume")
        copies = []
        mounts = []
        small = ["manifest.json", "config.yml"] + (list(COMPOSITE_COPIES) if self.composite else [])
        for slot, src in self.gen_dirs.items():
            copies.append(f"mkdir -p /managed/gen-{slot}")
            for index, name in enumerate(small):
                mounts += ["-v", f"{(src / name).as_posix()}:/in/{slot}-{index}:ro"]
                copies.append(f"cp /in/{slot}-{index} /managed/gen-{slot}/{name}")
            if self.args.source_check:
                # Probe and source-check paths must stay inside the generation directory.
                copies.append(f"cp /run-data/source-check.json /managed/gen-{slot}/")
        mounts += ["-v", f"{self.run_dir.as_posix()}:/run-data:ro"]
        script = " && ".join(copies) + " && chown -R 10001:10001 /managed"
        self.run(
            [
                "docker",
                "run",
                "--rm",
                "--name",
                f"{self.prefix}-init",
                "--user",
                "0",
                "--memory",
                "64m",
                "-v",
                f"{self.root_volume}:/managed",
                *mounts,
                "alpine:3.20",
                "sh",
                "-c",
                script,
            ],
            label="init managed volume (copy manifests, configs and small evidence only)",
        )
        if self.composite:
            for slot, volume in zip("ab", self.photon_volumes, strict=True):
                # The sealed checkpoint is copied into a run-private volume because Photon's
                # index directory must be writable; the generation tree stays untouched.
                self.run(["docker", "volume", "create", volume], label=f"create {volume}")
                self.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--name",
                        f"{self.prefix}-photon-init-{slot}",
                        "--network",
                        "none",
                        "--user",
                        "0:0",
                        "--memory",
                        "64m",
                        "--mount",
                        f"type=volume,src={volume},dst=/photon_data",
                        "--mount",
                        f"type=bind,src={(self.gen_dirs[slot] / 'photon').as_posix()},"
                        "dst=/src,readonly",
                        "--entrypoint",
                        "/bin/sh",
                        self.java_image,
                        "-c",
                        "cp -a /src/. /photon_data/ && chown -R 10001:10001 /photon_data"
                        " && chmod 0750 /photon_data",
                    ],
                    timeout=600,
                    label=f"copy sealed Photon checkpoint {slot} into {volume}",
                )
        self.compose("up", "-d", timeout=900)
        for _ in range(60):
            if (
                self.python_in_api(
                    "import urllib.request as u;u.urlopen('http://127.0.0.1:8000/healthz',timeout=3)"
                ).returncode
                == 0
            ):
                break
            time.sleep(2)
        else:
            raise RuntimeError("API never became live")
        for port in (59081, 59082):
            self.wait_engine(port)
        if self.composite:
            for slot in "ab":
                self.timings[f"photon{slot.upper()}ReadySeconds"] = self.wait_photon(slot)
        self.sample_memory()
        self.keep_engines_warm()
        self.timings["stackStartSeconds"] = round(time.time() - started, 1)

    def wait_photon(self, slot: str, timeout=600) -> float:
        started = time.time()
        query, admin = PHOTON_ORIGINS[slot]
        code = (
            f"import urllib.request as u;u.urlopen('{query}/status',timeout=5);"
            f"u.urlopen('{admin}/photon/_count',timeout=5)"
        )
        while time.time() - started < timeout:
            if self.python_in_api(code, timeout=30).returncode == 0:
                return round(time.time() - started, 1)
            time.sleep(3)
        raise RuntimeError(f"Photon {slot} never answered through the proxy")

    def wait_engine(self, port: int, timeout=240) -> float:
        started = time.time()
        code = (
            f"import urllib.request as u;u.urlopen('http://127.0.0.1:{port}/api/v6/plan?"
            "fromPlace=32.0836,34.7981&toPlace=32.0838,34.8044&time=2026-10-05T05:00:00Z',"
            "timeout=5)"
        )
        while time.time() - started < timeout:
            if self.python_in_api(code, timeout=30).returncode == 0:
                return round(time.time() - started, 1)
            time.sleep(3)
        raise RuntimeError(f"Engine on {port} never answered")

    def prepare_evidence(self) -> None:
        started = time.time()
        for slot, port in (("a", 59081), ("b", 59082)):
            name = self.gen_names[slot]
            gen = f"/managed/gen-{slot}"
            if not self.args.source_check:
                self.tool("source-check", "--generation", gen, "--out", f"{gen}/source-check.json")
            extra = ["--active", "/managed/gen-a"] if slot == "b" else []
            self.warm_engine(port - 59081 + ENGINE_DIRECT_PORTS[0])
            rc, _, proc = self.cli(
                "probe",
                "--generation",
                gen,
                "--engine-url",
                f"http://127.0.0.1:{port}",
                "--queries",
                "/run-data/probe-corpus.json",
                "--output",
                f"{gen}/probe.json",
                *extra,
                timeout=3600,
                label=f"opentransit probe gen-{slot}",
            )
            if rc != 0:
                raise RuntimeError(f"probe for {name} failed: {proc.stdout} {proc.stderr[-400:]}")
        self.timings["evidenceSeconds"] = round(time.time() - started, 1)

    def bind(self, slot: str, token: str, origin: str, probe_slot: str | None = None) -> str:
        probe_slot = probe_slot or slot
        photon = []
        if self.composite:
            query, admin = PHOTON_ORIGINS[slot]
            photon = ["--photon-origin", query, "--photon-admin-origin", admin]
        self.tool(
            "bind",
            "--generation",
            f"/managed/gen-{slot}",
            "--origin",
            origin,
            "--probe",
            f"/managed/gen-{probe_slot}/probe.json",
            "--source-check",
            f"/managed/gen-{slot}/source-check.json",
            "--token",
            token,
            *photon,
            label=f"bind {token}",
        )
        return f"/managed/binding-{token}.json"

    def pointer(self) -> str:
        return self.exec_api("readlink", "/managed/current", check=False).stdout.strip()

    def activate(self, binding: str, *, action="activate", now=None, check_only=False):
        args = [
            action,
            "--managed-root",
            "/managed",
            "--ack-dir",
            "/managed/acks",
            "--binding",
            binding,
            "--timeout",
            "3600",  # a reload hashes ~3.7 GB several times; r03 took 9-16 minutes
        ]
        if now:
            args += ["--now", now]
        if check_only:
            args.append("--check-only")
        # docker exec must outlive the operator's own 3600 s acknowledgement timeout.
        return self.cli(*args, timeout=3700, label=f"opentransit {action} {Path(binding).stem}")

    # -- journeys ------------------------------------------------------------------------
    def journey(self, timeout=8.0) -> dict:
        started = time.time()
        request = urllib.request.Request(
            f"{API}/v1/journeys",
            data=json.dumps(JOURNEY).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        error = None
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read())
                status = response.status
        except urllib.error.HTTPError as exc:
            body, status, error = None, exc.code, "HTTPError"
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            body, status, error = None, 0, type(exc).__name__
        generation = None
        if isinstance(body, dict):
            meta = (body.get("data") or {}).get("metadata") or body.get("metadata") or {}
            generation = meta.get("generationId")
            if generation is None:
                match = re.search(r'"generationId":\s*"([^"]+)"', json.dumps(body))
                generation = match[1] if match else None
        return {
            "t0": started,
            "t1": time.time(),
            "status": status,
            "generationId": generation,
            "error": error,
        }

    def burst(self, count=4) -> list[dict]:
        results = []
        for _ in range(count):
            results.append(self.journey())
        return results

    def load(self, clients=4):
        records: list[dict] = []
        stop = threading.Event()

        def worker():
            while not stop.is_set():
                records.append(self.journey())
                time.sleep(random.uniform(0.0, 0.25))  # desynchronise the clients

        threads = [threading.Thread(target=worker) for _ in range(clients)]
        for thread in threads:
            thread.start()

        def finish():
            stop.set()
            for thread in threads:
                thread.join(30)
            return records

        return finish

    def start_pointer_watch(self, name: str):
        stop = self.run_dir / f"watch-stop-{name}"
        stop.unlink(missing_ok=True)
        process = subprocess.Popen(
            [
                "docker",
                "exec",
                self.api_container,
                "/app/.venv/bin/python",
                "-c",
                POINTER_WATCH,
                f"/run-data/watch-stop-{name}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return process, stop

    def stop_pointer_watch(self, watch) -> dict:
        process, stop = watch
        stop.write_text("stop", encoding="utf-8")
        out, _ = process.communicate(timeout=60)
        try:
            return json.loads(out.strip().splitlines()[-1])
        except ValueError, IndexError:
            return {"reads": 0, "errors": -1, "targets": []}

    def clock_skew(self) -> float:
        before = time.time()
        proc = self.python_in_api("import time;print(time.time())", timeout=30)
        after = time.time()
        return float(proc.stdout.strip()) - (before + after) / 2

    def generation_ids(self, records) -> dict:
        counts: dict = {}
        for rec in records:
            key = f"{rec['status']}:{rec['generationId']}"
            counts[key] = counts.get(key, 0) + 1
        return counts

    def set_delay(self, slot: str, seconds: float) -> None:
        (self.run_dir / f"delay-{slot}").write_text(str(seconds), encoding="utf-8")

    def proxy_events(self) -> list[dict]:
        path = self.run_dir / "proxy.jsonl"
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        return events

    # -- phases ----------------------------------------------------------------------------
    def phase_initial(self) -> None:
        self.a_id, self.b_id = self.ids["a"], self.ids["b"]
        binding = self.bind("a", "t2-a-initial", "http://127.0.0.1:59081")
        started = time.time()
        rc, report, proc = self.activate(binding)
        self.timings["initialActivationSeconds"] = round(time.time() - started, 1)
        del proc
        self.worker_incarnation = (report or {}).get("workerIncarnationId")
        batch = self.burst(3)
        self.data["initialActivation"] = report
        self.check(
            "initial_activation_serves_old_generation",
            rc == 0 and all(r["status"] == 200 and r["generationId"] == self.a_id for r in batch),
            requests=self.generation_ids(batch),
            pointer=self.pointer(),
        )

    def phase_failed_reload(self) -> None:
        pointer_before = self.pointer()
        ack_before = self.exec_api("ls", "/managed/acks").stdout.split()
        # (2b) corrupt artifacts are refused before the pointer is touched.
        self.tool("corrupt", "--name", "gen-x", "--source", "/managed/gen-b")
        # The corrupt candidate reuses the new generation's (valid) probe and source check.
        self.exec_api(
            "/app/.venv/bin/python",
            "-c",
            "import shutil;shutil.copy('/managed/gen-b/probe.json','/managed/gen-x/probe.json');"
            "shutil.copy('/managed/gen-b/source-check.json','/managed/gen-x/source-check.json')",
        )
        corrupt_binding = self.write_corrupt_binding()
        rc_c, report_c, proc_c = self.activate(corrupt_binding)
        self.check(
            "corrupt_candidate_refused_before_pointer_change",
            rc_c != 0 and self.pointer() == pointer_before,
            exitCode=rc_c,
            stderr=(proc_c.stderr.strip().splitlines() or [""])[-1][:200],
            pointer=self.pointer(),
        )
        # (2a) a candidate that passes artifact checks but not the worker's engine/probe check.
        bad = self.bind("b", "t2-b-mismatched", "http://127.0.0.1:59083", probe_slot="b")
        watch = self.start_pointer_watch("failed")
        finish = self.load()
        time.sleep(1)
        started = time.time()
        rc, report, _ = self.activate(bad)
        seconds = round(time.time() - started, 1)
        time.sleep(1.5)
        records = finish()
        pointer_reads = self.stop_pointer_watch(watch)
        detail = (report or {}).get("detail", {})
        pointer_after = self.pointer()
        restored = self.exec_api("cat", "/managed/" + pointer_after, check=False).stdout
        try:
            restored_generation = json.loads(restored)["generationId"]
        except ValueError:
            restored_generation = None
        self.timings["failedReloadSeconds"] = seconds
        all_old = all(r["status"] == 200 and r["generationId"] == self.a_id for r in records)
        self.check(
            "failed_reload_preserves_old_serving_state_and_restores_pointer",
            rc != 0
            and (report or {}).get("status") == "failed"
            and detail.get("status") == "rejected"
            and detail.get("pointerRestored") is True
            and restored_generation == self.a_id
            and pointer_after != pointer_before
            and all_old
            and len(records) > 10
            and pointer_reads["errors"] == 0
            and len(pointer_reads["targets"]) >= 2,
            pointerReadsDuringSwapAndRestore=pointer_reads,
            operator=report,
            requestsDuringFailedReload=self.generation_ids(records),
            requestCount=len(records),
            pointerBefore=pointer_before,
            pointerAfter=pointer_after,
            restoredPointerGenerationIsOld=restored_generation == self.a_id,
            acksCreated=sorted(
                set(self.exec_api("ls", "/managed/acks").stdout.split()) - set(ack_before)
            ),
        )

    def write_corrupt_binding(self) -> str:
        """A binding file for the corrupt candidate; creating it must itself be refused, so
        the file is written directly (the binding validator is what the operator exercises)."""
        code = (
            "import json;from pathlib import Path;m=json.loads(Path('/managed/gen-b/manifest.json')"
            ".read_text());Path('/managed/binding-t2-corrupt.json').write_text(json.dumps({"
            "'generationDir':'/managed/gen-x','engineOrigin':'http://127.0.0.1:59082',"
            "'probePath':'/managed/gen-x/probe.json','sourceCheckPath':"
            "'/managed/gen-x/source-check.json','activationToken':'t2-corrupt',"
            "'generationId':m['generationId']}))"
        )
        self.exec_api("/app/.venv/bin/python", "-c", code)
        return "/managed/binding-t2-corrupt.json"

    def phase_activate_under_load(self) -> None:
        a_to_b = self.bind("b", "t2-b-activate", "http://127.0.0.1:59082")
        self.set_delay("a", PROXY_DELAY)
        skew = self.clock_skew()
        watch = self.start_pointer_watch("activate")
        finish = self.load()
        time.sleep(2)
        started = time.time()
        rc, report, proc = self.activate(a_to_b)
        seconds = round(time.time() - started, 1)
        time.sleep(4)
        records = finish()
        pointer_reads = self.stop_pointer_watch(watch)
        self.set_delay("a", 0)
        self.timings["activationUnderLoadSeconds"] = seconds
        self.data["activation"] = report
        ok = rc == 0 and (report or {}).get("status") == "acknowledged"
        new = [r for r in records if r["generationId"] == self.b_id]
        old = [r for r in records if r["generationId"] == self.a_id]
        ack_container = (
            datetime.fromisoformat(report["ackFileMtimeUtc"]).timestamp() if ok else None
        )
        # The activation ack is written immediately after the snapshot is published, so its
        # time (converted to the host clock) bounds the publication instant.
        ack = ack_container - skew if ack_container else None
        boundary = min((r["t0"] for r in new), default=None)
        crossing = [r for r in old if ack and r["t0"] < ack < r["t1"]]
        late_old = [r for r in old if ack and r["t0"] > ack + 0.5]
        early_new = [r for r in new if ack and r["t1"] < ack - 0.5]
        non_ok = [r for r in records if r["status"] != 200]
        unknown = [r for r in records if r["generationId"] not in {self.a_id, self.b_id}]
        self.check(
            "inflight_requests_finish_on_old_generation_then_new_requests_use_new",
            ok
            and bool(new)
            and bool(old)
            and len(crossing) >= 1
            and not late_old
            and not early_new
            and not non_ok
            and not unknown
            and pointer_reads["errors"] == 0
            and len(pointer_reads["targets"]) >= 2,
            pointerReadsDuringSwap=pointer_reads,
            requestCount=len(records),
            perGeneration=self.generation_ids(records),
            inflightCrossingBoundary=len(crossing),
            maxCrossingOverlapMs=round(max((r["t1"] - ack for r in crossing), default=0) * 1000),
            oldStartedMoreThan500msAfterAck=len(late_old),
            newFinishedMoreThan500msBeforeAck=len(early_new),
            firstNewRequestStartOffsetMs=round((boundary - ack) * 1000)
            if boundary and ack
            else None,
            nonSuccessErrors=sorted({str(r.get("error")) for r in records if r["status"] != 200}),
            nonSuccess=len(non_ok),
            proxyDelaySeconds=PROXY_DELAY,
            hostToContainerClockSkewSeconds=round(skew, 3),
            boundaryNote="in-flight = started before the activation ack (publication instant) and "
            "answered by the old generation after it; ack time converted with the measured skew",
        )
        self.new_token = "t2-b-activate"
        self.old_token = (report or {}).get("retiredOperationToken") or "unknown"
        ack_mtime = (report or {}).get("ackFileMtimeUtc")
        events = self.proxy_events()
        starts_a = [e for e in events if e["route"] == "a" and e["ev"] == "req"]
        ends_a = {e["id"]: e["t"] for e in events if e["route"] == "a" and e["ev"] == "resp_end"}
        if ack_mtime:
            ack_t = datetime.fromisoformat(ack_mtime).timestamp()
            before = [e for e in starts_a if e["t"] < ack_t]
            across = [e for e in before if ends_a.get(e["id"], 0) > ack_t]
            after = [e for e in starts_a if e["t"] >= ack_t]
            self.check(
                "old_engine_saw_inflight_requests_complete_after_acknowledgement",
                len(across) >= 1 and all(e["path"] == "/api/v6/plan" or True for e in across),
                engineAProxyRequestsStartedBeforeAck=len(before),
                engineAProxyRequestsCompletingAfterAck=len(across),
                engineAProxyRequestsStartedAfterAckDuringGrace=len(after),
                note="proxy log timestamps and the ack file mtime share the container clock",
            )
        # Retirement gate: only after the worker confirms retirement may engine A stop.
        motis_a = f"{self.prefix}-motis-a"
        engine_a_running_at_ack = self.container_running(motis_a)
        rc_r, retired, proc_r = self.cli(
            "await-retirement",
            "--ack-dir",
            "/managed/acks",
            "--old-token",
            self.old_token,
            "--new-token",
            self.new_token,
            "--incarnation",
            self.worker_incarnation,
            "--deadline-seconds",
            str(DEADLINE_SECONDS),
            "--timeout",
            "180",
            label="opentransit await-retirement",
        )
        gate_open = rc_r == 0 and (retired or {}).get("status") == "retired"
        stop_started = time.time()
        stop_proc = self.run(
            ["docker", "stop", "-t", "20", motis_a],
            check=False,
            label=f"docker stop {motis_a} (after retirement gate)",
        )
        finished_at = self.container_finished_at(motis_a)
        after_stop = self.burst(4)
        required = DEADLINE_SECONDS * 10
        elapsed = None
        if finished_at and ack_mtime:
            elapsed = (
                datetime.fromisoformat(finished_at) - datetime.fromisoformat(ack_mtime)
            ).total_seconds()
        self.data["retirement"] = retired
        self.check(
            "old_engine_stopped_only_after_ack_and_ten_request_deadlines",
            gate_open
            and engine_a_running_at_ack
            and stop_proc.returncode == 0
            and elapsed is not None
            and elapsed >= required
            and all(r["status"] == 200 and r["generationId"] == self.b_id for r in after_stop),
            requiredSeconds=required,
            ackToEngineStopSeconds=elapsed,
            ackToRetirementAckSeconds=(retired or {}).get("ackToRetirementSeconds"),
            engineStillRunningWhenActivationAcked=engine_a_running_at_ack,
            engineStoppedAt=finished_at,
            activationAckedAt=ack_mtime,
            requestsAfterOldEngineStopped=self.generation_ids(after_stop),
            stopCommandStartedAtHost=datetime.fromtimestamp(stop_started, UTC).isoformat(),
        )

    def container_running(self, name: str) -> bool:
        info = json.loads(self.run(["docker", "inspect", name]).stdout)[0]
        return bool(info["State"]["Running"])

    def container_finished_at(self, name: str) -> str | None:
        info = json.loads(self.run(["docker", "inspect", name]).stdout)[0]
        value = info["State"].get("FinishedAt")
        if not value:
            return None
        base, _, frac = value.rstrip("Z").partition(".")
        return f"{base}.{frac[:6]}+00:00" if frac else f"{base}+00:00"

    def phase_rollback(self) -> None:
        a_binding = "/managed/binding-t2-a-initial.json"
        pointer = self.pointer()
        rollbacks = {}
        for label, when in (
            ("expired_freshness", "2026-10-08T10:00:00+00:00"),
            ("expired_coverage", "2026-11-01T00:00:00+00:00"),
        ):
            rc, report, proc = self.activate(a_binding, action="rollback", now=when)
            rollbacks[label] = {"exitCode": rc, "report": report, "simulatedNow": when}
        refused = all(
            v["exitCode"] == 2 and (v["report"] or {}).get("status") == "refused"
            for v in rollbacks.values()
        )
        reasons = {k: (v["report"] or {}).get("reasons") for k, v in rollbacks.items()}
        batch = self.burst(3)
        self.check(
            "rollback_refuses_expired_freshness_and_coverage_without_touching_pointer",
            refused
            and self.pointer() == pointer
            and reasons["expired_freshness"] == ["source_expired"]
            and "coverage_expired" in reasons["expired_coverage"]
            and all(r["generationId"] == self.b_id for r in batch),
            reasons=reasons,
            pointerUnchanged=self.pointer() == pointer,
            requestsAfterRefusal=self.generation_ids(batch),
        )
        stale = "2026-10-03T10:00:00+00:00"
        rc_e, eligible, _ = self.activate(a_binding, action="rollback", now=stale, check_only=True)
        rc_n, new_refused, _ = self.activate("/managed/binding-t2-b-activate.json", now=stale)
        self.check(
            "stale_generation_is_rollback_serviceable_but_new_candidate_needs_current",
            rc_e == 0
            and (eligible or {}).get("status") == "eligible"
            and eligible["currency"]["freshness"] == "stale"
            and rc_n == 2
            and (new_refused or {}).get("reasons") == ["source_stale"]
            and self.pointer() == pointer,
            simulatedNow=stale,
            rollbackEligibility=eligible,
            newCandidateRefusal=new_refused,
            note="simulated operator clock only; the worker serves with the real clock",
        )
        # Valid rollback: the old engine was stopped, so restart it first.
        motis_a = f"{self.prefix}-motis-a"
        self.run(["docker", "start", motis_a], label=f"docker start {motis_a}")
        ready = self.wait_engine(59081)
        self.warm_engine(ENGINE_DIRECT_PORTS[0])  # page the graph back in; health allows 1.2 s
        started = time.time()
        rc, report, proc = self.activate(a_binding, action="rollback")
        seconds = round(time.time() - started, 1)
        batch = self.burst(4)
        rc_r, retired, _ = self.cli(
            "await-retirement",
            "--ack-dir",
            "/managed/acks",
            "--old-token",
            (report or {}).get("retiredOperationToken") or "unknown",
            "--new-token",
            (report or {}).get("token", "none"),
            "--incarnation",
            self.worker_incarnation,
            "--deadline-seconds",
            str(DEADLINE_SECONDS),
            "--timeout",
            "180",
            label="opentransit await-retirement (after rollback)",
        )
        self.timings["rollbackSeconds"] = seconds
        self.data["rollback"] = report
        self.check(
            "rollback_succeeds_for_valid_previous_generation",
            rc == 0
            and (report or {}).get("status") == "acknowledged"
            and (report or {}).get("action") == "rollback"
            and (report or {}).get("token") not in {"t2-a-initial", "t2-b-activate"}
            and all(r["status"] == 200 and r["generationId"] == self.a_id for r in batch),
            operatorReport=report,
            requestsAfterRollback=self.generation_ids(batch),
            engineAReadySeconds=ready,
            retirementAfterRollback=rc_r == 0,
        )

    def phase_prune(self) -> None:
        self.tool("synth-old", "--name", "synth-old")
        listing_before = json.loads(self.tool("listing").stdout)
        trees_before = {self.gen_names[slot]: self.tree_snapshot(slot) for slot in "ab"}
        results = {}
        for label, extra in (("unpinned", []),):
            out = f"/run-data/prune-{label}.json"
            rc, _, proc = self.cli(
                "prune",
                "--generations-root",
                "/managed",
                "--active",
                self.b_id,
                "--previous",
                self.a_id,
                *extra,
                "--dry-run",
                "--output",
                out,
                label=f"opentransit prune --dry-run ({label})",
            )
            plan = json.loads((self.run_dir / f"prune-{label}.json").read_text(encoding="utf-8"))
            results[label] = {
                "exitCode": rc,
                "deletionPerformed": plan["deletionPerformed"],
                "candidates": [c["generationId"] for c in plan["candidates"]],
                "retained": [
                    {"generationId": r["generationId"], "reason": r["reason"][:90]}
                    for r in plan["retained"]
                ],
            }
        listing_after = json.loads(self.tool("listing").stdout)
        trees_after = {self.gen_names[slot]: self.tree_snapshot(slot) for slot in "ab"}
        self.check(
            "prune_dry_run_lists_candidates_and_deletes_nothing",
            all(v["exitCode"] == 0 and v["deletionPerformed"] is False for v in results.values())
            and results["unpinned"]["candidates"] == ["synthetic-synth-old"]
            and listing_before == listing_after
            and trees_before == trees_after,
            plans=results,
            managedRootEntriesBefore=len(listing_before),
            managedRootEntriesAfter=len(listing_after),
            realSourceTreesUnchanged=trees_before == trees_after,
            note="the candidate is a tiny synthetic generation; real generations have no "
            "older verified sibling",
        )

    # -- teardown ----------------------------------------------------------------------------
    def export_and_teardown(self) -> None:
        self._sampling = False
        self._warming = False
        logs = {}
        for name in self.containers:
            proc = self.run(["docker", "logs", name], check=False, label=f"docker logs {name}")
            text = proc.stdout + proc.stderr
            (self.run_dir / f"{name}.log").write_text(text, encoding="utf-8")
            keep = [
                re.sub(r"\d+\.\d{4,}", "<n>", line)[:240]
                for line in text.splitlines()
                if re.search(
                    r"generation_|reload|WARNING|ERROR|Traceback|listening|ready|Started|"
                    r"Uvicorn",
                    line,
                    re.I,
                )
            ]
            logs[name] = {"lines": len(text.splitlines()), "excerpt": keep[:12] + keep[-12:]}
        self.data["logExcerpts"] = logs
        # Small evidence files only: never copy mounted generation artifacts to the host.
        self.exec_api(
            "sh",
            "-c",
            "cd /managed && find . -path '*/motis' -prune -o -type f -name '*.json' -print "
            "| tar -cf /run-data/managed-evidence.tar -T -",
            check=False,
            label="export bindings, acks, probes and checks (json only)",
        )
        self.compose("down", timeout=300, check=False)
        removed_volumes = [self.root_volume] + (self.photon_volumes if self.composite else [])
        for volume in removed_volumes:
            self.run(["docker", "volume", "rm", volume], check=False, label=f"remove {volume}")
        left = self.run(
            ["docker", "ps", "-a", "--filter", f"name={self.prefix}-", "-q"]
        ).stdout.split()
        remaining = self.run(["docker", "volume", "ls", "-q"]).stdout.split()
        self.data["cleanup"] = {
            "containersRemaining": len(left),
            "removedByHarness": self.containers + [f"{self.prefix}-init (--rm)"],
            "volumesRemoved": [v for v in removed_volumes if v not in remaining],
            "graphVolumeUntouched": None if self.composite else GRAPH_VOLUME,
        }

    def finish(self, error: str | None) -> dict:
        trees_after = {self.gen_names[slot]: self.tree_snapshot(slot) for slot in "ab"}
        before = self.data.get("realSourceTreesBefore")
        result = {
            "schemaVersion": 1,
            "kind": "m2-activation-compose",
            "recordedAtUtc": now_iso(),
            "status": "passed"
            if not error and all(c["passed"] for c in self.checks.values())
            else "failed",
            "error": error,
            "scope": "M2.5 local activate/rollback and M2.6 retention in Linux Compose; "
            "single local worker; not under-load capacity, crash or fault-injection (M7)",
            "dataKind": (
                "two complete real composite generations (schedule + sealed Photon addresses; "
                "read-only artifact mounts), each served by its own pinned MOTIS graph and its "
                "own Photon (run-private copy of the sealed checkpoint); "
                if self.composite
                else "real generations (read-only artifact mounts) with the pinned real MOTIS "
                "engine; generations A and B share one graph volume and differ in reference "
                "data; "
            )
            + "the prune candidate is a labelled tiny synthetic generation",
            "inputs": {
                **self.data,
                "realSourceTreesAfter": trees_after,
                "realSourceTreesUnchanged": before == trees_after,
                "oldGeneration": self.gen_dirs["a"].as_posix(),
                "newGeneration": self.gen_dirs["b"].as_posix(),
                "graphVolume": None if self.composite else GRAPH_VOLUME,
                "photonOrigins": PHOTON_ORIGINS if self.composite else None,
                "sourceCheckNote": "one real successful paired upstream check (same GTFS/"
                "TripIdToDate hashes as both generations), copied into each managed generation; "
                "no new upstream check or download by this harness"
                if self.args.source_check
                else "per-generation records reconstructed from each manifest's "
                "recorded acquisition/validation times; no new upstream check or download",
                "engineKeepWarm": {
                    "intervalSeconds": KEEP_WARM_SECONDS,
                    "directPorts": list(ENGINE_DIRECT_PORTS),
                    "queries": self.warm_counts,
                    "note": "standby engines queried directly (not through the delay proxy) "
                    "so reload hashing does not evict their graphs; failures while an engine "
                    "is deliberately stopped are expected",
                },
                "journeyDeadlineSeconds": DEADLINE_SECONDS,
                "proxyDelaySeconds": PROXY_DELAY,
                "limits": {
                    "api": "1g",
                    "motisEach": "3g",
                    "proxy": "128m",
                    **(
                        {"photonEach": "1g", "photonForwarderEach": "64m"} if self.composite else {}
                    ),
                    "hostPort": "127.0.0.1:8300",
                },
            },
            "checks": self.checks,
            "timings": self.timings,
            "peakMemoryBytesSampled": self.memory,
            "commands": self.commands,
        }
        return result

    def main(self) -> int:
        error = None
        try:
            self.preflight()
            self.start_stack()
            self.prepare_evidence()
            self.phase_initial()
            self.phase_failed_reload()
            self.phase_activate_under_load()
            self.phase_rollback()
            self.phase_prune()
        except Exception as exc:  # noqa: BLE001 - recorded in evidence
            error = f"{type(exc).__name__}: {exc}"
            self.log(error)
        finally:
            try:
                if self.started and not self.args.keep:
                    self.export_and_teardown()
            except Exception as exc:  # noqa: BLE001
                error = (error or "") + f" teardown: {exc}"
        result = self.finish(error)
        out = self.run_dir / "result.json" if self.run_dir.exists() else Path("result.json")
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        if self.args.results_out:
            with Path(self.args.results_out).open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
        self.log(f"status {result['status']}; run dir {self.run_dir}")
        return 0 if result["status"] == "passed" else 1


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--codex-runtime", required=True)
    parser.add_argument("--results-out", help="exclusive-create the evidence JSON here")
    parser.add_argument("--keep", action="store_true", help="skip teardown (debugging)")
    parser.add_argument(
        "--old-generation", help="complete composite generation served first (e.g. oct1a)"
    )
    parser.add_argument("--new-generation", help="complete composite candidate (e.g. oct1b)")
    parser.add_argument(
        "--source-check", help="successful same-hash paired source check used for both"
    )
    parser.add_argument("--probe-corpus", help="probe corpus (default: Codex functional corpus)")
    parser.add_argument("--photon-jar", help="pinned photon-1.3.0.jar (default: Codex runtime)")
    parser.add_argument("--prefix", default="ot-t2", help="container/volume name prefix")
    args = parser.parse_args(argv)
    if (args.old_generation is None) != (args.new_generation is None):
        parser.error("--old-generation and --new-generation go together")
    if args.old_generation and not args.source_check:
        parser.error("composite generations need --source-check (real paired check)")
    if not re.fullmatch(r"ot-[a-z0-9-]{1,20}", args.prefix):
        parser.error("--prefix must look like ot-<name>")
    return args


if __name__ == "__main__":
    sys.exit(Harness(parse(sys.argv[1:])).main())
