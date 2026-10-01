"""Generation snapshot activation tests use synthetic local artifacts only."""

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from opentransit.activation import SnapshotLease, SnapshotManager
from opentransit.build.activation import (
    activate_current,
    activation_ack_filename,
    activation_failure_ack_filename,
    read_binding,
    restore_current_if_current,
    retirement_ack_filename,
    write_binding,
)
from opentransit.build.generations import (
    CANONICAL_INPUTS,
    build_generation,
)
from opentransit.core.generation import Generation

pytest_plugins = ["test_generation_build"]


class FakeClient:
    def __init__(self):
        self.closed = False

    async def aclose(self):
        self.closed = True


@pytest.fixture
def generation_factory(inputs, tmp_path):
    provenance_path = inputs / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    checked = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    for name in (CANONICAL_INPUTS["gtfs"], CANONICAL_INPUTS["trip_id_to_date"]):
        provenance["inputs"][name].update(status="unchanged", checkedAt=checked)
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
    built = []

    def runner(command, stdout, stderr, check, timeout):
        assert stderr is not None
        assert check is False
        if command[1] == "run" and "--entrypoint" in command:
            # The generation builder first verifies the new image-user volume mount.
            assert timeout == 30
            assert command[command.index("--entrypoint") + 1] == "/bin/sh"
            assert any(
                item.startswith("type=volume,") and item.endswith("dst=/data") for item in command
            )
            assert 'test "$(id -u)" = 100' in command[-1]
            stdout.write("uid=100(motis) gid=101(motis) writable /data\n")
        elif command[1] == "run":
            # This is the actual import container, distinct from volume preflight.
            assert timeout == 600
            assert any(
                item.startswith("type=volume,") and item.endswith("dst=/data") for item in command
            )
            stdout.write("synthetic import success\n")
        elif command[1] == "cp":
            assert timeout == 600
            Path(command[-1], "graph.bin").write_bytes(b"synthetic graph")
            stdout.write("synthetic volume export success\n")
        else:
            raise AssertionError(f"Unexpected Docker command: {command}")
        return SimpleNamespace(returncode=0)

    def build(name, geocoding=False):
        directory = build_generation(
            inputs,
            tmp_path / name,
            datetime.now(UTC).date(),
            geocoding=geocoding,
            runner=runner,
        )
        built.append(directory)
        return directory

    return build


def make_binding(generation_dir, token, *, origin="http://127.0.0.1:59081"):
    generation_dir = Path(generation_dir)
    probe = generation_dir / f"probe-{token}.json"
    source_check = generation_dir / f"source-check-{token}.json"
    probe.write_text("{}\n", encoding="utf-8")
    source_check.write_text("{}\n", encoding="utf-8")
    generation = Generation.load(generation_dir / "manifest.json")
    raw = {
        "generationDir": str(generation_dir.resolve()),
        "engineOrigin": origin,
        "probePath": str(probe.resolve()),
        "sourceCheckPath": str(source_check.resolve()),
        "activationToken": token,
        "generationId": generation.id,
    }
    path = generation_dir / f"binding-{token}.json"
    write_binding(path, raw)
    return path


def select_file(path, binding_path):
    data = json.loads(binding_path.read_text(encoding="utf-8"))
    temporary = path.with_suffix(".next")
    temporary.write_text(json.dumps(data), encoding="utf-8")
    os.replace(temporary, path)


def lease_for(binding, client=None, generation_override=None):
    generation = generation_override or Generation.load(binding.generation_dir / "manifest.json")
    snapshot = SimpleNamespace(generation=generation, motis=None)
    return SnapshotLease(snapshot, client or FakeClient())


