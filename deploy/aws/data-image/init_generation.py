"""Copy one verified generation bundle into task-local volumes (DRAFT; never deployed).

Runs as the nonessential ``init`` container of the Fargate task. It is stdlib-only so the
data image can sit on the same pinned Python base layer as the API image.

Contract (exit codes are the only success signal ECS sees through ``dependsOn: SUCCESS``):

* 0  every manifest entry was copied, and the destination bytes match their SHA-256
* 2  the payload manifest is missing or malformed
* 3  a source or destination hash differs (corrupt image layer or failed write)
* 4  a destination volume was not empty (a copy never overwrites)
* 5  a semantic guard failed (generation ID, MOTIS listener, Photon attestation)

Semantic verification of the generation (graph tree, reference counts, address composite,
routing probe) is left to ``opentransit probe`` in the verifier container and to the API
lifespan; this script verifies byte integrity of the copy and the cheap guards above.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path, PurePosixPath

CHUNK = 1 << 20
SCHEMA_VERSION = 1
ROOTS = ("generation", "photon")
SERVING_PORT = 8080


class InitError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def log(event: str, **fields: object) -> None:
    """One JSON line per event; never log request data (there is none in this process)."""
    print(json.dumps({"event": event, **fields}, sort_keys=True), flush=True)


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise InitError(2, f"{label} is not a safe relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise InitError(2, f"{label} is not a safe relative path")
    return path


def load_payload_manifest(payload: Path) -> dict:
    try:
        manifest = json.loads((payload / "payload-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InitError(2, f"payload manifest unreadable: {type(exc).__name__}") from exc
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise InitError(2, "payload manifest schema is unsupported")
    generation_id = manifest.get("generationId")
    if not isinstance(generation_id, str) or not re.fullmatch(r"[a-f0-9]{64}", generation_id):
        raise InitError(2, "payload manifest generationId is invalid")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise InitError(2, "payload manifest lists no files")
    seen: set[tuple[str, str]] = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise InitError(2, "payload manifest entry is malformed")
        _safe_relative(entry.get("src"), "src")
        _safe_relative(entry.get("dst"), "dst")
        if entry.get("root") not in ROOTS:
            raise InitError(2, "payload manifest root must be generation or photon")
        if type(entry.get("bytes")) is not int or entry["bytes"] < 0:
            raise InitError(2, "payload manifest bytes is invalid")
        if not re.fullmatch(r"[a-f0-9]{64}", str(entry.get("sha256", ""))):
            raise InitError(2, "payload manifest sha256 is invalid")
        key = (entry["root"], entry["dst"])
        if key in seen:
            raise InitError(2, "payload manifest repeats a destination")
        seen.add(key)
    return manifest


def tree_sha256(entries: list[dict]) -> str:
    """Tree digest identical to the sealed Photon checkpoint and graph-tree algorithms."""
    digest = hashlib.sha256()
    for item in sorted(entries, key=lambda e: e["path"]):
        digest.update(f"{item['path']}\0{item['bytes']}\0{item['sha256']}\n".encode())
    return digest.hexdigest()


def _drop_cache(descriptor: int) -> None:
    advise = getattr(os, "posix_fadvise", None)
    if advise is not None:
        try:
            advise(descriptor, 0, 0, os.POSIX_FADV_DONTNEED)
        except OSError:
            pass


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            digest.update(chunk)
        _drop_cache(stream.fileno())
    return digest.hexdigest()


def copy_verified(source: Path, destination: Path, entry: dict) -> None:
    """Copy while hashing the source, flush to disk, then re-read the destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    copied = 0
    with source.open("rb") as reader, destination.open("xb") as writer:
        for chunk in iter(lambda: reader.read(CHUNK), b""):
            digest.update(chunk)
            writer.write(chunk)
            copied += len(chunk)
        writer.flush()
        os.fsync(writer.fileno())
        _drop_cache(writer.fileno())
        _drop_cache(reader.fileno())
    if copied != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
        raise InitError(3, f"source bytes differ from the payload manifest: {entry['dst']}")
    if destination.stat().st_size != entry["bytes"] or _hash_file(destination) != entry["sha256"]:
        raise InitError(3, f"destination bytes differ after copy: {entry['dst']}")


def _require_empty(directory: Path, label: str) -> None:
    if not directory.is_dir():
        raise InitError(4, f"{label} volume is not mounted")
    leftovers = [p.name for p in directory.iterdir() if p.name != "lost+found"]
    if leftovers:
        raise InitError(4, f"{label} volume is not empty; refusing to overwrite")


