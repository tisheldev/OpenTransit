"""Stage one verified generation as the build context of the data-initialization image.

Host-side helper (DRAFT). Run it inside the API project environment so the same
``verify_artifacts`` code that guards serving also guards packaging:

    uv run --project services/api python deploy/aws/tools/stage_bundle.py \\
        --generation <generation dir> --probe-queries <probe corpus> \\
        [--photon-data <sealed Photon checkpoint clone>] --output <new staging dir>

The output directory must not exist. Large files are hard-linked when the filesystem allows
and copied otherwise; sources are never modified. Layout (one Docker layer per top-level
directory, so layers pull and unpack in parallel):

    payload/reference/reference.sqlite
    payload/graph/**              MOTIS graph tree (becomes /generation/motis)
    payload/photon/**             sealed Photon data tree (becomes /photon_data), if addresses
    payload/small/*               manifest, config, address catalog, attestation, probe corpus
    payload-manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

from opentransit.core.artifacts import verify_artifacts

SCHEMA_VERSION = 1
SMALL_FILES = (
    "manifest.json",
    "config.yml",
    "schedule-component-manifest.json",
    "address-catalog.sqlite",
    "photon-import-attestation.json",
)
SERVING_PORT = 8080


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_entries(root: Path) -> list[dict]:
    """Every file below root, including zero-byte files, sorted like the sealed checkpoint."""
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"{root} contains a symlink: {path.name}")
        if path.is_file():
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return entries


def tree_digest(entries: list[dict]) -> str:
    digest = hashlib.sha256()
    for item in entries:
        digest.update(f"{item['path']}\0{item['bytes']}\0{item['sha256']}\n".encode())
    return digest.hexdigest()


def place(source: Path, target: Path, *, force_copy: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not force_copy:
        try:
            os.link(source, target)
            return
        except OSError:
            pass
    shutil.copy2(source, target)


def check_serving_port(graph: Path) -> None:
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
            raise ValueError(
                f"graph config.yml listens on {match.group(1)}; rebuild without --local-engine-slot"
            )


def stage(
    generation: Path,
    output: Path,
    *,
    photon_data: Path | None = None,
    probe_queries: Path | None = None,
    force_copy: bool = False,
) -> dict:
    generation = Path(generation).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("state") != "ready":
        raise ValueError("Only a ready generation can be packaged")
    verify_artifacts(generation, manifest)  # includes the address composite when present
    check_serving_port(generation / "motis")

    addresses = manifest.get("addressSearch") is not None
    if addresses and photon_data is None:
        raise ValueError("An address generation needs its sealed Photon data tree")
    if not addresses and photon_data is not None:
        raise ValueError("Photon data was supplied for a generation without address search")

    photon_entries: list[dict] = []
    if addresses:
        photon_root = Path(photon_data).resolve(strict=True)
        photon_entries = tree_entries(photon_root)
        attestation = json.loads(
            (generation / "photon-import-attestation.json").read_text(encoding="utf-8")
        )
        sealed = attestation["checkpoint"]
        if (
            tree_digest(photon_entries) != sealed["treeSha256"]
            or len(photon_entries) != sealed["files"]
            or sum(e["bytes"] for e in photon_entries) != sealed["bytes"]
        ):
            raise ValueError(
                "Photon data tree differs from the sealed attestation checkpoint; use a clone "
                "of the quiescent checkpoint, never a volume that has been served"
            )

    files: list[dict] = []
    payload = output / "payload"

    def add(source: Path, src: str, root: str, dst: str) -> None:
        place(source, payload / src, force_copy=force_copy)
        files.append(
            {
                "src": src,
                "root": root,
                "dst": dst,
                "bytes": source.stat().st_size,
                "sha256": sha256_file(source),
            }
        )

    try:
        add(
            generation / "reference.sqlite",
            "reference/reference.sqlite",
            "generation",
            "reference.sqlite",
        )
        for item in manifest["artifacts"]["motis"]["files"]:
            add(
                generation / "motis" / item["path"],
                f"graph/{item['path']}",
                "generation",
                f"motis/{item['path']}",
            )
        for name in SMALL_FILES:
            if (generation / name).is_file():
                add(generation / name, f"small/{name}", "generation", name)
        if probe_queries is not None:
            add(
                Path(probe_queries).resolve(strict=True),
                "small/probe-queries.json",
                "generation",
                "probe-queries.json",
            )
        for item in photon_entries:
            add(photon_root / item["path"], f"photon/{item['path']}", "photon", item["path"])
        keep = payload / "photon" / ".keep"
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.touch()
        (payload / "small").mkdir(parents=True, exist_ok=True)
        # Entries carry the manifest's own hashes; fail loudly if a source drifted while staging.
        for item, expected in zip(
            manifest["artifacts"]["motis"]["files"],
            [f for f in files if f["src"].startswith("graph/")],
            strict=True,
        ):
            if item["sha256"] != expected["sha256"]:
                raise ValueError(f"Graph file changed while staging: {item['path']}")
        # The graph digest skips zero-byte files, but MOTIS still opens them (for example
        # routed_shapes_*.bin when no shapes were routed), so stage them as verified-empty.
        listed = {item["path"] for item in manifest["artifacts"]["motis"]["files"]}
        graph_dir = generation / "motis"
        for path in sorted(graph_dir.rglob("*")):
            relative = path.relative_to(graph_dir).as_posix()
            if path.is_file() and relative not in listed:
                if path.stat().st_size:
                    raise ValueError(f"Graph file outside the manifest: {relative}")
                add(path, f"graph/{relative}", "generation", f"motis/{relative}")
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise

    payload_manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "generationId": manifest["generationId"],
        "addressSearch": addresses,
        "probeQueriesIncluded": probe_queries is not None,
        "files": files,
    }
    (output / "payload-manifest.json").write_text(
        json.dumps(payload_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--photon-data", type=Path)
    parser.add_argument("--probe-queries", type=Path)
    parser.add_argument("--copy", action="store_true", help="copy instead of hard-linking")
    args = parser.parse_args(argv)
    try:
        result = stage(
            args.generation,
            args.output,
            photon_data=args.photon_data,
            probe_queries=args.probe_queries,
            force_copy=args.copy,
        )
    except (OSError, ValueError, KeyError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "generationId": result["generationId"],
                "files": len(result["files"]),
                "bytes": sum(f["bytes"] for f in result["files"]),
                "addressSearch": result["addressSearch"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
