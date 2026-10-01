"""Generate the H3 route-review sheet through the product path (POST /v1/journeys).

Reuses the PoC journey corpus (poc/corpora/journeys.json, case IDs unchanged),
assigns concrete Asia/Jerusalem departure instants inside the generation's
coverage window, calls the API, saves raw request/response evidence and renders
a Markdown sheet for a human reviewer.

The tool never fills a verdict. "Usable?" and "Notes" stay blank for the user
(checkpoint H3 / P0-02); machine output is context only. Comparison links are
constructed, never fetched. Output paths must be new files.

Calendar awareness (S8): ordinary cases avoid holiday dates; extra cases cover a
Friday afternoon, a Saturday, an Israeli holiday date, the DST fall-back day and
both occurrences of the repeated hour. A rule that cannot be satisfied inside
the window is listed as omitted in the sheet, never silently dropped.

Usage:
    python tools/h3_review.py --api-url http://127.0.0.1:8000 --output H3.md
    python tools/h3_review.py --plan-only --first-day 2026-09-30 --last-day 2026-10-30
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

JERUSALEM = ZoneInfo("Asia/Jerusalem")
SCHEMA_VERSION = 1
ARRIVE_BY_BASES = ("J01", "J11", "J12")
ARRIVE_BY_OFFSET = timedelta(minutes=90)
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# Built-in table (autumn 2026 only, from the published Hebrew calendar; verify
# against the official calendar and the feed's calendar before relying on it).
# Kinds: holiday = day off, chol_hamoed = intermediate days, eve = erev chag /
# Hoshana Rabbah, isru_chag = day after.
BUILTIN_HOLIDAYS: dict[date, tuple[str, str]] = {
    date(2026, 9, 11): ("eve", "Erev Rosh Hashana"),
    date(2026, 9, 12): ("holiday", "Rosh Hashana (day 1)"),
    date(2026, 9, 13): ("holiday", "Rosh Hashana (day 2)"),
    date(2026, 9, 20): ("eve", "Erev Yom Kippur"),
    date(2026, 9, 21): ("holiday", "Yom Kippur"),
    date(2026, 9, 25): ("eve", "Erev Sukkot"),
    date(2026, 9, 26): ("holiday", "Sukkot (first day)"),
    date(2026, 9, 27): ("chol_hamoed", "Chol HaMoed Sukkot"),
    date(2026, 9, 28): ("chol_hamoed", "Chol HaMoed Sukkot"),
    date(2026, 9, 29): ("chol_hamoed", "Chol HaMoed Sukkot"),
    date(2026, 9, 30): ("chol_hamoed", "Chol HaMoed Sukkot"),
    date(2026, 10, 1): ("chol_hamoed", "Chol HaMoed Sukkot"),
    date(2026, 10, 2): ("eve", "Hoshana Rabbah / erev Shemini Atzeret-Simchat Torah"),
    date(2026, 10, 3): ("holiday", "Shemini Atzeret / Simchat Torah"),
    date(2026, 10, 4): ("isru_chag", "Isru Chag"),
}


@dataclass(frozen=True)
class Rule:
    """A calendar rule: how to pick one concrete local instant inside the window."""

    tag: str
    kind: str  # ordinary | night | holiday | dst_day | dst_repeat
    weekday: int | None = None
    hour: int = 0
    minute: int = 0
    fold: int = 0


RULES: dict[str, Rule] = {
    r.tag: r
    for r in (
        Rule("weekday_morning", "ordinary", 0, 8, 0),
        Rule("weekday_midday", "ordinary", 1, 13, 0),
        Rule("weekday_evening", "ordinary", 2, 18, 30),
        Rule("late_night", "night", 1, 23, 40),
        Rule("after_midnight", "night", 2, 2, 30),
        Rule("shabbat", "ordinary", 5, 12, 0),
        Rule("friday_afternoon", "ordinary", 4, 15, 30),
        Rule("holiday_morning", "holiday", None, 8, 0),
        Rule("holiday_midday", "holiday", None, 13, 0),
        Rule("dst_day_peak", "dst_day", None, 8, 0),
        Rule("dst_repeat_first", "dst_repeat", None, 1, 30, 0),
        Rule("dst_repeat_second", "dst_repeat", None, 1, 30, 1),
    )
}

# Calendar-aware additions: (new id, corpus case whose route/OD is reused, rule tag, note).
SUPPLEMENTAL: tuple[tuple[str, str, str, str], ...] = (
    ("J11-FRI", "J11", "friday_afternoon", "Friday afternoon: expect reduced or no rail service"),
    ("J12-FRI", "J12", "friday_afternoon", "Friday afternoon: expect reduced or no rail service"),
    ("J11-SAT", "J11", "shabbat", "Saturday noon: expect no national rail"),
    ("J05-SAT", "J05", "shabbat", "Saturday noon: Jerusalem urban case"),
    ("J01-HOL", "J01", "holiday_morning", "Israeli holiday timetable, morning"),
    ("J12-HOL", "J12", "holiday_midday", "Israeli holiday timetable, midday intercity"),
    ("J01-DST", "J01", "dst_day_peak", "Peak on the DST fall-back day"),
    ("J22-DST1", "J22", "dst_repeat_first", "Repeated hour, first occurrence (earlier offset)"),
    ("J22-DST2", "J22", "dst_repeat_second", "Repeated hour, second occurrence (later offset)"),
)


@dataclass(frozen=True)
class Slot:
    rule: str
    instant: datetime  # aware Asia/Jerusalem, fold set where it matters
    flags: tuple[str, ...]


@dataclass(frozen=True)
class Omission:
    rule: str
    reason: str


@dataclass
class CaseSpec:
    id: str
    base_id: str
    corpus: dict[str, Any]
    rule: str
    slot: Slot | None
    omission: Omission | None
    anchor: str  # depart | arrive
    note: str = ""
    expect: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- dates


def local(value: datetime) -> datetime:
    return value.astimezone(JERUSALEM)


def at_local(day: date, hour: int, minute: int, fold: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=JERUSALEM).replace(fold=fold)


def is_fall_back_day(day: date) -> bool:
    start = at_local(day, 0, 0).utcoffset()
    end = at_local(day, 23, 59).utcoffset()
    return start is not None and end is not None and end < start


def fall_back_days(first: date, last: date) -> list[date]:
    return [d for d in iter_days(first, last) if is_fall_back_day(d)]


def repeated_hour(day: date) -> int | None:
    """The local hour whose :30 occurs twice on a fall-back day."""
    for hour in range(24):
        if at_local(day, hour, 30, 0).utcoffset() != at_local(day, hour, 30, 1).utcoffset():
            return hour
    return None


def iter_days(first: date, last: date):
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


def day_flags(day: date, holidays: dict[date, tuple[str, str]]) -> tuple[str, ...]:
    flags = []
    if day in holidays:
        flags.append(f"Holiday calendar: {holidays[day][1]} ({holidays[day][0]})")
    if day.weekday() == 4:
        flags.append("Friday (erev Shabbat)")
    if day.weekday() == 5:
        flags.append("Shabbat")
    if is_fall_back_day(day):
        flags.append("DST fall-back day: clocks go back 02:00 to 01:00")
    return tuple(flags)


def resolve_window(
    status_from: datetime | None,
    status_until: datetime | None,
    first_day: date | None,
    last_day: date | None,
) -> tuple[datetime, datetime]:
    """Half-open [start, end) window: coverage clipped by optional local days."""
    starts, ends = [], []
    if status_from is not None:
        starts.append(status_from)
    if status_until is not None:
        ends.append(status_until)
    if first_day is not None:
        starts.append(at_local(first_day, 0, 0))
    if last_day is not None:
        ends.append(at_local(last_day + timedelta(days=1), 0, 0))
    if not starts or not ends:
        raise ValueError("A coverage window needs a start and an end")
    start, end = max(starts), min(ends)
    if start >= end:
        raise ValueError("The generation window is empty after clipping")
    return start, end


def plan_slot(
    rule: Rule,
    window: tuple[datetime, datetime],
    earliest: datetime,
    holidays: dict[date, tuple[str, str]],
) -> Slot | Omission:
    """Pick the first suitable instant for a rule inside [window), not before earliest."""
    start, end = window
    first_day = local(max(start, earliest)).date()
    last_day = local(end - timedelta(microseconds=1)).date()
    days = list(iter_days(first_day, last_day))
    busy = set(holidays) | set(fall_back_days(first_day - timedelta(days=1), last_day))

    def usable(instant: datetime) -> bool:
        return start <= instant < end and instant >= earliest

    ranks: dict[date, int] = {}
    if rule.kind in ("dst_day", "dst_repeat"):
        candidates = [d for d in days if is_fall_back_day(d)]
    elif rule.kind == "holiday":
        # Prefer a full holiday or chol hamoed day; an eve or isru chag is the fallback.
        candidates = [d for d in days if d in holidays and d.weekday() != 5]
        ranks = {d: 0 if holidays[d][0] in ("holiday", "chol_hamoed") else 1 for d in candidates}
    else:
        wanted = [d for d in days if d.weekday() == rule.weekday]
        if rule.kind == "night":
            candidates = [
                d for d in wanted if not ({d - timedelta(days=1), d, d + timedelta(days=1)} & busy)
            ]
        else:
            candidates = [d for d in wanted if d not in busy]

    options = []
    for day in candidates:
        hour = rule.hour
        if rule.kind == "dst_repeat":
            found = repeated_hour(day)
            if found is None:
                continue
            hour = found
        instant = at_local(day, hour, rule.minute, rule.fold)
        if usable(instant):
            options.append((ranks.get(day, 0), day, instant))
    if not options:
        return Omission(rule.tag, _omission_reason(rule, window, earliest))
    _, day, instant = min(options, key=lambda o: (o[0], o[1]))
    return Slot(rule.tag, instant, day_flags(day, holidays))


def _omission_reason(rule: Rule, window: tuple[datetime, datetime], earliest: datetime) -> str:
    span = (
        f"{local(max(window[0], earliest)).strftime('%Y-%m-%d %H:%M')} .. "
        f"{local(window[1]).strftime('%Y-%m-%d %H:%M')}"
    )
    what = {
        "dst_day": "no DST fall-back day",
        "dst_repeat": "no repeated-hour instant",
        "holiday": "no Israeli holiday date (non-Shabbat) from the holiday table",
    }.get(rule.kind, "no matching ordinary weekday")
    return f"{what} in the usable range {span} (Asia/Jerusalem)"


def build_case_specs(
    corpus: dict[str, Any],
    window: tuple[datetime, datetime],
    earliest: datetime,
    holidays: dict[date, tuple[str, str]],
    arrive_by: bool = False,
) -> list[CaseSpec]:
    by_id = {case["id"]: case for case in corpus["cases"]}
    if len(by_id) != len(corpus["cases"]):
        raise ValueError("Corpus case IDs are not unique")
    cache: dict[str, Slot | Omission] = {}

    def slot_for(tag: str) -> Slot | Omission:
        if tag not in cache:
            cache[tag] = plan_slot(RULES[tag], window, earliest, holidays)
        return cache[tag]

    def spec(case_id, base, tag, anchor="depart", note="", shift=timedelta(0)) -> CaseSpec:
        result = slot_for(tag)
        slot = omission = None
        if isinstance(result, Slot):
            shifted = (result.instant.astimezone(UTC) + shift).astimezone(JERUSALEM)
            slot = Slot(result.rule, shifted, result.flags)
            if shift and not (window[0] <= slot.instant < window[1]):
                omission, slot = Omission(tag, "arrive-by instant falls outside the window"), None
        else:
            omission = result
        return CaseSpec(
            case_id, base, by_id[base], tag, slot, omission, anchor, note, by_id[base]["expect"]
        )

    specs = [spec(c["id"], c["id"], c["depart"]) for c in corpus["cases"]]
    for case_id, base, tag, note in SUPPLEMENTAL:
        if base not in by_id:
            raise ValueError(f"Supplemental case {case_id} needs corpus case {base}")
        specs.append(spec(case_id, base, tag, note=note))
    if arrive_by:
        for base in ARRIVE_BY_BASES:
            tag = by_id[base]["depart"]
            specs.append(
                spec(
                    f"{base}-AB",
                    base,
                    tag,
                    anchor="arrive",
                    note="Arrive-by 90 minutes after the base departure time",
                    shift=ARRIVE_BY_OFFSET,
                )
            )
    return specs


def render_plan_table(specs: list[CaseSpec]) -> str:
    rows = ["| Case | Rule | Requested (Asia/Jerusalem) | Calendar flags |", "|---|---|---|---|"]
    for item in specs:
        if item.slot is None:
            when, flags = f"OMITTED: {item.omission.reason}", ""
        else:
            when = f"{item.anchor} {fmt_requested(item.slot.instant)}"
            flags = "; ".join(item.slot.flags) or "ordinary day"
        rows.append(f"| {item.id} | {item.rule} | {cell(when)} | {cell(flags)} |")
    return "\n".join(rows)


# ------------------------------------------------------------------------ requests


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Expected an instant with an explicit offset")
    return parsed


def request_body(
    item: CaseSpec, lang: str, results: int, walk_minutes: int | None
) -> dict[str, Any]:
    assert item.slot is not None
    origin, target = item.corpus["from"], item.corpus["to"]
    body: dict[str, Any] = {
        "from": {"kind": "coordinate", "latitude": origin["lat"], "longitude": origin["lon"]},
        "to": {"kind": "coordinate", "latitude": target["lat"], "longitude": target["lon"]},
        "arriveBy" if item.anchor == "arrive" else "departAt": item.slot.instant.isoformat(
            timespec="seconds"
        ),
        "lang": lang,
        "results": results,
    }
    if walk_minutes is not None:
        body["maxAccessWalkMinutes"] = walk_minutes
        body["maxEgressWalkMinutes"] = walk_minutes
    return body


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def call_case(client: httpx.Client, body: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "request": body,
        "requestedAt": now_iso(),
        "httpStatus": None,
        "response": None,
        "responseText": None,
        "error": None,
    }
    try:
        response = client.post("/v1/journeys", json=body)
    except httpx.HTTPError as exc:
        record["error"] = f"{type(exc).__name__}"
    else:
        record["httpStatus"] = response.status_code
        record["requestIdHeader"] = response.headers.get("x-request-id")
        try:
            record["response"] = response.json()
        except ValueError:
            record["responseText"] = response.text[:500]
    record["receivedAt"] = now_iso()
    return record


def fetch_status(client: httpx.Client) -> dict[str, Any]:
    response = client.get("/v1/status")
    response.raise_for_status()
    body = response.json()
    meta, data = body.get("meta") or {}, body.get("data") or {}
    if not meta.get("generationId") or not meta.get("coverage"):
        raise ValueError("The API reports no active generation")
    if not data.get("ready"):
        raise ValueError(f"The API is not ready: {json.dumps(data, sort_keys=True)}")
    return body


# ------------------------------------------------------------------------ rendering


def cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def offset_text(instant: datetime) -> str:
    raw = instant.strftime("%z")
    return f"{raw[:3]}:{raw[3:]}"


def fmt_requested(instant: datetime) -> str:
    when = local(instant)
    return f"{WEEKDAY_NAMES[when.weekday()]} {when:%Y-%m-%d %H:%M} (UTC{offset_text(when)})"


def fmt_clock(value: str | datetime, show_offset: bool) -> str:
    instant = local(parse_instant(value) if isinstance(value, str) else value)
    text = f"{instant:%H:%M}"
    if show_offset:
        text += f"({offset_text(instant)})"
    return text


def fmt_day_clock(value: str, show_offset: bool) -> str:
    instant = local(parse_instant(value))
    return (
        f"{WEEKDAY_NAMES[instant.weekday()]} {instant:%Y-%m-%d} {fmt_clock(instant, show_offset)}"
    )


def is_transition_day(day: date) -> bool:
    return at_local(day, 23, 59).utcoffset() != at_local(day, 0, 0).utcoffset()


def minutes(seconds: float | None) -> str:
    return "?" if seconds is None else f"{round(seconds / 60)} min"


def name_pair(point: dict[str, Any]) -> str:
    if point.get("name_he") and point["name_he"] != point["name"]:
        return f"{point['name']} ({point['name_he']})"
    return point["name"]


def comparison_links(corpus_case: dict[str, Any], instant: datetime, anchor: str) -> list[str]:
    origin, target = corpus_case["from"], corpus_case["to"]
    google = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={origin['lat']},{origin['lon']}&destination={target['lat']},{target['lon']}"
        "&travelmode=transit"
    )
    moovit = (
        f"https://moovitapp.com/?fll={origin['lat']}_{origin['lon']}"
        f"&tll={target['lat']}_{target['lon']}"
        f"&from={quote(origin['name'])}&to={quote(target['name'])}"
    )
    when = local(instant)
    verb = "Arrive by" if anchor == "arrive" else "Depart at"
    return [
        f"[Google Maps transit]({google})",
        f"[Moovit (unofficial deep link; may not prefill)]({moovit})",
        f"Set the time yourself to **{verb} {when:%H:%M}, {WEEKDAY_NAMES[when.weekday()]} "
        f"{when:%Y-%m-%d}** (Google's documented URL has no time parameter).",
    ]


def render_leg(leg: dict[str, Any], show_offset: bool) -> str:
    timing = leg["timing"]
    start = fmt_clock(timing["scheduledDeparture"], show_offset)
    end = fmt_clock(timing["scheduledArrival"], show_offset)
    origin, destination = leg["from"], leg["to"]
    if leg.get("kind") == "walk" or not leg.get("transit"):
        dist = leg.get("distanceMeters")
        distance = f", {round(dist)} m" if dist is not None else ""
        if leg.get("geometryUnavailableReason") == "street_path_unavailable":
            distance += " (timetable transfer; street path unavailable)"
        return (
            f"Walk {minutes(leg.get('durationSeconds'))}{distance}: "
            f"{origin['name']} {start} -> {destination['name']} {end}"
        )
    transit = leg["transit"]
    code = lambda p: f" [code {p['stopCode']}]" if p.get("stopCode") else ""  # noqa: E731
    headsign = f" toward {transit['headsign']}" if transit.get("headsign") else ""
    return (
        f"**{leg['mode']} {transit['routeShortName']}** ({transit['operatorName']}){headsign}: "
        f"board {origin['name']}{code(origin)} {start} -> alight {destination['name']}"
        f"{code(destination)} {end} "
        f"(service date {transit['serviceDate']}, trip `{transit['sourceTripId']}`)"
    )


def render_journey(index: int, journey: dict[str, Any], show_offset: bool) -> list[str]:
    timing = journey["timing"]
    lines = [
        f"**Option {index}:** departs {fmt_day_clock(timing['scheduledDeparture'], show_offset)}, "
        f"arrives {fmt_day_clock(timing['scheduledArrival'], show_offset)}; "
        f"total {minutes(journey['durationSeconds'])}, {journey['transfers']} transfer(s), "
        f"walking {minutes(journey['walkingSeconds'])} / "
        + (
            "unknown distance"
            if journey.get("walkingDistanceMeters") is None
            else f"{round(journey['walkingDistanceMeters'])} m"
        ),
        "",
    ]
    for number, leg in enumerate(journey["legs"], 1):
        lines.append(f"{number}. {render_leg(leg, show_offset)}")
    transit_legs = [leg for leg in journey["legs"] if leg.get("transit")]
    transfers = []
    for before, after in zip(transit_legs, transit_legs[1:], strict=False):
        wait = (
            parse_instant(after["timing"]["scheduledDeparture"])
            - parse_instant(before["timing"]["scheduledArrival"])
        ).total_seconds()
        transfers.append(f"{before['to']['name']} -> {after['from']['name']}: {minutes(wait)}")
    lines.append("")
    lines.append(
        "Transfers (alight to next boarding, including any walk): "
        + ("; ".join(transfers) if transfers else "none")
    )
    return lines


def required_number(corpus_case: dict[str, Any]) -> int | None:
    match = re.search(r"#(\d+)", corpus_case.get("prd_ref") or "")
    return int(match.group(1)) if match else None


def expectation_text(expect: dict[str, Any]) -> str:
    parts = [f"outcome `{expect.get('outcome', '?')}`"]
    for key in sorted(k for k in expect if k != "outcome"):
        parts.append(f"{key} = {expect[key]}")
    return ", ".join(parts)


def render_case(item: CaseSpec, record: dict[str, Any] | None, generation_id: str) -> list[str]:
    corpus_case = item.corpus
    origin, target = corpus_case["from"], corpus_case["to"]
    title = f"## {item.id} — {name_pair(origin)} → {name_pair(target)}"
    tags = [f"category `{corpus_case['category']}`", f"calendar rule `{item.rule}`"]
    number = required_number(corpus_case) if item.id == item.base_id else None
    lines = [title, ""]
    heading = [f"**Required journey #{number}** — {corpus_case['prd_ref']}"] if number else []
    lines.append(" · ".join(heading + tags))
    if item.id != item.base_id:
        lines += ["", f"Calendar variant of {item.base_id}: {item.note}."]
    lines.append("")
    if item.slot is None:
        lines += [
            f"**NOT GENERATED:** {item.omission.reason}.",
            "",
            "No request was sent. This calendar situation is not covered by this sheet.",
            "",
            "---",
            "",
        ]
        return lines
    instant = item.slot.instant
    show_offset = is_transition_day(local(instant).date())
    verb = "Arrive by" if item.anchor == "arrive" else "Depart at"
    key = "arriveBy" if item.anchor == "arrive" else "departAt"
    lines.append(
        f"**Requested:** {verb} {fmt_requested(instant)}  \nRequest field: "
        f"`{key}={instant.isoformat(timespec='seconds')}`"
    )
    lines.append(f"**Calendar flags:** {'; '.join(item.slot.flags) or 'ordinary day'}")
    lines.append("**Compare:** " + " · ".join(comparison_links(corpus_case, instant, item.anchor)))
    lines.append(
        f"**Corpus expectation (context, not a verdict):** {expectation_text(item.expect)}"
    )
    lines += ["", f"> What to check: {corpus_case['human_review']}", ""]
    lines += render_result(record, show_offset, generation_id, item.expect.get("outcome"))
    lines += [
        "",
        "| Usable? (Y/N) | Notes | Compared against / when checked |",
        "|---|---|---|",
        "|  |  |  |",
        "",
        "---",
        "",
    ]
    return lines


def render_result(
    record: dict[str, Any] | None,
    show_offset: bool,
    generation_id: str,
    expected_outcome: str | None,
) -> list[str]:
    if record is None:
        return ["**API RESULT:** not requested."]
    if record["error"]:
        return [f"**API RESULT: REQUEST FAILED** ({record['error']}). No answer was received."]
    status, body = record["httpStatus"], record["response"]
    if status != 200 or not isinstance(body, dict) or "data" not in body:
        if isinstance(body, dict) and "code" in body:
            return [
                f"**API RESULT: ERROR {status} `{body['code']}`** — {body.get('detail', '')} "
                f"(request id `{body.get('requestId', '?')}`). "
                "This is an error, not a no-route answer."
            ]
        text = record["responseText"] or "unparseable"
        return [f"**API RESULT: UNEXPECTED HTTP {status}** — {text}"]
    data, meta = body["data"], body["meta"]
    lines = []
    seen = meta["generationId"]
    if seen != generation_id:
        lines.append(f"**WARNING: response generation `{seen}` differs from `{generation_id}`.**")
        lines.append("")
    if meta.get("warnings"):
        lines.append(f"API warnings: {', '.join(meta['warnings'])}")
        lines.append("")
    outcome = data["outcome"]
    if outcome == "no_route":
        lines.append(
            "**API RESULT: NO ROUTE** — a valid search inside coverage returned no journey. "
            "The API does not state a cause (no service, walking limit and data gaps look alike)."
        )
    else:
        count = len(data["journeys"])
        lines.append(f"**API RESULT: {count} journey option(s) returned** (scheduled times).")
    if expected_outcome in ("route", "no-route"):
        matches = (expected_outcome == "route") == (outcome == "routes_found")
        lines.append(
            f"Machine note: {'matches' if matches else 'DIFFERS FROM'} the corpus expectation "
            f"`{expected_outcome}`. This is not a judgement of quality."
        )
    lines.append(f"Request id `{meta['requestId']}`.")
    for index, journey in enumerate(data["journeys"], 1):
        lines += ["", *render_journey(index, journey, show_offset)]
    return lines


def render_sheet(
    *,
    specs: list[CaseSpec],
    records: dict[str, dict[str, Any]],
    status: dict[str, Any],
    generated_at: datetime,
    window: tuple[datetime, datetime],
    earliest: datetime,
    corpus_path: str,
    corpus_sha256: str,
    api_url: str,
    options: dict[str, Any],
) -> str:
    meta = status["meta"]
    gid = meta["generationId"]
    coverage = meta["coverage"]
    required = sorted(
        (required_number(s.corpus), s)
        for s in specs
        if s.id == s.base_id and required_number(s.corpus)
    )
    mixed = sorted(
        {
            r["response"]["meta"]["generationId"]
            for r in records.values()
            if isinstance(r.get("response"), dict)
            and isinstance(r["response"].get("meta"), dict)
            and r["response"]["meta"].get("generationId") != gid
        }
    )
    lines = [
        "# H3 route-review sheet — through the API (POST /v1/journeys)",
        "",
        "> **Scheduled only; realtime not enabled.** Times are MOT timetable times. "
        "No delay, prediction or alert is shown.",
        "",
    ]
    if meta.get("mode") != "real":
        lines += [
            f"> **DATA MODE `{meta.get('mode')}` — NOT REAL FEED DATA. Not valid for H3 review.**",
            "",
        ]
    if mixed:
        lines += [
            f"> **MIXED GENERATIONS DETECTED: {', '.join(mixed)}. Regenerate this sheet.**",
            "",
        ]
    lines += [
        "**You are the reviewer.** Everything machine-made below is context. Fill only the "
        "`Usable? (Y/N)` and `Notes` cells yourself, comparing with Google Maps, Moovit or "
        "BetterRail at the stated date and time. The generator never writes a verdict. "
        "Release gate: at least **9 of the 10 required journeys** judged usable.",
        "",
        "## Generation",
        "",
        f"- Generation id: `{gid}` (mode `{meta.get('mode')}`, "
        f"freshness `{meta.get('freshness')}`)",
        f"- Data built: {meta.get('dataBuiltAt')}",
        f"- Coverage window (half-open, as reported by the API): {coverage['from']} .. "
        f"{coverage['until']}",
        f"- Window used for dates: {local(window[0]):%Y-%m-%d %H:%M} .. "
        f"{local(window[1]):%Y-%m-%d %H:%M} Asia/Jerusalem; earliest request instant "
        f"{local(earliest):%Y-%m-%d %H:%M}",
        f"- Capabilities reported: realtime `{status['data'].get('realtime')}`, alerts "
        f"`{status['data'].get('alerts')}`",
        f"- Generated {generated_at.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ} "
        f"({local(generated_at):%Y-%m-%d %H:%M} Israel) against `{api_url}`",
        f"- Corpus `{corpus_path}` sha256 `{corpus_sha256[:16]}…`; case IDs are the PoC IDs. "
        "Coordinates are the corpus's approximate hand-entered points; the API plans from them.",
        f"- Request options: lang `{options['lang']}`, results {options['results']}, walking "
        f"limits {options['walk']}, arrive-by variants {'on' if options['arrive_by'] else 'off'}",
        f"- Raw requests and responses: `{options['raw_name']}`",
        "",
        "## Required ten — your tally",
        "",
        "| # | Case | Requested | Usable? (Y/N) |",
        "|---|---|---|---|",
    ]
    for number, item in required:
        when = fmt_requested(item.slot.instant) if item.slot else "NOT GENERATED"
        lines.append(f"| {number} | {item.id} | {cell(when)} | |")
    lines += ["", "Total usable: ____ / 10", "", "## Date selection", ""]
    lines += [render_plan_table(specs), ""]
    omitted = [s for s in specs if s.slot is None]
    if omitted:
        lines += ["**Not covered by this sheet:** " + ", ".join(s.id for s in omitted), ""]
    lines += [
        "Holiday dates come from a built-in 2026 table and any `--holiday` overrides; verify them "
        "against the official calendar. Cases marked Shabbat, Friday, holiday or DST are "
        "deliberately unusual: no or reduced service can be correct there.",
        "",
        "---",
        "",
    ]
    for item in specs:
        lines += render_case(item, records.get(item.id), gid)
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- driver


def display_path(path: Path) -> str:
    """Repository-relative when possible, so sheets do not embed a worktree location."""
    root = Path(__file__).resolve().parents[3]
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_exclusive(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def holiday_table(extra: list[str]) -> dict[date, tuple[str, str]]:
    table = dict(BUILTIN_HOLIDAYS)
    for entry in extra:
        day, _, label = entry.partition("=")
        table[date.fromisoformat(day)] = ("holiday", label or "Holiday (user supplied)")
    return table


def run(
    *,
    client: httpx.Client,
    corpus_path: Path,
    output: Path,
    raw_output: Path,
    first_day: date | None,
    last_day: date | None,
    now: datetime,
    allow_past: bool,
    allow_fixture: bool,
    arrive_by: bool,
    lang: str,
    results: int,
    walk_minutes: int | None,
    holidays: dict[date, tuple[str, str]],
    api_url: str,
) -> int:
    if output.exists() or raw_output.exists():
        raise FileExistsError("Output paths must be new; existing files are never overwritten")
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    status = fetch_status(client)
    meta = status["meta"]
    if meta.get("mode") != "real" and not allow_fixture:
        raise ValueError(
            f"Generation mode is {meta.get('mode')!r}; pass --allow-fixture to proceed"
        )
    window = resolve_window(
        parse_instant(meta["coverage"]["from"]),
        parse_instant(meta["coverage"]["until"]),
        first_day,
        last_day,
    )
    earliest = window[0] if allow_past else max(window[0], now)
    specs = build_case_specs(corpus, window, earliest, holidays, arrive_by)
    records: dict[str, dict[str, Any]] = {}
    for item in specs:
        if item.slot is not None:
            body = request_body(item, lang, results, walk_minutes)
            records[item.id] = call_case(client, body)
    sheet = render_sheet(
        specs=specs,
        records=records,
        status=status,
        generated_at=now,
        window=window,
        earliest=earliest,
        corpus_path=display_path(corpus_path),
        corpus_sha256=sha256_file(corpus_path),
        api_url=api_url,
        options={
            "lang": lang,
            "results": results,
            "walk": "API defaults" if walk_minutes is None else f"{walk_minutes} min access/egress",
            "arrive_by": arrive_by,
            "raw_name": raw_output.name,
        },
    )
    raw = {
        "schemaVersion": SCHEMA_VERSION,
        "tool": "services/api/tools/h3_review.py",
        "generationId": meta["generationId"],
        "generatedAt": now.astimezone(UTC).isoformat(timespec="seconds"),
        "apiUrl": api_url,
        "corpus": {"path": display_path(corpus_path), "sha256": sha256_file(corpus_path)},
        "window": [window[0].isoformat(), window[1].isoformat()],
        "status": status,
        "dates": [
            {
                "id": s.id,
                "rule": s.rule,
                "anchor": s.anchor,
                "instant": s.slot.instant.isoformat() if s.slot else None,
                "flags": list(s.slot.flags) if s.slot else [],
                "omitted": s.omission.reason if s.omission else None,
            }
            for s in specs
        ],
        "cases": [{"id": cid, **record} for cid, record in records.items()],
    }
    write_exclusive(raw_output, json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
    write_exclusive(output, sheet)
    failed = [cid for cid, r in records.items() if r["error"] or r["httpStatus"] != 200]
    mixed = [
        cid
        for cid, r in records.items()
        if isinstance(r.get("response"), dict)
        and r["response"].get("meta", {}).get("generationId") not in (None, meta["generationId"])
    ]
    print(
        f"generation {meta['generationId']}: {len(records)} requests, "
        f"{len(specs) - len(records)} omitted, {len(failed)} errors, {len(mixed)} mixed-generation"
    )
    if failed:
        print("error cases: " + ", ".join(failed), file=sys.stderr)
    return 3 if failed or mixed else 0


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", help="API base URL, e.g. http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, help="New Markdown sheet path")
    parser.add_argument("--raw-output", type=Path, help="New raw JSON path (default beside sheet)")
    parser.add_argument("--corpus", type=Path, default=root / "poc/corpora/journeys.json")
    parser.add_argument("--first-day", type=date.fromisoformat, help="Local YYYY-MM-DD, inclusive")
    parser.add_argument("--last-day", type=date.fromisoformat, help="Local YYYY-MM-DD, inclusive")
    parser.add_argument("--now", type=parse_instant, help="Override the clock (ISO with offset)")
    parser.add_argument("--allow-past", action="store_true", help="Allow instants before now")
    parser.add_argument("--allow-fixture", action="store_true", help="Accept fixture-mode data")
    parser.add_argument("--arrive-by", action="store_true", help="Add arrive-by variants")
    parser.add_argument("--holiday", action="append", default=[], metavar="YYYY-MM-DD[=LABEL]")
    parser.add_argument("--lang", choices=("he", "en"), default="he")
    parser.add_argument("--results", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--max-walk-minutes", type=int, choices=range(1, 31), metavar="1-30")
    parser.add_argument("--plan-only", action="store_true", help="Print dates; no API calls")
    return parser


def main(argv: list[str] | None = None, transport: httpx.BaseTransport | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    now = args.now or datetime.now(UTC)
    try:
        holidays = holiday_table(args.holiday)
        if args.plan_only:
            if not (args.first_day and args.last_day):
                parser.error("--plan-only needs --first-day and --last-day")
            window = resolve_window(None, None, args.first_day, args.last_day)
            earliest = window[0] if args.allow_past else max(window[0], now)
            corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
            specs = build_case_specs(corpus, window, earliest, holidays, args.arrive_by)
            print(render_plan_table(specs))
            return 0
        if not args.api_url or not args.output:
            parser.error("--api-url and --output are required")
        raw_output = args.raw_output or args.output.with_name(args.output.stem + ".raw.json")
        with httpx.Client(
            base_url=args.api_url.rstrip("/"),
            timeout=httpx.Timeout(30.0, connect=3.0),
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        ) as client:
            return run(
                client=client,
                corpus_path=args.corpus,
                output=args.output,
                raw_output=raw_output,
                first_day=args.first_day,
                last_day=args.last_day,
                now=now,
                allow_past=args.allow_past,
                allow_fixture=args.allow_fixture,
                arrive_by=args.arrive_by,
                lang=args.lang,
                results=args.results,
                walk_minutes=args.max_walk_minutes,
                holidays=holidays,
                api_url=args.api_url,
            )
    except (OSError, ValueError, KeyError, httpx.HTTPError, json.JSONDecodeError) as exc:
        print(f"h3 review failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
