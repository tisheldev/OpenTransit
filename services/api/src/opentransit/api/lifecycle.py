"""Runtime/snapshot lifecycle: provider verification, worker records and the app lifespan."""

import asyncio
import json
import os
import signal
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI

from opentransit.activation import SnapshotLease, SnapshotManager
from opentransit.address_catalog import AddressCatalog
from opentransit.api.log import LOG
from opentransit.build.activation import read_binding
from opentransit.config import Settings
from opentransit.core.artifacts import ArtifactDigests, verify_address_composite
from opentransit.motis import MotisClient
from opentransit.runtime import AddressProviderBinding, RuntimeSnapshot, capture_snapshot
from opentransit.search_readiness import (
    READY,
    SearchWarmup,
    enabled_backends,
    install_warmup,
    prepare_search,
    retry_until_ready,
)


async def _load_address_provider(
    manifest_path: Path,
    settings: Settings,
    transport,
    *,
    photon_url: str | None = None,
    photon_admin_url: str | None = None,
    digests: ArtifactDigests | None = None,
):
    """Verify the sealed Photon binding before making it available to a snapshot.

    Explicit origins (from a managed activation binding) take precedence over the fixed
    settings origins, so two address composites can each be served by their own Photon.
    Pass the load's ``digests`` so the snapshot reuses the artifact hashes computed here.
    """
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("addressSearch") is None:
        return None
    if (photon_url is None) != (photon_admin_url is None):
        raise ValueError("Photon query and admin origins must be supplied together")
    if photon_url is None:
        photon_url, photon_admin_url = settings.photon_url, settings.photon_admin_url
    if photon_url is None or photon_admin_url is None:
        raise ValueError("Composite address generation requires fixed Photon query/admin origins")

    def open_verified_catalog():
        metadata = verify_address_composite(manifest_path.parent, manifest, digests)
        catalog = AddressCatalog(
            manifest_path.parent / "address-catalog.sqlite", metadata["sourceDumpSha256"]
        )
        return metadata, catalog

    # Hashing and counting the ~134 MB catalog takes seconds on a slow mount; a managed
    # reload does this while the old snapshot serves, so keep it off the event loop.
    metadata, catalog = await asyncio.to_thread(open_verified_catalog)
    client = httpx.AsyncClient(
        base_url=photon_url,
        timeout=settings.engine_timeout_seconds,
        transport=transport,
        trust_env=False,
        follow_redirects=False,
    )
    admin = httpx.AsyncClient(
        base_url=photon_admin_url,
        timeout=settings.engine_timeout_seconds,
        transport=transport,
        trust_env=False,
        follow_redirects=False,
    )

    async def get_json(session, path: str) -> dict:
        body = bytearray()
        async with asyncio.timeout(settings.engine_timeout_seconds):
            async with session.stream("GET", path) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 2 * 1024 * 1024:
                        raise ValueError("Photon verification response exceeds the startup bound")
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Photon verification endpoint returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("Photon verification endpoint returned a non-object response")
        return value

    try:
        root = await get_json(admin, "/")
        if root.get("cluster_uuid") != metadata["clusterUuid"]:
            raise ValueError("Photon cluster UUID differs from its sealed attestation")
        settings_body = await get_json(admin, "/photon/_settings?flat_settings=true")
        index_settings = settings_body.get("photon", {}).get("settings", {})
        if index_settings.get("index.uuid") != metadata["indexUuid"] or index_settings.get(
            "index.blocks.write"
        ) not in {"true", True}:
            raise ValueError("Photon index UUID or immutable write block differs from attestation")
        count = await get_json(admin, "/photon/_count")
        shards = count.get("_shards", {})
        if (
            count.get("count") != metadata["documentCount"]
            or shards.get("failed") != 0
            or not isinstance(shards.get("successful"), int)
            or shards["successful"] <= 0
        ):
            raise ValueError("Photon index document count or shard status differs from attestation")

        for probe in metadata["probes"]:
            osm_type, osm_id = probe.get("osmType"), probe.get("osmId")
            if osm_type not in {"N", "W"} or not isinstance(osm_id, str) or not osm_id.isdigit():
                raise ValueError("Photon source probe identity is malformed")
            payload = catalog.lookup(osm_type, osm_id)
            if not isinstance(payload, dict):
                raise ValueError("Photon source probe is absent from the immutable catalog")
            place = payload
            centroid = place.get("centroid")
            if (
                place.get("object_type") != osm_type
                or str(place.get("object_id")) != osm_id
                or not isinstance(centroid, list)
                or len(centroid) != 2
                or abs(float(centroid[1]) - float(probe["lat"])) > 1e-7
                or abs(float(centroid[0]) - float(probe["lon"])) > 1e-7
            ):
                raise ValueError("Attested Photon probe differs from the source catalog")
            record = await get_json(admin, f"/photon/_doc/{osm_type}{osm_id}")
            source = record.get("_source")
            coordinate = source.get("coordinate") if isinstance(source, dict) else None
            if (
                record.get("found") is not True
                or not isinstance(source, dict)
                or str(source.get("osm_id")) != osm_id
                or source.get("osm_type") != osm_type
                or source.get("type") != place.get("address_type")
                or not isinstance(coordinate, dict)
                or abs(float(coordinate.get("lat")) - float(centroid[1])) > 1e-7
                or abs(float(coordinate.get("lon")) - float(centroid[0])) > 1e-7
                or (
                    place.get("housenumber") is not None
                    and source.get("housenumber") != place.get("housenumber")
                )
            ):
                raise ValueError("Live Photon document differs from its attested source object")
        return AddressProviderBinding(
            client,
            photon_url,
            metadata["addressArtifactIdentity"],
            metadata["indexUuid"],
            catalog,
        )
    except BaseException:
        try:
            await _close_runtime_resources((client,), catalog)
        except BaseException:
            LOG.warning("photon_binding_cleanup_failed")
        raise
    finally:
        try:
            await admin.aclose()
        except Exception:
            LOG.warning("photon_admin_client_cleanup_failed")


