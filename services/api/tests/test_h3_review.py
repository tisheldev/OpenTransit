import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from opentransit.api.schemas import JourneyRequest
from tools import h3_review as h3

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "poc/corpora/journeys.json"
COVERAGE = {"from": "2026-09-30T00:00:00+03:00", "until": "2026-10-31T00:00:00+02:00"}
NOW = datetime(2026, 10, 1, 9, 0, tzinfo=h3.JERUSALEM)
GENERATION = "gen-20261001-test"


def corpus():
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def window(first=None, last=None):
    return h3.resolve_window(
        h3.parse_instant(COVERAGE["from"]), h3.parse_instant(COVERAGE["until"]), first, last
    )


def plan(first=None, last=None, now=NOW, arrive_by=False, holidays=None):
    win = window(first, last)
    specs = h3.build_case_specs(
        corpus(), win, max(win[0], now), holidays or h3.BUILTIN_HOLIDAYS, arrive_by
    )
    return {spec.id: spec for spec in specs}


def stamp(spec):
    return h3.local(spec.slot.instant).strftime("%Y-%m-%d %H:%M %z")


# ------------------------------------------------------------------ date selection


def test_corpus_ids_preserved_and_required_ten_present():
    specs = plan()
    assert [f"J{n:02d}" for n in range(1, 26)] == [i for i in specs if "-" not in i]
    required = {h3.required_number(s.corpus) for s in specs.values() if s.id == s.base_id}
    assert required - {None} == set(range(1, 11))


def test_ordinary_rules_use_the_poc_weekday_times_and_skip_holidays():
    specs = plan()
    assert stamp(specs["J01"]) == "2026-10-05 08:00 +0300"  # Monday, after the holiday week
    assert stamp(specs["J03"]) == "2026-10-06 13:00 +0300"
    assert stamp(specs["J04"]) == "2026-10-07 18:30 +0300"
    assert stamp(specs["J21"]) == "2026-10-06 23:40 +0300"
    assert stamp(specs["J22"]) == "2026-10-07 02:30 +0300"
    for spec in specs.values():
        if spec.slot and spec.rule in ("weekday_morning", "weekday_midday", "weekday_evening"):
            assert spec.slot.instant.date() not in h3.BUILTIN_HOLIDAYS


def test_friday_shabbat_and_holiday_cases():
    specs = plan()
    assert stamp(specs["J11-FRI"]) == "2026-10-09 15:30 +0300"
    assert stamp(specs["J25"]) == "2026-10-10 12:00 +0300"
    assert stamp(specs["J11-SAT"]) == stamp(specs["J25"])
    assert "Shabbat" in specs["J25"].slot.flags
    # Oct 1 08:00 has passed at NOW, so the morning case falls to the eve; midday is Chol HaMoed.
    assert stamp(specs["J12-HOL"]) == "2026-10-01 13:00 +0300"
    assert specs["J01-HOL"].slot.instant.date() == date(2026, 10, 2)
    assert any("Holiday calendar" in flag for flag in specs["J12-HOL"].slot.flags)
    # The pure Shabbat case must not be Simchat Torah (a holiday Saturday), Oct 3.
    assert specs["J25"].slot.instant.date() != date(2026, 10, 3)


def test_dst_fall_back_day_and_both_occurrences_of_repeated_hour():
    assert h3.fall_back_days(date(2026, 9, 30), date(2026, 10, 30)) == [date(2026, 10, 25)]
    assert h3.repeated_hour(date(2026, 10, 25)) == 1
    assert h3.repeated_hour(date(2026, 10, 24)) is None
    assert not h3.is_fall_back_day(date(2026, 10, 24))
    specs = plan()
    assert stamp(specs["J01-DST"]) == "2026-10-25 08:00 +0200"
    first, second = specs["J22-DST1"].slot.instant, specs["J22-DST2"].slot.instant
    assert first.isoformat() == "2026-10-25T01:30:00+03:00"
    assert second.isoformat() == "2026-10-25T01:30:00+02:00"
    assert second.astimezone(UTC) - first.astimezone(UTC) == timedelta(hours=1)


