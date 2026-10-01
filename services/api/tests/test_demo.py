"""M3.8: the one-command scheduled demo, tested against a mocked API (no real engine)."""

import io
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from opentransit import demo
from opentransit.build import cli

EXAMPLE = json.loads((Path(__file__).parents[1] / "examples" / "journey.json").read_text())


def timing(start, end):
    return {
        "scheduledDeparture": start,
        "scheduledArrival": end,
        "timingState": "scheduled",
        "expectedDeparture": None,
        "expectedArrival": None,
        "delaySeconds": None,
        "observedAt": None,
    }


def response_body(outcome="routes_found", capabilities=None):
    place = {"name": "A", "latitude": 32.0, "longitude": 34.8}
    walk = {
        "kind": "walk",
        "mode": "walk",
        "from": {**place, "name": "Dizengoff Center"},
        "to": {**place, "name": "Stop A"},
        "timing": timing("2026-10-02T08:05:00+03:00", "2026-10-02T08:10:00+03:00"),
        "durationSeconds": 300,
        "transit": None,
    }
    bus = {
        "kind": "transit",
        "mode": "bus",
        "from": {**place, "name": "Stop A"},
        "to": {**place, "name": "Technion"},
        "timing": timing("2026-10-02T08:12:00+03:00", "2026-10-02T09:30:00+03:00"),
        "durationSeconds": 4680,
        "transit": {
            "routeShortName": "7",
            "headsign": "Haifa",
            "operatorName": "Synthetic operator",
            "serviceDate": "2026-10-02",
        },
    }
    journeys = []
    if outcome == "routes_found":
        journeys = [
            {
                "id": "journey-1",
                "timing": timing("2026-10-02T08:05:00+03:00", "2026-10-02T09:30:00+03:00"),
                "durationSeconds": 5100,
                "walkingSeconds": 300,
                "walkingDistanceMeters": 400.0,
                "transfers": 0,
                "legs": [walk, bus],
            }
        ]
    return {
        "data": {"outcome": outcome, "journeys": journeys, "alerts": None},
        "meta": {
            "generationId": "gen-1",
            "mode": "fixture",
            "freshness": "current",
            "coverage": {"from": "2026-09-30T00:00:00+03:00", "until": "2026-10-31T00:00:00+02:00"},
            "capabilities": capabilities or {"realtime": "not_enabled", "alerts": "not_enabled"},
            "appliedConstraints": {"transferWalkLimit": "not_enforced"},
            "warnings": [],
        },
    }


def run(handler, depart_at="2026-10-02T08:00:00+03:00", **kwargs):
    out, err = io.StringIO(), io.StringIO()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    code = demo.run_demo("http://api.test/", depart_at, client=client, out=out, err=err, **kwargs)
    return code, out.getvalue(), err.getvalue()


def test_default_departure_is_tomorrow_0800_israel_time_with_explicit_offset():
    assert demo.default_depart_at(datetime(2026, 10, 1, 12, tzinfo=UTC)) == (
        "2026-10-02T08:00:00+03:00"
    )
    # 22:30 UTC is already the next Israeli date.
    assert demo.default_depart_at(datetime(2026, 10, 1, 22, 30, tzinfo=UTC)) == (
        "2026-10-03T08:00:00+03:00"
    )
    # The clocks go back on 2026-10-25; 08:00 that day is +02:00.
    assert demo.default_depart_at(datetime(2026, 10, 24, 12, tzinfo=UTC)) == (
        "2026-10-25T08:00:00+02:00"
    )


def test_request_uses_the_documented_example_coordinates():
    body = demo.build_request("2026-10-02T08:00:00+03:00", 3, "en")
    assert body["from"] == EXAMPLE["from"] and body["to"] == EXAMPLE["to"]
    assert body["departAt"] == "2026-10-02T08:00:00+03:00"


