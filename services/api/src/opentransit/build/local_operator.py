"""Local operator actions: coverage-checked activation, rollback and retirement gating.

The operator never replaces serving state itself. It selects an immutable binding with the
atomic ``current`` pointer, signals the single local API worker, waits for that worker's
acknowledgement, and restores the pointer when the worker rejects the candidate. Stopping the
old engine is left to the caller, who must wait for :func:`await_retirement` first.
"""

from __future__ import annotations

import json
import os
import re
import signal
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from opentransit.build.activation import (
    GenerationBinding,
    activate_current,
    activation_ack_filename,
    activation_failure_ack_filename,
    current_target,
    new_operation_token,
    read_binding,
    read_binding_metadata,
    restore_current_if_current,
    retirement_ack_filename,
    write_binding,
)
from opentransit.core.generation import Generation
from opentransit.core.time import as_utc_instant
from opentransit.runtime import apply_source_check

DEADLINE_MULTIPLE = 10
_SAFE = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")


class ActivationRefused(ValueError):
    """The candidate was refused before the pointer was touched."""

    def __init__(self, reasons: list[str], detail: dict | None = None) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons
        self.detail = detail or {}


class ActivationFailed(RuntimeError):
    """The worker rejected or never acknowledged the candidate."""

    def __init__(self, message: str, detail: dict) -> None:
        super().__init__(message)
        self.detail = detail


def check_currency(binding, now: datetime) -> dict:
    """Re-check coverage and source freshness for a binding at ``now`` without the engine.

    A new candidate needs ``current`` freshness. A rollback binding re-serves a generation that
    was already serving, so ``aging`` and ``stale`` stay serviceable (and are labelled); only
    ``expired`` freshness or lapsed coverage is refused.
    """
    if now.utcoffset() is None:
        raise ValueError("Operator clock must have an explicit timezone")
    manifest_path = binding.generation_dir / "manifest.json"
    generation = Generation.load(manifest_path)
    if binding.source_check_path is None:
        raise ActivationRefused(["source_check_missing"])
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        generation = apply_source_check(generation, manifest, binding.source_check_path)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ActivationRefused([f"source_check_invalid:{type(exc).__name__}"]) from exc
    reasons = []
    instant = as_utc_instant(now)
    if instant < as_utc_instant(generation.coverage_from):
        reasons.append("coverage_not_started")
    elif instant >= as_utc_instant(generation.coverage_until):
        reasons.append("coverage_expired")
    freshness = generation.freshness(now)
    rollback = binding.purpose == "rollback"
    if not (generation.freshness_serviceable(now) if rollback else freshness == "current"):
        reasons.append(f"source_{freshness}")
    detail = {
        "generationId": generation.id,
        "checkedAt": instant.isoformat(),
        "coverage": {
            "from": generation.coverage_from.isoformat(),
            "until": generation.coverage_until.isoformat(),
        },
        "sourceCheckedAt": generation.source_checked_at.isoformat()
        if generation.source_checked_at
        else None,
        "freshness": freshness,
        "purpose": binding.purpose,
    }
    if reasons:
        raise ActivationRefused(reasons, detail)
    return detail


def read_worker_record(ack_dir: Path) -> dict:
    """Return the live worker's control record or fail without signalling anything."""
    from opentransit.api.lifecycle import _pid_is_same_process

    path = Path(ack_dir) / "workers" / "worker.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("No managed API worker record is available") from exc
    incarnation = record.get("workerIncarnationId")
    if (
        record.get("controlSignal") != "SIGUSR1"
        or not isinstance(incarnation, str)
        or not _SAFE.fullmatch(incarnation)
        or not _pid_is_same_process(record)
    ):
        raise RuntimeError("The recorded managed API worker is not live")
    return record


def signal_worker(record: dict) -> None:
    os.kill(record["pid"], signal.SIGUSR1)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    return data if isinstance(data, dict) else None


def _utc_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()