def test_window_clipping_omits_rules_that_do_not_fit():
    last = date(2026, 10, 6)
    specs = plan(first=date(2026, 10, 5), last=last)
    assert specs["J01"].slot.instant.date() == date(2026, 10, 5)
    assert specs["J21"].slot.instant.date() == last  # 23:40 on the last day still fits
    for case_id in ("J04", "J22", "J25", "J11-FRI", "J01-DST", "J22-DST1", "J22-DST2"):
        assert specs[case_id].slot is None, case_id
        assert "usable range" in specs[case_id].omission.reason
    end = window(last=last)[1]
    assert all(s.slot.instant < end for s in specs.values() if s.slot)


def test_holiday_cases_are_omitted_when_the_window_has_no_holiday():
    specs = plan(first=date(2026, 10, 5))
    assert specs["J01-HOL"].slot is None and specs["J12-HOL"].slot is None
    assert "holiday" in specs["J01-HOL"].omission.reason
    assert specs["J01"].slot is not None


def test_custom_holiday_and_now_after_slot_moves_to_next_week():
    specs = plan(first=date(2026, 10, 5), holidays={date(2026, 10, 14): ("holiday", "Test")})
    assert specs["J01-HOL"].slot.instant.date() == date(2026, 10, 14)
    later = plan(now=datetime(2026, 10, 5, 8, 30, tzinfo=h3.JERUSALEM))
    assert later["J01"].slot.instant.date() == date(2026, 10, 12)


def test_window_is_the_intersection_with_coverage():
    start, end = window(date(2026, 10, 5), date(2026, 10, 8))
    assert h3.local(start).isoformat() == "2026-10-05T00:00:00+03:00"
    assert h3.local(end).isoformat() == "2026-10-09T00:00:00+03:00"
    assert window(date(2026, 9, 1), date(2026, 12, 31)) == window()
    with pytest.raises(ValueError):
        window(date(2026, 11, 5), None)
    with pytest.raises(ValueError):
        window(None, date(2026, 9, 1))


def test_arrive_by_variants_are_opt_in_and_use_arrive_by_field():
    assert not any(i.endswith("-AB") for i in plan())
    specs = plan(arrive_by=True)
    body = h3.request_body(specs["J11-AB"], "he", 3, None)
    assert body["arriveBy"] == "2026-10-05T09:30:00+03:00" and "departAt" not in body


# ----------------------------------------------------------------------- mock API


def status_body(mode="real", ready=True, generation=GENERATION):
    return {
        "data": {"ready": ready, "realtime": "not_enabled", "alerts": "not_enabled"},
        "meta": {
            "requestId": "s1",
            "generationId": generation,
            "mode": mode,
            "freshness": "current",
            "dataBuiltAt": "2026-10-01T05:00:00+00:00",
            "coverage": COVERAGE,
        },
    }


def location(name):
    return {"name": name, "latitude": 32.0, "longitude": 34.8, "stopId": None, "stopCode": "100"}


def timing(dep, arr):
    return {"scheduledDeparture": dep, "scheduledArrival": arr, "timingState": "scheduled"}


def transit_leg(mode, origin, target, start, end, route, operator, headsign, trip):
    return {
        "kind": "transit",
        "mode": mode,
        "from": location(origin),
        "to": location(target),
        "timing": timing(start, end),
        "durationSeconds": 900,
        "distanceMeters": None,
        "geometry": None,
        "geometryUnavailableReason": "unavailable",
        "transit": {
            "operatorId": "1",
            "operatorName": operator,
            "routeId": "r1",
            "routeShortName": route,
            "headsign": headsign,
            "engineTripId": "e1",
            "sourceTripId": trip,
            "serviceDate": "2026-10-01",
            "startTime": "08:00:00",
        },
    }


