#!/usr/bin/env python3
"""One-command LIVE acceptance run for one complete generation (stack, probe, checks, search).

    uv run --project services/api --locked python services/api/tools/acceptance_run.py \\
        --generation D:/ot/generations/<id> --run-id <id> \\
        --results-prefix services/api/results/acceptance-<id>-<date>-01

It starts ONE slot-free MOTIS, the generation's sealed Photon checkpoint (if present) and the API
(all in one network namespace, as in deploy/aws/local/compose.yaml), then runs in order:

  1 stack       MOTIS (2g) + Photon (1g, checkpoint copied into a fresh Docker volume)
  2 probe       `opentransit probe` in a verifier container against the generation's probe corpus
  3 api_start   API (1g) bound to the passed probe (required for /readyz)
  4 readyz      /readyz x50 (all 200 expected; errors[] reasons kept) + MOTIS "VERIFY FAIL" count
  5 walk_caps   tools/check_walk_caps.py against the API
  6 demo        `opentransit demo` Dizengoff Center -> Technion
  7 h3_review   tools/h3_review.py --allow-past -> sheet + raw (holiday cases outside coverage are
                reported as not generated, never hidden)
  8 search      tools/evaluate_search.py over the frozen corpora, log-correlated timings, H4 sheet

Outputs are `<prefix>-<name>` files (a prefix ending in `/` puts them in that directory); the run
refuses to start if any already exists and never overwrites. `<prefix>-summary.json` holds every
check's PASS/FAIL/ERROR/SKIPPED with values, generation IDs, image digests, source commit and
timings. Product failures are reported, not hidden: exit 0 = every check PASS, 1 = at least one
check FAIL, 2 = a runner or infrastructure error (stack did not start, tool crashed).

Nothing here approves anything: structural routing checks are not H3 and search scores are not H4.
Everything created is named `ot-acc-<run-id>-*`, uses host ports 8500-8599 and hard memory caps, and
is removed at the end after its logs are exported (--keep-stack keeps it). Generations are mounted
read-only from where they are; they are never copied into Docker volumes (Photon's 80 MB checkpoint
is the one exception: its index must be writable, so it is copied into a run-private volume).
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[2]
API_SRC = REPO / "services/api/src"
JERUSALEM = ZoneInfo("Asia/Jerusalem")

SCHEMA_VERSION = 1
INFRA_STEPS = ("stack", "probe", "api_start")
STEPS = ("stack", "probe", "api_start", "readyz", "walk_caps", "demo", "h3_review", "search")
API_IMAGE_DEFAULT = "opentransit-api:latest"
MOTIS_IMAGE_BASE = "ghcr.io/motis-project/motis"
JAVA_IMAGE_BASE = "eclipse-temurin:21.0.12.1_1-jre"
PHOTON_JAR_CONTAINER_PATH = "/opt/photon/photon-1.3.0.jar"
PHOTON_USER = "10001:10001"
API_USER = "10001"

# Hard caps (docker run --memory == --memory-swap) and the allowed host port range.
MEMORY_CAPS = {"motis": "2g", "photon": "1g", "api": "1g", "verifier": "512m", "photon-init": "64m"}
PORT_RANGE = (8500, 8599)
MOTIS_HEALTH_QUERY = "/api/v6/plan?fromPlace=32.0836,34.7981&toPlace=32.0838,34.8044"
READYZ_REQUESTS = 50
SEARCH_P95_TARGET_MS = 40.0
ADDRESS_TOP1_TARGET = 0.80
# journeys.json ids used by the preserved structural probe corpus (ten required; see probe.py).
PHOTON_JAR_CANDIDATES = (
    "C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/.runtime/m4-photon-spike-20260930/"
    "photon-1.3.0.jar",
)
# Unscored requests sent before the corpus so cold-start cost is recorded as its own finding
# instead of silently landing on the first scored cases. (query, types) over all categories.
WARMUP_QUERIES = (
    ("Jerusalem Central Bus Station", ("stop", "station")),
    ("Ben Yehuda Street", ("address",)),
    ("Ichilov Hospital", ("poi",)),
    ("Beersheba", ("stop", "station", "poi", "address")),
    ("Allenby 10 Tel Aviv", ("stop", "station", "poi", "address")),
    ("Haifa Hof HaCarmel", ("stop", "station")),
    ("Rothschild Boulevard", ("address",)),
    ("Azrieli Center", ("stop", "station", "poi", "address")),
)
COLD_START_LIMIT_MS = 3000.0  # the evaluator's per-request client timeout
BAD_FIRST_PASS_OUTCOMES = ("http_error", "unavailable", "invalid_response", "generation_mismatch")
LOG_ROLES = ("motis", "photon", "api", "verifier", "photon-init")


class RunnerError(RuntimeError):
    """Infrastructure or runner failure (exit 2), as opposed to a failing product check."""


def now_utc() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None = None) -> str:
    return (value or now_utc()).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ----------------------------------------------------------------------------- pure helpers


def sanitize_run_id(value: str) -> str:
    """Docker-safe lowercase run ID (used in every container/volume name)."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,30}", value):
        raise ValueError("--run-id must be 1-31 chars of lowercase letters, digits and '-'")
    return value


def join_prefix(prefix: str, name: str) -> Path:
    """`<prefix>-<name>`; a prefix ending in a path separator or dash adds no extra dash."""
    if prefix.endswith(("/", "\\", "-")):
        return Path(prefix + name)
    return Path(f"{prefix}-{name}")


def container_name(run_id: str, role: str) -> str:
    return f"ot-acc-{run_id}-{role}"


def output_paths(prefix: str) -> dict[str, Path]:
    """Every file the run may create; all must be absent before starting."""
    names = {
        "summary": "summary.json",
        "runtime": "runtime.json",
        "source_hashes": "source-hashes.json",
        "probe_queries": "probe-queries.json",
        "probe": "probe.json",
        "readyz": "readyz.json",
        "walk_caps": "walk-caps.json",
        "demo": "demo.txt",
        "h3_sheet": "h3-review.md",
        "h3_raw": "h3-review-raw.json",
        "search_raw": "search-raw.json",
        "search": "search.json",
        "h4_sheet": "h4-review.md",
        "search_api_log": "search-api-container.log",
        "work": "work",
    }
    paths = {key: join_prefix(prefix, value) for key, value in names.items()}
    for role in LOG_ROLES:
        paths[f"log_{role}"] = join_prefix(prefix, f"{role}.log")
    return paths


