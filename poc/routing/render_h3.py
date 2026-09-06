#!/usr/bin/env python3
"""Render poc/results/journeys-h3-review.md -- the sheet a human sits down with.

Checkpoint H3 is a person comparing these itineraries against Moovit, Google
Maps and BetterRail and deciding whether they are ones a real traveller would
take. PRD 7 sets the bar at 9 of the 10 required journeys, and nothing in
poc/routing/ is allowed to make that call.

So this file's only job is to put each returned itinerary in front of that
person in a form they can read without opening a JSON file or this code:
local Israeli clock times, line numbers, operator names, stop names as the feed
spells them, and a blank verdict line to fill in.

Everything the machine already decided is shown too -- but as context, clearly
separated from the verdict, never as the answer.

Usage:
    python poc/routing/render_h3.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROUTING = Path(__file__).resolve().parent
POC = ROUTING.parent
OUT = POC / "results" / "journeys-h3-review.md"

PRIMARY = ROUTING / "corpus-result.json"
VARIANT = ROUTING / "corpus-result-generous-walk.json"
DIAGNOSIS = ROUTING / "no-route-diagnosis.json"
BUILD = ROUTING / "import-result.json"
STRESS = ROUTING / "serving-stress.json"
STEADY = ROUTING / "serving-steady.json"

from feed_context import IL


def L(iso: str | None) -> str:
    """UTC timestamp -> Israeli local clock time, which is what a reviewer
    comparing against Moovit is looking at."""
    if not iso:
        return "??:??"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IL).strftime("%H:%M")
    except Exception:
        return iso


def Lfull(iso: str | None) -> str:
    if not iso:
        return "?"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IL).strftime("%a %d %b %H:%M")
    except Exception:
        return iso


def minutes_after(requested: str, actual: str) -> int | None:
    try:
        a = datetime.fromisoformat(requested)
        b = datetime.fromisoformat(actual.replace("Z", "+00:00"))
        return round((b - a).total_seconds() / 60)
    except Exception:
        return None


def render_itinerary(raw: dict, requested: str) -> list[str]:
    """One itinerary as a readable timeline."""
    L_ = []
    legs = raw.get("legs") or []
    off = minutes_after(requested, raw.get("startTime"))
    off_txt = ""
    if off is not None:
        off_txt = " (at the requested time)" if off <= 2 else f" ({off} min after the requested time)"
    L_.append(f"    Departs {Lfull(raw.get('startTime'))}{off_txt}")
    L_.append(f"    Arrives {Lfull(raw.get('endTime'))} "
              f"-- {round((raw.get('duration') or 0) / 60)} min, {raw.get('transfers')} transfer(s)")
    L_.append("")
    for lg in legs:
        mode = (lg.get("mode") or "?").upper()
        frm = (lg.get("from") or {}).get("name") or "?"
        to = (lg.get("to") or {}).get("name") or "?"
        t = f"{L(lg.get('startTime'))}-{L(lg.get('endTime'))}"
        if mode == "WALK":
            d = lg.get("distance")
            dist = f"{round(d)} m" if isinstance(d, (int, float)) else "distance not reported"
            L_.append(f"    {t}  walk {dist:<24} {frm} -> {to}")
        else:
            line = (lg.get("routeShortName") or "").strip() or "(no line number in feed)"
            agency = lg.get("agencyName") or "?"
            head = lg.get("headsign") or ""
            label = f"{mode.lower().replace('_', ' ')} {line}"
            L_.append(f"    {t}  {label:<29} {frm} -> {to}")
            L_.append(f"{'':<15}operator {agency}" + (f", towards {head}" if head else ""))
    return L_


def main() -> int:
    primary = json.loads(PRIMARY.read_text(encoding="utf-8"))
    variant = json.loads(VARIANT.read_text(encoding="utf-8")) if VARIANT.exists() else None
    build = json.loads(BUILD.read_text(encoding="utf-8")) if BUILD.exists() else {}
    stress = json.loads(STRESS.read_text(encoding="utf-8")) if STRESS.exists() else {}
    steady = json.loads(STEADY.read_text(encoding="utf-8")) if STEADY.exists() else {}
    from feed_context import verified_context
    feed_sha, _ = verified_context()
    for evidence in (primary, variant, build, stress, steady):
        if evidence and evidence.get('feed_sha256') != feed_sha:
            raise ValueError('Mixed-feed H3 evidence; rerun routing measurements')
    diagnosis = []  # Historical probes are preserved in comparisons; do not mix feeds.

    var_by_id = {c["id"]: c for c in (variant or {}).get("cases", [])}

    out: list[str] = []
    A = out.append

    A("# POC-2 — journey review sheet for checkpoint H3")
    A("")
    A("**This sheet is the checkpoint, not a report of one.** Everything below was")
    A("produced by machine checks that verify *structure* — that legs join up, that")
    A("times run forwards, that stop ids exist in the feed, that durations are not")
    A("absurd. None of it judges whether a route is one a person would actually take.")
    A("PRD §7 puts that bar at **9 of the 10 required journeys producing reasonable,**")
    A("**usable routes**, judged by comparison against Moovit, Google Maps and")
    A("BetterRail. That judgement is yours.")
    A("")
    A("Fill in the `Verdict:` line under each case. `reasonable` / `not reasonable` /")
    A("`unsure`, plus a note if it helps.")
    A("")
    A("---")
    A("")
    A("## What you are looking at")
    A("")
    A(f"- **Feed:** `israel-public-transportation.zip`, sha256 `{primary['feed_sha256'][:16]}…`")
    A(f"- **Service window:** {primary['feed_window']}; departures resolved from service calendars")
    A(f"- **Engine:** MOTIS v2.11.2, endpoint `{primary['plan_endpoint']}`")
    A(f"- **Graph built:** {round((build.get('wall_seconds') or 0))} s, peak {build.get('peak_rss_mb')} MB, "
      f"{build.get('graph_size_mb')} MB on disk")
    A("- **Served from:** a container capped at **8 GB** (system-design §320's production box)")
    if steady:
        A(f"- **At rest:** {steady['steady_rss_mb']} MB, "
          f"{steady['steady_pct_of_cap']}% of the cap; range {steady['min_rss_mb']}–{steady['max_rss_mb']} MB across {steady['samples']} samples")
    if stress:
        A(f"- **Under load:** {stress['requests']} requests, HTTP statuses {stress['http_status_counts']}, p95 {stress['latency_ms']['p95']} ms, "
          f"peak {stress['peak_rss_mb']} MB = {stress['peak_rss_pct_of_cap']}% of the cap; "
          f"OOM killed: {stress['container_state_after'].get('oom_killed')}, restarts: {stress['container_state_after'].get('restart_count')}")
    A("")
    A("Times are **Israeli local time (Asia/Jerusalem)**. Stop names are exactly as the")
    A("MOT feed spells them, in Hebrew, because that is what you will be matching")
    A("against in Moovit.")
    A("")
    A("### Two query profiles were run")
    A("")
    A("- **default** — MOTIS as shipped. This is the primary result. It allows 15")
    A("  minutes of walking to the first stop and from the last.")
    A("- **generous-walk** — the same 25 cases with that walking budget raised to 30")
    A("  minutes. Where the two disagree it is noted in the case, because \"no route\"")
    A("  caused by a walking budget is a very different finding from \"no route\"")
    A("  caused by the data.")
    A("")
    j = primary["journeys"]
    A(f"**Machine totals (default profile): {j['answered']}/{j['total']} answered, "
      f"{j['structural_pass_any']} structurally consistent with the case's expectations.**")
    if variant:
        vj = variant["journeys"]
        A(f"**Same under generous-walk: {vj['structural_pass_any']}/{vj['total']}.**")
    A("")
    A("---")
    A("")

    # ---------------------------------------------------------------- cases
    for c in primary["cases"]:
        cid = c["id"]
        A(f"## {cid} — {c['from']} → {c['to']}")
        A("")
        if c.get("prd_ref"):
            A(f"*{c['prd_ref']}* · category `{c['category']}`")
        else:
            A(f"category `{c['category']}`")
        A("")
        A(f"**Departing:** {c['depart_local']} (rule `{c['depart_rule']}`)")
        A("")
        if c.get("human_review"):
            A(f"> **What to check:** {c['human_review']}")
            A("")

        exp = c["expect"]
        bits = [f"outcome `{exp.get('outcome', 'route')}`"]
        for k in ("modes_any_of", "modes_all_of", "min_transfers", "max_transfers",
                  "min_duration_min", "max_duration_min", "max_walk_m"):
            if k in exp:
                bits.append(f"`{k}` = {exp[k]}")
        A("**The corpus expected:** " + ", ".join(bits))
        A("")

        outcome = c.get("outcome")
        if outcome == "error":
            A(f"**RESULT: request failed** — {c.get('notes')}")
        elif outcome == "no-route":
            A("**RESULT: no route returned.**")
            A("")
            vc = var_by_id.get(cid)
            if vc and vc.get("outcome") == "route":
                A("With the walking budget raised to 30 minutes each end, this case *does*")
                A("route. The itinerary it produces is shown below — it is from the")
                A("**generous-walk** profile, not the default one.")
                A("")
                vr = json.loads((ROUTING / "responses-generous-walk" / f"{cid}.json")
                                .read_text(encoding="utf-8"))
                its = (vr.get("response") or {}).get("itineraries") or []
                if its:
                    A("```")
                    out.extend(render_itinerary(its[0], vc["depart_local"]))
                    A("```")
                    A("")
            else:
                rel = [d for d in diagnosis if d.get("probe", "").startswith(cid)]
                if rel:
                    A("Probes run against this case (see `poc/routing/no-route-diagnosis.json`):")
                    A("")
                    A("| variation | result |")
                    A("| --- | --- |")
                    for d in rel:
                        n = d.get("n_itineraries")
                        res = "no route" if not n else f"{n} itineraries, {d.get('duration_min')} min, {d.get('transfers')} transfers"
                        A(f"| {d['probe']} — {d['variant']} | {res} |")
                    A("")
        else:
            its = c.get("itineraries") or []
            resp = json.loads((ROUTING / "responses" / f"{cid}.json").read_text(encoding="utf-8"))
            raw_its = (resp.get("response") or {}).get("itineraries") or []
            A(f"**RESULT: {len(raw_its)} itinerary/itineraries returned.** The first one — the one a")
            A("user would be shown — is:")
            A("")
            if raw_its:
                A("```")
                out.extend(render_itinerary(raw_its[0], c["depart_local"]))
                A("```")
                A("")
            if len(raw_its) > 1:
                A("<details><summary>Alternatives MOTIS also returned "
                  f"({len(raw_its) - 1} more)</summary>")
                A("")
                for i, it in enumerate(raw_its[1:4], start=1):
                    A(f"**Alternative {i}**")
                    A("")
                    A("```")
                    out.extend(render_itinerary(it, c["depart_local"]))
                    A("```")
                    A("")
                A("</details>")
                A("")

        # Machine notes, clearly fenced off from the human verdict.
        mach = []
        if c.get("structural"):
            mach.append(f"structural check (any itinerary): **{c['structural']}**")
        if c.get("structural_first") and c.get("structural_first") != c.get("structural"):
            mach.append(f"structural check (the itinerary shown): **{c['structural_first']}**")
        for n in (c.get("notes") or []):
            mach.append(n)
        s0 = (c.get("itineraries") or [{}])[0]
        if s0.get("expectation_failures"):
            mach.append("first itinerary missed: " + "; ".join(s0["expectation_failures"]))
        if s0.get("wellformed_problems"):
            mach.append("**well-formedness problems: " + "; ".join(s0["wellformed_problems"]) + "**")
        if mach:
            A("<sub>Machine checks (structure only — not a quality judgement): "
              + " · ".join(mach) + "</sub>")
            A("")
        A(f"**Verdict:** ")
        A("")
        A("---")
        A("")

    A("## When you are done")
    A("")
    A("Count the verdicts on the ten PRD §7 journeys — the cases tagged with a")
    A("`PRD §7` reference above. Nine or more `reasonable` meets the PRD bar and")
    A("POC-2 can move from PARTIAL to PASS. Fewer than nine is the FAIL/STOP")
    A("condition in PRD §7, which says to investigate another engine before")
    A("continuing — and ADR 0004 says that switch is your decision, not an agent's.")
    A("")
    A("Update `poc/results/poc-2.json` with the outcome and re-run")
    A("`python poc/poc_status.py --write`.")
    A("")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(out)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
