import asyncio
import json
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from opentransit.activation import SnapshotLease, SnapshotManager
from opentransit.address_catalog import AddressCatalog
from opentransit.api.places import places_router
from opentransit.api.reference import metadata, reference_router
from opentransit.api.schemas import (
    Coordinate,
    Coverage,
    JourneyData,
    JourneyRequest,
    JourneyResponse,
    Metadata,
    Problem,
)
from opentransit.api.timetable import timetable_router
from opentransit.build.activation import read_binding
from opentransit.config import Settings
from opentransit.core.artifacts import verify_address_composite
from opentransit.core.place_ref import decode_place_ref
from opentransit.motis import EngineFailure, MotisClient
from opentransit.runtime import AddressProviderBinding, RuntimeSnapshot, capture_snapshot

LOG = logging.getLogger("opentransit.requests")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    LOG.addHandler(logging.StreamHandler())


async def _load_address_provider(manifest_path: Path, settings: Settings, transport):
    """Verify the sealed Photon binding before making it available to a snapshot."""
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("addressSearch") is None:
        return None
    if settings.photon_url is None or settings.photon_admin_url is None:
        raise ValueError("Composite address generation requires fixed Photon query/admin origins")
    metadata = verify_address_composite(manifest_path.parent, manifest)
    catalog = AddressCatalog(
        manifest_path.parent / "address-catalog.sqlite", metadata["sourceDumpSha256"]
    )
    client = httpx.AsyncClient(
        base_url=settings.photon_url,
        timeout=settings.engine_timeout_seconds,
        transport=transport,
        trust_env=False,
        follow_redirects=False,
    )
    admin = httpx.AsyncClient(
        base_url=settings.photon_admin_url,
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
            settings.photon_url,
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


def problem(request: Request, status: int, code: str, detail: str, errors=None) -> JSONResponse:
    payload = Problem(
        type=f"urn:opentransit:problem:{code.lower().replace('_', '-')}",
        title=code.replace("_", " ").capitalize(),
        status=status,
        code=code,
        detail=detail,
        requestId=request.state.request_id,
        errors=errors,
    )
    return JSONResponse(
        payload.model_dump(exclude_none=True),
        status_code=status,
        media_type="application/problem+json",
    )


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


class SafeRequests(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = uuid4().hex
        started = time.perf_counter()
        if request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 16_384:
                    response = problem(request, 413, "BODY_TOO_LARGE", "Body limit is 16 KiB.")
                    break
            else:
                request._body = bytes(body)
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        LOG.info(
            "request_id=%s route=%s status=%s duration_ms=%.1f",
            request.state.request_id,
            route.path if route else "unmatched",
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response


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


def create_app(
    settings: Settings | None = None,
    transport=None,
    clock=None,
    signal_installer=None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    clock = clock or (lambda: datetime.now(UTC))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.planning_semaphore = asyncio.Semaphore(16)
        app.state.snapshot_manager = None
        app.state.snapshot = None
        app.state.generation_geocoding = {}
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
                try:
                    address_provider = await _load_address_provider(
                        binding.generation_dir / "manifest.json", settings, transport
                    )
                    motis = MotisClient(client)
                    snapshot = await asyncio.to_thread(
                        RuntimeSnapshot.load,
                        binding.generation_dir / "manifest.json",
                        motis,
                        source_check_path=binding.source_check_path,
                        probe_path=binding.probe_path,
                        address_provider=address_provider,
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
                        or generation.freshness(now) != "current"
                    ):
                        raise ValueError("Candidate coverage or source freshness is not current")
                    async with asyncio.timeout(settings.engine_timeout_seconds):
                        if not await motis.ready(now):
                            raise ValueError("Candidate engine health check failed")
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
                            await manager.aclose()
                        finally:
                            if worker_record is not None and worker_lock is not None:
                                _release_worker_record(worker_record, worker_lock, manager=manager)
            return

        async with httpx.AsyncClient(
            base_url=settings.motis_url,
            timeout=settings.engine_timeout_seconds,
            transport=transport,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            address_provider = None
            try:
                address_provider = await _load_address_provider(
                    settings.manifest_path, settings, transport
                )
                app.state.snapshot = RuntimeSnapshot.load(
                    settings.manifest_path,
                    MotisClient(client),
                    source_check_path=settings.source_check_path,
                    probe_path=settings.probe_path,
                    address_provider=address_provider,
                )
                if app.state.snapshot is not None:
                    _record_geocoding_config(
                        app, settings.manifest_path, app.state.snapshot.generation.id
                    )
            except Exception:
                app.state.snapshot = None
                LOG.warning("generation_unavailable")
            try:
                yield
            finally:
                if address_provider is not None:
                    try:
                        await _close_runtime_resources(
                            (address_provider.client,), address_provider.catalog
                        )
                    except Exception:
                        LOG.warning("address_provider_shutdown_cleanup_failed")

    app = FastAPI(title="OpenTransit — local schedule preview", version="0.1.0", lifespan=lifespan)
    app.add_middleware(SafeRequests)
    app.include_router(reference_router(clock, problem))
    app.include_router(timetable_router(clock, problem))
    app.include_router(places_router(clock, problem))
    if settings.playground_enabled:
        app.mount(
            "/playground",
            StaticFiles(directory=Path(__file__).with_name("playground"), html=True),
            name="playground",
        )

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError):
        # Error contexts and rejected values can contain precise passenger data.
        # Report declared schema paths only; unknown field names are redacted.
        allowed = {
            "body",
            "from",
            "to",
            "kind",
            "latitude",
            "longitude",
            "stopId",
            "placeRef",
            "departAt",
            "arriveBy",
            "modes",
            "results",
            "lang",
            "maxAccessWalkMinutes",
            "maxEgressWalkMinutes",
            "maxDirectWalkMinutes",
        }
        fields = [
            {
                "field": ".".join(str(p) if p in allowed else "field" for p in e["loc"]),
                "reason": "Invalid or unsupported field",
            }
            for e in exc.errors()
        ]
        return problem(request, 422, "INVALID_REQUEST", "Check the declared input fields.", fields)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return problem(request, exc.status_code, "HTTP_ERROR", "The request cannot be served.")

    @app.get("/healthz")
    async def health():
        return {"status": "alive"}

    async def readiness(snapshot, now):
        if snapshot is None:
            return False, "unavailable", "unavailable"
        generation = snapshot.generation
        if not generation.contains(now) or generation.freshness(now) == "expired":
            return False, "expired", "unchecked"
        if not snapshot.routing_verified:
            return False, "available", "unverified"
        try:
            async with asyncio.timeout(settings.journey_deadline_seconds):
                healthy = await snapshot.motis.ready(now)
        except EngineFailure, TimeoutError:
            return False, "available", "unavailable"
        if not healthy:
            return False, "available", "unavailable"
        return snapshot.reference is not None, "available", "available"

    @app.get("/readyz")
    async def ready(request: Request):
        snapshot = capture_snapshot(app.state)
        usable, _, _ = await readiness(snapshot, clock())
        if not usable:
            return problem(request, 503, "NOT_READY", "A complete usable generation is required.")
        return {"status": "ready", "generationId": snapshot.generation.id}

    @app.get("/v1/status")
    async def status(request: Request):
        snapshot = capture_snapshot(app.state)
        now = clock()
        usable, static_state, engine_state = await readiness(snapshot, now)
        data = {
            "ready": usable,
            "staticData": static_state,
            "routing": engine_state,
            "reference": "available" if snapshot and snapshot.reference else "unavailable",
            "realtime": "not_enabled",
            "alerts": "not_enabled",
        }
        if snapshot is None:
            return {
                "data": data,
                "meta": {
                    "requestId": request.state.request_id,
                    "generatedAt": now,
                    "generationId": None,
                },
            }
        generation = snapshot.generation
        data["lastValidatedAt"] = (
            generation.source_checked_at
            if generation.source_check_recorded
            else generation.validated_at
        )
        return JSONResponse(
            jsonable_encoder({"data": data, "meta": metadata(request, snapshot, now)})
        )

    @app.post(
        "/v1/journeys",
        response_model=JourneyResponse,
        responses={
            status: {
                "content": {"application/problem+json": {"schema": Problem.model_json_schema()}}
            }
            for status in (413, 422, 503, 504)
        },
    )
    async def plan(query: JourneyRequest, request: Request):
        snapshot = capture_snapshot(app.state)  # Engine/reference/generation stay together.
        now = clock()
        if snapshot is None:
            return problem(request, 503, "DATA_UNAVAILABLE", "No verified graph is configured.")
        generation = snapshot.generation
        if not snapshot.routing_verified:
            return problem(
                request, 503, "DATA_UNAVAILABLE", "The candidate engine needs verification."
            )
        freshness = generation.freshness(now)
        if now >= generation.coverage_until or freshness == "expired":
            return problem(request, 503, "FEED_EXPIRED", "The graph requires a fresh build.")
        if not generation.contains(query.time_anchor):
            return problem(request, 422, "OUTSIDE_SERVICE_WINDOW", "Choose a time inside coverage.")
        try:
            query = _resolve_place_locations(query, generation.id)
        except ValueError:
            return problem(
                request,
                422,
                "INVALID_PLACE_REF",
                "The place reference is invalid or belongs to another generation.",
            )
        semaphore = app.state.planning_semaphore
        if semaphore.locked():
            return problem(request, 503, "SERVER_OVERLOADED", "Planning capacity is busy.")
        try:
            async with asyncio.timeout(settings.journey_deadline_seconds):
                async with semaphore:
                    result = await snapshot.motis.plan(query, generation, snapshot.reference)
        except (EngineFailure, TimeoutError) as exc:
            code = exc.code if isinstance(exc, EngineFailure) else "ENGINE_TIMEOUT"
            status = exc.status if isinstance(exc, EngineFailure) else 504
            return problem(request, status, code, "Scheduled planning is temporarily unavailable.")
        return JourneyResponse(
            data=JourneyData(
                outcome="routes_found" if result.journeys else "no_route",
                journeys=result.journeys,
            ),
            meta=Metadata(
                requestId=request.state.request_id,
                generationId=generation.id,
                generatedAt=now,
                dataBuiltAt=generation.built_at,
                mode=generation.mode,
                coverage=Coverage(start=generation.coverage_from, until=generation.coverage_until),
                freshness=freshness,
                rankingPolicy=result.ranking_policy,
                appliedConstraints=result.applied_constraints,
                warnings=([] if freshness == "current" else ["STATIC_DATA_AGING"])
                + result.warnings,
            ),
        )

    return app


def _resolve_place_locations(query: JourneyRequest, generation_id: str) -> JourneyRequest:
    updates = {}
    for field in ("origin", "destination"):
        location = getattr(query, field)
        if getattr(location, "kind", None) != "place":
            continue
        place = decode_place_ref(location.placeRef, generation_id)
        updates[field] = Coordinate(
            kind="coordinate",
            latitude=place.latitude,
            longitude=place.longitude,
        )
    return query.model_copy(update=updates) if updates else query
