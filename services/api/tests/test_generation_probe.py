"""Synthetic structural candidate probe tests; no Docker or network is used."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import pytest

from opentransit.build.generations import CANONICAL_INPUTS
from opentransit.build.generations import build_generation as generation_builder
from opentransit.build.probe import probe_generation

pytest_plugins = ["test_generation_build"]


@pytest.fixture
def current_generation(inputs, tmp_path):
    provenance_path = inputs / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    checked = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
    for name in (CANONICAL_INPUTS["gtfs"], CANONICAL_INPUTS["trip_id_to_date"]):
        provenance["inputs"][name].update(status="unchanged", checkedAt=checked)
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    def runner(command, stdout, stderr, check, timeout):
        if "--entrypoint" in command:
            stdout.write("uid=100 gid=101 writable /data\n")
        elif command[1] == "cp":
            from pathlib import Path

            (Path(command[-1]) / "graph.bin").write_bytes(b"synthetic graph")
        return type("Result", (), {"returncode": 0})()

    return generation_builder(
        inputs,
        tmp_path / "candidate",
        datetime.now(UTC).date(),
        runner=runner,
    )


def journey(identifier="J01", departure=None):
    return {
        "id": identifier,
        "params": {
            "fromPlace": "32.08,34.78",
            "toPlace": "32.09,34.79",
            "time": (departure or datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
            "numItineraries": "1",
        },
    }


def _probe(*args, **kwargs):
    return asyncio.run(probe_generation(*args, **kwargs))


def response_payload():
    return {
        "itineraries": [
            {
                "transfers": 0,
                "legs": [
                    {
                        "scheduledStartTime": "2026-09-30T08:00:00+03:00",
                        "scheduledEndTime": "2026-09-30T08:20:00+03:00",
                    }
                ],
            }
        ],
        "direct": [],
    }


def test_probe_records_verified_structural_result_exclusively(current_generation, tmp_path):
    current = datetime.now(UTC)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response_payload()))
    result = _probe(
        current_generation,
        "http://127.0.0.1:58082",
        [journey(departure=current + timedelta(minutes=1))],
        transport=transport,
        now=current,
    )
    assert result["status"] == "passed"
    assert result["structuralOnly"] is True
    assert result["humanH3Approval"] is False
    assert result["journeyIds"] == ["J01"]
    assert result["caseCount"] == 1
    assert len(result["corpusSha256"]) == 64
    assert result["warnings"]
    assert result["journeys"][0]["structure"]["itineraries"][0]["legCount"] == 1
    assert len(result["journeys"][0]["responseSha256"]) == 64
    assert json.loads((current_generation / "probe.json").read_text(encoding="utf-8")) == result
    with pytest.raises(FileExistsError):
        _probe(current_generation, "http://127.0.0.1:58082", [journey()], transport=transport)


def test_probe_fails_bad_engine_response_and_still_preserves_report(current_generation):
    current = datetime.now(UTC)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"itineraries": {}}))
    result = _probe(
        current_generation,
        "http://localhost:58082",
        [journey(departure=current + timedelta(minutes=1))],
        transport=transport,
        now=current,
    )
    assert result["status"] == "failed"
    assert result["journeys"][0]["status"] == "failed"
    assert (current_generation / "probe.json").is_file()


@pytest.mark.parametrize(
    ("response", "expected_status", "observed"),
    [
        (response_payload(), "passed", "route"),
        ({"itineraries": [], "direct": []}, "passed", "no_route"),
        ({"itineraries": [{"legs": [], "transfers": 0}], "direct": []}, "failed", None),
    ],
)
def test_either_outcome_accepts_valid_route_or_empty_and_rejects_malformed(
    current_generation, tmp_path, response, expected_status, observed
):
    current = datetime.now(UTC)
    query = journey(departure=current + timedelta(minutes=1))
    query["expect"] = {"outcome": "either"}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response))
    result = _probe(
        current_generation,
        "http://127.0.0.1:58082",
        [query],
        transport=transport,
        now=current,
        report_path=tmp_path / f"either-{expected_status}-{observed}.json",
    )
    entry = result["journeys"][0]
    assert result["status"] == expected_status
    assert entry["status"] == expected_status
    if observed is not None:
        assert entry["structure"]["outcome"] == observed


def test_probe_rejects_unknown_outcome_label(current_generation, tmp_path):
    current = datetime.now(UTC)
    query = journey(departure=current + timedelta(minutes=1))
    query["expect"] = {"outcome": "no-route"}
    result = _probe(
        current_generation,
        "http://127.0.0.1:58082",
        [query],
        now=current,
        report_path=tmp_path / "unknown-outcome.json",
    )
    assert result["status"] == "failed"
    assert "expected outcome" in result["failure"]


def test_probe_blocks_stale_candidate_and_rejects_non_loopback_url(current_generation, tmp_path):
    current = datetime.now(UTC)
    stale = _probe(
        current_generation,
        "http://127.0.0.1:58082",
        [journey(departure=current + timedelta(minutes=1))],
        now=current + timedelta(days=8),
        report_path=tmp_path / "stale-probe.json",
    )
    assert stale["status"] == "failed"
    assert "freshness" in stale["failure"]

    remote = _probe(
        current_generation,
        "http://example.com",
        [journey(departure=current + timedelta(minutes=1))],
        now=current,
        report_path=tmp_path / "remote-probe.json",
    )
    assert remote["status"] == "failed"
    assert "loopback" in remote["failure"]


def test_probe_count_guard_blocks_drop_and_requires_override(current_generation, tmp_path):
    active = tmp_path / "active"
    active.mkdir()
    # Construct only the minimal valid artifacts needed by the common verifier.
    graph = active / "motis"
    graph.mkdir()
    graph_file = graph / "graph.bin"
    graph_file.write_bytes(b"graph")
    config = active / "config.yml"
    config.write_bytes(b"config\n")
    reference = active / "reference.sqlite"
    reference.write_bytes(b"reference")
    graph_hash = hashlib.sha256(b"graph").hexdigest()
    ref_hash = hashlib.sha256(b"reference").hexdigest()
    config_hash = hashlib.sha256(b"config\n").hexdigest()
    tree_hash = hashlib.sha256(f"graph.bin\0{5}\0{graph_hash}\n".encode()).hexdigest()
    active_manifest = {
        "generationId": "active",
        "state": "ready",
        "engineDigest": "sha256:" + "a" * 64,
        "artifacts": {
            "motis": {
                "path": "motis",
                "sha256": tree_hash,
                "files": [{"path": "graph.bin", "bytes": 5, "sha256": graph_hash}],
            },
            "config": {"path": "config.yml", "sha256": config_hash},
            "reference": {
                "path": "reference.sqlite",
                "sha256": ref_hash,
                "counts": {"stops": 20, "routes": 10},
            },
        },
    }
    (active / "manifest.json").write_text(json.dumps(active_manifest), encoding="utf-8")
    candidate_counts = json.loads(
        (current_generation / "manifest.json").read_text(encoding="utf-8")
    )["artifacts"]["reference"]["counts"]
    active_manifest["artifacts"]["reference"]["counts"] = {
        "stops": candidate_counts["stops"] * 3,
        "routes": candidate_counts["routes"] * 3,
    }
    (active / "manifest.json").write_text(json.dumps(active_manifest), encoding="utf-8")
    current = datetime.now(UTC)
    result = _probe(
        current_generation,
        "http://127.0.0.1:58082",
        [journey(departure=current + timedelta(minutes=1))],
        active_dir=active,
        now=current,
        report_path=tmp_path / "guard.json",
    )
    assert result["status"] == "failed"
    assert "count drop" in result["failure"]


@pytest.mark.parametrize("source_type", ["params", "request-url"])
def test_probe_records_corpus_hash_and_explicit_override_times(
    current_generation, tmp_path, source_type
):
    current = datetime.now(UTC)
    original = "2026-09-07T08:00:00+03:00"
    requested = (current + timedelta(minutes=2)).isoformat()
    query_string = urlencode(
        {"fromPlace": "32.08,34.78", "toPlace": "32.09,34.79", "time": original}
    )
    query = {"id": "J01", "probeTime": requested, "expect": {"outcome": "route"}}
    if source_type == "params":
        query["params"] = {
            "fromPlace": "32.08,34.78",
            "toPlace": "32.09,34.79",
            "time": original,
        }
    else:
        query["request"] = {"url": f"http://example.test/api/v6/plan?{query_string}"}
    corpus = tmp_path / "selected-h3.json"
    corpus.write_text(json.dumps({"cases": [query]}), encoding="utf-8")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response_payload()))
    result = _probe(
        current_generation,
        "http://127.0.0.1:58082",
        corpus,
        transport=transport,
        now=current,
        report_path=tmp_path / "override-report.json",
    )
    assert result["corpusSha256"] == hashlib.sha256(corpus.read_bytes()).hexdigest()
    entry = result["journeys"][0]
    assert entry["sourceDepartureTime"] == original
    assert entry["departureTime"] == requested


def test_probe_rejects_more_than_ten_instead_of_truncating(current_generation, tmp_path):
    current = datetime.now(UTC)
    queries = [journey(f"J{i:02d}", current + timedelta(minutes=1)) for i in range(11)]
    report_path = tmp_path / "too-many.json"
    result = _probe(
        current_generation,
        "http://127.0.0.1:58082",
        queries,
        now=current,
        report_path=report_path,
    )
    assert result["status"] == "failed"
    assert "at most 10" in result["failure"]
    assert report_path.is_file()


def test_probe_total_deadline_and_cancellation_preserve_reports(current_generation, tmp_path):
    current = datetime.now(UTC)

    async def slow(request):
        await asyncio.sleep(2)
        return httpx.Response(200, json=response_payload())

    timed_out = _probe(
        current_generation,
        "http://127.0.0.1:58082",
        [journey(departure=current + timedelta(minutes=1))],
        transport=httpx.MockTransport(slow),
        now=current,
        report_path=tmp_path / "timeout.json",
    )
    assert timed_out["journeys"][0]["failure"].startswith("TimeoutError:")
    assert (tmp_path / "timeout.json").is_file()

    async def cancel():
        task = asyncio.create_task(
            probe_generation(
                current_generation,
                "http://127.0.0.1:58082",
                [journey(departure=current + timedelta(minutes=1))],
                transport=httpx.MockTransport(slow),
                now=current,
                report_path=tmp_path / "cancelled.json",
            )
        )
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return
        raise AssertionError("Cancelled probe unexpectedly returned")

    asyncio.run(cancel())
    assert (
        json.loads((tmp_path / "cancelled.json").read_text(encoding="utf-8"))["status"] == "failed"
    )