def check_motis_listener(graph: Path) -> None:
    """The task serves MOTIS on 8080; a local-engine-slot build bakes in another port."""
    config = graph / "config.yml"
    if not config.is_file():
        return
    in_server = False
    for line in config.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\S", line):
            in_server = line.strip() == "server:"
            continue
        match = re.match(r"^\s+port:\s*(\d+)\s*$", line)
        if in_server and match and int(match.group(1)) != SERVING_PORT:
            raise InitError(
                5,
                f"graph config.yml listens on port {match.group(1)}, not {SERVING_PORT}; "
                "rebuild the generation without --local-engine-slot",
            )


def check_photon_attestation(generation: Path, photon_entries: list[dict]) -> None:
    attestation_path = generation / "photon-import-attestation.json"
    try:
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
        sealed = attestation["checkpoint"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InitError(5, "Photon payload requires a readable sealed attestation") from exc
    listed = [
        {"path": e["dst"], "bytes": e["bytes"], "sha256": e["sha256"]} for e in photon_entries
    ]
    if (
        tree_sha256(listed) != sealed.get("treeSha256")
        or len(listed) != sealed.get("files")
        or sum(e["bytes"] for e in listed) != sealed.get("bytes")
    ):
        raise InitError(5, "Photon data tree differs from the sealed attestation checkpoint")


def apply_permissions(
    generation: Path,
    photon: Path | None,
    writable: list[Path],
    uid: int,
    gid: int,
) -> None:
    """Generation read-only for everyone; Photon and scratch volumes owned by the service user."""
    can_chown = hasattr(os, "geteuid") and os.geteuid() == 0

    def walk(root: Path, file_mode: int, dir_mode: int, owner: tuple[int, int] | None) -> None:
        for path in [root, *sorted(root.rglob("*"))]:
            if path.is_symlink():
                raise InitError(5, "volume contains a symlink")
            if owner is not None and can_chown:
                os.chown(path, *owner)
            os.chmod(path, dir_mode if path.is_dir() else file_mode)

    walk(generation, 0o444, 0o555, (0, 0))
    if photon is not None:
        walk(photon, 0o640, 0o750, (uid, gid))
    for path in writable:
        if not path.is_dir():
            raise InitError(4, "scratch volume is not mounted")
        if can_chown:
            os.chown(path, uid, gid)
        os.chmod(path, 0o750)


def run(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    payload = Path(args.payload)
    manifest = load_payload_manifest(payload)
    roots = {"generation": Path(args.generation_dir), "photon": Path(args.photon_dir)}
    entries = manifest["files"]
    photon_entries = [e for e in entries if e["root"] == "photon"]
    for name, directory in roots.items():
        if name == "generation" or photon_entries:
            _require_empty(directory, name)
    for path in args.writable_dir:
        if not Path(path).is_dir():
            raise InitError(4, f"scratch volume {path} is not mounted")

    total = 0
    for entry in entries:
        copy_verified(
            payload / entry["src"],
            roots[entry["root"]] / entry["dst"],
            entry,
        )
        total += entry["bytes"]
    copy_seconds = time.monotonic() - started

    generation = roots["generation"]
    try:
        copied_manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InitError(5, "copied manifest.json is unreadable") from exc
    if copied_manifest.get("generationId") != manifest["generationId"]:
        raise InitError(5, "copied manifest differs from the payload generation ID")
    check_motis_listener(generation / "motis")
    if photon_entries:
        check_photon_attestation(generation, photon_entries)
    elif copied_manifest.get("addressSearch") is not None:
        raise InitError(5, "address generation requires its Photon data payload")

    apply_permissions(
        generation,
        roots["photon"] if photon_entries else None,
        [Path(p) for p in args.writable_dir],
        args.uid,
        args.gid,
    )
    summary = {
        "generationId": manifest["generationId"],
        "files": len(entries),
        "bytes": total,
        "photonFiles": len(photon_entries),
        "copySeconds": round(copy_seconds, 2),
        "totalSeconds": round(time.monotonic() - started, 2),
        "freeBytesAfter": shutil.disk_usage(generation).free,
    }
    log("init_complete", **summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", default="/payload")
    parser.add_argument("--generation-dir", default="/generation")
    parser.add_argument("--photon-dir", default="/photon_data")
    parser.add_argument("--writable-dir", action="append", default=[])
    parser.add_argument("--uid", type=int, default=10001)
    parser.add_argument("--gid", type=int, default=10001)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except InitError as exc:
        log("init_failed", code=exc.code, reason=str(exc))
        return exc.code
    except OSError as exc:
        log("init_failed", code=1, reason=type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