def existing_outputs(paths: dict[str, Path]) -> list[Path]:
    return sorted(path for path in paths.values() if path.exists())


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("Instant needs an explicit offset")
    return parsed


def redate_probe_corpus(
    corpus: dict, coverage_from: datetime, coverage_until: datetime
) -> tuple[dict, list[dict]]:
    """Give out-of-coverage probe departures a `probeTime` in coverage (same weekday and clock).

    The probe supports `probeTime`: the engine is asked at that instant while the corpus records
    the original (`sourceDepartureTime`). Shifts are whole weeks in Israel local time so a
    weekday/weekend and clock rule is preserved. Cases already inside coverage are untouched.
    Returns (new corpus, changes); the input is never mutated.
    """
    cases = corpus.get("cases") if isinstance(corpus, dict) else corpus
    if not isinstance(cases, list) or not cases:
        raise ValueError("Probe corpus has no cases")
    result, changes = [], []
    for case in cases:
        case = json.loads(json.dumps(case))
        original = parse_instant(case["params"]["time"])
        existing = case.get("probeTime")
        when = parse_instant(existing) if existing else original
        if coverage_from <= when < coverage_until:
            result.append(case)
            continue
        local = when.astimezone(JERUSALEM)
        for weeks in range(1, 60):
            shifted = datetime.combine(
                local.date() + timedelta(weeks=weeks), local.timetz().replace(tzinfo=None)
            ).replace(tzinfo=JERUSALEM)
            if shifted >= coverage_from:
                break
        if not coverage_from <= shifted < coverage_until:
            raise ValueError(f"Case {case['id']} cannot be placed inside coverage")
        case["probeTime"] = shifted.isoformat()
        changes.append(
            {
                "id": case["id"],
                "from": when.isoformat(),
                "probeTime": case["probeTime"],
                "rule": "whole weeks, Israel local clock",
            }
        )
        result.append(case)
    out = dict(corpus) if isinstance(corpus, dict) else {}
    out["cases"] = result
    if changes:
        out["acceptanceRedating"] = {
            "reason": "source departures outside this generation's coverage use probeTime",
            "coverage": [coverage_from.isoformat(), coverage_until.isoformat()],
            "changedCaseIds": [item["id"] for item in changes],
        }
    return out, changes


def pick_service_day(
    coverage_from: datetime, coverage_until: datetime, requested: date | None = None
) -> str:
    """08:00 Israel time on a Sunday-Thursday inside coverage (first one after its first day)."""
    if requested is not None:
        candidates = [requested]
    else:
        start = coverage_from.astimezone(JERUSALEM).date() + timedelta(days=1)
        candidates = [start + timedelta(days=offset) for offset in range(14)]
    for day in candidates:
        if requested is None and day.weekday() in (4, 5):  # Friday, Saturday
            continue
        when = datetime.combine(day, dtime(8, 0)).replace(tzinfo=JERUSALEM)
        if coverage_from <= when < coverage_until - timedelta(days=1):
            return when.isoformat()
    raise ValueError("No suitable service day inside coverage")


def count_verify_fail(text: str) -> int:
    return len(re.findall(r"VERIFY FAIL", text))


def summarize_readyz(samples: list[dict]) -> dict:
    """samples: [{"status": int, "ms": float, "errors": list|None, "generationId": str|None}]."""
    ok = [item for item in samples if item["status"] == 200]
    failures = [item for item in samples if item["status"] != 200]
    reasons: dict[str, int] = {}
    for item in failures:
        for error in item.get("errors") or [{"condition": "transport", "reason": "NO_RESPONSE"}]:
            if isinstance(error, dict):
                key = f"{error.get('condition')}:{error.get('reason')}"
                reasons[key] = reasons.get(key, 0) + 1
    return {
        "requests": len(samples),
        "ok": len(ok),
        "failed": len(failures),
        "statuses": sorted({item["status"] for item in samples}),
        "failureReasons": dict(sorted(reasons.items())),
        "generationIds": sorted({item["generationId"] for item in ok if item.get("generationId")}),
        "maxMs": max((item["ms"] for item in samples), default=None),
    }


def parse_demo_output(text: str) -> dict:
    """Extract generation, outcome, journeys, legs and arrival from `opentransit demo` output."""
    generation = re.search(r"Generation:\s+(\S+)", text)
    outcome = re.search(r"Outcome:\s+(\S+) \((\d+) journey", text)
    journeys = []
    for match in re.finditer(
        r"Journey (\d+): depart (\d\d:\d\d) arrive (\d\d:\d\d) \(([^,]+), (\d+) transfer", text
    ):
        journeys.append(
            {
                "number": int(match.group(1)),
                "depart": match.group(2),
                "arrive": match.group(3),
                "duration": match.group(4),
                "transfers": int(match.group(5)),
            }
        )
    # Leg lines: four spaces, "HH:MM-HH:MM", mode, ... [timingState]
    blocks = re.split(r"\n(?=  Journey \d+:)", text)
    for journey, block in zip(journeys, blocks[1:], strict=False):
        journey["legs"] = len(re.findall(r"^    \d\d:\d\d-\d\d:\d\d ", block, re.MULTILINE))
    return {
        "generationId": generation.group(1) if generation else None,
        "outcome": outcome.group(1) if outcome else None,
        "journeyCount": int(outcome.group(2)) if outcome else 0,
        "journeys": journeys,
        "scheduledLabelled": "[scheduled" in text,
    }