def journey(departure):
    dep = datetime.fromisoformat(departure)
    iso = [(dep + timedelta(minutes=m)).isoformat() for m in (0, 5, 20, 26, 40)]
    walk = {
        "kind": "walk",
        "mode": "walk",
        "from": location("Origin"),
        "to": location("Stop A"),
        "timing": timing(iso[0], iso[1]),
        "durationSeconds": 300,
        "distanceMeters": 410.0,
        "geometry": None,
        "geometryUnavailableReason": None,
        "transit": None,
    }
    return {
        "id": "j1",
        "timing": timing(iso[0], iso[4]),
        "durationSeconds": 2400,
        "walkingSeconds": 300,
        "walkingDistanceMeters": 410.0,
        "transfers": 1,
        "legs": [
            walk,
            transit_leg("bus", "Stop A", "Hub", iso[1], iso[2], "480", "Dan", "Ramat Gan", "123_1"),
            transit_leg(
                "rail", "Hub", "End", iso[3], iso[4], "Rail", "Israel Railways", None, "9_1"
            ),
        ],
    }


def answer(body, generation=GENERATION, outcome="routes_found"):
    when = body.get("departAt") or body["arriveBy"]
    return {
        "data": {
            "outcome": outcome,
            "journeys": [journey(when)] if outcome == "routes_found" else [],
            "alerts": None,
        },
        "meta": {"requestId": "r-" + when[:13], "generationId": generation, "warnings": []},
    }


def make_transport(status=None, behave=None, seen=None):
    def handler(request):
        if request.url.path == "/v1/status":
            return httpx.Response(200, json=status or status_body())
        body = json.loads(request.content)
        if seen is not None:
            seen.append(body)
        reply = behave(body) if behave else None
        return reply if reply is not None else httpx.Response(200, json=answer(body))

    return httpx.MockTransport(handler)


def run_main(tmp_path, transport, *extra, name="h3.md"):
    out = tmp_path / name
    args = ["--api-url", "http://api.test", "--output", str(out), "--now", NOW.isoformat()]
    return h3.main([*args, *extra], transport=transport), out


def case_section(sheet, case_id):
    return next(p for p in sheet.split("\n## ") if p.startswith(f"{case_id} "))


def test_end_to_end_sheet_and_raw_evidence(tmp_path):
    seen = []
    har_karkom = next(c for c in corpus()["cases"] if c["id"] == "J23")["from"]["lat"]

    def behave(body):
        if body["from"]["latitude"] == har_karkom:
            return httpx.Response(200, json=answer(body, outcome="no_route"))
        if body.get("departAt", "").startswith("2026-10-01T13:00"):  # J12-HOL
            problem = {
                "type": "x",
                "title": "t",
                "status": 504,
                "code": "ENGINE_TIMEOUT",
                "detail": "Scheduled planning is temporarily unavailable.",
                "requestId": "rid-9",
            }
            return httpx.Response(504, json=problem)
        return None

    code, out = run_main(tmp_path, make_transport(behave=behave, seen=seen))
    assert code == 3  # one case errored; the sheet is still written
    sheet = out.read_text(encoding="utf-8")
    head = sheet[: sheet.index("## Date selection")]
    assert GENERATION in head
    assert "Scheduled only; realtime not enabled" in head
    assert COVERAGE["from"] in head and COVERAGE["until"] in head
    assert "Total usable: ____ / 10" in head
    assert "NOT REAL FEED DATA" not in sheet
    # NO ROUTE and API errors render distinctly.
    assert "API RESULT: NO ROUTE" in case_section(sheet, "J23")
    assert "ERROR 504 `ENGINE_TIMEOUT`" in case_section(sheet, "J12-HOL")
    assert "not a no-route answer" in case_section(sheet, "J12-HOL")
    # Itinerary content, comparison links and DST offsets.
    j01 = case_section(sheet, "J01")
    for text in (
        "**bus 480** (Dan) toward Ramat Gan",
        "board Stop A [code 100] 08:05",
        "Hub -> Hub: 6 min",
        "walking 5 min / 410 m",
        "service date 2026-10-01",
        "https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748",
        "moovitapp.com",
        "Set the time yourself to **Depart at 08:00, Mon 2026-10-05**",
    ):
        assert text in j01, text
    assert "דיזנגוף סנטר" in j01
    assert "**Required journey #1**" in j01
    assert "Required journey" not in case_section(sheet, "J22-DST2")  # variants are extras
    assert "- Corpus `poc/corpora/journeys.json` sha256" in head  # repo-relative, not a worktree
    assert "01:30(+03:00)" in case_section(sheet, "J22-DST1")
    assert "01:30(+02:00)" in case_section(sheet, "J22-DST2")
    # Verdict cells are blank for every generated case; nothing pre-fills Y or N.
    assert sheet.count("\n|  |  |  |\n") == len(seen)
    assert "| 1 | J01 |" in head and head.count("| |") >= 10
    # Raw evidence: one record per request, valid request bodies, timestamps and generation.
    raw = json.loads(out.with_name("h3.raw.json").read_text(encoding="utf-8"))
    assert raw["generationId"] == GENERATION and len(raw["cases"]) == len(seen)
    assert all(c["requestedAt"] and c["receivedAt"] for c in raw["cases"])
    for body in seen:
        JourneyRequest.model_validate(body)
    assert not [d for d in raw["dates"] if d["omitted"]]


