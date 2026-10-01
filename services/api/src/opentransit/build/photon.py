"""Import, seal and checkpoint a Photon 1.3.0 address index through an injected Docker runner.

This module turns the manual launcher/sealing scripts used for the preserved composite generation
into reusable steps. Nothing here starts Docker unless the caller supplies the real ``runner``;
unit tests inject a fake one. Containers and volumes are never removed: failed or finished
attempts stay available for diagnosis, as with the MOTIS import.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from opentransit.core.artifacts import JAVA_21_IMAGE_DIGEST, PHOTON_130_JAR_SHA256

JAVA_IMAGE = f"eclipse-temurin:21.0.12.1_1-jre@{JAVA_21_IMAGE_DIGEST}"
PHOTON_JAR_CONTAINER_PATH = "/opt/photon/photon-1.3.0.jar"
PHOTON_USER = "10001:10001"
MAX_PHOTON_MEMORY_GIB = 2
SERVE_MEMORY_GIB = 1
PHOTON_LISTEN_PORT = 2322
PHOTON_ADMIN_ORIGIN = "http://127.0.0.1:9201"
INDEX_NAME = "photon"
SETUP_MARKER = "Database has been successfully set up with the following properties:"
_COMPLETION = re.compile(
    r"Finished import of\s+(?P<count>\d+)\s+photon documents\.\s+"
    r"\(Total processing time: [0-9.]+s\)"
)
_FATAL = re.compile(
    r"(?im)IO error while importing|Cannot initialize database|Import error\.|"
    r"Import thread failed\.|Failed to save database properties after import"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_photon_jar(path: Path) -> Path:
    jar = Path(path).resolve(strict=True)
    if sha256_file(jar) != PHOTON_130_JAR_SHA256:
        raise ValueError("Photon JAR hash differs from the pinned Photon 1.3.0 artifact")
    return jar


def _bind(source: Path, target: str) -> str:
    text = Path(source).resolve().as_posix()
    if "," in text:
        raise ValueError("Docker bind paths containing commas are unsupported")
    return f"type=bind,src={text},dst={target},readonly"


def _run(runner: Callable, command: list[str], log_path: Path, timeout: int):
    """Run one Docker command, keeping stdout+stderr as evidence."""
    with Path(log_path).open("w", encoding="utf-8", errors="replace") as log:
        return runner(command, stdout=log, stderr=subprocess.STDOUT, check=False, timeout=timeout)


def _capture(runner: Callable, command: list[str], base: Path, timeout: int) -> tuple[int, str]:
    """Run a command whose stdout is data; stderr is kept separately as evidence."""
    out_path, err_path = base.with_suffix(".out"), base.with_suffix(".err")
    with (
        out_path.open("w", encoding="utf-8", errors="replace") as out,
        err_path.open("w", encoding="utf-8", errors="replace") as err,
    ):
        result = runner(command, stdout=out, stderr=err, check=False, timeout=timeout)
    return result.returncode, out_path.read_text(encoding="utf-8", errors="replace")


def _state(runner: Callable, container: str, base: Path) -> dict:
    code, text = _capture(
        runner, ["docker", "inspect", "--format", "{{json .State}}", container], base, 30
    )
    if code != 0:
        raise RuntimeError(f"Could not inspect container {container}")
    return json.loads(text)


def check_import_log(text: str, expected_documents: int) -> dict:
    """Exit code zero is not success: require the setup marker, exact count and no fatal marker."""
    setup = text.count(SETUP_MARKER)
    completions = list(_COMPLETION.finditer(text))
    fatal = _FATAL.findall(text)
    indexed = int(completions[0].group("count")) if len(completions) == 1 else -1
    if setup != 1 or len(completions) != 1 or indexed != expected_documents or fatal:
        raise ValueError(
            f"Photon import is unverified: setupMarkers={setup}, "
            f"completionLines={len(completions)}, indexedCount={indexed}/{expected_documents}, "
            f"fatalMarkers={len(fatal)}"
        )
    return {"indexedDocuments": indexed, "setupMarkers": setup, "fatalMarkers": 0}


def photon_memory_args(memory_gib: int) -> tuple[list[str], str]:
    if isinstance(memory_gib, bool) or not isinstance(memory_gib, int):
        raise ValueError("Photon memory cap must be an integer number of GiB")
    if not 1 <= memory_gib <= MAX_PHOTON_MEMORY_GIB:
        raise ValueError(f"Photon import memory cap must be 1..{MAX_PHOTON_MEMORY_GIB} GiB")
    heap = "1g" if memory_gib == 2 else "512m"
    return [f"--memory={memory_gib}g", f"--memory-swap={memory_gib}g"], heap


def import_photon(
    dump_path: Path,
    jar_path: Path,
    logs_dir: Path,
    expected_documents: int,
    *,
    memory_gib: int = MAX_PHOTON_MEMORY_GIB,
    timeout_seconds: int = 1800,
    runner: Callable = subprocess.run,
) -> dict:
    """Create a new Docker volume and import the enriched dump under a hard memory cap."""
    jar = check_photon_jar(jar_path)
    caps, heap = photon_memory_args(memory_gib)
    logs_dir = Path(logs_dir)
    token = uuid.uuid4().hex[:12]
    volume = f"opentransit-photon-data-{token}"
    init_name = f"opentransit-photon-init-{token}"
    import_name = f"opentransit-photon-import-{token}"
    result = {
        "volumeName": volume,
        "initContainerName": init_name,
        "importContainerName": import_name,
        "memoryCapBytes": memory_gib * 1024**3,
        "javaHeap": heap,
        "image": JAVA_IMAGE,
        "expectedDocuments": expected_documents,
        "startedAt": datetime.now(UTC).isoformat(),
    }
    clock = time.perf_counter()
    code = runner(
        ["docker", "volume", "create", volume],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=60,
    ).returncode
    if code != 0:
        raise RuntimeError("Docker failed to create the Photon volume")
    volume_mount = f"type=volume,src={volume},dst=/photon_data"
    init = _run(
        runner,
        [
            "docker", "run", "--name", init_name, "--memory=64m", "--memory-swap=64m",
            "--network", "none", "--user", "0:0", "--mount", volume_mount,
            "--entrypoint", "/bin/sh", JAVA_IMAGE, "-c",
            "chown -R 10001:10001 /photon_data && chmod 0750 /photon_data",
        ],
        logs_dir / "photon-init.log",
        120,
    )  # fmt: skip
    if init.returncode != 0:
        raise RuntimeError(f"Photon volume initializer failed; inspect {logs_dir}/photon-init.log")
    imported = _run(
        runner,
        [
            "docker", "run", "--name", import_name, *caps, "--network", "none",
            "--user", PHOTON_USER, "--mount", volume_mount,
            "--mount", _bind(jar, PHOTON_JAR_CONTAINER_PATH),
            "--mount", _bind(dump_path, "/input/address-enriched.jsonl"),
            JAVA_IMAGE, "java", "-Xms256m", f"-Xmx{heap}", "-jar", PHOTON_JAR_CONTAINER_PATH,
            "-data-dir", "/photon_data", "import", "-j", "1",
            "-import-file", "/input/address-enriched.jsonl", "-languages", "he,en",
            "-extra-tags", "ALL",
        ],
        logs_dir / "photon-import.log",
        timeout_seconds,
    )  # fmt: skip
    state = _state(runner, import_name, logs_dir / "photon-import-state")
    result.update(
        {
            "exitCode": imported.returncode,
            "state": state,
            "elapsedSeconds": round(time.perf_counter() - clock, 2),
            "finishedAt": state.get("FinishedAt") or datetime.now(UTC).isoformat(),
        }
    )
    if (
        imported.returncode != 0
        or state.get("Status") != "exited"
        or state.get("ExitCode") != 0
        or state.get("OOMKilled")
    ):
        raise RuntimeError(
            f"Photon import did not exit cleanly (exit={imported.returncode}, "
            f"oomKilled={state.get('OOMKilled')}); inspect {logs_dir}/photon-import.log"
        )
    text = (logs_dir / "photon-import.log").read_text(encoding="utf-8", errors="replace")
    result["logCheck"] = check_import_log(text, expected_documents)
    return result


def pick_probe_documents(dump_path: Path) -> list[dict]:
    """First house and first street source document of the enriched dump (deterministic)."""
    wanted = {"house", "street"}
    found: dict[str, dict] = {}
    with Path(dump_path).open("r", encoding="utf-8") as source:
        source.readline()
        for line in source:
            place = json.loads(line)["content"][0]
            kind = place.get("address_type")
            if kind in wanted and kind not in found:
                lon, lat = place["centroid"]
                found[kind] = {
                    "osmType": place["object_type"],
                    "osmId": str(place["object_id"]),
                    "kind": kind,
                    "housenumber": place.get("housenumber"),
                    "lat": lat,
                    "lon": lon,
                }
            if len(found) == len(wanted):
                break
    if len(found) != len(wanted):
        raise ValueError("Enriched dump lacks a house or street document to probe")
    return [found["house"], found["street"]]


class _ContainerHttp:
    """HTTP from inside the serving container (no host port is published)."""

    def __init__(self, runner: Callable, container: str, logs_dir: Path) -> None:
        self.runner, self.container, self.logs_dir = runner, container, Path(logs_dir)
        self.records: list[dict] = []
        code, text = _capture(
            runner,
            ["docker", "exec", container, "sh", "-c", "command -v curl || command -v wget"],
            self.logs_dir / "photon-http-client",
            30,
        )
        tool = Path(text.strip().splitlines()[0]).name if code == 0 and text.strip() else None
        if tool not in {"curl", "wget"}:
            raise RuntimeError(
                "The pinned Java image has neither curl nor wget; cannot query Photon's admin API"
            )
        self.tool = tool

    def request(self, method: str, url: str, body: dict | None = None) -> dict:
        payload = None if body is None else json.dumps(body)
        if self.tool == "curl":
            command = ["curl", "-sS", "--max-time", "30", "-X", method]
            command += ["-H", "Content-Type: application/json"]
            if payload is not None:
                command += ["-d", payload]
        else:
            command = ["wget", "-q", "-O", "-", "--timeout=30", f"--method={method}"]
            command += ["--header=Content-Type: application/json"]
            if payload is not None:
                command += [f"--body-data={payload}"]
        number = len(self.records) + 1
        started = datetime.now(UTC).isoformat()
        code, text = _capture(
            self.runner,
            ["docker", "exec", self.container, *command, url],
            self.logs_dir / f"photon-http-{number:02d}",
            60,
        )
        record = {"startedAt": started, "method": method, "url": url, "exitCode": code}
        try:
            record["body"] = json.loads(text) if text.strip() else None
        except json.JSONDecodeError:
            record["body"] = None
            record["rawBody"] = text[:2000]
        self.records.append(record)
        if code != 0 or record["body"] is None:
            raise RuntimeError(f"Photon request failed: {method} {url} (exit {code})")
        return record["body"]


def tree_checkpoint(root: Path) -> dict:
    """Hash every file (zero-byte included) in the order deploy/aws/tools/stage_bundle.py uses."""
    root = Path(root)
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Photon data tree contains a symbolic link")
        if path.is_file():
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    if not entries:
        raise ValueError("Photon data tree is empty")
    digest = hashlib.sha256()
    for item in entries:
        digest.update(f"{item['path']}\0{item['bytes']}\0{item['sha256']}\n".encode())
    return {
        "treeSha256": digest.hexdigest(),
        "files": len(entries),
        "bytes": sum(item["bytes"] for item in entries),
    }


def seal_photon(
    volume_name: str,
    jar_path: Path,
    probes: list[dict],
    expected_documents: int,
    logs_dir: Path,
    data_dir: Path,
    *,
    runner: Callable = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
    ready_timeout_seconds: int = 240,
    stop_timeout_seconds: int = 60,
) -> dict:
    """Serve the imported index once, set its write block, verify probes, stop and copy it out.

    The index is read only through the container's own loopback (no published ports). After the
    write block and flush the container is stopped and the data directory is copied to the host
    ``data_dir``; that host tree is the checkpoint (never served again) the H-0 image stages.
    """
    jar = check_photon_jar(jar_path)
    logs_dir, data_dir = Path(logs_dir), Path(data_dir)
    if data_dir.exists():
        raise FileExistsError(f"Refusing to overwrite {data_dir}")
    serve = f"opentransit-photon-seal-{uuid.uuid4().hex[:12]}"
    caps = [f"--memory={SERVE_MEMORY_GIB}g", f"--memory-swap={SERVE_MEMORY_GIB}g"]
    started = _run(
        runner,
        [
            "docker", "run", "--detach", "--name", serve, *caps, "--user", PHOTON_USER,
            "--mount", f"type=volume,src={volume_name},dst=/photon_data",
            "--mount", _bind(jar, PHOTON_JAR_CONTAINER_PATH),
            JAVA_IMAGE, "java", "-Xms256m", "-Xmx512m", "-jar", PHOTON_JAR_CONTAINER_PATH,
            "-data-dir", "/photon_data", "serve", "-listen-ip", "127.0.0.1",
            "-listen-port", str(PHOTON_LISTEN_PORT),
        ],
        logs_dir / "photon-seal-start.log",
        120,
    )  # fmt: skip
    if started.returncode != 0:
        raise RuntimeError(f"Photon sealing container failed to start; inspect {logs_dir}")
    http = None
    result: dict = {"containerName": serve, "volumeName": volume_name, "probes": []}
    try:
        http = _ContainerHttp(runner, serve, logs_dir)
        deadline = time.monotonic() + ready_timeout_seconds
        status_url = f"http://127.0.0.1:{PHOTON_LISTEN_PORT}/status"
        while True:
            running = _state(runner, serve, logs_dir / "photon-seal-state-poll").get("Running")
            if not running:
                raise RuntimeError("Photon exited before becoming ready; inspect the seal logs")
            try:
                http.request("GET", status_url)
                break
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Photon did not become ready before the timeout") from None
                sleep(3)
        admin = PHOTON_ADMIN_ORIGIN
        cluster = http.request("GET", admin + "/")
        settings = http.request("GET", f"{admin}/{INDEX_NAME}/_settings?flat_settings=true")
        index_settings = settings[INDEX_NAME]["settings"]
        count = http.request("GET", f"{admin}/{INDEX_NAME}/_count")
        if count.get("count") != expected_documents or count.get("_shards", {}).get("failed"):
            raise ValueError(
                f"Photon index count {count.get('count')} differs from the expected "
                f"{expected_documents}"
            )
        acknowledged = http.request(
            "PUT", f"{admin}/{INDEX_NAME}/_settings", {"index": {"blocks": {"write": True}}}
        )
        if acknowledged.get("acknowledged") is not True:
            raise ValueError("Photon did not acknowledge the write block")
        flushed = http.request("POST", f"{admin}/{INDEX_NAME}/_flush?wait_if_ongoing=true", {})
        if flushed.get("_shards", {}).get("failed"):
            raise ValueError("Photon flush reported failed shards")
        blocked = http.request("GET", f"{admin}/{INDEX_NAME}/_settings?flat_settings=true")[
            INDEX_NAME
        ]["settings"]
        if (
            blocked.get("index.blocks.write") != "true"
            or blocked.get("index.uuid") != index_settings.get("index.uuid")
            or not blocked.get("index.uuid")
        ):
            raise ValueError("Photon index is not write-blocked under the same index UUID")
        after = http.request("GET", f"{admin}/{INDEX_NAME}/_count")
        if after.get("count") != expected_documents or after.get("_shards", {}).get("failed"):
            raise ValueError("Photon document count changed while sealing")
        sealed_at = datetime.now(UTC).isoformat()
        for probe in probes:
            document = http.request(
                "GET", f"{admin}/{INDEX_NAME}/_doc/{probe['osmType']}{probe['osmId']}"
            )
            source = document.get("_source") or {}
            coordinate = source.get("coordinate") or {}
            if (
                document.get("found") is not True
                or document.get("_id") != probe["osmType"] + probe["osmId"]
                or source.get("osm_type") != probe["osmType"]
                or str(source.get("osm_id")) != probe["osmId"]
                or source.get("type") != probe["kind"]
                or source.get("housenumber") != probe["housenumber"]
                or abs(coordinate.get("lat", 1e9) - probe["lat"]) >= 1e-7
                or abs(coordinate.get("lon", 1e9) - probe["lon"]) >= 1e-7
            ):
                raise ValueError(f"Photon source document differs from the dump: {probe}")
            result["probes"].append(
                {
                    "osmType": probe["osmType"],
                    "osmId": probe["osmId"],
                    "lat": probe["lat"],
                    "lon": probe["lon"],
                }
            )
        result.update(
            {
                "indexUuid": index_settings["index.uuid"],
                "clusterUuid": cluster["cluster_uuid"],
                "documentCount": count["count"],
                "sealedAt": sealed_at,
            }
        )
    finally:
        if http is not None:
            (logs_dir / "photon-seal-http.json").write_text(
                json.dumps(http.records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        _run(
            runner,
            ["docker", "stop", "--time", str(stop_timeout_seconds), serve],
            logs_dir / "photon-seal-stop.log",
            stop_timeout_seconds + 60,
        )
        _run(runner, ["docker", "logs", serve], logs_dir / "photon-seal-container.log", 60)
    state = _state(runner, serve, logs_dir / "photon-seal-state-final")
    result["stoppedState"] = state
    if (
        state.get("Status") != "exited"
        or state.get("OOMKilled")
        or state.get("ExitCode")
        not in {
            0,
            143,
        }
    ):
        raise RuntimeError(f"Photon sealing container did not stop cleanly: {state}")
    data_dir.mkdir(parents=True)
    copied = _run(
        runner,
        ["docker", "cp", f"{serve}:/photon_data/.", str(data_dir)],
        logs_dir / "photon-export.log",
        600,
    )
    if copied.returncode != 0:
        raise RuntimeError(f"Photon data export failed; inspect {logs_dir}/photon-export.log")
    checkpoint = tree_checkpoint(data_dir)
    result["checkpoint"] = {
        **checkpoint,
        "recordedAt": datetime.now(UTC).isoformat(),
        "preservedQuiescent": True,
        "hostCopyNeverServed": True,
        "servedOnlyToSeal": True,
        "source": "docker cp of the stopped sealing container's data volume",
    }
    return result