def test_reload_publishes_complete_snapshot_and_retires_old_after_grace(
    generation_factory, tmp_path
):
    async def run():
        old_dir = generation_factory("old")
        new_dir = generation_factory("new", geocoding=True)
        old_binding = make_binding(old_dir, "old-token")
        new_binding = make_binding(new_dir, "new-token")
        current = tmp_path / "current.json"
        select_file(current, old_binding)
        old_client = FakeClient()
        old_binding_obj = read_binding(current, tmp_path)
        old_lease = lease_for(old_binding_obj, old_client)
        started = asyncio.Event()
        release = asyncio.Event()
        new_client = FakeClient()

        async def factory(binding):
            started.set()
            await release.wait()
            return lease_for(binding, new_client)

        manager = SnapshotManager(
            current,
            factory,
            tmp_path / "acks",
            0.02,
            initial_lease=old_lease,
            managed_root=tmp_path,
        )
        captured = manager.current_snapshot
        select_file(current, new_binding)
        reload_task = asyncio.create_task(manager.reload_current("new-token"))
        await started.wait()
        assert manager.current_snapshot is captured
        release.set()
        new_snapshot = await reload_task
        assert manager.current_snapshot is new_snapshot
        assert captured is old_lease.snapshot
        ack_name = activation_ack_filename("new-token", manager.worker_incarnation_id)
        ack = json.loads((tmp_path / "acks" / ack_name).read_text(encoding="utf-8"))
        assert ack["generationId"] == new_snapshot.generation.id
        assert ack["engineOrigin"] == "http://127.0.0.1:59081"
        assert ack["workerId"] == "api-worker"
        assert ack["workerIncarnationId"] == manager.worker_incarnation_id
        assert not old_client.closed
        await asyncio.sleep(0.25)
        assert old_client.closed
        assert (
            tmp_path / "acks" / retirement_ack_filename("old-token", manager.worker_incarnation_id)
        ).is_file()
        await manager.aclose()
        assert new_client.closed

    asyncio.run(run())


def test_snapshot_lease_owns_both_provider_clients_until_shutdown(generation_factory, tmp_path):
    class Catalog:
        def __init__(self):
            self.closed = False

        def lookup(self, osm_type, full_osm_id):
            return None

        def close(self):
            self.closed = True

    async def run():
        class GateClient(FakeClient):
            def __init__(self, started, release):
                super().__init__()
                self.started = started
                self.release = release

            async def aclose(self):
                self.started.set()
                await self.release.wait()
                self.closed = True

        directory = generation_factory("multi-provider")
        binding_path = make_binding(directory, "multi-provider-token")
        current = tmp_path / "current.json"
        select_file(current, binding_path)
        started, release = asyncio.Event(), asyncio.Event()
        motis_client = GateClient(started, release)
        photon_client = FakeClient()
        catalog = Catalog()
        snapshot = SimpleNamespace(
            generation=Generation.load(directory / "manifest.json"),
            motis=None,
            address_provider=SimpleNamespace(client=photon_client, catalog=catalog),
        )
        lease = SnapshotLease(snapshot, motis_client, (photon_client,))
        manager = SnapshotManager(
            current,
            lambda _: lease,
            tmp_path / "acks",
            0.01,
            initial_lease=lease,
            managed_root=tmp_path,
        )
        close_waiter = asyncio.create_task(manager.aclose())
        await started.wait()
        close_waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await close_waiter
        release.set()
        await manager.aclose()
        assert motis_client.closed and photon_client.closed and catalog.closed

    asyncio.run(run())


def test_stale_token_does_not_call_factory_or_replace_snapshot(generation_factory, tmp_path):
    async def run():
        directory = generation_factory("stale")
        binding_path = make_binding(directory, "current-token")
        current = tmp_path / "current.json"
        select_file(current, binding_path)
        original = lease_for(read_binding(current, tmp_path))
        calls = []

        async def factory(binding):
            calls.append(binding.activation_token)
            return lease_for(binding)

        manager = SnapshotManager(
            current,
            factory,
            tmp_path / "acks",
            0.001,
            initial_lease=original,
            managed_root=tmp_path,
        )
        with pytest.raises(RuntimeError, match="no longer current"):
            await manager.reload_current("stale-token")
        assert manager.current_snapshot is original.snapshot
        assert calls == []
        await manager.aclose()

    asyncio.run(run())


def test_bad_factory_snapshot_closes_candidate_and_keeps_old(generation_factory, tmp_path):
    async def run():
        old_dir = generation_factory("factory-old")
        new_dir = generation_factory("factory-new", geocoding=True)
        old_path = make_binding(old_dir, "old")
        new_path = make_binding(new_dir, "new")
        current = tmp_path / "current.json"
        select_file(current, old_path)
        original = lease_for(read_binding(current, tmp_path))
        candidate_client = FakeClient()

        async def factory(binding):
            wrong_generation = Generation.load(old_dir / "manifest.json")
            return lease_for(binding, candidate_client, wrong_generation)

        manager = SnapshotManager(
            current,
            factory,
            tmp_path / "acks",
            0.001,
            initial_lease=original,
            managed_root=tmp_path,
        )
        select_file(current, new_path)
        with pytest.raises(ValueError, match="differs from the binding"):
            await manager.reload_current("new")
        assert manager.current_snapshot is original.snapshot
        assert candidate_client.closed
        await manager.aclose()

    asyncio.run(run())


