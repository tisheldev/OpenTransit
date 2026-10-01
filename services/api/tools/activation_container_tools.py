"""In-container helpers for the activation Compose harness (run with `docker exec`).

source-check  reconstruct a paired-check record from a manifest's own recorded provenance
              (no new upstream check is made or claimed)
bind          write an immutable binding for one generation and engine origin (optionally
              with that generation's Photon query/admin origins)
synth-old     create a tiny, labelled synthetic ready generation older than the real ones
corrupt       create a candidate whose artifacts differ from its manifest
listing       list a managed root without following mounts into their contents
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from opentransit.build.activation import write_binding


def _write_new(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def source_check(generation: Path, out: Path) -> None:
    manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
    inputs = manifest["inputs"]
    sources = {}
    for key, name in (
        ("gtfs", "israel-public-transportation.zip"),
        ("trip_id_to_date", "TripIdToDate.zip"),
    ):
        sources[key] = {
            "status": "new",
            "sha256": inputs[name]["sha256"],
            "checkedAt": inputs[name]["acquiredAt"],
        }
    _write_new(
        out,
        {
            "pairedValidation": "passed",
            "validation": {"valid": True},
            "validatedAt": manifest["validatedAt"],
            "sources": sources,
            "provenance": "reconstructed from the generation manifest's recorded acquisition "
            "and validation times; no new upstream check was made (ot-t2 harness)",
        },
    )


def bind(
    root: Path,
    generation: Path,
    origin: str,
    probe: Path,
    check: Path,
    token: str,
    photon: tuple[str, str] | None = None,
) -> None:
    manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
    data = {
        "generationDir": str(generation.resolve()),
        "engineOrigin": origin,
        "probePath": str(probe.resolve()),
        "sourceCheckPath": str(check.resolve()),
        "activationToken": token,
        "generationId": manifest["generationId"],
    }
    if photon is not None:
        data["photonOrigin"], data["photonAdminOrigin"] = photon
    write_binding(root / f"binding-{token}.json", data, root)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synth_old(root: Path, name: str) -> None:
    directory = root / name
    (directory / "motis").mkdir(parents=True)
    graph, config, reference = b"synthetic-graph", b"synthetic: true\n", b"synthetic-reference"
    (directory / "motis" / "graph.bin").write_bytes(graph)
    (directory / "config.yml").write_bytes(config)
    (directory / "reference.sqlite").write_bytes(reference)
    tree = f"graph.bin\0{len(graph)}\0{_digest(graph)}\n".encode()
    manifest = {
        "schemaVersion": 1,
        "generationId": f"synthetic-{name}",
        "state": "ready",
        "mode": "fixture",
        "builtAt": "2026-09-01T00:00:00+00:00",
        "engineDigest": "sha256:" + "a" * 64,
        "artifacts": {
            "motis": {
                "path": "motis",
                "sha256": _digest(tree),
                "files": [{"path": "graph.bin", "bytes": len(graph), "sha256": _digest(graph)}],
            },
            "config": {"path": "config.yml", "sha256": _digest(config)},
            "reference": {"path": "reference.sqlite", "sha256": _digest(reference)},
        },
        "note": "tiny synthetic generation created by the ot-t2 harness for the prune check",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def corrupt(root: Path, name: str, source: Path) -> None:
    directory = root / name
    (directory / "motis").mkdir(parents=True)
    shutil.copyfile(source / "manifest.json", directory / "manifest.json")
    shutil.copyfile(source / "config.yml", directory / "config.yml")
    (directory / "reference.sqlite").write_bytes(b"truncated reference")


def listing(root: Path) -> list[dict]:
    entries = []
    for current, dirs, files in os.walk(root, followlinks=False):
        depth = Path(current).relative_to(root).parts
        for name in sorted(dirs + files):
            path = Path(current) / name
            link = path.is_symlink()
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "kind": "symlink" if link else "dir" if path.is_dir() else "file",
                    "bytes": None if link or path.is_dir() else path.stat().st_size,
                }
            )
        # Mounted artifact trees are identified by name only; their contents are hashed by
        # the product commands and are never listed or traversed here.
        dirs[:] = [d for d in dirs if not (len(depth) >= 1 and d == "motis")]
    return sorted(entries, key=lambda item: item["path"])


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("source-check", "bind", "synth-old", "corrupt", "listing"):
        sub = commands.add_parser(name)
        sub.add_argument("--root", type=Path, default=Path("/managed"))
        if name == "source-check":
            sub.add_argument("--generation", type=Path, required=True)
            sub.add_argument("--out", type=Path, required=True)
        if name == "bind":
            sub.add_argument("--generation", type=Path, required=True)
            sub.add_argument("--origin", required=True)
            sub.add_argument("--probe", type=Path, required=True)
            sub.add_argument("--source-check", type=Path, required=True)
            sub.add_argument("--token", required=True)
            sub.add_argument("--photon-origin")
            sub.add_argument("--photon-admin-origin")
        if name in {"synth-old", "corrupt"}:
            sub.add_argument("--name", required=True)
        if name == "corrupt":
            sub.add_argument("--source", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "source-check":
        source_check(args.generation, args.out)
    elif args.command == "bind":
        photon = (
            (args.photon_origin, args.photon_admin_origin)
            if args.photon_origin or args.photon_admin_origin
            else None
        )
        bind(
            args.root,
            args.generation,
            args.origin,
            args.probe,
            args.source_check,
            args.token,
            photon,
        )
    elif args.command == "synth-old":
        synth_old(args.root, args.name)
    elif args.command == "corrupt":
        corrupt(args.root, args.name, args.source)
    else:
        print(json.dumps(listing(args.root)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