async def _close_runtime_resources(clients=(), catalog=None) -> None:
    """Close provider resources together; finish cleanup even if the caller is cancelled."""

    async def close_resources():
        errors = [
            result
            for result in await asyncio.gather(
                *(client.aclose() for client in clients), return_exceptions=True
            )
            if isinstance(result, BaseException)
        ]
        if catalog is not None:
            try:
                catalog.close()
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise BaseExceptionGroup("Runtime resources failed to close", errors)

    task = asyncio.create_task(close_resources())
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        except BaseException:
            LOG.warning("runtime_resource_cleanup_failed")
        raise


def _record_geocoding_config(app, manifest_path: Path, generation_id: str) -> None:
    """Remember the static setting belonging to the exact loaded generation."""
    enabled = False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("generationId") == generation_id:
            artifact = manifest.get("artifacts", {}).get("config", {})
            config_path = manifest_path.parent / artifact.get("path", "config.yml")
            if config_path.resolve().parent == manifest_path.parent.resolve():
                enabled = any(
                    line.strip() == "geocoding: true"
                    for line in config_path.read_text(encoding="utf-8").splitlines()
                )
    except OSError, ValueError, TypeError, KeyError:
        enabled = False
    configured = app.state.generation_geocoding
    configured[generation_id] = enabled
    while len(configured) > 8:
        configured.pop(next(iter(configured)))


async def _warm_search(app, settings: Settings, snapshot) -> SearchWarmup:
    """Build the snapshot's stop index and warm its geocoders before it is published."""
    enabled = app.state.generation_geocoding.get(snapshot.generation.id, False)
    return await prepare_search(
        snapshot,
        enabled_backends(snapshot, enabled),
        attempts=settings.warmup_attempts,
        retry_seconds=settings.warmup_retry_seconds,
        timeout_seconds=settings.journey_deadline_seconds,
    )


def _install_search(app, settings: Settings, snapshot, record: SearchWarmup) -> None:
    """Record the warm-up outcome; a backend that stayed down keeps retrying in background."""
    generation_id = snapshot.generation.id
    install_warmup(app.state.search_warmup, generation_id, record)
    if all(state == READY for state in record.backends.values()):
        return

    def is_current() -> bool:
        current = capture_snapshot(app.state)
        return current is not None and current.generation.id == generation_id

    task = asyncio.create_task(
        retry_until_ready(
            snapshot,
            record,
            is_current=is_current,
            timeout_seconds=settings.journey_deadline_seconds,
            interval_seconds=settings.warmup_recovery_seconds,
        )
    )
    record.retry_task = task
    app.state.search_warmup_tasks.add(task)
    task.add_done_callback(app.state.search_warmup_tasks.discard)