def test_ack_failure_rolls_back_in_memory_and_closes_candidate(generation_factory, tmp_path):
    async def run():
        old_dir = generation_factory("ack-old")
        new_dir = generation_factory("ack-new", geocoding=True)
        old_path = make_binding(old_dir, "old")
        new_path = make_binding(new_dir, "new")
        current = tmp_path / "current.json"
        select_file(current, old_path)
        original = lease_for(read_binding(current, tmp_path))
        candidate_client = FakeClient()
        blocked_acks = tmp_path / "ack-file"
        blocked_acks.write_text("not a directory", encoding="utf-8")

        async def factory(binding):
            return lease_for(binding, candidate_client)

        manager = SnapshotManager(
            current,
            factory,
            blocked_acks,
            0.001,
            initial_lease=original,
            managed_root=tmp_path,
        )
        select_file(current, new_path)
        with pytest.raises((FileExistsError, NotADirectoryError, OSError)):
            await manager.reload_current("new")
        assert manager.current_snapshot is original.snapshot
        assert candidate_client.closed
        await manager.aclose()

    asyncio.run(run())


def test_binding_path_containment_and_freshness_factory(generation_factory, tmp_path):
    async def run():
        old_dir = generation_factory("fresh-old")
        stale_dir = generation_factory("fresh-stale", geocoding=True)
        old_path = make_binding(old_dir, "old")
        stale_path = make_binding(stale_dir, "stale")
        manifest_path = stale_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["sourceCheckedAt"] = "2026-09-20T00:00:00+00:00"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        current = tmp_path / "current.json"
        select_file(current, old_path)
        original = lease_for(read_binding(current, tmp_path))

        async def factory(binding):
            generation = Generation.load(binding.generation_dir / "manifest.json")
            if generation.freshness(datetime.now(UTC)) != "current":
                raise ValueError("Candidate source freshness is not current")
            return lease_for(binding)

        manager = SnapshotManager(
            current,
            factory,
            tmp_path / "acks",
            0.001,
            initial_lease=original,
            managed_root=tmp_path,
        )
        select_file(current, stale_path)
        with pytest.raises(ValueError, match="freshness"):
            await manager.reload_current("stale")
        assert manager.current_snapshot is original.snapshot
        with pytest.raises(ValueError, match="escapes generations root"):
            from opentransit.build.activation import validate_binding

            (tmp_path / "generations").mkdir()
            validate_binding(
                {**json.loads(stale_path.read_text()), "generationDir": str(tmp_path)},
                generations_root=tmp_path / "generations",
            )
        await manager.aclose()

    asyncio.run(run())


@pytest.mark.skipif(os.name != "posix", reason="atomic symlink activation is Linux/POSIX-only")
def test_atomic_current_pointer_and_restore(generation_factory, tmp_path):
    root = tmp_path
    first_dir = generation_factory("pointer-first")
    second_dir = generation_factory("pointer-second", geocoding=True)
    first = make_binding(first_dir, "pointer-one")
    second = make_binding(second_dir, "pointer-two")
    rollback = make_binding(first_dir, "pointer-rollback")
    current = root / "current"
    prior = activate_current(root, current, first)
    assert prior is None
    assert read_binding(current, root).activation_token == "pointer-one"
    prior = activate_current(root, current, second)
    assert prior == first.relative_to(root).as_posix()
    assert read_binding(current, root).activation_token == "pointer-two"
    assert restore_current_if_current(root, current, "pointer-two", rollback)
    assert read_binding(current, root).activation_token == "pointer-rollback"