def test_omitted_cases_are_listed_and_not_requested(tmp_path):
    seen = []
    code, out = run_main(
        tmp_path, make_transport(seen=seen), "--first-day", "2026-10-05", "--last-day", "2026-10-06"
    )
    sheet = out.read_text(encoding="utf-8")
    assert code == 0
    assert "**Not covered by this sheet:**" in sheet
    assert "**NOT GENERATED:**" in case_section(sheet, "J25")
    assert 0 < len(seen) < 34


def test_refuses_to_overwrite_and_makes_no_requests(tmp_path):
    out = tmp_path / "h3.md"
    out.write_text("human verdicts", encoding="utf-8")
    seen = []
    code, _ = run_main(tmp_path, make_transport(seen=seen))
    assert code == 2 and out.read_text(encoding="utf-8") == "human verdicts" and seen == []
    out.unlink()
    raw = tmp_path / "h3.raw.json"
    raw.write_text("{}", encoding="utf-8")
    code, _ = run_main(tmp_path, make_transport(seen=seen))
    assert code == 2 and raw.read_text(encoding="utf-8") == "{}" and not out.exists()
    assert seen == []
    with pytest.raises(FileExistsError):
        h3.write_exclusive(raw, "x")


def test_fixture_data_and_unready_api_are_refused(tmp_path):
    code, out = run_main(tmp_path, make_transport(status=status_body(mode="fixture")))
    assert code == 2 and not out.exists()
    code, out = run_main(tmp_path, make_transport(status=status_body(ready=False)), name="b.md")
    assert code == 2 and not out.exists()
    code, out = run_main(
        tmp_path, make_transport(status=status_body(mode="fixture")), "--allow-fixture", name="c.md"
    )
    assert code == 0 and "NOT REAL FEED DATA" in out.read_text(encoding="utf-8")


def test_mixed_generation_and_transport_failure_are_flagged(tmp_path):
    def behave(body):
        if body["departAt"].startswith("2026-10-05T08:00"):
            return httpx.Response(200, json=answer(body, generation="other-gen"))
        if body["departAt"].startswith("2026-10-06T13:00"):
            raise httpx.ConnectError("boom")
        return None

    code, out = run_main(tmp_path, make_transport(behave=behave))
    sheet = out.read_text(encoding="utf-8")
    assert code == 3
    assert "MIXED GENERATIONS DETECTED: other-gen" in sheet
    assert "response generation `other-gen` differs" in case_section(sheet, "J01")
    assert "REQUEST FAILED** (ConnectError)" in case_section(sheet, "J03")


def test_arrive_by_requests_are_sent_when_enabled(tmp_path):
    seen = []
    code, _ = run_main(tmp_path, make_transport(seen=seen), "--arrive-by")
    assert code == 0
    arrive = [b for b in seen if "arriveBy" in b]
    assert len(arrive) == 3 and all("departAt" not in b for b in arrive)


def test_plan_only_makes_no_api_calls(capsys):
    code = h3.main(
        [
            "--plan-only",
            "--first-day",
            "2026-09-30",
            "--last-day",
            "2026-10-30",
            "--now",
            NOW.isoformat(),
        ]
    )
    table = capsys.readouterr().out
    assert code == 0 and "J22-DST2" in table and "UTC+02:00" in table
