"""The real-engine walking-cap checker, exercised on synthetic API responses only."""

import json

import httpx

from tools.check_walk_caps import main, run, violations


def leg(kind, seconds):
    return {"kind": kind, "durationSeconds": seconds}


def journey(*legs, duration=None):
    return {"id": "j", "legs": list(legs), "durationSeconds": duration or 0}


def test_walks_are_checked_against_their_own_caps_with_minute_tolerance():
    ok = journey(leg("walk", 300), leg("transit", 900), leg("walk", 600), leg("transit", 60))
    assert violations(ok, 5, 5, 5) == []  # transfer walk (600 s) is not capped
    long_access = journey(leg("walk", 400), leg("walk", 200), leg("transit", 10), leg("walk", 60))
    assert violations(long_access, 5, 15, 30) == ["access walk 600s > 5 min"]
    assert violations(journey(leg("transit", 10), leg("walk", 361)), 15, 5, 30) == [
        "egress walk 361s > 5 min"
    ]
    assert violations(journey(leg("walk", 360)), 1, 1, 5) == []
    assert violations(journey(leg("walk", 361), duration=361), 1, 1, 5) == [
        "direct walk 361s > 5 min"
    ]


def api(walk_seconds):
    def handler(request):
        caps = json.loads(request.content)
        assert {caps[k] for k in caps if k.endswith("WalkMinutes")} == {
            caps["maxAccessWalkMinutes"]
        }
        payload = {
            "data": {
                "outcome": "routes_found",
                "journeys": [journey(leg("walk", walk_seconds), leg("transit", 60))],
            },
            "meta": {"generationId": "g", "warnings": []},
        }
        return httpx.Response(200, json=payload)

    return handler


def test_run_reports_violations_for_the_caps_that_are_exceeded():
    client = httpx.Client(transport=httpx.MockTransport(api(400)))
    report = run("http://api.test", "2026-10-02T08:00:00+03:00", client)
    assert [c["capMinutes"] for c in report["cases"]].count(1) == 2
    # 400 s exceeds the 1 and 5 minute caps (plus tolerance) for both pairs, not 15 or 30.
    assert report["violationCount"] == 4
    assert report["errors"] == 0
    assert all(c["violations"] == [] for c in report["cases"] if c["capMinutes"] >= 15)


def test_main_never_overwrites_evidence_and_signals_errors(tmp_path, monkeypatch):
    real_client = httpx.Client

    def unavailable(**kwargs):
        return real_client(transport=httpx.MockTransport(lambda r: httpx.Response(503, json={})))

    monkeypatch.setattr(httpx, "Client", unavailable)
    output = tmp_path / "evidence.json"
    args = ["--depart-at", "2026-10-02T08:00:00+03:00", "--output", str(output)]
    assert main(args) == 2 and json.loads(output.read_text())["errors"] == 8
    before = output.read_bytes()
    assert main(args) == 2 and output.read_bytes() == before
