"""Immutable generation bindings and Linux atomic current-pointer operations."""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from opentransit.core.artifacts import verify_artifacts
from opentransit.core.generation import Generation

_TOKEN = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
_LOCAL_POINTER_LOCKS: dict[str, threading.RLock] = {}
_LOCAL_POINTER_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class GenerationBinding:
    generation_dir: Path
    engine_origin: str
    probe_path: Path | None
    source_check_path: Path | None
    activation_token: str
    generation_id: str
    # "rollback" re-serves a previously served generation and may be aging or stale (still
    # serviceable); a new candidate ("activate") must have current source freshness.
    purpose: str = "activate"
    # Optional per-generation Photon query/admin origins. Address composites built separately
    # carry different sealed indexes, so blue/green activation needs one Photon per binding;
    # when absent the worker uses its fixed OPENTRANSIT_PHOTON_* origins.
    photon_origin: str | None = None
    photon_admin_origin: str | None = None

    def as_dict(self) -> dict:
        data = {
            "generationDir": str(self.generation_dir),
            "engineOrigin": self.engine_origin,
            "probePath": str(self.probe_path) if self.probe_path else None,
            "sourceCheckPath": str(self.source_check_path) if self.source_check_path else None,
            "activationToken": self.activation_token,
            "generationId": self.generation_id,
        }
        if self.purpose != "activate":
            data["purpose"] = self.purpose
        if self.photon_origin is not None:
            data["photonOrigin"] = self.photon_origin
            data["photonAdminOrigin"] = self.photon_admin_origin
        return data


def _origin(value: object, label: str = "engineOrigin") -> str:
    if not isinstance(value, str):
        raise ValueError(f"Binding {label} must be an HTTP loopback origin")
    parsed = urlsplit(value)
    if parsed.scheme != "http" or not parsed.hostname or parsed.path not in {"", "/"}:
        raise ValueError(f"Binding {label} must be an HTTP loopback origin")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(f"Binding {label} must be loopback")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"Binding {label} has an invalid port") from exc
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"Binding {label} must contain only an origin")
    if port is None:
        raise ValueError(f"Binding {label} must include an explicit port")
    return value.rstrip("/")


def _photon_origins(data: dict) -> tuple[str | None, str | None]:
    query, admin = data.get("photonOrigin"), data.get("photonAdminOrigin")
    if (query is None) != (admin is None):
        raise ValueError("Binding photonOrigin and photonAdminOrigin must be set together")
    if query is None:
        return None, None
    return _origin(query, "photonOrigin"), _origin(admin, "photonAdminOrigin")


def _safe_path(value: object, label: str, required: bool = False) -> Path | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"Binding {label} must be an absolute path")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"Binding {label} must be absolute")
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise ValueError(f"Binding {label} may not be a symlink or junction")
    return path.resolve(strict=True)


def _purpose(data: dict) -> str:
    purpose = data.get("purpose", "activate")
    if purpose not in {"activate", "rollback"}:
        raise ValueError("Binding purpose must be activate or rollback")
    return purpose


def validate_binding(
    data: dict, generations_root: Path | None = None, *, verify: bool = True
) -> GenerationBinding:
    """Validate a binding; ``verify=False`` skips hashing artifacts (cheap pre-checks only)."""
    if not isinstance(data, dict):
        raise ValueError("Binding must be a JSON object")
    token = data.get("activationToken")
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        raise ValueError("Binding activationToken is invalid")
    generation_dir = _safe_path(data.get("generationDir"), "generationDir", required=True)
    assert generation_dir is not None
    if generations_root is not None:
        root = Path(generations_root).resolve(strict=True)
        try:
            generation_dir.relative_to(root)
        except ValueError as exc:
            raise ValueError("Binding generationDir escapes generations root") from exc
    manifest_path = generation_dir / "manifest.json"
    if manifest_path.is_symlink() or getattr(manifest_path, "is_junction", lambda: False)():
        raise ValueError("Generation manifest may not be a symlink or junction")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generation = Generation.load(manifest_path)
    if data.get("generationId") != generation.id:
        raise ValueError("Binding generationId differs from its manifest")
    if verify:
        verify_artifacts(generation_dir, manifest)
    probe_path = _safe_path(data.get("probePath"), "probePath")
    source_check_path = _safe_path(data.get("sourceCheckPath"), "sourceCheckPath")
    for label, path in (("probePath", probe_path), ("sourceCheckPath", source_check_path)):
        if path is not None:
            try:
                path.relative_to(generation_dir)
            except ValueError as exc:
                raise ValueError(f"Binding {label} must stay inside its generation") from exc
    return GenerationBinding(
        generation_dir,
        _origin(data.get("engineOrigin")),
        probe_path,
        source_check_path,
        token,
        generation.id,
        _purpose(data),
        *_photon_origins(data),
    )


def read_binding(path: Path, generations_root: Path, *, verify: bool = True) -> GenerationBinding:
    pointer_or_file = Path(path)
    if not pointer_or_file.exists():
        raise FileNotFoundError(pointer_or_file)
    resolved = pointer_or_file.resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_file():
        raise ValueError("Binding must resolve to a regular immutable file")
    root = Path(generations_root).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Binding file escapes generations root") from exc
    return validate_binding(json.loads(resolved.read_text(encoding="utf-8")), root, verify=verify)


