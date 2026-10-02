"""Pure parts of the live acceptance runner; no Docker, network or real generation is used."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from tools import acceptance_run as acc

COVERAGE = (
    datetime.fromisoformat("2026-10-01T00:00:00+03:00"),
    datetime.fromisoformat("2026-11-01T00:00:00+02:00"),
)
BUNDLED = Path(acc.TOOLS) / "acceptance-probe-corpus.json"


def test_run_id_and_prefix_naming():
    assert acc.sanitize_run_id("oct1b") == "oct1b"
    for bad in ("", "Oct1", "a_b", "-x", "x" * 40, "a b"):
        with pytest.raises(ValueError):
            acc.sanitize_run_id(bad)
    assert acc.container_name("oct1b", "api") == "ot-acc-oct1b-api"
    assert acc.join_prefix("results/acc-1", "summary.json") == Path("results/acc-1-summary.json")
    assert acc.join_prefix("results/acc/", "summary.json") == Path("results/acc/summary.json")
    assert acc.join_prefix("results/acc-dev1-", "summary.json") == Path(
        "results/acc-dev1-summary.json"
    )


def test_output_paths_cover_every_file_and_refuse_existing(tmp_path):
    paths = acc.output_paths(str(tmp_path / "run"))
    assert {"summary", "probe", "readyz", "walk_caps", "demo", "h3_sheet", "h3_raw"} <= paths.keys()
    assert {"search_raw", "search", "h4_sheet", "log_api", "log_motis", "work"} <= paths.keys()
    assert len(set(paths.values())) == len(paths)
    assert acc.existing_outputs(paths) == []
    paths["summary"].write_text("x")
    assert acc.existing_outputs(paths) == [paths["summary"]]


def test_bundled_probe_corpus_is_redated_into_coverage_only_where_needed():
    corpus = json.loads(BUNDLED.read_text(encoding="utf-8"))
    original = json.dumps(corpus, sort_keys=True)
    derived, changes = acc.redate_probe_corpus(corpus, *COVERAGE)
    assert json.dumps(corpus, sort_keys=True) == original  # input never mutated
    assert len(derived["cases"]) == 10
    moved = {item["id"] for item in changes}
    assert moved == {"J04", "J22", "J23"}  # the three September 30 departures
    for case in derived["cases"]:
        when = datetime.fromisoformat(case.get("probeTime") or case["params"]["time"])
        assert COVERAGE[0] <= when < COVERAGE[1]
        if case["id"] in moved:
            original_time = next(c for c in corpus["cases"] if c["id"] == case["id"])["params"][
                "time"
            ]
            before = datetime.fromisoformat(original_time).astimezone(acc.JERUSALEM)
            after = when.astimezone(acc.JERUSALEM)
            assert (before.weekday(), before.timetz().replace(tzinfo=None)) == (
                after.weekday(),
                after.timetz().replace(tzinfo=None),
            )
            assert case["params"]["time"] == original_time  # source preserved beside probeTime
    assert derived["acceptanceRedating"]["changedCaseIds"] == sorted(moved, key=lambda x: x)


def test_redating_preserves_local_clock_across_the_october_dst_change():
    case = {"id": "X", "params": {"time": "2026-09-29T08:00:00+03:00"}}
    late = (
        datetime.fromisoformat("2026-10-25T00:00:00+03:00"),
        datetime.fromisoformat("2026-11-25T00:00:00+02:00"),
    )
    derived, changes = acc.redate_probe_corpus({"cases": [case]}, *late)
    shifted = datetime.fromisoformat(derived["cases"][0]["probeTime"])
    assert shifted.utcoffset().total_seconds() == 2 * 3600  # +02:00 after the fall-back
    assert shifted.astimezone(acc.JERUSALEM).strftime("%H:%M") == "08:00"
    assert changes[0]["id"] == "X"
    # In coverage already: untouched, no redating block
    inside, none = acc.redate_probe_corpus(
        {"cases": [case]}, datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 11, 1, tzinfo=UTC)
    )
    assert none == [] and "probeTime" not in inside["cases"][0]
    assert "acceptanceRedating" not in inside
    with pytest.raises(ValueError):
        acc.redate_probe_corpus({"cases": []}, *COVERAGE)


def test_service_day_is_a_sunday_to_thursday_morning_inside_coverage():
    first = acc.pick_service_day(*COVERAGE)
    assert first == "2026-10-04T08:00:00+03:00"  # Oct 2-3 are Friday/Saturday
    explicit = acc.pick_service_day(*COVERAGE, requested=date(2026, 10, 1))
    assert explicit == "2026-10-01T08:00:00+03:00"
    with pytest.raises(ValueError):
        acc.pick_service_day(*COVERAGE, requested=date(2026, 12, 1))
    after_dst = (
        datetime.fromisoformat("2026-10-23T00:00:00+03:00"),
        datetime.fromisoformat("2026-11-23T00:00:00+02:00"),
    )
    assert acc.pick_service_day(*after_dst) == "2026-10-25T08:00:00+02:00"


def test_verify_fail_count_and_readyz_summary():
    log = "a\n[VERIFY FAIL] query time x\nok\n[VERIFY FAIL] query time y\n"
    assert acc.count_verify_fail(log) == 2 and acc.count_verify_fail("") == 0
    samples = [{"status": 200, "ms": 3.0, "errors": None, "generationId": "g"}] * 47
    samples += [
        {
            "status": 503,
            "ms": 9.0,
            "errors": [{"condition": "engine", "reason": "ENGINE_TIMEOUT"}],
            "generationId": None,
        }
    ] * 2
    samples += [{"status": 0, "ms": 5000.0, "errors": None, "generationId": None}]
    summary = acc.summarize_readyz(samples)
    assert (summary["requests"], summary["ok"], summary["failed"]) == (50, 47, 3)
    assert summary["statuses"] == [0, 200, 503]
    assert summary["failureReasons"] == {"engine:ENGINE_TIMEOUT": 2, "transport:NO_RESPONSE": 1}
    assert summary["generationIds"] == ["g"] and summary["maxMs"] == 5000.0


DEMO = """OpenTransit scheduled journey demo (Dizengoff Center -> Technion)
  API:        http://127.0.0.1:8500
  Generation: abc123 (real data, freshness current)
  Outcome:    routes_found (2 journey(s))

  Journey 1: depart 08:05 arrive 09:41 (1h36m, 1 transfer(s), walking 12m / 800 m)  [scheduled]
    08:05-08:12  walk       A -> B  [scheduled]
    08:14-08:50  rail       B -> C line 1  [scheduled]
    08:55-09:41  bus        C -> D line 2  [scheduled]

  Journey 2: depart 08:20 arrive 09:59 (1h39m, 0 transfer(s), walking 5m / 300 m)  [scheduled]
    08:20-09:59  rail       B -> D  [scheduled]
