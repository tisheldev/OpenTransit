"""In-process blue/green snapshot publication with explicit engine ownership."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opentransit.build.activation import (
    GenerationBinding,
    activation_ack_filename,
    activation_failure_ack_filename,
    activation_lock,
    current_target,
    read_binding,
    read_binding_metadata,
    retirement_ack_filename,
)

_TOKEN = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")


@dataclass(frozen=True)
class SnapshotLease:
    """A complete snapshot and the clients/resources kept alive for its requests."""

    snapshot: Any
    owned_client: Any
    additional_clients: tuple[Any, ...] = ()

    @property
    def owned_clients(self) -> tuple[Any, ...]:
        clients = (self.owned_client, *self.additional_clients)
        return tuple({id(client): client for client in clients}.values())


class ActivationError(RuntimeError):
    """Candidate activation failed without replacing the serving snapshot."""


class SnapshotManager:
    def __init__(
        self,
        current_binding_path: Path,
        snapshot_factory: Callable[[GenerationBinding], Any],
        ack_dir: Path,
        deadline_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        initial_lease: SnapshotLease | None = None,
        *,
        managed_root: Path,
        worker_id: str = "api-worker",
    ) -> None:
        if deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be positive")
        if not worker_id or len(worker_id) > 128:
            raise ValueError("worker_id must contain 1 to 128 characters")
        self.current_binding_path = Path(current_binding_path)
        self.managed_root = Path(managed_root).resolve(strict=True)
        try:
            self.current_binding_path.parent.resolve(strict=True).relative_to(self.managed_root)
        except ValueError as exc:
            raise ValueError("Current binding pointer must be inside managed root") from exc
        if self.current_binding_path.parent.resolve(strict=True) != self.managed_root:
            raise ValueError("Current binding pointer must be directly inside managed root")
        self.snapshot_factory = snapshot_factory
        self.ack_dir = Path(ack_dir)
        self.deadline_seconds = float(deadline_seconds)
        self.clock = clock
        self.worker_id = worker_id
        self.worker_incarnation_id = uuid.uuid4().hex
        self._active: tuple[SnapshotLease, GenerationBinding] | None = None
        self._reload_lock = asyncio.Lock()
        self._shutdown_task: asyncio.Task | None = None
        self._retire_tasks: set[asyncio.Task] = set()
        self._owned_leases: dict[int, SnapshotLease] = {}
        self._lease_close_tasks: dict[int, asyncio.Task] = {}
        self._closed = False
        self._published_target = current_target(self.current_binding_path)
        if initial_lease is not None:
            binding = read_binding(self.current_binding_path, self.managed_root)
            self._validate_lease(initial_lease, binding)
            self._active = (initial_lease, binding)
            self._owned_leases[id(initial_lease)] = initial_lease

    @property
    def current_snapshot(self) -> Any | None:
        """The immutable snapshot a request should capture before its first await."""
        return self._active[0].snapshot if self._active else None

    @property
    def current_binding(self) -> GenerationBinding | None:
        return self._active[1] if self._active else None

    @staticmethod
    def _validate_lease(lease: SnapshotLease, binding: GenerationBinding) -> None:
        if not isinstance(lease, SnapshotLease):
            raise TypeError("snapshot_factory must return SnapshotLease")
        generation = getattr(lease.snapshot, "generation", None)
        generation_id = getattr(generation, "id", None)
        if generation_id != binding.generation_id:
            raise ValueError("Factory snapshot generation differs from the binding")
        motis = getattr(lease.snapshot, "motis", None)
        client = getattr(motis, "client", None)
        origin = getattr(client, "base_url", None)
        if origin is not None and str(origin).rstrip("/") != binding.engine_origin:
            raise ValueError("Factory engine origin differs from the binding")
        owned_clients = lease.owned_clients
        if client is not None and all(client is not owned for owned in owned_clients):
            raise ValueError("SnapshotLease must own the snapshot's engine client")
        provider = getattr(lease.snapshot, "address_provider", None)
        address_client = getattr(provider, "client", None)
        if address_client is not None and all(
            address_client is not owned for owned in owned_clients
        ):
            raise ValueError("SnapshotLease must own the snapshot's address provider client")
        if any(not callable(getattr(owned, "aclose", None)) for owned in owned_clients):
            raise TypeError("SnapshotLease clients must provide async aclose()")

    async def _create_lease(self, binding: GenerationBinding) -> SnapshotLease:
        """Factories must close resources they allocate if cancelled before returning a lease."""
        result = self.snapshot_factory(binding)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, SnapshotLease):
            raise TypeError("snapshot_factory must return SnapshotLease")
        self._owned_leases[id(result)] = result
        try:
            self._validate_lease(result, binding)
        except BaseException:
            await self._close_lease(result)
            raise
        return result

    async def initialize(self) -> Any:
        """Build and publish the current binding if no bootstrap lease was supplied."""
        if self._closed:
            raise RuntimeError("Snapshot manager is closed")
        if self._active is not None:
            return self._active[0].snapshot
        binding = await asyncio.to_thread(
            read_binding, self.current_binding_path, self.managed_root
        )
        return await self.reload_current(binding.activation_token)

    async def reload_current(self, token: str) -> Any:
        """Construct, recheck, publish and ACK the binding selected by ``current``."""
        if self._closed:
            raise RuntimeError("Snapshot manager is closed")
        if not isinstance(token, str) or not _TOKEN.fullmatch(token):
            raise ValueError("Activation token is invalid")
        async with self._reload_lock:
            if self._closed:
                raise RuntimeError("Snapshot manager is closed")
            try:
                binding = await asyncio.to_thread(
                    read_binding, self.current_binding_path, self.managed_root
                )
            except Exception:
                raise
            if binding.activation_token != token:
                raise ActivationError("Requested activation token is no longer current")
            if self._active and self._active[1].activation_token == token:
                if self._active[1].as_dict() != binding.as_dict():
                    raise ActivationError("Activation token was reused for a different binding")
                return self._active[0].snapshot

            try:
                candidate = await self._create_lease(binding)
            except BaseException:
                self._write_failure_ack(binding, "factory_rejected")
                raise
            try:
                with activation_lock(self.managed_root):
                    current = read_binding_metadata(self.current_binding_path, self.managed_root)
                    if current is None or current.get("activationToken") != token:
                        raise ActivationError(
                            "Current binding changed while the candidate was loading"
                        )
                    if self._closed:
                        raise RuntimeError("Snapshot manager is closed")
                    if current != binding.as_dict():
                        raise ActivationError("Activation token was reused for a different binding")
                    old_active = self._active
                    self._active = (candidate, binding)
                    try:
                        self._write_ack(
                            self._ack_filename(token),
                            {
                                "activationToken": token,
                                "operationToken": token,
                                "generationId": binding.generation_id,
                                "engineOrigin": binding.engine_origin,
                                "workerId": self.worker_id,
                                "workerIncarnationId": self.worker_incarnation_id,
                                "ackWriteStartedMonotonic": self.clock(),
                            },
                        )
                    except BaseException:
                        self._active = old_active
                        raise
                    ack_at = self.clock()
                    self._published_target = current_target(self.current_binding_path)
            except BaseException:
                if self._active is None or self._active[0] is not candidate:
                    await self._close_lease(candidate)
                self._write_failure_ack(binding, "publication_rejected")
                raise

            if old_active is not None:
                task = asyncio.create_task(self._retire_after_ack(*old_active, ack_at))
                self._retire_tasks.add(task)
                task.add_done_callback(self._retire_tasks.discard)
            return candidate.snapshot

    def _ack_filename(self, token: str) -> str:
        return activation_ack_filename(token, self.worker_incarnation_id)

    async def _retire_after_ack(
        self, lease: SnapshotLease, binding: GenerationBinding, acknowledged_at: float
    ) -> None:
        grace_seconds = 10 * self.deadline_seconds
        remaining = grace_seconds - (self.clock() - acknowledged_at)
        grace_elapsed = remaining <= 0
        try:
            if remaining > 0:
                await asyncio.sleep(remaining)
                grace_elapsed = True
        finally:
            await self._close_lease(lease)
        if not grace_elapsed:
            return
        try:
            self._write_ack(
                retirement_ack_filename(binding.activation_token, self.worker_incarnation_id),
                {
                    "activationToken": binding.activation_token,
                    "operationToken": binding.activation_token,
                    "generationId": binding.generation_id,
                    "engineOrigin": binding.engine_origin,
                    "workerId": self.worker_id,
                    "workerIncarnationId": self.worker_incarnation_id,
                    "retiredAtMonotonic": self.clock(),
                    "graceSeconds": grace_seconds,
                },
            )
        except OSError, FileExistsError:
            # Missing retirement ACK is a stop signal to operators, never permission
            # to stop an engine. The old client is already closed after the grace.
            return

    def _write_failure_ack(self, attempted: GenerationBinding, failure_code: str) -> None:
        active_binding = self._active[1] if self._active else None
        try:
            self._write_ack(
                activation_failure_ack_filename(
                    attempted.activation_token, self.worker_incarnation_id
                ),
                {
                    "activationToken": attempted.activation_token,
                    "operationToken": attempted.activation_token,
                    "generationId": attempted.generation_id,
                    "engineOrigin": attempted.engine_origin,
                    "workerId": self.worker_id,
                    "workerIncarnationId": self.worker_incarnation_id,
                    "status": "rejected",
                    "failureCode": failure_code,
                    "activeOperationToken": (
                        active_binding.activation_token if active_binding else None
                    ),
                    "activeGenerationId": active_binding.generation_id if active_binding else None,
                    "activeEngineOrigin": active_binding.engine_origin if active_binding else None,
                },
            )
        except OSError, FileExistsError:
            # Failure ACK is diagnostic; it must never hide the activation failure.
            return

    def _write_ack(self, filename: str, data: dict) -> None:
        self.ack_dir.mkdir(parents=True, exist_ok=True)
        destination = self.ack_dir / filename
        temporary = self.ack_dir / f".{filename}.{uuid.uuid4().hex}.tmp"
        payload = json.dumps(data, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, destination)
            if os.name == "posix":
                try:
                    descriptor = os.open(self.ack_dir, os.O_RDONLY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                except OSError:
                    destination.unlink(missing_ok=True)
                    raise
        finally:
            temporary.unlink(missing_ok=True)

    async def _close_lease(self, lease: SnapshotLease) -> None:
        key = id(lease)
        if key not in self._owned_leases:
            return
        task = self._lease_close_tasks.get(key)
        if task is None:
            closed_resources: set[int] = set()

            async def close_owned_clients():
                errors = []
                for owned_client in lease.owned_clients:
                    if id(owned_client) in closed_resources:
                        continue
                    try:
                        result = owned_client.aclose()
                        if inspect.isawaitable(result):
                            await result
                        closed_resources.add(id(owned_client))
                    except BaseException as exc:
                        errors.append(exc)
                provider = getattr(lease.snapshot, "address_provider", None)
                catalog = getattr(provider, "catalog", None)
                close = getattr(catalog, "close", None)
                if callable(close) and id(catalog) not in closed_resources:
                    try:
                        result = close()
                        if inspect.isawaitable(result):
                            await result
                        closed_resources.add(id(catalog))
                    except BaseException as exc:
                        errors.append(exc)
                if errors:
                    raise BaseExceptionGroup("Snapshot resources failed to close", errors)

            task = asyncio.create_task(close_owned_clients())
            self._lease_close_tasks[key] = task
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            except BaseException:
                self._lease_close_tasks.pop(key, None)
                raise
            else:
                self._lease_close_tasks.pop(key, None)
                self._owned_leases.pop(key, None)
            raise
        except BaseException:
            self._lease_close_tasks.pop(key, None)
            raise
        else:
            self._lease_close_tasks.pop(key, None)
            self._owned_leases.pop(key, None)

    async def aclose(self) -> None:
        self._closed = True
        task = self._shutdown_task
        if task is None or (task.done() and (task.cancelled() or task.exception() is not None)):
            task = asyncio.create_task(self._shutdown())
            self._shutdown_task = task
        await asyncio.shield(task)

    async def _shutdown(self) -> None:
        async with self._reload_lock:
            retirement_tasks = tuple(self._retire_tasks)
            for task in retirement_tasks:
                task.cancel()
            if retirement_tasks:
                await asyncio.gather(*retirement_tasks, return_exceptions=True)
            errors = []
            for lease in tuple(self._owned_leases.values()):
                try:
                    await self._close_lease(lease)
                except BaseException as exc:
                    errors.append(exc)
            if errors:
                raise BaseExceptionGroup("One or more snapshot clients failed to close", errors)
            self._active = None

    async def close(self) -> None:
        await self.aclose()
