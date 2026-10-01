"""Conservative generation-retention planning. This module never deletes files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from opentransit.build.generations import verify_artifacts
from opentransit.core.generation import instant


@dataclass(frozen=True)
class RetentionPlan:
    candidates: tuple[dict, ...]
    retained: tuple[dict, ...]
    dry_run: bool = True

    def as_dict(self) -> dict:
        return {
            "dryRun": self.dry_run,
            "deletionPerformed": False,
            "candidates": list(self.candidates),
            "retained": list(self.retained),
        }


def plan_prune(
    generations_root: Path,
    active_generation_id: str | None,
    previous_generation_id: str | None,
    evidence_pinned_ids: set[str] | tuple[str, ...] = (),
    draining_generation_ids: set[str] | tuple[str, ...] = (),
) -> RetentionPlan:
    """List only verified generations older than the protected previous generation."""
    root = Path(generations_root).resolve()
    pinned = set(evidence_pinned_ids)
    draining = set(draining_generation_ids)
    records: list[tuple[str, Path, dict, datetime]] = []
    ids: dict[str, list[tuple[Path, dict, datetime]]] = {}
    retained: list[dict] = []
    for directory in sorted(root.iterdir()):
        if directory.is_symlink() or getattr(directory, "is_junction", lambda: False)():
            retained.append(
                {
                    "path": str(directory),
                    "generationId": None,
                    "reason": "symlink or junction is retained without traversal",
                }
            )
            continue
        if not directory.is_dir():
            continue
        try:
            directory.resolve().relative_to(root)
        except ValueError:
            retained.append(
                {
                    "path": str(directory),
                    "generationId": None,
                    "reason": "resolved path escapes generations root",
                }
            )
            continue
        manifest_path = directory / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            generation_id = manifest["generationId"]
            if not isinstance(generation_id, str) or not generation_id:
                raise ValueError("missing generation identity")
            built_at = instant(manifest["builtAt"])
            if manifest.get("state") != "ready":
                raise ValueError("generation is not ready")
            verify_artifacts(directory)
            record = (directory, manifest, built_at)
            records.append((generation_id, *record))
            ids.setdefault(generation_id, []).append(record)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            retained.append(
                {"path": str(directory), "generationId": None, "reason": f"unverified: {exc}"}
            )

    duplicate_ids = {generation_id for generation_id, matches in ids.items() if len(matches) > 1}
    for generation_id in duplicate_ids:
        for directory, _, _ in ids[generation_id]:
            retained.append(
                {
                    "path": str(directory),
                    "generationId": generation_id,
                    "reason": "duplicate generation identity; retained due to collision",
                }
            )
    manifests = {
        generation_id: (directory, manifest, built_at)
        for generation_id, directory, manifest, built_at in records
        if generation_id not in duplicate_ids
    }
    active_unknown = active_generation_id is not None and active_generation_id not in manifests
    previous = manifests.get(previous_generation_id) if previous_generation_id else None
    previous_unknown = previous_generation_id is not None and previous is None
    boundary = previous[2] if previous else None

    candidates = []
    for generation_id, (directory, manifest, built_at) in manifests.items():
        if generation_id == active_generation_id:
            reason = "active generation"
        elif generation_id == previous_generation_id:
            reason = "previous generation"
        elif generation_id in pinned:
            reason = "evidence-pinned"
        elif generation_id in draining:
            reason = "draining"
        elif active_unknown:
            reason = "active generation identity is unavailable"
        elif previous_unknown:
            reason = "previous generation boundary is unavailable"
        elif boundary is None:
            reason = "previous generation boundary is unavailable"
        elif built_at >= boundary:
            reason = "not proven older than previous generation"
        else:
            candidates.append(
                {
                    "path": str(directory),
                    "generationId": generation_id,
                    "builtAt": manifest["builtAt"],
                    "reason": "verified, older than previous, and unpinned",
                }
            )
            continue
        retained.append({"path": str(directory), "generationId": generation_id, "reason": reason})
    return RetentionPlan(tuple(candidates), tuple(retained))