"""


def test_demo_output_parsing():
    parsed = acc.parse_demo_output(DEMO)
    assert parsed["generationId"] == "abc123"
    assert (parsed["outcome"], parsed["journeyCount"]) == ("routes_found", 2)
    assert [(j["depart"], j["arrive"], j["legs"]) for j in parsed["journeys"]] == [
        ("08:05", "09:41", 3),
        ("08:20", "09:59", 1),
    ]
    assert parsed["scheduledLabelled"] is True
    empty = acc.parse_demo_output("garbage")
    assert empty["journeyCount"] == 0 and empty["journeys"] == [] and empty["outcome"] is None


def _request(ms):
    return {"processDurationMs": ms}


def _record(category, first, warm=()):
    return {
        "case": {"category": category},
        "firstPass": _request(first),
        "warmRepeats": [_request(value) for value in warm],
    }


def test_percentile_matches_the_evaluators_nearest_rank_rule():
    assert acc.percentile([], 95) is None
    assert acc.percentile([5.0], 95) == 5.0
    assert acc.percentile([float(n) for n in range(1, 21)], 95) == 19.0
    assert acc.percentile([float(n) for n in range(1, 21)], 50) == 10.0


def test_latency_is_reported_overall_and_per_category_for_first_pass_and_all_requests():
    records = [
        _record("address", 40.0, (10.0, 12.0)),
        _record("address", 20.0, (11.0,)),
        _record("station", 5.0, (4.0, 6.0)),
        {"case": {"category": "station"}, "firstPass": {"processDurationMs": None}},
    ]
    latency = acc.latency_by_category(records)
    first = latency["firstPass"]
    assert first["overall"]["count"] == 3 and first["overall"]["maxMs"] == 40.0
    assert first["byCategory"]["address"]["p50Ms"] == 20.0
    assert first["byCategory"]["address"]["p95Ms"] == 40.0
    every = latency["allRequests"]
    assert every["byCategory"]["address"]["count"] == 5
    assert every["byCategory"]["station"]["count"] == 3  # the uncorrelated request is skipped
    assert every["overall"]["count"] == 8


def test_search_summary_scores_latency_and_targets_without_claiming_h4():
    records = [_record("address", 39.0, (10.0,)), _record("address", 41.0, (12.0,))]
    result = {
        "summary": {
            "overall": {"top1": 3, "top5": 4, "denominator": 5},
            "byCategory": {
                "address": {"top1": 2, "top5": 2, "total": 2, "unavailable": 0},
                "venue": {"top1": 1, "top5": 2, "total": 3, "unavailable": 0},
            },
            "byLanguage": {},
            "byCorpus": {},
            "firstPassOutcomes": {"success": 5},
        },
        "timing": {
            "correlation": {
                "verified": True,
                "requestCount": 4,
                "matchedCount": 4,
                "unmatchedCount": 0,
            }
        },
        "records": records,
    }
    summary = acc.search_summary(result)
    assert summary["overall"] == {"top1": 3, "top5": 4, "total": 5}
    assert summary["byCategory"]["venue"]["total"] == 3
    assert summary["logCorrelation"]["unmatchedCount"] == 0
    targets = summary["targets"]
    assert targets["addressTop1Rate"] == 1.0 and targets["addressTop1Meets80Percent"] is True
    assert targets["firstPassP95Meets40Ms"] is False  # nearest-rank p95 of [39, 41] is 41
    assert targets["allRequestsP95Meets40Ms"] is False
    assert summary["humanH4Approval"] is False and "not an H4" in targets["basis"]


def test_source_hashes_cover_files_under_src_prefix(tmp_path):
    (tmp_path / "opentransit" / "api").mkdir(parents=True)
    (tmp_path / "opentransit" / "a.py").write_bytes(b"a")
    (tmp_path / "opentransit" / "api" / "b.js").write_bytes(b"b")
    (tmp_path / "opentransit" / "__pycache__").mkdir()
    (tmp_path / "opentransit" / "__pycache__" / "a.pyc").write_bytes(b"x")
    hashes = acc.source_hashes(tmp_path)
    assert sorted(hashes) == ["src/opentransit/a.py", "src/opentransit/api/b.js"]
    assert hashes["src/opentransit/a.py"] == acc.sha256_file(tmp_path / "opentransit" / "a.py")


def test_overall_status_and_exit_codes():
    ok = {"a": {"status": "PASS"}, "b": {"status": "PASS"}}
    assert acc.overall_status(ok) == "PASS" and acc.exit_code("PASS") == 0
    assert acc.overall_status({**ok, "c": {"status": "FAIL"}}) == "FAIL"
    assert acc.exit_code("FAIL") == 1
    assert acc.overall_status({**ok, "c": {"status": "ERROR"}}) == "ERROR"
    assert acc.overall_status({**ok, "c": {"status": "SKIPPED"}}) == "INCOMPLETE"
    assert acc.exit_code("ERROR") == acc.exit_code("INCOMPLETE") == 2
    assert acc.overall_status({"c": {"status": "FAIL"}, "d": {"status": "ERROR"}}) == "ERROR"


def _option(argv, flag):
    return argv[argv.index(flag) + 1]


def _assert_caps(argv, memory):
    assert _option(argv, "--memory") == memory and _option(argv, "--memory-swap") == memory
    assert "--init" in argv


def test_docker_commands_use_named_capped_isolated_containers(tmp_path):
    generation = tmp_path / "gen"
    motis = acc.motis_argv(
        "r1", "ghcr.io/motis-project/motis@sha256:" + "a" * 64, generation, 8500, None
    )
    assert _option(motis, "--name") == "ot-acc-r1-motis"
    _assert_caps(motis, "2g")
    assert _option(motis, "--publish") == "127.0.0.1:8500:8000"  # loopback only, API port
    assert any("dst=/data,readonly" in item for item in motis)  # the graph is read-only
    assert motis[-4:] == ["/motis", "server", "-d", "/data"]
    assert "--cpus" not in motis
    assert "--cpus" in acc.motis_argv("r1", "img", generation, 8500, "2")

    java = "eclipse-temurin:21.0.12.1_1-jre@sha256:" + "b" * 64
    init = acc.photon_init_argv(
        "r1", java, "ot-acc-r1-photon", generation / "photon" / "photon_data"
    )
    assert _option(init, "--network") == "none" and _option(init, "--user") == "0:0"
    _assert_caps(init, "64m")
    photon = acc.photon_argv("r1", java, "ot-acc-r1-photon", tmp_path / "photon-1.3.0.jar", None)
    _assert_caps(photon, "1g")
    assert _option(photon, "--network") == "container:ot-acc-r1-motis"
    assert "-Xmx512m" in photon and "127.0.0.1" in photon  # loopback listener, heap under the cap

    verifier = acc.verifier_argv(
        "r1", "api:img", generation, tmp_path / "src", tmp_path / "q.json", tmp_path / "work"
    )
    _assert_caps(verifier, "512m")
    assert "--read-only" in verifier and _option(verifier, "--network") == (
        "container:ot-acc-r1-motis"
    )
    assert "probe" in verifier and _option(verifier, "--engine-url") == "http://127.0.0.1:8080"
    assert any(item.endswith("dst=/generation,readonly") for item in verifier)
    assert any(item.endswith("dst=/run/opentransit") for item in verifier)  # only writable mount

    with_photon = acc.api_argv(
        "r1", "api:img", generation, tmp_path / "src", tmp_path / "work", photon=True, cpus=None
    )
    _assert_caps(with_photon, "1g")
    assert "OPENTRANSIT_PROBE=/run/opentransit/probe.json" in with_photon
    assert "OPENTRANSIT_RATE_LIMIT_ENABLED=0" in with_photon
    assert "OPENTRANSIT_PHOTON_URL=http://127.0.0.1:2322" in with_photon
    assert "OPENTRANSIT_MOTIS_URL=http://127.0.0.1:8080" in with_photon
    without = acc.api_argv(
        "r1", "api:img", generation, tmp_path / "src", tmp_path / "work", photon=False, cpus=None
    )
    assert not any("PHOTON" in item for item in without)
    assert any(item.endswith("dst=/run/opentransit,readonly") for item in without)  # probe is ro
    for argv in (motis, init, photon, verifier, with_photon):
        names = [argv[argv.index("--name") + 1]]
        assert all(name.startswith("ot-acc-") for name in names)


def test_ports_are_limited_to_the_assigned_range():
    assert acc.check_port(8500) == 8500 and acc.check_port(8599) == 8599
    for port in (8499, 8600, 8000, 59181):
        with pytest.raises(ValueError):
            acc.check_port(port)


def test_bind_paths_with_commas_are_refused(tmp_path):
    with pytest.raises(ValueError):
        acc.mount(tmp_path / "a,b", "/x")


def test_cli_accepts_only_known_steps_and_requires_a_prefix():
    args = acc.parse_args(
        ["--generation", "g", "--run-id", "r", "--results-prefix", "p", "--steps", "readyz,demo"]
    )
    assert args.steps == ("readyz", "demo") and args.port == 8500
    with pytest.raises(SystemExit):
        acc.parse_args(
            ["--generation", "g", "--run-id", "r", "--results-prefix", "p", "--steps", "bogus"]
        )
    with pytest.raises(SystemExit):
        acc.parse_args(["--generation", "g", "--run-id", "r"])


def test_cold_start_assessment_flags_slow_or_failed_warmup_requests():
    clean = acc.warmup_assessment([{"status": 200, "ms": 40.0}, {"status": 200, "ms": 12.0}])
    assert clean["clean"] is True and clean["firstMs"] == 40.0
    slow = acc.warmup_assessment([{"status": 200, "ms": 5200.0}, {"status": 503, "ms": 1200.0}])
    assert slow["clean"] is False and slow["slowerThanClientTimeout"] == 1
    assert slow["nonOk"] == [{"status": 503, "ms": 1200.0}]
    assert acc.warmup_assessment([])["clean"] is False


def test_first_pass_failures_count_only_unusable_outcomes():
    outcomes = {"success": 170, "valid_empty": 9, "http_error": 2, "unavailable": 1}
    assert acc.first_pass_failures({"firstPassOutcomes": outcomes}) == 3
    assert acc.first_pass_failures({"firstPassOutcomes": {"success": 5}}) == 0
    assert acc.first_pass_failures({}) == 0
