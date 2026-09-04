#!/usr/bin/env python3
"""POC-2, measurement 1 of 2: the MOTIS graph BUILD, uncapped.

system-design.md 320 says the graph is built on a dev machine or a spot
instance and the artifact is shipped. So this runs through the compose `build`
profile, which carries no mem_limit, and is allowed the whole machine.

The point of this script is not to run docker -- one command would do that. The
point is that it *samples* while docker runs, because "the import succeeded" is
not a POC-2 deliverable and "the import succeeded, took N minutes and peaked at
M GB" is. The import is long (30-90 min was the estimate), so this is designed
to be launched as a background process and left alone:

    python poc/routing/run_import.py &

Outputs, all under poc/routing/:
    import.log              full stdout+stderr of `motis import`
    import-samples.jsonl    one resource sample every 5 s
    import-result.json      wall time, peak RSS, graph size, exit code

Nothing here interprets the result. If the import OOMs, that is recorded as an
OOM, and ADR 0004 is explicit that the next step is a WSL2 memory raise, not a
different routing engine.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROUTING = Path(__file__).resolve().parent
POC = ROUTING.parent
COMPOSE = POC / "docker-compose.yml"

# The graph lives in the `motisgraph` named volume, NOT on the Windows
# filesystem. docker-compose.yml carries the full explanation; the short version
# is that MOTIS grows memory-mapped files and a Docker Desktop bind mount cannot
# do that ("unable to import: resize error"). Compose prefixes volume names with
# the project directory name.
VOLUME = "poc_motisgraph"

LOG = ROUTING / "import.log"
SAMPLES = ROUTING / "import-samples.jsonl"
RESULT = ROUTING / "import-result.json"

CONTAINER = "poc-motis-build"
SAMPLE_INTERVAL_S = 5.0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_bytes(s: str) -> float | None:
    """docker stats prints '1.234GiB' / '512MiB' / '0B'. Return bytes."""
    s = s.strip()
    units = {
        "B": 1,
        "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3, "TiB": 1024 ** 4,
        "kB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4,
    }
    for u in sorted(units, key=len, reverse=True):
        if s.endswith(u):
            try:
                return float(s[: -len(u)]) * units[u]
            except ValueError:
                return None
    return None


def volume_size_bytes() -> int | None:
    """Apparent size of the graph inside the named volume, via a throwaway
    container. `du -sb` (apparent size) rather than disk usage, because MOTIS
    creates sparse mmap files and disk usage under-reports what has to be
    shipped and then loaded."""
    try:
        out = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{VOLUME}:/data:ro",
             "alpine:3.20", "du", "-sb", "/data"],
            capture_output=True, text=True, timeout=180,
        )
        if out.returncode != 0:
            return None
        return int(out.stdout.split()[0])
    except Exception:
        return None


class Sampler(threading.Thread):
    """Poll `docker stats` for the build container until told to stop."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.stop_flag = threading.Event()
        self.peak_rss = 0.0
        self.peak_at = None
        self.n = 0

    def run(self) -> None:
        with SAMPLES.open("w", encoding="utf-8") as fh:
            while not self.stop_flag.is_set():
                sample = self.one()
                if sample:
                    fh.write(json.dumps(sample) + "\n")
                    fh.flush()
                self.stop_flag.wait(SAMPLE_INTERVAL_S)

    def one(self) -> dict | None:
        try:
            out = subprocess.run(
                ["docker", "stats", "--no-stream", "--format",
                 "{{.MemUsage}}|{{.MemPerc}}|{{.CPUPerc}}|{{.PIDs}}", CONTAINER],
                capture_output=True, text=True, timeout=30,
            )
        except Exception:
            return None
        line = out.stdout.strip()
        if out.returncode != 0 or not line:
            # Container not up yet, or already gone. Not an error.
            return None
        try:
            mem_usage, mem_perc, cpu_perc, pids = line.split("|")
            used = parse_bytes(mem_usage.split("/")[0])
        except Exception:
            return None
        if used is None:
            return None
        self.n += 1
        if used > self.peak_rss:
            self.peak_rss = used
            self.peak_at = now()
        return {
            "t": now(),
            "mem_bytes": used,
            "mem_mb": round(used / 1024 ** 2, 1),
            "mem_perc_of_vm": mem_perc.strip(),
            "cpu_perc": cpu_perc.strip(),
            "pids": pids.strip(),
        }