def _wait_for_ack(
    ack_dir: Path,
    token: str,
    incarnation: str,
    timeout: float,
    poll: float,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> tuple[str, dict, Path]:
    success = Path(ack_dir) / activation_ack_filename(token, incarnation)
    failure = Path(ack_dir) / activation_failure_ack_filename(token, incarnation)
    deadline = clock() + timeout
    while True:
        data = _read_json(success)
        if data is not None:
            return "acknowledged", data, success
        data = _read_json(failure)
        if data is not None:
            return "rejected", data, failure
        if clock() >= deadline:
            raise TimeoutError("No worker acknowledgement before the timeout")
        sleep(poll)


def reissue_binding(root: Path, binding_path: Path, purpose: str = "activate") -> Path:
    """Write a new binding for the same generation with a fresh operation token.

    ``write_binding`` verifies every artifact, so the source binding is only parsed here.
    """
    root = Path(root).resolve(strict=True)
    existing = read_binding(Path(binding_path), root, verify=False)
    data = existing.as_dict()
    data["activationToken"] = new_operation_token()
    if purpose == "rollback":
        data["purpose"] = "rollback"
    else:
        data.pop("purpose", None)
    path = root / f"binding-{data['activationToken']}.json"
    write_binding(path, data, root)
    return path


def activate(
    managed_root: Path,
    binding_path: Path,
    ack_dir: Path,
    *,
    now: datetime | None = None,
    timeout: float = 900.0,
    poll: float = 0.25,
    action: str = "activate",
    signaller: Callable[[dict], None] = signal_worker,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict:
    """Select ``binding_path``, signal the worker and wait; restore the pointer on rejection."""
    root = Path(managed_root).resolve(strict=True)
    current = root / "current"
    now = now or datetime.now(UTC)
    # Cheap refusal first; activate_current verifies every artifact before the pointer moves.
    candidate = read_binding(Path(binding_path), root, verify=False)
    currency = check_currency(candidate, now)
    worker = read_worker_record(ack_dir)
    previous = read_binding_metadata(current, root)
    previous_target = current_target(current)
    started = datetime.now(UTC)
    activate_current(root, current, Path(binding_path))
    report = {
        "action": action,
        "token": candidate.activation_token,
        "generationId": candidate.generation_id,
        "engineOrigin": candidate.engine_origin,
        "previousToken": previous["activationToken"] if previous else None,
        "previousGenerationId": previous["generationId"] if previous else None,
        "currency": currency,
        "workerIncarnationId": worker["workerIncarnationId"],
        "pointerSwappedAt": started.isoformat(),
    }
    signaller(worker)
    report["signalledAt"] = datetime.now(UTC).isoformat()
    try:
        status, data, path = _wait_for_ack(
            ack_dir,
            candidate.activation_token,
            worker["workerIncarnationId"],
            timeout,
            poll,
            sleep,
            clock,
        )
    except TimeoutError:
        status, data, path = "timeout", {}, None
    if status == "acknowledged":
        report.update(
            status="acknowledged",
            ack=data,
            ackFileMtimeUtc=_utc_mtime(path),
            # Retirement is acknowledged under the token the worker actually served, which
            # differs from previousToken after a failed activation restored the pointer.
            retiredOperationToken=data.get("replacedOperationToken"),
        )
        return report
    report.update(status=status, failureAck=data or None)
    if previous is None:
        report["pointerRestored"] = False
        raise ActivationFailed("Candidate was not acknowledged and no prior pointer exists", report)
    if previous_target is None:
        report["pointerRestored"] = False
        raise ActivationFailed("Prior pointer was not a symlink; cannot restore it", report)
    restore_path = reissue_binding(root, root / previous_target, "rollback")
    restored = restore_current_if_current(root, current, candidate.activation_token, restore_path)
    pointer = read_binding_metadata(current, root)
    report.update(
        pointerRestored=restored,
        restoreToken=json.loads(restore_path.read_text(encoding="utf-8"))["activationToken"],
        pointerToken=pointer["activationToken"] if pointer else None,
        pointerGenerationId=pointer["generationId"] if pointer else None,
    )
    raise ActivationFailed(f"Worker did not accept the candidate ({status})", report)


def rollback(
    managed_root: Path,
    to_binding_path: Path,
    ack_dir: Path,
    *,
    check_only: bool = False,
    **options,
) -> dict:
    """Re-check coverage/freshness, then activate a fresh-token rollback binding.

    Serviceable (current, aging or stale) generations roll back; expired ones are refused
    before the pointer is touched. ``check_only`` reports eligibility without changing anything.
    """
    root = Path(managed_root).resolve(strict=True)
    existing = read_binding(Path(to_binding_path), root, verify=False)
    probe = GenerationBinding(**{**existing.__dict__, "purpose": "rollback"})
    currency = check_currency(probe, options.get("now") or datetime.now(UTC))
    if check_only:
        return {"status": "eligible", "action": "rollback", "currency": currency}
    fresh = reissue_binding(root, to_binding_path, "rollback")
    return activate(root, fresh, ack_dir, action="rollback", **options)


def await_retirement(
    ack_dir: Path,
    *,
    old_token: str,
    new_token: str,
    incarnation: str,
    deadline_seconds: float,
    timeout: float = 120.0,
    poll: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict:
    """Wait for the worker to confirm it retired the old snapshot; verify the grace period.

    Only after this returns may the caller stop the old engine.
    """
    ack_dir = Path(ack_dir)
    path = ack_dir / retirement_ack_filename(old_token, incarnation)
    activation = ack_dir / activation_ack_filename(new_token, incarnation)
    deadline = clock() + timeout
    while True:
        data = _read_json(path)
        if data is not None:
            break
        if clock() >= deadline:
            raise TimeoutError("No retirement acknowledgement before the timeout")
        sleep(poll)
    required = DEADLINE_MULTIPLE * deadline_seconds
    if not isinstance(data.get("graceSeconds"), int | float) or data["graceSeconds"] < required:
        raise ActivationFailed(
            "Retirement grace is shorter than ten request deadlines",
            {"graceSeconds": data.get("graceSeconds"), "requiredSeconds": required},
        )
    acknowledged_at = datetime.fromtimestamp(activation.stat().st_mtime, UTC)
    retired_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    elapsed = (retired_at - acknowledged_at).total_seconds()
    if elapsed < required:
        raise ActivationFailed(
            "Retirement acknowledgement predates ten request deadlines",
            {"elapsedSeconds": elapsed, "requiredSeconds": required},
        )
    return {
        "status": "retired",
        "oldToken": old_token,
        "newToken": new_token,
        "graceSeconds": data["graceSeconds"],
        "requiredSeconds": required,
        "activationAckAtUtc": acknowledged_at.isoformat(),
        "retiredAtUtc": retired_at.isoformat(),
        "ackToRetirementSeconds": elapsed,
        "retirement": data,
    }
