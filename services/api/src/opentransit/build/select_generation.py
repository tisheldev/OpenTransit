"""Select a verified, probed generation as ``current`` (thin wrapper over local activation).

This adds no activation semantics. It writes one immutable binding file with a fresh operation
token (``write_binding``) and swaps the ``current`` pointer (``activate_current``), both from
``opentransit.build.activation``. Those functions verify every artifact hash, and the pointer
swap needs Linux/POSIX locking and symlinks. A running API worker adopts the new pointer through
its own reload path, which keeps the old snapshot for in-flight requests.
"""

from __future__ import annotations

import json
from pathlib import Path

from opentransit.build.activation import activate_current, new_operation_token, write_binding


def select_generation(
    generation_dir: Path,
    generations_root: Path,
    engine_origin: str,
    *,
    probe_path: Path | None = None,
    source_check_path: Path | None = None,
    current_name: str = "current",
    operation_token: str | None = None,
) -> dict:
    """Bind ``generation_dir`` to ``engine_origin`` and make it current; return what happened."""
    generation = Path(generation_dir).resolve(strict=True)
    root = Path(generations_root).resolve(strict=True)
    try:
        generation.relative_to(root)
    except ValueError as exc:
        raise ValueError("Generation must be inside the generations root") from exc
    manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("state") != "ready":
        raise ValueError("Only a ready generation can be selected")
    probe = Path(probe_path) if probe_path else generation / "probe.json"
    try:
        report = json.loads(probe.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            "A passed candidate probe is required (run `opentransit probe` first)"
        ) from exc
    if report.get("status") != "passed" or report.get("generationId") != manifest["generationId"]:
        raise ValueError("The probe did not pass for this generation")
    token = operation_token or new_operation_token()
    binding_path = root / "bindings" / f"{generation.name}-{token[:12]}.json"
    binding = write_binding(
        binding_path,
        {
            "generationDir": str(generation),
            "engineOrigin": engine_origin,
            "probePath": str(probe.resolve()),
            "sourceCheckPath": str(Path(source_check_path).resolve())
            if source_check_path
            else None,
            "activationToken": token,
            "generationId": manifest["generationId"],
        },
        root,
    )
    previous = activate_current(root, root / current_name, binding_path)
    return {
        "generationId": binding.generation_id,
        "binding": str(binding_path),
        "current": str(root / current_name),
        "previousTarget": previous,
        "engineOrigin": binding.engine_origin,
    }