def test_success_prints_scheduled_labels_and_disabled_realtime():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=response_body())

    code, out, err = run(handler, results=2, lang="he")
    assert code == demo.EXIT_OK == 0 and err == ""
    assert seen[0].method == "POST" and str(seen[0].url) == "http://api.test/v1/journeys"
    sent = json.loads(seen[0].content)
    assert sent["from"] == EXAMPLE["from"] and sent["results"] == 2 and sent["lang"] == "he"
    assert "Realtime:   not_enabled" in out and "Alerts:     not_enabled" in out
    assert out.count("[scheduled]") == 3  # journey + two legs
    assert "predicted times and delays are not provided" in out
    assert "Outcome:    routes_found (1 journey(s))" in out
    assert "08:12-09:30  bus" in out and "line 7 to Haifa" in out
    assert "service date 2026-10-02" in out
    assert "transferWalkLimit=not_enforced" in out
    assert "gen-1 (fixture data" in out


def test_missing_realtime_capability_is_reported_unavailable_not_assumed():
    code, out, _ = run(lambda r: httpx.Response(200, json=response_body(capabilities={"x": 1})))
    assert code == 0
    assert "Realtime:   unavailable" in out and "Alerts:     unavailable" in out


def test_no_route_exits_nonzero_but_prints_the_outcome():
    code, out, err = run(lambda r: httpx.Response(200, json=response_body("no_route")))
    assert code == demo.EXIT_NO_ROUTE == 1
    assert "Outcome:    no_route (0 journey(s))" in out and "no route found" in err


def test_api_problem_is_reported_with_code_and_request_id():
    problem = {"code": "FEED_EXPIRED", "detail": "Needs a fresh build.", "requestId": "abc"}
    code, out, err = run(lambda r: httpx.Response(503, json=problem))
    assert code == demo.EXIT_ERROR == 2 and out == ""
    assert "HTTP 503 FEED_EXPIRED" in err and "requestId abc" in err


def connect_error(request):
    raise httpx.ConnectError("down", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        connect_error,
        lambda r: httpx.Response(500, text="boom"),
        lambda r: httpx.Response(200, text="not json"),
        lambda r: httpx.Response(200, json={"data": {}}),
    ],
)
def test_connection_http_and_malformed_failures_are_errors(handler):
    code, out, err = run(handler)
    assert code == 2 and out == "" and err.startswith("error:")


def test_departure_without_offset_is_rejected_before_any_request():
    def handler(request):
        pytest.fail("Request sent with an ambiguous time")

    code, _, err = run(handler, depart_at="2026-10-02T08:00:00")
    assert code == 2 and "explicit offset" in err
    assert run(handler, depart_at="tomorrow")[0] == 2


def test_command_against_the_real_app_with_a_synthetic_engine(client_factory, engine_route):
    """The CLI payload is accepted by the actual route and schema validation."""
    out, err = io.StringIO(), io.StringIO()
    with client_factory(lambda r: httpx.Response(200, json=engine_route)) as client:
        code = demo.run_demo(
            "http://testserver", "2026-09-30T08:00:00+03:00", client=client, out=out, err=err
        )
    assert code == 0, err.getvalue()
    assert "Realtime:   not_enabled" in out.getvalue() and "[scheduled]" in out.getvalue()


def test_cli_subcommand_forwards_arguments_and_exit_code(monkeypatch):
    captured = {}

    def fake(api_url, depart_at, **kwargs):
        captured.update(api_url=api_url, depart_at=depart_at, **kwargs)
        return 1

    monkeypatch.setattr(demo, "run_demo", fake)
    assert cli.main(["demo"]) == 1
    assert captured == {
        "api_url": "http://127.0.0.1:8000",
        "depart_at": None,
        "results": 3,
        "lang": "en",
    }
    cli.main(
        ["demo", "--api-url", "http://127.0.0.1:8002", "--depart-at", "2026-10-02T08:00:00+03:00"]
        + ["--results", "5", "--lang", "he"]
    )
    assert captured["api_url"] == "http://127.0.0.1:8002" and captured["results"] == 5