def read_binding_metadata(path: Path, generations_root: Path) -> dict | None:
    """Read cheap immutable pointer metadata without rehashing generation artifacts."""
    pointer = Path(path)
    if not pointer.exists():
        return None
    root = Path(generations_root).resolve(strict=True)
    resolved = pointer.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("Binding must resolve to a regular immutable file")
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Binding file escapes generations root") from exc
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Binding must be a JSON object")
    token = data.get("activationToken")
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        raise ValueError("Binding activationToken is invalid")
    generation_dir_value = data.get("generationDir")
    if not isinstance(generation_dir_value, str) or not generation_dir_value:
        raise ValueError("Binding generationDir must be an absolute path")
    generation_dir = Path(generation_dir_value)
    if not generation_dir.is_absolute():
        raise ValueError("Binding generationDir must be absolute")
    generation_dir_resolved = generation_dir.resolve(strict=True)
    try:
        generation_dir_resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Binding generationDir escapes generations root") from exc
    if not isinstance(data.get("generationId"), str) or not data["generationId"]:
        raise ValueError("Binding generationId is invalid")
    return data


def write_binding(
    path: Path, data: dict, generations_root: Path | None = None
) -> GenerationBinding:
    """Create and fsync a complete binding file once; never replace existing evidence."""
    binding = validate_binding(data, generations_root)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(binding.as_dict(), sort_keys=True, indent=2).encode("utf-8") + b"\n"
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
        _fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return binding


@contextmanager
def _pointer_lock(root: Path):
    if os.name != "posix":
        raise OSError("Atomic generation pointers require Linux/POSIX")
    import fcntl

    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".activation.lock"
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def activation_lock(root: Path):
    """Shared short commit lock for operators and in-process activation managers."""
    if os.name == "posix":
        return _pointer_lock(root)
    lock_key = str(Path(root).resolve(strict=True))
    with _LOCAL_POINTER_LOCKS_GUARD:
        lock = _LOCAL_POINTER_LOCKS.setdefault(lock_key, threading.RLock())

    @contextmanager
    def local_lock():
        with lock:
            yield

    return local_lock()


def new_operation_token() -> str:
    """Create a unique activation/rollback operation token, separate from generation ID."""
    return uuid.uuid4().hex


def activation_ack_filename(operation_token: str, worker_incarnation_id: str) -> str:
    if not _TOKEN.fullmatch(operation_token) or not _TOKEN.fullmatch(worker_incarnation_id):
        raise ValueError("ACK operation and worker-incarnation tokens must be safe")
    return f"{operation_token}.{worker_incarnation_id}.json"


def activation_failure_ack_filename(operation_token: str, worker_incarnation_id: str) -> str:
    return (
        activation_ack_filename(operation_token, worker_incarnation_id).removesuffix(".json")
        + ".failed.json"
    )


def retirement_ack_filename(operation_token: str, worker_incarnation_id: str) -> str:
    return "retired-" + activation_ack_filename(operation_token, worker_incarnation_id)


def _fsync_directory(path: Path) -> None:
    if os.name == "posix":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def current_target(current_path: Path) -> str | None:
    current_path = Path(current_path)
    if not current_path.is_symlink():
        return None
    return os.readlink(current_path)


def _swap_symlink(root: Path, current_path: Path, target: str) -> str | None:
    current_path = Path(current_path)
    root = Path(root).resolve(strict=True)
    if current_path.parent.resolve(strict=True) != root:
        raise ValueError("Current pointer must be directly inside its generations root")
    candidate = (current_path.parent / target).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Current pointer target escapes generations root") from exc
    old_target = current_target(current_path)
    if current_path.exists() and old_target is None:
        raise ValueError("Current pointer path exists and is not a symlink")
    temporary = root / f".current-{uuid.uuid4().hex}"
    os.symlink(target, temporary, target_is_directory=False)
    try:
        os.replace(temporary, current_path)
        _fsync_directory(root)
    finally:
        temporary.unlink(missing_ok=True)
    return old_target


def activate_current(root: Path, current_path: Path, binding_path: Path) -> str | None:
    """Atomically select one immutable binding file; return the prior symlink target."""
    root = Path(root).resolve(strict=True)
    binding_path = Path(binding_path)
    if binding_path.is_symlink() or getattr(binding_path, "is_junction", lambda: False)():
        raise ValueError("Immutable binding file may not be a symlink or junction")
    binding = read_binding(binding_path, root)
    try:
        relative = binding_path.resolve(strict=True).relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Binding file escapes generations root") from exc
    with _pointer_lock(root):
        current = read_binding_metadata(current_path, root)
        candidate = read_binding_metadata(binding_path, root)
        if candidate is None:
            raise FileNotFoundError(binding_path)
        if candidate != binding.as_dict():
            raise ValueError("Binding file changed after validation")
        if current is not None and current["activationToken"] == candidate["activationToken"]:
            raise ValueError("Each activation requires a fresh operation token")
        return _swap_symlink(root, current_path, relative)


def restore_current_if_current(
    root: Path,
    current_path: Path,
    expected_current_token: str,
    rollback_binding_path: Path,
) -> bool:
    """CAS-select a newly validated rollback binding only while the expected op is current."""
    root = Path(root).resolve(strict=True)
    rollback_binding_path = Path(rollback_binding_path)
    rollback = read_binding(rollback_binding_path, root)
    try:
        relative = rollback_binding_path.resolve(strict=True).relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Rollback binding file escapes generations root") from exc
    with _pointer_lock(root):
        current = read_binding_metadata(current_path, root)
        if current is None or current["activationToken"] != expected_current_token:
            return False
        if rollback.activation_token == expected_current_token:
            raise ValueError("Rollback requires a fresh operation token")
        if read_binding_metadata(rollback_binding_path, root) != rollback.as_dict():
            raise ValueError("Rollback binding changed after validation")
        _swap_symlink(root, current_path, relative)
        return True


def restore_current(root: Path, current_path: Path, previous_target: str) -> None:
    """Reject token-reusing rollback; use restore_current_if_current with a fresh binding."""
    raise ValueError("Rollback requires a fresh validated binding and operation token")
