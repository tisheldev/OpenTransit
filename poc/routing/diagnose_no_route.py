#!/usr/bin/env python3
"""Why did J09, J17 and J21 return no route?

A no-route is only a finding if it is the engine's answer to a fair question.
Three things can produce an empty result that have nothing to do with whether
Israeli GTFS routes:

  1. The origin or destination coordinate is not near any stop. The corpus says
     so itself -- provenance.coordinates: "APPROXIMATE, hand-entered, NOT yet
     validated against the real GTFS stop set."
  2. MOTIS's default searchWindow is 900 s. With timetableView=true it looks for
     departures in a 15-minute slice. A service every 40 minutes can fall
     outside it.
  3. maxPreTransitTime / maxPostTransitTime default to 900 s of walking, so a
     stop 1.5 km away is out of reach.

This probes each case along those three axes and prints a table. It changes
nothing and decides nothing; it exists so the writeup can say which of the
three it was instead of "MOTIS returned nothing".

The corrected coordinates below are NOT written back into
poc/corpora/journeys.json -- that file belongs to Agent A, who is snapping
every case to a real stop. They are probes.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from feed_context import verified_context, departure_iso

ROUTING = Path(__file__).resolve().parent
BASE = "http://localhost:58080/api/v6/plan"
OUT = ROUTING / "no-route-diagnosis.json"

# (label, from lat/lon, to lat/lon, depart local)
PROBES = [
    # J09 -- Haifa University -> Bat Galim. Both ends have stops within 700 m,
    # so this is the interesting one: neither coordinate is obviously wrong.
    ("J09 as-corpus", (32.7614, 35.0207), (32.8283, 34.9539), "2026-09-09T18:30:00+03:00"),
    ("J09 to the real Bat Galim rail station", (32.7614, 35.0207), (32.8330, 34.9530), "2026-09-09T18:30:00+03:00"),

    # J17/J21 -- Ben Gurion Airport T3. The corpus coordinate 32.0114,34.8867 is
    # 1.53 km from the nearest stop in the feed. The airport's actual T3
    # rail/bus interchange is around 32.0000,34.8706.
    ("J17 as-corpus", (31.9017, 35.0074), (32.0114, 34.8867), "2026-09-07T08:00:00+03:00"),
    ("J17 to the real T3 interchange", (31.9017, 35.0074), (32.0000, 34.8706), "2026-09-07T08:00:00+03:00"),
    ("J21 as-corpus", (32.0836, 34.7981), (32.0114, 34.8867), "2026-09-08T23:40:00+03:00"),
    ("J21 to the real T3 interchange", (32.0836, 34.7981), (32.0000, 34.8706), "2026-09-08T23:40:00+03:00"),
]

# Each probe is run under these query variants, changing one thing at a time.
VARIANTS = [
    ("defaults (as the corpus run)", {}),
    ("searchWindow 2 h", {"searchWindow": "7200"}),
    ("searchWindow 6 h", {"searchWindow": "21600"}),
    ("walk up to 30 min each end", {"maxPreTransitTime": "1800", "maxPostTransitTime": "1800"}),
    ("searchWindow 6 h + 30 min walk",
     {"searchWindow": "21600", "maxPreTransitTime": "1800", "maxPostTransitTime": "1800"}),
]


def ask(frm, to, when, extra):
    q = {"fromPlace": f"{frm[0]},{frm[1]}", "toPlace": f"{to[0]},{to[1]}",
         "time": when, "arriveBy": "false", "numItineraries": "5", "timetableView": "true"}
    q.update(extra)
    try:
        with urllib.request.urlopen(BASE + "?" + urllib.parse.urlencode(q), timeout=180) as r:
            return json.loads(r.read().decode("utf-8")), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    feed_sha, resolved = verified_context()
    corpus = json.loads((ROUTING.parent / 'corpora/journeys.json').read_text(encoding='utf-8'))
    cases = {c['id']: c for c in corpus['cases']}
    results = []
    for label, frm, to, when in PROBES:
        case = cases[label[:3]]
        when = departure_iso(resolved[case['depart']])
        if 'as-corpus' in label:
            frm = (case['from']['lat'], case['from']['lon'])
            to = (case['to']['lat'], case['to']['lon'])
        print(f"\n{label}   depart {when}")
        for vname, extra in VARIANTS:
            body, err = ask(frm, to, when, extra)
            if err:
                print(f"   {vname:32s} ERROR {err}")
                results.append({"probe": label, "variant": vname, "error": err})
                continue
            its = body.get("itineraries") or []
            row = {"probe": label, "variant": vname, "n_itineraries": len(its),
                   "from": frm, "to": to, "depart_local": when, "params": extra}
            if its:
                it = its[0]
                row.update(first_departure=it["startTime"], first_arrival=it["endTime"],
                           duration_min=round(it["duration"] / 60), transfers=it["transfers"],
                           modes=sorted({(l.get("mode") or "") for l in it["legs"]}))
                print(f"   {vname:32s} {len(its)} itineraries, first departs {it['startTime']}, "
                      f"{round(it['duration'] / 60)} min, {it['transfers']} transfers")
            else:
                print(f"   {vname:32s} NO ROUTE")
            results.append(row)
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
