"""Local managed-activation app integration using synthetic generations only."""

import asyncio
import json
import os
import shutil
import signal
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from test_reference_api import reference_client

from opentransit.api.app import create_app
from opentransit.api.lifecycle import install_activation_signal
from opentransit.build.activation import (
    activation_failure_ack_filename,
    write_binding,
)
from opentransit.config import Settings

NOW = datetime(2026, 9, 30, 9, tzinfo=UTC)


def _managed_generation(root: Path, source_manifest: Path, engine_route: dict) -> Path:
    staging = root / "staging"
    staging.mkdir()
    manifest_path = staging / "manifest.json"
    shutil.copy2(source_manifest, manifest_path)
    with reference_client(manifest_path, engine_route, now=NOW):
        pass

    generation_dir = root / "generation-a"
    generation_dir.mkdir()
    for name in ("manifest.json", "reference.sqlite", "config.yml", "feed.zip", "probe.json"):
        shutil.copy2(staging / name, generation_dir / name)
    shutil.copytree(staging / "motis", generation_dir / "motis")

    manifest = json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["inputs"]["TripIdToDate.zip"] = {"sha256": "b" * 64}
    (generation_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    source_check = {
        "pairedValidation": "passed",
        "validation": {"valid": True},
        "validatedAt": NOW.isoformat(),
        "sources": {
            "gtfs": {
                "status": "unchanged",
                "sha256": manifest["inputs"]["israel-public-transportation.zip"]["sha256"],
                "checkedAt": NOW.isoformat(),
            },
            "trip_id_to_date": {
                "status": "unchanged",
                "sha256": "b" * 64,
                "checkedAt": NOW.isoformat(),
            },
        },
    }
    source_check_path = generation_dir / "source-check.json"
    source_check_path.write_text(json.dumps(source_check), encoding="utf-8")
    return generation_dir


def _binding(root: Path, generation_dir: Path, token: str, *, port=58081, probe=None):
    manifest_path = generation_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    probe_path = probe or generation_dir / "probe.json"
    if probe is not None:
        data = json.loads((generation_dir / "probe.json").read_text(encoding="utf-8"))
        data["engineOrigin"] = f"http://127.0.0.1:{port}"
        probe_path.write_text(json.dumps(data), encoding="utf-8")
    raw = {
        "generationDir": str(generation_dir.resolve()),
        "engineOrigin": f"http://127.0.0.1:{port}",
        "probePath": str(probe_path.resolve()),
        "sourceCheckPath": str((generation_dir / "source-check.json").resolve()),
        "activationToken": token,
        "generationId": manifest["generationId"],
    }
    destination = root / f"binding-{token}.json"
    write_binding(destination, raw, root)
    return destination


def _select(current: Path, binding_path: Path):
    temporary = current.with_suffix(".next")
    temporary.write_bytes(binding_path.read_bytes())
    os.replace(temporary, current)


class BlockingEngineTransport(httpx.AsyncBaseTransport):
    def __init__(self, route_body):
        self.route_body = route_body
        self.first_journey_entered = threading.Event()
        self.release_first_journey = threading.Event()
        self.journey_ports = []

    async def handle_async_request(self, request):
        if request.url.path != "/api/v6/plan":
            return httpx.Response(404, request=request)
        if request.url.params.get("fromPlace") == "32.0836,34.7981":
            return httpx.Response(
                200,
                json={"itineraries": [], "direct": []},
                request=request,
            )
        self.journey_ports.append(request.url.port)
        if request.url.port == 58081 and len(self.journey_ports) == 1:
            self.first_journey_entered.set()
            await asyncio.to_thread(self.release_first_journey.wait, 5)
        return httpx.Response(200, json=self.route_body, request=request)


def _settings(root, generation_dir, current, ack_dir):
    return Settings(
        manifest_path=generation_dir / "manifest.json",
        motis_url="http://127.0.0.1:58081",
        engine_timeout_seconds=4.0,
        journey_deadline_seconds=6.0,
        current_binding_path=current,
        managed_root=root,
        ack_dir=ack_dir,
    )


def _installer(control):
    def install(loop, callback):
        control["trigger"] = lambda: loop.call_soon_threadsafe(callback)
        return lambda: control.update(removed=True)

    return install


def test_managed_settings_are_opt_in_together_and_linux_only(tmp_path, monkeypatch):
    import opentransit.config as config

    root = tmp_path.resolve()
    current = root / "current"
    ack = root / "acks"
    with pytest.raises(ValueError, match="configured together"):
        Settings(root / "manifest.json", managed_root=root)
    monkeypatch.setattr(config.sys, "platform", "win32")
    with pytest.raises(ValueError, match="Linux"):
        Settings(
            root / "manifest.json",
            current_binding_path=current,
            managed_root=root,
            ack_dir=ack,
        )
    monkeypatch.setattr(config.sys, "platform", "linux")
    current.touch()
    settings = Settings(
        root / "manifest.json",
        current_binding_path=current,
        managed_root=root,
        ack_dir=ack,
    )
    assert settings.managed_root == root


def test_capture_snapshot_uses_manager_as_one_atomic_runtime_reference():
    from opentransit.runtime import capture_snapshot

    old, new = object(), object()
    state = SimpleNamespace(
        snapshot=object(), snapshot_manager=SimpleNamespace(current_snapshot=old)
    )
    assert capture_snapshot(state) is old
    state.snapshot_manager.current_snapshot = new
    assert capture_snapshot(state) is new
    state.snapshot_manager = None
    assert capture_snapshot(state) is state.snapshot


@pytest.mark.skipif(os.name != "posix", reason="managed local worker requires Linux file locks")
def test_inflight_request_keeps_old_engine_while_signal_publishes_new_snapshot(
    manifest, engine_route, query, tmp_path, monkeypatch
):
    import opentransit.config as config

    monkeypatch.setattr(config.sys, "platform", "linux")
    root = tmp_path.resolve()
    generation_dir = _managed_generation(root, manifest, engine_route)
    current, ack_dir = root / "current.json", root / "acks"
    initial = _binding(root, generation_dir, "initial")
    _select(current, initial)
    workers = ack_dir / "workers"
    workers.mkdir(parents=True)
    (workers / "worker.json").write_text(
        json.dumps({"pid": 999999999, "processStartId": "stale", "workerIncarnationId": "old"}),
        encoding="utf-8",
    )
    probe2 = generation_dir / "probe-next.json"
    next_binding = _binding(root, generation_dir, "next", port=58082, probe=probe2)
    transport = BlockingEngineTransport(engine_route)
    control = {}
    app = create_app(
        _settings(root, generation_dir, current, ack_dir),
        transport=transport,
        clock=lambda: NOW,
        signal_installer=_installer(control),
    )

    with TestClient(app) as client:
        manager = client.app.state.snapshot_manager
        first_incarnation = manager.worker_incarnation_id
        record_path = client.app.state.worker_record_path
        record = json.loads(record_path.read_text(encoding="utf-8"))
        assert record_path.name == "worker.json"
        assert record["workerIncarnationId"] == first_incarnation
        assert record["controlSignal"] == "SIGUSR1"
        from opentransit.api.lifecycle import _acquire_worker_record

        with pytest.raises(RuntimeError, match="already owns"):
            _acquire_worker_record(ack_dir, manager=manager)
        response_data = {}
        request_thread = threading.Thread(
            target=lambda: response_data.setdefault(
                "response", client.post("/v1/journeys", json=query)
            )
        )
        request_thread.start()
        assert transport.first_journey_entered.wait(5)

        _select(current, next_binding)
        control["trigger"]()
        deadline = time.monotonic() + 5
        while manager.current_binding.activation_token != "next" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert manager.current_binding.activation_token == "next"
        assert manager.current_snapshot.motis.client.base_url.host == "127.0.0.1"
        transport.release_first_journey.set()
        request_thread.join(5)
        assert not request_thread.is_alive()
        assert response_data["response"].status_code == 200
        assert transport.journey_ports == [58081]

        new_response = client.post("/v1/journeys", json=query)
        assert new_response.status_code == 200
        assert transport.journey_ports == [58081, 58082]
        exposed_paths = client.get("/openapi.json").json()["paths"]
        assert not any(
            action in path
            for path in exposed_paths
            for action in ("activate", "rollback", "reload")
        )
    assert not record_path.exists()


@pytest.mark.skipif(os.name != "posix", reason="managed local worker requires Linux file locks")
def test_unready_startup_stays_live_and_recovers_after_signal(
    manifest, engine_route, tmp_path, monkeypatch
):
    import opentransit.config as config

    monkeypatch.setattr(config.sys, "platform", "linux")
    root = tmp_path.resolve()
    generation_dir = _managed_generation(root, manifest, engine_route)
    current, ack_dir = root / "current.json", root / "acks"
    binding_path = _binding(root, generation_dir, "recovered")
    transport = BlockingEngineTransport(engine_route)
    control = {}
    app = create_app(
        _settings(root, generation_dir, current, ack_dir),
        transport=transport,
        clock=lambda: NOW,
        signal_installer=_installer(control),
    )
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503
        assert client.app.state.snapshot_manager.current_snapshot is None
        _select(current, binding_path)
        control["trigger"]()
        manager = client.app.state.snapshot_manager
        deadline = time.monotonic() + 5
        while manager.current_snapshot is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert manager.current_binding.activation_token == "recovered"
        assert client.get("/readyz").status_code == 200
        record_path = client.app.state.worker_record_path
    assert not record_path.exists()


@pytest.mark.skipif(os.name != "posix", reason="managed local worker requires Linux file locks")
def test_bad_candidate_probe_is_rejected_while_previous_snapshot_keeps_serving(
    manifest, engine_route, tmp_path, monkeypatch
):
    import opentransit.config as config

    monkeypatch.setattr(config.sys, "platform", "linux")
    root = tmp_path.resolve()
    generation_dir = _managed_generation(root, manifest, engine_route)
    current, ack_dir = root / "current.json", root / "acks"
    initial = _binding(root, generation_dir, "initial")
    _select(current, initial)
    bad_probe = generation_dir / "probe-bad.json"
    probe_data = json.loads((generation_dir / "probe.json").read_text(encoding="utf-8"))
    probe_data["generationId"] = "wrong-generation"
    bad_probe.write_text(json.dumps(probe_data), encoding="utf-8")
    bad_binding = _binding(
        root,
        generation_dir,
        "bad-probe",
        port=58082,
        probe=bad_probe,
    )
    # Restore the deliberately mismatched generation id after _binding prepares the port.
    probe_data["generationId"] = "wrong-generation"
    bad_probe.write_text(json.dumps(probe_data), encoding="utf-8")

    control = {}
    app = create_app(
        _settings(root, generation_dir, current, ack_dir),
        transport=BlockingEngineTransport(engine_route),
        clock=lambda: NOW,
        signal_installer=_installer(control),
    )
    with TestClient(app) as client:
        manager = client.app.state.snapshot_manager
        active_before = manager.current_snapshot
        _select(current, bad_binding)
        control["trigger"]()
        failure_path = ack_dir / activation_failure_ack_filename(
            "bad-probe", manager.worker_incarnation_id
        )
        deadline = time.monotonic() + 5
        while not failure_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert failure_path.is_file()
        failure = json.loads(failure_path.read_text(encoding="utf-8"))
        assert failure["activeOperationToken"] == "initial"
        assert failure["workerIncarnationId"] == manager.worker_incarnation_id
        assert manager.current_snapshot is active_before
        assert manager.current_binding.activation_token == "initial"
        assert manager.current_snapshot.motis.client.base_url.port == 58081
        assert client.get("/readyz").status_code == 200
    assert not client.app.state.worker_record_path.exists()


@pytest.mark.skipif(os.name != "posix", reason="managed local worker requires Linux file locks")
def test_snapshot_with_unowned_engine_client_is_rejected_and_old_snapshot_serves(
    manifest, engine_route, tmp_path, monkeypatch
):
    import opentransit.api.lifecycle as lifecycle_module
    import opentransit.config as config

    monkeypatch.setattr(config.sys, "platform", "linux")
    root = tmp_path.resolve()
    generation_dir = _managed_generation(root, manifest, engine_route)
    current, ack_dir = root / "current.json", root / "acks"
    initial = _binding(root, generation_dir, "initial")
    _select(current, initial)
    next_binding = _binding(root, generation_dir, "wrong-client", port=58082)
    control = {}
    app = create_app(
        _settings(root, generation_dir, current, ack_dir),
        transport=BlockingEngineTransport(engine_route),
        clock=lambda: NOW,
        signal_installer=_installer(control),
    )

    with TestClient(app) as client:
        manager = client.app.state.snapshot_manager
        original = manager.current_snapshot
        generation, reference = original.generation, original.reference

        class MismatchedMotis:
            def __init__(self, origin):
                self.client = SimpleNamespace(base_url=origin)

            async def ready(self, now):
                return True

        monkeypatch.setattr(
            lifecycle_module.RuntimeSnapshot,
            "load",
            classmethod(
                lambda cls, path, motis, **kwargs: SimpleNamespace(
                    generation=generation,
                    reference=reference,
                    routing_verified=True,
                    motis=MismatchedMotis("http://127.0.0.1:58082"),
                )
            ),
        )
        _select(current, next_binding)
        control["trigger"]()
        failure_path = ack_dir / activation_failure_ack_filename(
            "wrong-client", manager.worker_incarnation_id
        )
        deadline = time.monotonic() + 5
        while not failure_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert failure_path.is_file()
        assert manager.current_snapshot is original
        assert manager.current_binding.activation_token == "initial"


@pytest.mark.skipif(sys.platform != "linux", reason="native SIGUSR1 is Linux-only")
def test_native_sigusr1_handler_installs_and_removes_on_main_thread():
    loop = asyncio.new_event_loop()
    seen = []
    try:
        remove = install_activation_signal(loop, lambda: seen.append(True))
        os.kill(os.getpid(), signal.SIGUSR1)
        loop.run_until_complete(asyncio.sleep(0.01))
        assert seen == [True]
        remove()
    finally:
        loop.close()