@pytest.mark.skipif(os.name != "posix", reason="atomic symlink activation is Linux/POSIX-only")
def test_failed_candidate_keeps_snapshot_then_fresh_rollback_reactivates_old_generation(
    generation_factory, tmp_path
):
    async def run():
        root = tmp_path
        old_dir = generation_factory("rollback-old")
        new_dir = generation_factory("rollback-new", geocoding=True)
        old_path = make_binding(old_dir, "rollback-old")
        new_path = make_binding(new_dir, "rollback-new")
        fresh_old_path = make_binding(old_dir, "rollback-old-fresh")
        current = root / "current"
        activate_current(root, current, old_path)
        original = lease_for(read_binding(current, root))

        async def factory(binding):
            if binding.activation_token == "rollback-new":
                raise ValueError("Candidate coverage/freshness is not current")
            return lease_for(binding)

        manager = SnapshotManager(
            current,
            factory,
            root / "acks",
            0.001,
            initial_lease=original,
            managed_root=root,
        )
        activate_current(root, current, new_path)
        with pytest.raises(ValueError, match="freshness"):
            await manager.reload_current("rollback-new")
        assert manager.current_snapshot is original.snapshot
        assert read_binding(current, root).activation_token == "rollback-new"
        failure_name = activation_failure_ack_filename(
            "rollback-new", manager.worker_incarnation_id
        )
        failure = json.loads((root / "acks" / failure_name).read_text(encoding="utf-8"))
        assert failure["activeOperationToken"] == "rollback-old"
        assert failure["workerIncarnationId"] == manager.worker_incarnation_id

        assert restore_current_if_current(root, current, "rollback-new", fresh_old_path)
        await manager.reload_current("rollback-old-fresh")
        assert manager.current_snapshot.generation.id == original.snapshot.generation.id
        assert manager.current_binding.activation_token == "rollback-old-fresh"
        await manager.aclose()

    asyncio.run(run())


def test_binding_factory_rechecks_token_before_publication(generation_factory, tmp_path):
    async def run():
        old_dir = generation_factory("race-old")
        new_dir = generation_factory("race-new", geocoding=True)
        old_path = make_binding(old_dir, "race-old")
        new_path = make_binding(new_dir, "race-new")
        current = tmp_path / "current.json"
        select_file(current, old_path)
        original = lease_for(read_binding(current, tmp_path))
        candidate_client = FakeClient()
        entered, release = asyncio.Event(), asyncio.Event()

        async def factory(binding):
            entered.set()
            await release.wait()
            return lease_for(binding, candidate_client)

        manager = SnapshotManager(
            current,
            factory,
            tmp_path / "acks",
            0.001,
            initial_lease=original,
            managed_root=tmp_path,
        )
        select_file(current, new_path)
        task = asyncio.create_task(manager.reload_current("race-new"))
        await entered.wait()
        select_file(current, old_path)
        release.set()
        with pytest.raises(RuntimeError, match="changed while"):
            await task
        assert manager.current_snapshot is original.snapshot
        assert candidate_client.closed
        await manager.aclose()

    asyncio.run(run())


def test_restart_same_binding_has_distinct_worker_incarnation_ack(generation_factory, tmp_path):
    async def run():
        directory = generation_factory("restart")
        binding_path = make_binding(directory, "persisted-operation")
        current = tmp_path / "current.json"
        select_file(current, binding_path)
        client1 = FakeClient()

        async def factory1(binding):
            return lease_for(binding, client1)

        first = SnapshotManager(
            current,
            factory1,
            tmp_path / "acks",
            0.001,
            managed_root=tmp_path,
        )
        await first.initialize()
        incarnation1 = first.worker_incarnation_id
        await first.aclose()

        client2 = FakeClient()

        async def factory2(binding):
            return lease_for(binding, client2)

        second = SnapshotManager(
            current,
            factory2,
            tmp_path / "acks",
            0.001,
            managed_root=tmp_path,
        )
        await second.initialize()
        incarnation2 = second.worker_incarnation_id
        assert incarnation1 != incarnation2
        for incarnation in (incarnation1, incarnation2):
            ack = json.loads(
                (
                    tmp_path / "acks" / activation_ack_filename("persisted-operation", incarnation)
                ).read_text(encoding="utf-8")
            )
            assert ack["workerIncarnationId"] == incarnation
        await second.aclose()

    asyncio.run(run())