def main() -> int:
    if not shutil.which("docker"):
        print("docker not on PATH", file=sys.stderr)
        return 2

    # A previous partial import leaves a half-written data dir that `motis
    # import` will happily reuse -- its task table records which steps are
    # already "current". Start from an empty volume so the build measurement is
    # a build and not a resume.
    subprocess.run(["docker", "compose", "-f", str(COMPOSE), "--profile", "serve",
                    "--profile", "build", "down", "-v", "--remove-orphans"],
                   cwd=str(POC), capture_output=True, text=True, timeout=180)
    subprocess.run(["docker", "volume", "rm", "-f", VOLUME],
                   capture_output=True, text=True, timeout=120)
    print(f"cleared volume {VOLUME}")

    # Record what the machine was actually willing to give a container. This is
    # the number that matters when reading an OOM: Docker Desktop on Windows
    # caps every container at the WSL2 VM size, not at host RAM.
    vm = subprocess.run(
        ["docker", "info", "--format", "{{.MemTotal}}|{{.NCPU}}|{{.ServerVersion}}"],
        capture_output=True, text=True, timeout=60,
    ).stdout.strip()
    vm_mem, vm_cpu, docker_ver = (vm.split("|") + ["", "", ""])[:3]

    sampler = Sampler()
    sampler.start()

    started_wall = time.monotonic()
    started_iso = now()
    print(f"[{started_iso}] starting MOTIS import (uncapped build profile)")
    print(f"  container VM memory ceiling: {int(vm_mem) / 1024**3:.1f} GiB, {vm_cpu} CPUs, docker {docker_ver}")

    with LOG.open("w", encoding="utf-8", errors="replace") as log:
        log.write(f"# motis import started {started_iso}\n")
        log.write(f"# vm_mem_bytes={vm_mem} vm_cpus={vm_cpu} docker={docker_ver}\n")
        log.flush()
        proc = subprocess.Popen(
            ["docker", "compose", "-f", str(COMPOSE), "--profile", "build",
             "run", "--rm", "--name", CONTAINER, "motis-build"],
            stdout=log, stderr=subprocess.STDOUT, cwd=str(POC),
        )
        rc = proc.wait()

    elapsed = time.monotonic() - started_wall
    sampler.stop_flag.set()
    sampler.join(timeout=20)

    graph_bytes = volume_size_bytes()
    tail = ""
    try:
        tail = "\n".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-40:])
    except Exception:
        pass

    result = {
        "measurement": "build",
        "memory_cap": f"uncapped (WSL2 VM ceiling {int(vm_mem) / 1024**3:.1f} GiB on a 32 GB host)",
        "started_utc": started_iso,
        "finished_utc": now(),
        "wall_seconds": round(elapsed, 1),
        "wall_human": f"{int(elapsed // 60)}m {int(elapsed % 60)}s",
        "exit_code": rc,
        "ok": rc == 0,
        "peak_rss_bytes": int(sampler.peak_rss),
        "peak_rss_mb": round(sampler.peak_rss / 1024 ** 2, 1),
        "peak_rss_at_utc": sampler.peak_at,
        "samples_taken": sampler.n,
        "sample_interval_s": SAMPLE_INTERVAL_S,
        "graph_volume": VOLUME,
        "graph_size_bytes": graph_bytes,
        "graph_size_mb": round(graph_bytes / 1024 ** 2, 1) if graph_bytes else None,
        "docker": {"vm_mem_bytes": int(vm_mem or 0), "vm_cpus": vm_cpu, "server_version": docker_ver},
        "log_tail": tail,
    }
    RESULT.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"[{now()}] import exit={rc} wall={result['wall_human']} "
          f"peak={result['peak_rss_mb']} MB graph={result['graph_size_mb']} MB")
    if rc != 0:
        print("--- last 40 log lines ---")
        print(tail)
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