async def _cancel_search_tasks(app) -> None:
    tasks = tuple(app.state.search_warmup_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def install_activation_signal(loop, callback):
    """Install the private Linux worker control signal and return its remover."""
    if sys.platform != "linux":
        raise RuntimeError("Managed local activation requires Linux SIGUSR1 support")
    loop.add_signal_handler(signal.SIGUSR1, callback)
    return lambda: loop.remove_signal_handler(signal.SIGUSR1)


async def _close_client_safely(client: httpx.AsyncClient) -> None:
    task = asyncio.create_task(client.aclose())
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        await task
        raise


def _process_start_identity(pid: int) -> str | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except OSError:
        return None
    closing = stat.rfind(")")
    fields = stat[closing + 2 :].split() if closing >= 0 else []
    return fields[19] if len(fields) > 19 else None


def _pid_is_same_process(record: dict) -> bool:
    pid = record.get("pid")
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    previous = record.get("processStartId")
    current = _process_start_identity(pid)
    return current is None or (isinstance(previous, str) and previous == current)


def _acquire_worker_record(directory: Path, *, manager: SnapshotManager):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or getattr(directory, "is_junction", lambda: False)():
        raise ValueError("Worker control directory may not be a symlink or junction")
    directory = directory.resolve(strict=True)
    workers = directory / "workers"
    workers.mkdir(parents=True, exist_ok=True, mode=0o700)
    if workers.is_symlink() or getattr(workers, "is_junction", lambda: False)():
        raise ValueError("Worker record directory may not be a symlink or junction")
    if os.name == "posix":
        os.chmod(workers, 0o700)
    lock_path = workers / "worker.lock"
    lock_descriptor = os.open(
        lock_path,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    if os.name == "posix":
        os.fchmod(lock_descriptor, 0o600)
    lock_file = os.fdopen(lock_descriptor, "r+b")
    import fcntl

    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.close()
        raise RuntimeError(
            "A managed local API worker already owns this control directory"
        ) from exc

    path = workers / "worker.json"
    try:
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except OSError, ValueError:
                existing = {}
            if _pid_is_same_process(existing):
                raise RuntimeError("An existing live worker record owns this control directory")
            path.unlink()

        record = {
            "pid": os.getpid(),
            "processStartId": _process_start_identity(os.getpid()),
            "workerId": manager.worker_id,
            "workerIncarnationId": manager.worker_incarnation_id,
            "controlPath": str(path),
            "controlSignal": "SIGUSR1",
            "currentBindingPath": str(manager.current_binding_path),
            "startedAt": datetime.now(UTC).isoformat(),
        }
        payload = json.dumps(record, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        temporary = workers / f".{path.name}.{uuid4().hex}.tmp"
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)
            if os.name == "posix":
                os.chmod(path, 0o600)
                descriptor = os.open(workers, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
        return path, lock_file
    except BaseException:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
        raise


def _release_worker_record(path: Path, lock_file, *, manager: SnapshotManager) -> None:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("workerIncarnationId") == manager.worker_incarnation_id:
            path.unlink(missing_ok=True)
    except OSError, ValueError:
        pass
    finally:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


PLANNING_CONCURRENCY = 16  # One semaphore shared by journeys, departures and trips.


def make_lifespan(settings: Settings, transport, clock, signal_installer):
    """Build the ASGI lifespan that owns the runtime snapshot and worker record."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.planning_semaphore = asyncio.Semaphore(PLANNING_CONCURRENCY)
        app.state.snapshot_manager = None
        app.state.snapshot = None
        app.state.generation_geocoding = {}
        app.state.search_warmup = {}
        app.state.search_warmup_tasks = set()
        app.state.worker_incarnation_id = None
        app.state.worker_record_path = None
        app.state.activation_reload_tasks = set()
        if settings.current_binding_path is not None:
            assert settings.managed_root is not None and settings.ack_dir is not None
            if sys.platform != "linux":
                raise RuntimeError("Managed local activation is supported only on Linux")

            async def snapshot_factory(binding):
                if binding.probe_path is None or binding.source_check_path is None:
                    raise ValueError("Managed activation requires probe and source-check evidence")
                client = httpx.AsyncClient(
                    base_url=binding.engine_origin,
                    timeout=settings.engine_timeout_seconds,
                    transport=transport,
                    trust_env=False,
                    follow_redirects=False,
                )
                address_provider = None
                # Reuse the hashes computed when the binding was verified for this activation.
                digests = binding.artifact_digests or ArtifactDigests()
                try:
                    address_provider = await _load_address_provider(
                        binding.generation_dir / "manifest.json",
                        settings,
                        transport,
                        photon_url=binding.photon_origin,
                        photon_admin_url=binding.photon_admin_origin,
                        digests=digests,
                    )
                    motis = MotisClient(client)
                    snapshot = await asyncio.to_thread(
                        RuntimeSnapshot.load,
                        binding.generation_dir / "manifest.json",
                        motis,
                        source_check_path=binding.source_check_path,
                        probe_path=binding.probe_path,
                        address_provider=address_provider,
                        digests=digests,
                    )
                    _record_geocoding_config(
                        app, binding.generation_dir / "manifest.json", snapshot.generation.id
                    )
                    now = clock()
                    generation = snapshot.generation
                    if not snapshot.routing_verified:
                        raise ValueError("Candidate routing probe does not match its binding")
                    if snapshot.reference is None:
                        raise ValueError("Candidate reference database is unavailable")
                    if (
                        not generation.contains(now)
                        or now >= generation.coverage_until
                        or not (
                            generation.freshness_serviceable(now)
                            if binding.purpose == "rollback"
                            else generation.freshness(now) == "current"
                        )
                    ):
                        raise ValueError("Candidate coverage or source freshness is not current")
                    async with asyncio.timeout(settings.engine_timeout_seconds):
                        if not await motis.ready(now):
                            raise ValueError("Candidate engine health check failed")
                    # Stop index and geocoder warm-up complete before the candidate can be
                    # swapped in, so in-flight requests never see a half-built index.
                    warmup = await _warm_search(app, settings, snapshot)
                    _install_search(app, settings, snapshot, warmup)
                    return SnapshotLease(
                        snapshot,
                        client,
                        (address_provider.client,) if address_provider is not None else (),
                    )
                except BaseException:
                    try:
                        await _close_runtime_resources(
                            (client,)
                            + ((address_provider.client,) if address_provider is not None else ()),
                            address_provider.catalog if address_provider is not None else None,
                        )
                    except BaseException:
                        LOG.warning("candidate_resource_cleanup_failed")
                    raise

            manager = SnapshotManager(
                settings.current_binding_path,
                snapshot_factory,
                settings.ack_dir,
                settings.journey_deadline_seconds,
                managed_root=settings.managed_root,
            )
            app.state.snapshot_manager = manager
            app.state.worker_incarnation_id = manager.worker_incarnation_id
            loop = asyncio.get_running_loop()
            reload_tasks: set[asyncio.Task] = app.state.activation_reload_tasks

            async def reload_selected_binding():
                try:
                    binding = await asyncio.to_thread(
                        read_binding, settings.current_binding_path, settings.managed_root
                    )
                    await manager.reload_current(binding.activation_token)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    LOG.warning("generation_reload_failed kind=%s", type(exc).__name__)

            def schedule_reload():
                task = asyncio.create_task(reload_selected_binding())
                reload_tasks.add(task)
                task.add_done_callback(reload_tasks.discard)

            remove_signal_handler = None
            worker_record = None
            worker_lock = None
            try:
                worker_record, worker_lock = _acquire_worker_record(
                    settings.ack_dir, manager=manager
                )
                app.state.worker_record_path = worker_record
                installer = signal_installer or install_activation_signal
                remove_signal_handler = installer(loop, schedule_reload)
                try:
                    await manager.initialize()
                except Exception as exc:
                    LOG.warning("generation_unavailable kind=%s", type(exc).__name__)
                yield
            finally:
                try:
                    if remove_signal_handler is not None:
                        remove_signal_handler()
                finally:
                    for task in tuple(reload_tasks):
                        task.cancel()
                    try:
                        if reload_tasks:
                            await asyncio.gather(*tuple(reload_tasks), return_exceptions=True)
                    finally:
                        try:
                            await _cancel_search_tasks(app)
                        finally:
                            try:
                                await manager.aclose()
                            finally:
                                if worker_record is not None and worker_lock is not None:
                                    _release_worker_record(
                                        worker_record, worker_lock, manager=manager
                                    )
            return

        async with httpx.AsyncClient(
            base_url=settings.motis_url,
            timeout=settings.engine_timeout_seconds,
            transport=transport,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            address_provider = None
            # One digest per artifact for this startup, shared by both verification steps.
            digests = ArtifactDigests()
            try:
                address_provider = await _load_address_provider(
                    settings.manifest_path, settings, transport, digests=digests
                )
                snapshot = RuntimeSnapshot.load(
                    settings.manifest_path,
                    MotisClient(client),
                    source_check_path=settings.source_check_path,
                    probe_path=settings.probe_path,
                    address_provider=address_provider,
                    digests=digests,
                )
                _record_geocoding_config(app, settings.manifest_path, snapshot.generation.id)
                # Index and warm-up finish before the snapshot becomes visible to requests.
                warmup = await _warm_search(app, settings, snapshot)
                _install_search(app, settings, snapshot, warmup)
                app.state.snapshot = snapshot
            except Exception:
                app.state.snapshot = None
                LOG.warning("generation_unavailable")
            try:
                yield
            finally:
                await _cancel_search_tasks(app)
                if address_provider is not None:
                    try:
                        await _close_runtime_resources(
                            (address_provider.client,), address_provider.catalog
                        )
                    except Exception:
                        LOG.warning("address_provider_shutdown_cleanup_failed")

    return lifespan