def test_shutdown_during_blocked_factory_closes_candidate_and_active_without_publish(
    generation_factory, tmp_path
):
    async def run():
        old_dir = generation_factory("shutdown-old")
        new_dir = generation_factory("shutdown-new", geocoding=True)
        old_path = make_binding(old_dir, "shutdown-old")
        new_path = make_binding(new_dir, "shutdown-new")
        current = tmp_path / "current.json"
        select_file(current, old_path)
        old_client = FakeClient()
        original = lease_for(read_binding(current, tmp_path), old_client)
        entered, release = asyncio.Event(), asyncio.Event()
        candidate_client = FakeClient()

        async def factory(binding):
            entered.set()
            await release.wait()
            return lease_for(binding, candidate_client)

        manager = SnapshotManager(
            current,
            factory,
            tmp_path / "acks",
            0.001,
            initial_lease=original,
            managed_root=tmp_path,
        )
        select_file(current, new_path)
        reload_task = asyncio.create_task(manager.reload_current("shutdown-new"))
        await entered.wait()
        shutdown_task = asyncio.create_task(manager.aclose())
        await asyncio.sleep(0)
        assert manager._closed
        release.set()
        with pytest.raises(RuntimeError, match="closed"):
            await reload_task
        await shutdown_task
        assert manager.current_snapshot is None
        assert candidate_client.closed
        assert old_client.closed

    asyncio.run(run())


def test_cancelled_shutdown_waiter_does_not_cancel_cleanup(generation_factory, tmp_path):
    async def run():
        directory = generation_factory("shutdown-cancel")
        binding_path = make_binding(directory, "shutdown-cancel")
        current = tmp_path / "current.json"
        select_file(current, binding_path)
        client = FakeClient()

        async def factory(binding):
            return lease_for(binding, client)

        manager = SnapshotManager(current, factory, tmp_path / "acks", 0.001, managed_root=tmp_path)
        await manager.initialize()
        waiter = asyncio.create_task(manager.aclose())
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert manager._shutdown_task is not None
        await manager._shutdown_task
        assert client.closed
        assert manager.current_snapshot is None
        await manager.aclose()

    asyncio.run(run())


def test_failed_client_close_is_retryable(generation_factory, tmp_path):
    class RetryClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def aclose(self):
            self.calls += 1
            if self.calls == 1:
                raise OSError("transient close failure")
            self.closed = True

    async def run():
        directory = generation_factory("close-retry")
        binding_path = make_binding(directory, "close-retry")
        current = tmp_path / "current.json"
        select_file(current, binding_path)
        client = RetryClient()

        async def factory(binding):
            return lease_for(binding, client)

        manager = SnapshotManager(current, factory, tmp_path / "acks", 0.001, managed_root=tmp_path)
        await manager.initialize()
        with pytest.raises(BaseExceptionGroup):
            await manager.aclose()
        assert not client.closed
        await manager.aclose()
        assert client.closed
        assert client.calls == 2

    asyncio.run(run())


@pytest.mark.skipif(os.name != "posix", reason="atomic symlink activation is Linux/POSIX-only")
def test_rollback_cas_does_not_overwrite_later_selection(generation_factory, tmp_path):
    root = tmp_path
    first_dir = generation_factory("cas-first")
    second_dir = generation_factory("cas-second", geocoding=True)
    third_dir = generation_factory("cas-third", geocoding=True)
    first = make_binding(first_dir, "cas-old")
    failed = make_binding(second_dir, "cas-failed")
    later = make_binding(third_dir, "cas-later")
    rollback = make_binding(first_dir, "cas-rollback")
    current = root / "current"
    activate_current(root, current, first)
    activate_current(root, current, failed)
    activate_current(root, current, later)
    assert not restore_current_if_current(root, current, "cas-failed", rollback)
    assert read_binding(current, root).activation_token == "cas-later"


def test_same_operation_token_cannot_replay_different_binding(generation_factory, tmp_path):
    async def run():
        first_dir = generation_factory("same-token-first")
        second_dir = generation_factory("same-token-second", geocoding=True)
        first_path = make_binding(first_dir, "same-op")
        current = tmp_path / "current.json"
        select_file(current, first_path)

        async def factory(binding):
            return lease_for(binding)

        manager = SnapshotManager(current, factory, tmp_path / "acks", 0.001, managed_root=tmp_path)
        await manager.initialize()
        replacement = make_binding(second_dir, "same-op")
        select_file(current, replacement)
        with pytest.raises(RuntimeError, match="reused for a different binding"):
            await manager.reload_current("same-op")
        await manager.aclose()

    asyncio.run(run())
