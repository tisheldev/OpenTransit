"""Local operator activation/rollback tests use synthetic generations and a real manager."""

import asyncio
import json
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_activation import FakeClient, generation_factory, lease_for  # noqa: F401
from test_generation_build import inputs  # noqa: F401

from opentransit.activation import SnapshotManager
from opentransit.api.lifecycle import _process_start_identity
from opentransit.build import local_operator as operator
from opentransit.build.activation import (
    activate_current,
    current_target,
    read_binding,
    read_binding_metadata,
    retirement_ack_filename,
    write_binding,
)
from opentransit.build.cli import main
from opentransit.core.generation import Generation

posix_only = pytest.mark.skipif(os.name != "posix", reason="atomic pointers need Linux")


def make_binding(generation_dir: Path, token: str, root: Path, *, origin="http://127.0.0.1:59081"):
    generation_dir = Path(generation_dir)
    manifest = json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))
    generation = Generation.load(generation_dir / "manifest.json")
    checked = generation.validated_at
    gtfs = manifest["inputs"]["israel-public-transportation.zip"]["sha256"]
    mapping = manifest["inputs"]["TripIdToDate.zip"]["sha256"]
    source_check = generation_dir / f"source-check-{token}.json"
    source_check.write_text(
        json.dumps(
            {
                "pairedValidation": "passed",
                "validation": {"valid": True},
                "validatedAt": checked.isoformat(),
                "sources": {
                    "gtfs": {"status": "new", "sha256": gtfs, "checkedAt": checked.isoformat()},
                    "trip_id_to_date": {
                        "status": "new",
                        "sha256": mapping,
                        "checkedAt": checked.isoformat(),
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    probe = generation_dir / f"probe-{token}.json"
    probe.write_text("{}\n", encoding="utf-8")
    raw = {
        "generationDir": str(generation_dir.resolve()),
        "engineOrigin": origin,
        "probePath": str(probe.resolve()),
        "sourceCheckPath": str(source_check.resolve()),
        "activationToken": token,
        "generationId": generation.id,
    }
    path = root / f"binding-{token}.json"
    write_binding(path, raw, root)
    return path


class Worker:
    """A real SnapshotManager on a background loop plus the operator's signal seam."""

    def __init__(self, root, current, factory, initial, deadline=0.01):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.root = root
        self.signalled = []

        async def build():
            return SnapshotManager(
                current,
                factory,
                root / "acks",
                deadline,
                initial_lease=initial,
                managed_root=root,
            )

        self.manager = asyncio.run_coroutine_threadsafe(build(), self.loop).result(5)
        workers = root / "acks" / "workers"
        workers.mkdir(parents=True)
        (workers / "worker.json").write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "processStartId": _process_start_identity(os.getpid()),
                    "controlSignal": "SIGUSR1",
                    "workerIncarnationId": self.manager.worker_incarnation_id,
                }
            ),
            encoding="utf-8",
        )

    def signaller(self, record):
        token = read_binding_metadata(self.root / "current", self.root)["activationToken"]
        self.signalled.append(token)

        async def reload():
            try:
                await self.manager.reload_current(token)
            except Exception:
                pass

        asyncio.run_coroutine_threadsafe(reload(), self.loop)

    def close(self):
        asyncio.run_coroutine_threadsafe(self.manager.aclose(), self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)


@pytest.fixture
def served(generation_factory, tmp_path):  # noqa: F811
    root = tmp_path.resolve()
    old_dir = generation_factory("op-old")
    new_dir = generation_factory("op-new", geocoding=True)
    old = make_binding(old_dir, "op-old-1", root)
    new = make_binding(new_dir, "op-new-1", root)
    current = root / "current"
    activate_current(root, current, old)
    original = lease_for(read_binding(current, root))
    rejected = {"tokens": set()}

    async def factory(binding):
        if binding.activation_token in rejected["tokens"]:
            raise ValueError("candidate rejected")
        return lease_for(binding)

    worker = Worker(root, current, factory, original)
    yield SimpleNamespaceLike(
        root=root,
        current=current,
        old=old,
        new=new,
        old_dir=old_dir,
        new_dir=new_dir,
        original=original,
        worker=worker,
        rejected=rejected,
    )
    worker.close()


class SimpleNamespaceLike:
    def __init__(self, **values):
        self.__dict__.update(values)


@posix_only
def test_currency_check_names_each_expiry_reason(served):
    binding = read_binding(served.old, served.root)
    now = datetime.now(UTC)
    assert operator.check_currency(binding, now)["freshness"] == "current"
    with pytest.raises(operator.ActivationRefused) as stale:
        operator.check_currency(binding, now + timedelta(days=3))
    assert stale.value.reasons == ["source_stale"]
    rollback_binding = read_binding(
        operator.reissue_binding(served.root, served.old, "rollback"), served.root, verify=False
    )
    assert (
        operator.check_currency(rollback_binding, now + timedelta(days=3))["freshness"] == "stale"
    )
    with pytest.raises(operator.ActivationRefused) as expired:
        operator.check_currency(binding, now + timedelta(days=90))
    assert "coverage_expired" in expired.value.reasons
    with pytest.raises(operator.ActivationRefused) as early:
        operator.check_currency(binding, now - timedelta(days=5))
    assert "coverage_not_started" in early.value.reasons


@posix_only
def test_activate_waits_for_ack_and_retirement_requires_ten_deadlines(served):
    worker = served.worker
    held = worker.manager.current_snapshot
    result = operator.activate(
        served.root, served.new, served.root / "acks", signaller=worker.signaller, timeout=10
    )
    assert result["status"] == "acknowledged"
    assert result["previousToken"] == "op-old-1"
    assert worker.manager.current_snapshot is not held
    assert worker.manager.current_snapshot.generation.id == result["generationId"]
    retired = operator.await_retirement(
        served.root / "acks",
        old_token="op-old-1",
        new_token="op-new-1",
        incarnation=worker.manager.worker_incarnation_id,
        deadline_seconds=0.01,
        timeout=10,
    )
    assert retired["ackToRetirementSeconds"] >= retired["requiredSeconds"] == pytest.approx(0.1)
    ack_dir = served.root / "acks"
    assert (
        ack_dir / retirement_ack_filename("op-old-1", retired["retirement"]["workerIncarnationId"])
    ).is_file()
    with pytest.raises(operator.ActivationFailed, match="ten request deadlines"):
        operator.await_retirement(
            ack_dir,
            old_token="op-old-1",
            new_token="op-new-1",
            incarnation=worker.manager.worker_incarnation_id,
            deadline_seconds=1.0,
            timeout=1,
        )


@posix_only
def test_await_retirement_times_out_without_acknowledgement(served):
    with pytest.raises(TimeoutError):
        operator.await_retirement(
            served.root / "acks",
            old_token="never",
            new_token="never",
            incarnation=served.worker.manager.worker_incarnation_id,
            deadline_seconds=0.01,
            timeout=0.05,
            poll=0.01,
        )


@posix_only
def test_rejected_candidate_restores_pointer_and_old_snapshot_keeps_serving(served):
    served.rejected["tokens"].add("op-new-1")
    worker = served.worker
    held = worker.manager.current_snapshot
    with pytest.raises(operator.ActivationFailed) as failed:
        operator.activate(
            served.root, served.new, served.root / "acks", signaller=worker.signaller, timeout=10
        )
    detail = failed.value.detail
    assert detail["status"] == "rejected"
    assert detail["failureAck"]["failureCode"] == "factory_rejected"
    assert detail["failureAck"]["failureKind"] == "ValueError"
    assert detail["pointerRestored"] is True
    assert detail["pointerGenerationId"] == held.generation.id
    assert detail["pointerToken"] == detail["restoreToken"] != "op-old-1"
    assert read_binding(served.current, served.root).generation_id == held.generation.id
    assert worker.manager.current_snapshot is held
    assert not served.original.owned_client.closed


@posix_only
def test_unacknowledged_candidate_times_out_and_pointer_is_restored(served):
    with pytest.raises(operator.ActivationFailed) as failed:
        operator.activate(
            served.root,
            served.new,
            served.root / "acks",
            signaller=lambda record: None,
            timeout=0.05,
            poll=0.01,
        )
    assert failed.value.detail["status"] == "timeout"
    assert failed.value.detail["pointerRestored"] is True
    assert read_binding(served.current, served.root).generation_id == (
        served.worker.manager.current_snapshot.generation.id
    )


@posix_only
def test_rollback_refuses_expired_previous_before_touching_pointer(served):
    before = current_target(served.current)
    files_before = sorted(path.name for path in served.root.iterdir())
    future = datetime.now(UTC) + timedelta(days=10)
    with pytest.raises(operator.ActivationRefused) as refused:
        operator.rollback(
            served.root,
            served.old,
            served.root / "acks",
            now=future,
            signaller=served.worker.signaller,
        )
    assert refused.value.reasons == ["source_expired"]
    assert current_target(served.current) == before
    assert sorted(path.name for path in served.root.iterdir()) == files_before
    assert served.worker.signalled == []


@posix_only
def test_stale_generation_may_roll_back_but_a_new_candidate_may_not(served):
    stale = datetime.now(UTC) + timedelta(days=3)
    eligible = operator.rollback(
        served.root, served.old, served.root / "acks", now=stale, check_only=True
    )
    assert eligible["status"] == "eligible"
    assert eligible["currency"]["freshness"] == "stale"
    with pytest.raises(operator.ActivationRefused) as refused:
        operator.activate(
            served.root,
            served.new,
            served.root / "acks",
            now=stale,
            signaller=served.worker.signaller,
        )
    assert refused.value.reasons == ["source_stale"]
    assert served.worker.signalled == []


@posix_only
def test_rollback_to_valid_previous_uses_fresh_token(served):
    worker = served.worker
    operator.activate(
        served.root, served.new, served.root / "acks", signaller=worker.signaller, timeout=10
    )
    result = operator.rollback(
        served.root, served.old, served.root / "acks", signaller=worker.signaller, timeout=10
    )
    assert result["action"] == "rollback"
    assert result["status"] == "acknowledged"
    assert result["token"] not in {"op-old-1", "op-new-1"}
    assert result["previousToken"] == "op-new-1"
    assert (
        worker.manager.current_snapshot.generation.id
        == read_binding(served.old, served.root).generation_id
    )


@posix_only
def test_cli_reports_refusal_without_touching_pointer(served, capsys):
    before = current_target(served.current)
    code = main(
        [
            "rollback",
            "--managed-root",
            str(served.root),
            "--ack-dir",
            str(served.root / "acks"),
            "--binding",
            str(served.old),
            "--now",
            (datetime.now(UTC) + timedelta(days=90)).isoformat(),
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert code == 2
    assert report["status"] == "refused"
    assert "coverage_expired" in report["reasons"]
    assert current_target(served.current) == before


@posix_only
def test_retirement_gate_uses_the_workers_token_after_a_restored_failure(served):
    worker = served.worker
    ack_dir = served.root / "acks"
    served.rejected["tokens"].add("op-new-1")
    with pytest.raises(operator.ActivationFailed) as failed:
        operator.activate(served.root, served.new, ack_dir, signaller=worker.signaller, timeout=10)
    restore_token = failed.value.detail["restoreToken"]
    served.rejected["tokens"].clear()
    fresh = operator.reissue_binding(served.root, served.new)
    result = operator.activate(served.root, fresh, ack_dir, signaller=worker.signaller, timeout=10)
    # The pointer's previous token is the restored binding, but the worker still served the
    # original binding; retirement is acknowledged under the worker's token.
    assert result["previousToken"] == restore_token
    assert result["retiredOperationToken"] == "op-old-1"
    retired = operator.await_retirement(
        ack_dir,
        old_token=result["retiredOperationToken"],
        new_token=result["token"],
        incarnation=worker.manager.worker_incarnation_id,
        deadline_seconds=0.01,
        timeout=10,
    )
    assert retired["status"] == "retired"