def percentile(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile, identical to evaluate_search._percentile."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1))
    return ordered[index]


def _latency(values: list[float]) -> dict:
    return {
        "count": len(values),
        "p50Ms": percentile(values, 50),
        "p95Ms": percentile(values, 95),
        "maxMs": max(values) if values else None,
    }


def latency_by_category(records: list[dict]) -> dict:
    """API-process p50/p95 overall and per category, first pass and all requests."""
    first: dict[str, list[float]] = {}
    every: dict[str, list[float]] = {}
    for record in records:
        category = record["case"]["category"]
        requests = [record["firstPass"], *record.get("warmRepeats", [])]
        for index, request in enumerate(requests):
            value = request.get("processDurationMs")
            if value is None:
                continue
            every.setdefault(category, []).append(float(value))
            if index == 0:
                first.setdefault(category, []).append(float(value))

    def merged(source: dict[str, list[float]]) -> dict:
        everything = [value for items in source.values() for value in items]
        return {
            "overall": _latency(everything),
            "byCategory": {name: _latency(items) for name, items in sorted(source.items())},
        }

    return {"firstPass": merged(first), "allRequests": merged(every)}


def search_summary(result: dict) -> dict:
    """Mechanical scores and API-process latency from a finalized evaluation (not H4)."""
    summary = result["summary"]
    overall = summary["overall"]
    by_category = {
        name: {
            "top1": row["top1"],
            "top5": row["top5"],
            "total": row["total"],
            "unavailable": row["unavailable"],
        }
        for name, row in summary["byCategory"].items()
    }
    latency = latency_by_category(result["records"])
    timing = result.get("timing", {})
    correlation = timing.get("correlation", {})
    address = by_category.get("address")
    first_p95 = latency["firstPass"]["overall"]["p95Ms"]
    all_p95 = latency["allRequests"]["overall"]["p95Ms"]
    return {
        "overall": {
            "top1": overall["top1"],
            "top5": overall["top5"],
            "total": overall["denominator"],
        },
        "byCategory": by_category,
        "byLanguage": summary.get("byLanguage"),
        "byCorpus": summary.get("byCorpus"),
        "firstPassOutcomes": summary.get("firstPassOutcomes"),
        "latencyApiProcess": latency,
        "logCorrelation": {
            "verified": correlation.get("verified"),
            "requestCount": correlation.get("requestCount"),
            "matchedCount": correlation.get("matchedCount"),
            "unmatchedCount": correlation.get("unmatchedCount"),
        },
        "targets": {
            "basis": "mechanical thresholds from PROJECT_STATUS; not an H4 approval",
            "addressTop1Rate": (address["top1"] / address["total"]) if address else None,
            "addressTop1Meets80Percent": (
                address["top1"] / address["total"] >= ADDRESS_TOP1_TARGET if address else None
            ),
            "firstPassP95Meets40Ms": None
            if first_p95 is None
            else first_p95 <= SEARCH_P95_TARGET_MS,
            "allRequestsP95Meets40Ms": None if all_p95 is None else all_p95 <= SEARCH_P95_TARGET_MS,
        },
        "humanH4Approval": False,
    }


def warmup_assessment(samples: list[dict]) -> dict:
    """Cold-start finding from the unscored warm-up requests: [{"status", "ms"}]."""
    slow = [item for item in samples if item["ms"] > COLD_START_LIMIT_MS]
    failed = [item for item in samples if item["status"] != 200]
    return {
        "requests": len(samples),
        "firstMs": samples[0]["ms"] if samples else None,
        "maxMs": max((item["ms"] for item in samples), default=None),
        "slowerThanClientTimeout": len(slow),
        "nonOk": [{"status": item["status"], "ms": item["ms"]} for item in failed],
        "clean": bool(samples) and not slow and not failed,
    }


def first_pass_failures(summary: dict) -> int:
    outcomes = summary.get("firstPassOutcomes") or {}
    return sum(count for name, count in outcomes.items() if name in BAD_FIRST_PASS_OUTCOMES)


def source_hashes(src_root: Path) -> dict[str, str]:
    """`src/opentransit/...` -> SHA-256 for every tracked-source file under services/api/src."""
    hashes = {}
    root = Path(src_root)
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            hashes["src/" + path.relative_to(root).as_posix()] = sha256_file(path)
    return hashes


def overall_status(checks: dict[str, dict]) -> str:
    statuses = {item["status"] for item in checks.values()}
    if "ERROR" in statuses:
        return "ERROR"
    if "FAIL" in statuses:
        return "FAIL"
    if statuses <= {"PASS"}:
        return "PASS"
    return "INCOMPLETE"  # skipped steps without failures: not an acceptance pass


def exit_code(status: str) -> int:
    return {"PASS": 0, "FAIL": 1}.get(status, 2)


# ------------------------------------------------------------------- docker argv builders


def mount(source: Path | str, target: str, *, readonly: bool = True) -> list[str]:
    text = Path(source).resolve().as_posix()
    if "," in text:
        raise ValueError("Docker bind paths containing commas are unsupported")
    return ["--mount", f"type=bind,src={text},dst={target}" + (",readonly" if readonly else "")]


def _caps(role: str, cpus: str | None) -> list[str]:
    cap = MEMORY_CAPS[role]
    args = ["--memory", cap, "--memory-swap", cap, "--init", "--security-opt", "no-new-privileges"]
    if cpus:
        args += ["--cpus", cpus]
    return args


def check_port(port: int) -> int:
    if not PORT_RANGE[0] <= port <= PORT_RANGE[1]:
        raise ValueError(f"--port must be within {PORT_RANGE[0]}-{PORT_RANGE[1]}")
    return port


def motis_argv(run_id: str, image: str, generation: Path, port: int, cpus: str | None) -> list[str]:
    return [
        "docker", "run", "--detach", "--name", container_name(run_id, "motis"),
        *_caps("motis", cpus), "--tmpfs", "/tmp",
        "--publish", f"127.0.0.1:{check_port(port)}:8000",
        *mount(generation / "motis", "/data"),
        image, "/motis", "server", "-d", "/data",
    ]  # fmt: skip


def photon_init_argv(run_id: str, java_image: str, volume: str, checkpoint: Path) -> list[str]:
    return [
        "docker", "run", "--name", container_name(run_id, "photon-init"),
        *_caps("photon-init", None), "--network", "none", "--user", "0:0",
        "--mount", f"type=volume,src={volume},dst=/photon_data",
        *mount(checkpoint, "/src"),
        "--entrypoint", "/bin/sh", java_image, "-c",
        "cp -a /src/. /photon_data/ && chown -R 10001:10001 /photon_data"
        " && chmod 0750 /photon_data && ls /photon_data",
    ]  # fmt: skip


def photon_argv(
    run_id: str, java_image: str, volume: str, jar: Path, cpus: str | None
) -> list[str]:
    return [
        "docker", "run", "--detach", "--name", container_name(run_id, "photon"),
        *_caps("photon", cpus), "--user", PHOTON_USER, "--tmpfs", "/tmp",
        "--network", f"container:{container_name(run_id, 'motis')}",
        "--mount", f"type=volume,src={volume},dst=/photon_data",
        *mount(jar, PHOTON_JAR_CONTAINER_PATH),
        java_image, "java", "-Xms256m", "-Xmx512m", "-jar", PHOTON_JAR_CONTAINER_PATH,
        "-data-dir", "/photon_data", "serve", "-listen-ip", "127.0.0.1", "-listen-port", "2322",
    ]  # fmt: skip


def _python_env() -> list[str]:
    return ["--env", "PYTHONPATH=/src", "--env", "PYTHONDONTWRITEBYTECODE=1"]


def verifier_argv(
    run_id: str, api_image: str, generation: Path, src: Path, queries: Path, work: Path
) -> list[str]:
    return [
        "docker", "run", "--name", container_name(run_id, "verifier"),
        *_caps("verifier", None), "--read-only", "--tmpfs", "/tmp", "--user", API_USER,
        "--network", f"container:{container_name(run_id, 'motis')}",
        *_python_env(), "--env", "TMPDIR=/run/opentransit",
        *mount(generation, "/generation"), *mount(src, "/src"),
        *mount(queries, "/probe/queries.json"), *mount(work, "/run/opentransit", readonly=False),
        api_image, "/app/.venv/bin/python", "-m", "opentransit.build.cli", "probe",
        "--generation", "/generation", "--engine-url", "http://127.0.0.1:8080",
        "--queries", "/probe/queries.json", "--output", "/run/opentransit/probe.json",
    ]  # fmt: skip


def api_argv(
    run_id: str,
    api_image: str,
    generation: Path,
    src: Path,
    work: Path,
    *,
    photon: bool,
    cpus: str | None,
) -> list[str]:
    env = [
        "OPENTRANSIT_MANIFEST=/generation/manifest.json",
        "OPENTRANSIT_MOTIS_URL=http://127.0.0.1:8080",
        "OPENTRANSIT_PROBE=/run/opentransit/probe.json",
        # Operator measurement from one client: quotas must not falsify the corpus runs.
        "OPENTRANSIT_RATE_LIMIT_ENABLED=0",
    ]
    if photon:
        env += [
            "OPENTRANSIT_PHOTON_ADMIN_URL=http://127.0.0.1:9201",
            "OPENTRANSIT_PHOTON_URL=http://127.0.0.1:2322",
        ]
    args = [
        "docker", "run", "--detach", "--name", container_name(run_id, "api"),
        *_caps("api", cpus), "--read-only", "--tmpfs", "/tmp", "--user", API_USER,
        "--network", f"container:{container_name(run_id, 'motis')}",
        *_python_env(),
    ]  # fmt: skip
    for item in env:
        args += ["--env", item]
    args += [
        *mount(generation, "/generation"), *mount(src, "/src"), *mount(work, "/run/opentransit"),
        api_image, "/app/.venv/bin/uvicorn", "opentransit.api.app:create_app", "--factory",
        "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--log-level", "info",
        "--timeout-graceful-shutdown", "25",
    ]  # fmt: skip
    return args


# ------------------------------------------------------------------------------ the runner


@dataclass
class Runner:
    generation: Path
    run_id: str
    prefix: str
    port: int = 8500
    api_image: str = API_IMAGE_DEFAULT
    photon_jar: Path | None = None
    probe_corpus: Path | None = None
    service_date: date | None = None
    cpus: str | None = None
    steps: tuple[str, ...] = STEPS
    keep_stack: bool = False
    warm_search: bool = True
    attach: bool = False
    readyz_interval: float = 0.5
    start_timeout: float = 2400.0
    log: Callable[[str], None] = print
    paths: dict[str, Path] = field(init=False)
    manifest: dict = field(init=False)
    checks: dict[str, dict] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
    images: dict[str, Any] = field(default_factory=dict)
    memory_samples: dict[str, int] = field(default_factory=dict)
    started_at: str = ""
    coverage: tuple[datetime, datetime] | None = None
    api_url: str = ""
    depart_at: str = ""
    containers_started: list[str] = field(default_factory=list)
    volumes_created: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.generation = Path(self.generation).resolve(strict=True)
        self.run_id = sanitize_run_id(self.run_id)
        self.paths = output_paths(self.prefix)
        self.manifest = json.loads((self.generation / "manifest.json").read_text(encoding="utf-8"))
        cov = self.manifest["coverage"]
        self.coverage = (parse_instant(cov["from"]), parse_instant(cov["until"]))
        self.api_url = f"http://127.0.0.1:{check_port(self.port)}"
        self.depart_at = pick_service_day(*self.coverage, self.service_date)

    # ---- process helpers
    def say(self, message: str) -> None:
        self.log(f"[{datetime.now(UTC):%H:%M:%S}] {message}")

    def run(self, argv: Sequence[str], *, timeout: float = 120, check: bool = True, env=None):
        merged = {**os.environ, "MSYS_NO_PATHCONV": "1", "PYTHONUTF8": "1", **(env or {})}
        proc = subprocess.run(
            [str(item) for item in argv], capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, env=merged,
        )  # fmt: skip
        if check and proc.returncode != 0:
            tail = (proc.stderr or proc.stdout)[-600:]
            raise RunnerError(f"{' '.join(map(str, argv[:4]))} failed ({proc.returncode}): {tail}")
        return proc

    def docker(self, *args: str, timeout: float = 120, check: bool = True):
        return self.run(["docker", *args], timeout=timeout, check=check)

    def write_new(self, key: str, text: str) -> Path:
        path = self.paths[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        self.files[key] = str(path)
        return path

    def write_json(self, key: str, value: Any) -> Path:
        return self.write_new(key, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def record(self, name: str, status: str, started: float, **values: Any) -> dict:
        entry = {
            "status": status,
            "seconds": round(time.time() - started, 1),
            "finishedAt": iso(),
            **values,
        }
        self.checks[name] = entry
        self.say(f"{name}: {status} ({entry['seconds']} s)")
        return entry

    # ---- preflight and provenance
    def preflight(self) -> None:
        clash = existing_outputs(self.paths)
        if clash:
            raise RunnerError(
                "Refusing to overwrite existing outputs: " + ", ".join(map(str, clash))
            )
        self.docker("version", "--format", "{{.Server.Version}}", timeout=30)
        names = self.docker(
            "ps", "-a", "--filter", f"name=^ot-acc-{self.run_id}-", "--format", "{{.Names}}"
        ).stdout.split()
        if names and not self.attach:
            raise RunnerError(f"Containers already exist for run {self.run_id}: {names}")
        if not self.attach:
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                    raise RunnerError(f"Host port {self.port} is already in use")
        if not (self.generation / "manifest.json").is_file():
            raise RunnerError("Generation has no manifest.json")

    def git_info(self) -> dict:
        def git(*args: str) -> str:
            proc = self.run(["git", "-C", str(REPO), *args], check=False, timeout=60)
            return proc.stdout.strip()

        return {
            "commit": git("rev-parse", "HEAD"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirtyApiSource": git("status", "--porcelain", "--", "services/api/src") != "",
            "treeOfApiSource": git("rev-parse", "HEAD:services/api/src"),
        }

    def image_info(self, reference: str) -> dict:
        proc = self.docker(
            "image", "inspect", reference, "--format",
            "{{.Id}}|{{json .RepoDigests}}|{{.Created}}", check=False, timeout=60,
        )  # fmt: skip
        if proc.returncode != 0:
            return {"reference": reference, "present": False}
        image_id, digests, created = proc.stdout.strip().split("|", 2)
        return {
            "reference": reference, "present": True, "id": image_id,
            "repoDigests": json.loads(digests), "created": created,
        }  # fmt: skip

    def resolve_images(self) -> None:
        engine = self.manifest["engineDigest"]
        self.images["motis"] = self.image_info(f"{MOTIS_IMAGE_BASE}@{engine}")
        self.images["api"] = self.image_info(self.api_image)
        address = self.manifest.get("addressSearch")
        if address:
            java = f"{JAVA_IMAGE_BASE}@{address['javaImageDigest']}"
            self.images["java"] = self.image_info(java)
        for name, info in self.images.items():
            if not info.get("present"):
                raise RunnerError(f"Docker image for {name} is not present locally: {info}")

    def resolve_photon_jar(self) -> Path:
        candidates = [self.photon_jar, os.getenv("OPENTRANSIT_PHOTON_JAR"), *PHOTON_JAR_CANDIDATES]
        from opentransit.build.photon import check_photon_jar

        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return check_photon_jar(Path(candidate))
        raise RunnerError("Pinned photon-1.3.0.jar not found; pass --photon-jar")

    def sample_memory(self) -> None:
        names = [container_name(self.run_id, role) for role in ("motis", "photon", "api")]
        proc = self.docker(
            "stats", "--no-stream", "--format", "{{.Name}}|{{.MemUsage}}", *names,
            check=False, timeout=60,
        )  # fmt: skip
        for line in proc.stdout.splitlines():
            name, _, usage = line.partition("|")
            match = re.match(r"([\d.]+)\s*([KMG]i?B)", usage.strip())
            if match:
                scale = {"KiB": 1024, "KB": 1000, "MiB": 1024**2, "MB": 1000**2}
                scale |= {"GiB": 1024**3, "GB": 1000**3}
                value = int(float(match.group(1)) * scale[match.group(2)])
                self.memory_samples[name] = max(self.memory_samples.get(name, 0), value)

    # ---- http helpers
    def http(self, path: str, *, timeout: float = 10.0) -> tuple[int, Any, float]:
        started = time.perf_counter()
        request = urllib.request.Request(self.api_url + path)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status, body = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, body = exc.code, exc.read()
        except urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError:
            return 0, None, (time.perf_counter() - started) * 1000
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = None
        return status, parsed, (time.perf_counter() - started) * 1000

    def container_running(self, role: str) -> bool:
        proc = self.docker(
            "inspect", "--format", "{{.State.Running}}", container_name(self.run_id, role),
            check=False, timeout=30,
        )  # fmt: skip
        return proc.stdout.strip() == "true"

    def container_logs(self, role: str) -> str:
        proc = self.run(
            ["docker", "logs", container_name(self.run_id, role)], check=False, timeout=300
        )
        return proc.stdout + proc.stderr

    def wait_for(self, what: str, probe: Callable[[], bool], timeout: float, role: str) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if probe():
                return
            if not self.container_running(role):
                raise RunnerError(f"{what}: container {role} exited; see its exported log")
            time.sleep(3)
        raise RunnerError(f"{what} not ready within {timeout:.0f} s")

    # ---- steps
    def step_stack(self) -> None:
        started = time.time()
        run_id, generation = self.run_id, self.generation
        motis = container_name(run_id, "motis")
        argv = motis_argv(
            run_id, self.images["motis"]["reference"], generation, self.port, self.cpus
        )
        self.docker(*argv[1:], timeout=300)
        self.containers_started.append(motis)

        def motis_ready() -> bool:
            return "listening on" in self.container_logs("motis")

        self.wait_for("MOTIS", motis_ready, 300, "motis")
        wget = f"wget -qO- 'http://127.0.0.1:8080{MOTIS_HEALTH_QUERY}' >/dev/null 2>&1"
        health = self.docker("exec", motis, "sh", "-c", wget, check=False, timeout=60)
        values: dict[str, Any] = {"motisHealthExit": health.returncode}
        # Photon runs with -data-dir /photon_data and opens /photon_data/photon_data/node_1, so
        # the whole <generation>/photon tree (holding photon_data/) is the volume's content.
        checkpoint = generation / "photon"
        if self.manifest.get("addressSearch") and (checkpoint / "photon_data").is_dir():
            volume = f"ot-acc-{run_id}-photon"
            java = self.images["java"]["reference"]
            self.docker("volume", "create", volume, timeout=60)
            self.volumes_created.append(volume)
            self.docker(*photon_init_argv(run_id, java, volume, checkpoint)[1:], timeout=300)
            self.containers_started.append(container_name(run_id, "photon-init"))
            jar = self.resolve_photon_jar()
            self.docker(*photon_argv(run_id, java, volume, jar, self.cpus)[1:], timeout=300)
            self.containers_started.append(container_name(run_id, "photon"))
            photon = container_name(run_id, "photon")
            self.wait_for(
                "Photon",
                lambda: self.docker(
                    "exec", photon, "curl", "-fsS", "http://127.0.0.1:2322/status",
                    check=False, timeout=60,
                ).returncode == 0,
                600, "photon",
            )  # fmt: skip
            values["photon"] = {"jar": str(jar), "volume": volume}
        else:
            values["photon"] = None
        self.sample_memory()
        ok = health.returncode == 0
        self.record("stack", "PASS" if ok else "FAIL", started, **values)

    def probe_corpus_path(self) -> Path:
        for candidate in (
            self.probe_corpus,
            self.generation / "probe-queries.json",
            TOOLS / "acceptance-probe-corpus.json",
        ):
            if candidate is not None and Path(candidate).is_file():
                return Path(candidate)
        raise RunnerError("No probe corpus; pass --probe-corpus")

    def step_probe(self) -> None:
        started = time.time()
        source = self.probe_corpus_path()
        corpus = json.loads(source.read_text(encoding="utf-8"))
        derived, changes = redate_probe_corpus(corpus, *self.coverage)
        queries = self.write_json("probe_queries", derived)
        work = self.paths["work"]
        work.mkdir(parents=True, exist_ok=False)
        argv = verifier_argv(
            self.run_id, self.images["api"]["reference"], self.generation, API_SRC, queries, work
        )
        self.say("probe: verifying artifacts in the verifier container (reference hashing is slow)")
        proc = self.run(argv, timeout=self.start_timeout, check=False)
        self.containers_started.append(container_name(self.run_id, "verifier"))
        probe_file = work / "probe.json"
        report: dict = {}
        if probe_file.is_file():
            report = json.loads(probe_file.read_text(encoding="utf-8"))
            self.write_new("probe", probe_file.read_text(encoding="utf-8"))
        passed = proc.returncode == 0 and report.get("status") == "passed"
        journeys = report.get("journeys", [])
        self.record(
            "probe", "PASS" if passed else "FAIL", started,
            exitCode=proc.returncode, probeStatus=report.get("status"),
            failure=report.get("failure"), cases=report.get("caseCount"),
            passedJourneys=sum(1 for item in journeys if item.get("status") == "passed"),
            failedJourneys=[
                {"id": item.get("id"), "failure": item.get("failure")}
                for item in journeys if item.get("status") != "passed"
            ],
            probeCorpusSource=str(source), probeCorpusSourceSha256=sha256_file(source),
            probeCorpusUsedSha256=report.get("corpusSha256"),
            redated=changes, structuralOnly=True, humanH3Approval=False,
        )  # fmt: skip

    def step_api_start(self) -> None:
        started = time.time()
        work = self.paths["work"]
        if not (work / "probe.json").is_file():
            raise RunnerError("No probe report to bind the API to (probe step missing or failed)")
        photon = (
            self.manifest.get("addressSearch") is not None
            and (self.generation / "photon" / "photon_data").is_dir()
        )
        argv = api_argv(
            self.run_id, self.images["api"]["reference"], self.generation, API_SRC, work,
            photon=photon, cpus=self.cpus,
        )  # fmt: skip
        self.docker(*argv[1:], timeout=300)
        self.containers_started.append(container_name(self.run_id, "api"))
        self.say("api_start: waiting for /healthz (startup hashes every artifact)")
        self.wait_for(
            "API", lambda: self.http("/healthz", timeout=3)[0] == 200, self.start_timeout, "api"
        )
        healthy_after = round(time.time() - started, 1)
        # Wait (bounded) for the first 200 /readyz; record every pre-ready failure reason.
        pre_ready, first_ok = [], None
        for _ in range(120):
            status, body, ms = self.http("/readyz")
            if status == 200:
                first_ok = round(time.time() - started, 1)
                break
            pre_ready.append({"status": status, "errors": (body or {}).get("errors")})
            time.sleep(1)
        self.sample_memory()
        self.record(
            "api_start", "PASS" if first_ok is not None else "FAIL", started,
            healthzAfterSeconds=healthy_after, firstReadyzOkAfterSeconds=first_ok,
            preReadyFailures=pre_ready[:10], preReadyFailureCount=len(pre_ready),
            photonBound=photon, apiImage=self.images["api"]["id"],
        )  # fmt: skip

    def step_readyz(self) -> None:
        started = time.time()
        before = count_verify_fail(self.container_logs("motis"))
        samples = []
        for _ in range(READYZ_REQUESTS):
            status, body, ms = self.http("/readyz", timeout=5)
            samples.append(
                {
                    "status": status, "ms": round(ms, 1),
                    "errors": (body or {}).get("errors") if status != 200 else None,
                    "generationId": (body or {}).get("generationId") if status == 200 else None,
                }
            )  # fmt: skip
            time.sleep(self.readyz_interval)
        after = count_verify_fail(self.container_logs("motis"))
        summary = summarize_readyz(samples)
        self.write_json("readyz", {"summary": summary, "samples": samples})
        ok = summary["ok"] == READYZ_REQUESTS
        self.record(
            "readyz", "PASS" if ok else "FAIL", started, **summary,
            expected=READYZ_REQUESTS, motisVerifyFailDuringReadyz=after - before,
        )  # fmt: skip

    def tool(self, label: str, argv: list[str], *, timeout: float) -> subprocess.CompletedProcess:
        self.say(f"{label}: running {Path(str(argv[1])).name}")
        return self.run(argv, timeout=timeout, check=False)

    def step_walk_caps(self) -> None:
        started = time.time()
        out = self.paths["walk_caps"]
        proc = self.tool(
            "walk_caps",
            [sys.executable, str(TOOLS / "check_walk_caps.py"), "--api-url", self.api_url,
             "--depart-at", self.depart_at, "--output", str(out)],
            timeout=900,
        )  # fmt: skip
        report = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
        if out.is_file():
            self.files["walk_caps"] = str(out)
        self.record(
            "walk_caps", "PASS" if proc.returncode == 0 else "FAIL", started,
            exitCode=proc.returncode, departAt=self.depart_at,
            violationCount=report.get("violationCount"), errors=report.get("errors"),
            cases=len(report.get("cases", [])),
            statuses=sorted({c["status"] for c in report.get("cases", [])}),
            stderr=proc.stderr[-300:] or None,
        )  # fmt: skip

    def step_demo(self) -> None:
        started = time.time()
        proc = self.tool(
            "demo",
            [sys.executable, "-m", "opentransit.build.cli", "demo", "--api-url", self.api_url,
             "--depart-at", self.depart_at],
            timeout=120,
        )  # fmt: skip
        self.write_new("demo", f"# exit {proc.returncode}\n{proc.stdout}\n# stderr\n{proc.stderr}")
        parsed = parse_demo_output(proc.stdout)
        ok = proc.returncode == 0 and parsed["journeyCount"] > 0
        self.record(
            "demo", "PASS" if ok else "FAIL", started,
            exitCode=proc.returncode, departAt=self.depart_at, **parsed,
            stderr=proc.stderr[-300:] or None,
        )  # fmt: skip

    def step_h3_review(self) -> None:
        started = time.time()
        proc = self.tool(
            "h3_review",
            [sys.executable, str(TOOLS / "h3_review.py"), "--api-url", self.api_url,
             "--output", str(self.paths["h3_sheet"]), "--raw-output", str(self.paths["h3_raw"]),
             "--allow-past"],
            timeout=1800,
        )  # fmt: skip
        raw_path = self.paths["h3_raw"]
        values: dict[str, Any] = {"exitCode": proc.returncode, "toolOutput": proc.stdout[-300:]}
        errored: list[str] = []
        if raw_path.is_file():
            self.files["h3_raw"] = str(raw_path)
            self.files["h3_sheet"] = str(self.paths["h3_sheet"])
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            cases = raw.get("cases", [])
            errored = [c["id"] for c in cases if c.get("error") or c.get("httpStatus") != 200]
            omitted = [
                {"id": d["id"], "reason": d["omitted"]}
                for d in raw.get("dates", [])
                if d.get("omitted")
            ]
            values |= {
                "generationId": raw.get("generationId"), "casesGenerated": len(cases),
                "casesErrored": errored, "casesNotGenerated": omitted,
                "window": raw.get("window"), "humanH3Approval": False,
            }  # fmt: skip
        values["stderr"] = proc.stderr[-300:] or None
        # Not-generated cases (outside coverage) are reported, not a failure; errors are.
        ok = proc.returncode == 0 and not errored and values.get("casesGenerated", 0) > 0
        self.record("h3_review", "PASS" if ok else "FAIL", started, **values)

    def search_warmup(self) -> None:
        """Send the unscored warm-up set; its own check records the cold-start behaviour."""
        started = time.time()
        samples = []
        for query, types in WARMUP_QUERIES:
            params = "&".join(
                ["q=" + urllib.parse.quote(query), "lang=en", "limit=10"]
                + [f"type={kind}" for kind in types]
            )
            status, _, ms = self.http("/v1/places?" + params, timeout=30)
            samples.append(
                {"query": query, "types": list(types), "status": status, "ms": round(ms, 1)}
            )
        assessment = warmup_assessment(samples)
        self.record(
            "search_cold_start",
            "PASS" if assessment["clean"] else "FAIL",
            started,
            samples=samples,
            **assessment,
            note="unscored; requests are in the API log but not in the evaluation",
        )

    def step_search(self) -> None:
        if self.warm_search:
            self.search_warmup()
        started = time.time()
        hashes = self.write_json("source_hashes", source_hashes(API_SRC))
        git = self.git_info()
        runtime = {
            "schemaVersion": SCHEMA_VERSION,
            "capturedAt": iso(),
            "scope": "acceptance_run.py live stack; all final acceptance remains open",
            "status": "implemented_tested_not_human_accepted",
            "runId": self.run_id,
            "generationId": self.manifest["generationId"],
            "scheduleComponentGenerationId": self.manifest.get("scheduleComponentGenerationId"),
            "source": git,
            "images": self.images,
            "containers": {
                role: {"name": container_name(self.run_id, role), "memoryCap": cap}
                for role, cap in MEMORY_CAPS.items()
            },
            "cpus": self.cpus,
            "hostPort": self.port,
        }
        runtime_path = self.write_json("runtime", runtime)
        proc = self.tool(
            "search",
            [sys.executable, str(TOOLS / "evaluate_search.py"), "--api-url", self.api_url,
             "--manifest", str(self.generation / "manifest.json"),
             "--source-hashes", str(hashes), "--runtime-evidence", str(runtime_path),
             "--output", str(self.paths["search_raw"]),
             "--review-output", str(self.paths["h4_sheet"])],
            timeout=3600,
        )  # fmt: skip
        values: dict[str, Any] = {"evaluateExit": proc.returncode, "stdout": proc.stdout[-200:]}
        if proc.returncode != 0 or not self.paths["search_raw"].is_file():
            values["stderr"] = proc.stderr[-300:]
            self.record("search", "FAIL", started, **values)
            return
        self.files["search_raw"] = str(self.paths["search_raw"])
        self.files["h4_sheet"] = str(self.paths["h4_sheet"])
        log = self.write_new("search_api_log", self.container_logs("api"))
        final = self.tool(
            "search",
            [sys.executable, str(TOOLS / "evaluate_search.py"),
             "--finalize-input", str(self.paths["search_raw"]),
             "--output", str(self.paths["search"]), "--container-log-file", str(log)],
            timeout=600,
        )  # fmt: skip
        values["finalizeExit"] = final.returncode
        if final.returncode != 0 or not self.paths["search"].is_file():
            values["stderr"] = final.stderr[-300:]
            self.record("search", "FAIL", started, **values)
            return
        self.files["search"] = str(self.paths["search"])
        result = json.loads(self.paths["search"].read_text(encoding="utf-8"))
        values |= search_summary(result)
        correlated = values["logCorrelation"].get("unmatchedCount") == 0
        bad = first_pass_failures(values)
        values["firstPassFailures"] = bad
        values["warmedUp"] = self.warm_search
        self.sample_memory()
        self.record("search", "PASS" if correlated and bad == 0 else "FAIL", started, **values)

    def final_verify_fail_check(self) -> None:
        started = time.time()
        if not self.containers_started:
            return
        total = count_verify_fail(self.container_logs("motis"))
        self.record("motis_verify_fail", "PASS" if total == 0 else "FAIL", started, count=total)

    # ---- lifecycle
    def export_logs_and_cleanup(self) -> dict:
        exported, removed, problems = {}, [], []
        for role in LOG_ROLES:
            name = container_name(self.run_id, role)
            if name not in self.containers_started:
                continue
            try:
                self.write_new(f"log_{role}", self.container_logs(role))
                exported[role] = str(self.paths[f"log_{role}"])
            except (OSError, subprocess.SubprocessError, FileExistsError) as exc:
                problems.append(f"log {role}: {type(exc).__name__}")
        states = {}
        for name in self.containers_started:
            proc = self.docker(
                "inspect", "--format",
                "{{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} "
                "restarts={{.RestartCount}}", name, check=False, timeout=30,
            )  # fmt: skip
            states[name] = proc.stdout.strip()
        if not self.keep_stack:
            for name in reversed(self.containers_started):
                if self.docker("rm", "-f", name, check=False, timeout=120).returncode == 0:
                    removed.append(name)
            for volume in self.volumes_created:
                if self.docker("volume", "rm", volume, check=False, timeout=60).returncode == 0:
                    removed.append(volume)
        return {"logs": exported, "finalStates": states, "removed": removed, "problems": problems}

    def summary(self, finished: str, wall: float, cleanup: dict, error: str | None) -> dict:
        manifest = self.manifest
        status = overall_status(self.checks) if self.checks else "ERROR"
        return {
            "schemaVersion": SCHEMA_VERSION,
            "tool": "services/api/tools/acceptance_run.py",
            "runId": self.run_id,
            "status": status,
            "runnerError": error,
            "startedAt": self.started_at,
            "finishedAt": finished,
            "wallSeconds": round(wall, 1),
            "scope": "live acceptance run; structural/mechanical only: no H3 or H4 approval",
            "humanH3Approval": False,
            "humanH4Approval": False,
            "source": self.git_info(),
            "generation": {
                "dir": str(self.generation),
                "generationId": manifest.get("generationId"),
                "scheduleComponentGenerationId": manifest.get("scheduleComponentGenerationId"),
                "manifestSha256": sha256_file(self.generation / "manifest.json"),
                "mode": manifest.get("mode"),
                "coverage": manifest.get("coverage"),
                "engineDigest": manifest.get("engineDigest"),
                "inputs": {
                    name: record.get("sha256")
                    for name, record in manifest.get("inputs", {}).items()
                    if isinstance(record, dict)
                },
                "artifacts": {
                    name: record.get("sha256")
                    for name, record in manifest.get("artifacts", {}).items()
                    if isinstance(record, dict)
                },
                "addressSearch": manifest.get("addressSearch") is not None,
            },
            "images": self.images,
            "stack": {
                "apiUrl": self.api_url,
                "memoryCaps": MEMORY_CAPS,
                "cpus": self.cpus,
                "departAtUsedForWalkCapsAndDemo": self.depart_at,
                "memorySamplesBytes": self.memory_samples,
                "memorySamplingNote": "docker stats snapshots at step boundaries, not true peaks",
                **cleanup,
            },
            "checks": self.checks,
            "files": self.files,
        }

    def execute(self) -> int:
        started_wall = time.time()
        self.started_at = iso()
        error: str | None = None
        try:
            self.preflight()
            self.resolve_images()
            blocked: str | None = None
            sequence = [
                ("stack", self.step_stack), ("probe", self.step_probe),
                ("api_start", self.step_api_start), ("readyz", self.step_readyz),
                ("walk_caps", self.step_walk_caps), ("demo", self.step_demo),
                ("h3_review", self.step_h3_review), ("search", self.step_search),
            ]  # fmt: skip
            if self.attach:
                for role in ("motis", "photon", "api", "verifier", "photon-init"):
                    name = container_name(self.run_id, role)
                    if self.docker("inspect", name, check=False, timeout=30).returncode == 0:
                        self.containers_started.append(name)
                volume = f"ot-acc-{self.run_id}-photon"
                if (
                    self.docker("volume", "inspect", volume, check=False, timeout=30).returncode
                    == 0
                ):
                    self.volumes_created.append(volume)
            for name, function in sequence:
                if name not in self.steps or (self.attach and name in INFRA_STEPS):
                    self.checks[name] = {"status": "SKIPPED", "reason": "not selected/attached"}
                    continue
                if blocked:
                    self.checks[name] = {"status": "SKIPPED", "reason": blocked}
                    continue
                started = time.time()
                try:
                    function()
                except Exception as exc:  # a failing step is evidence, not a crash
                    error = f"{name}: {type(exc).__name__}: {exc}"
                    self.record(name, "ERROR", started, error=str(exc)[:600])
                    if name in INFRA_STEPS:
                        blocked = f"{name} did not complete"
                else:
                    if name == "stack" and self.checks[name]["status"] != "PASS":
                        blocked = "stack unhealthy"
            if container_name(self.run_id, "motis") in self.containers_started:
                self.final_verify_fail_check()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                if self.containers_started:
                    self.sample_memory()
                cleanup = (
                    self.export_logs_and_cleanup()
                    if self.containers_started or self.attach
                    else {"logs": {}, "finalStates": {}, "removed": [], "problems": []}
                )
            except Exception as exc:  # never lose the summary to a cleanup error
                cleanup = {"problems": [f"cleanup: {type(exc).__name__}: {exc}"]}
        summary = self.summary(iso(), time.time() - started_wall, cleanup, error)
        try:
            self.write_json("summary", summary)
        except FileExistsError:
            print("summary file already exists; not overwritten", file=sys.stderr)
        print(json.dumps({k: summary[k] for k in ("status", "runnerError", "wallSeconds")}))
        for name, check in summary["checks"].items():
            print(f"  {name:<18} {check['status']:<8} {check.get('seconds', '')}")
        return exit_code(summary["status"])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--generation", type=Path, required=True, help="complete generation dir")
    parser.add_argument("--run-id", required=True, help="names containers ot-acc-<run-id>-*")
    parser.add_argument("--results-prefix", required=True, help="output path prefix (new files)")
    parser.add_argument("--port", type=int, default=8500, help="host port, 8500-8599")
    parser.add_argument(
        "--api-image",
        default=API_IMAGE_DEFAULT,
        help="image with the API dependencies; the current source is bind-mounted",
    )
    parser.add_argument("--photon-jar", type=Path, help="pinned photon-1.3.0.jar (checked by hash)")
    parser.add_argument(
        "--probe-corpus",
        type=Path,
        help="default: <generation>/probe-queries.json, else the bundled corpus",
    )
    parser.add_argument(
        "--service-date",
        type=date.fromisoformat,
        help="local date for walk-cap/demo departures (default: first Sun-Thu)",
    )
    parser.add_argument("--cpus", help="optional docker --cpus value for MOTIS/Photon/API")
    parser.add_argument(
        "--steps", default=",".join(STEPS), help="comma list of: " + ", ".join(STEPS)
    )
    parser.add_argument(
        "--no-warm-search",
        action="store_true",
        help="skip the unscored warm-up (first scored requests then run cold)",
    )
    parser.add_argument("--keep-stack", action="store_true", help="leave containers running")
    parser.add_argument(
        "--attach",
        action="store_true",
        help="reuse a running stack of this run id (skips stack/probe/api_start)",
    )
    parser.add_argument("--readyz-interval", type=float, default=0.5)
    parser.add_argument("--start-timeout", type=float, default=2400.0)
    args = parser.parse_args(argv)
    steps = tuple(item.strip() for item in args.steps.split(",") if item.strip())
    unknown = set(steps) - set(STEPS)
    if unknown:
        parser.error(f"unknown steps: {sorted(unknown)}")
    args.steps = steps
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        runner = Runner(
            generation=args.generation, run_id=args.run_id, prefix=args.results_prefix,
            port=args.port, api_image=args.api_image, photon_jar=args.photon_jar,
            probe_corpus=args.probe_corpus, service_date=args.service_date, cpus=args.cpus,
            steps=args.steps, keep_stack=args.keep_stack,
            warm_search=not args.no_warm_search, attach=args.attach,
            readyz_interval=args.readyz_interval, start_timeout=args.start_timeout,
        )  # fmt: skip
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return runner.execute()


if __name__ == "__main__":
    raise SystemExit(main())
