# Known data problems

Findings about the real MOT data, recorded as they are discovered. PRD §13 requires this
list as a Phase 0 deliverable. Entries are evidence, not speculation: each cites the feed
hash it was observed in.

Feed hashes referenced here are recorded in `poc/data/manifest.json`.

---

## KDP-001 — The 10-day feed does not cover the current day

**Found:** Wave 0, 4 Sep 2026
**Feed:** `Gtfs_10_days.zip`, sha256 `08c168da…`, downloaded 4 Sep 2026 15:34 local
**Severity:** High — affects ADR 0005 and the PRD §39 demo

`feed_info.txt` declares:

```
feed_start_date=20260905
feed_end_date=20260914
```

The feed was downloaded on **4 September** and its service window begins on
**5 September**. Today is not in it.

The 60-day feed does cover today — its `calendar.txt` has services starting `20260904`.

### Why it matters

PRD §39's acceptance demo is `--depart-now`. Against the currently-published 10-day feed,
"now" falls outside the service window, so a correct engine returns **no journeys** — not
because routing is broken, but because the data does not describe today.

An operator therefore cannot run on the freshly-published 10-day feed alone. The options,
none of which are yet decided:

1. Retain the previous day's 10-day feed until the new window opens.
2. Use the 60-day feed for the current day and the 10-day feed for the near window.
3. Load both and prefer the 10-day feed wherever the windows overlap.

### Action

Revisit ADR 0005, which chose the 10-day feed as the primary input on the strength of
`data-access-findings.md` §1 ("for a journey planner the 10-day feed is the accurate one").
That reasoning is still sound about accuracy, but incomplete: it did not account for the
window opening tomorrow. This is a **decision for the developer**, not something an agent
should resolve unilaterally.

---

## KDP-002 — The two feeds express service days in incompatible ways

**Found:** Wave 0, 4 Sep 2026
**Feeds:** both, hashes `08c168da…` and `f26b63c2…`
**Severity:** Medium — a correctness trap for any shared ingestion code

The two feeds are structurally different, and neither is malformed.

**10-day feed** — `calendar_dates.txt` only, **no `calendar.txt` at all**. One `service_id`
per date, where the id *is* the date. The entire file is ten rows:

```
service_id,date,exception_type
20260905,20260905,1
20260906,20260906,1
...
20260914,20260914,1
```

Trips reference it directly: `route_id=3575, service_id=20260906, trip_id=1684794342`.

**60-day feed** — standard `calendar.txt` weekly patterns, **no `calendar_dates.txt`**:

```
service_id,sunday,monday,tuesday,wednesday,thursday,friday,saturday,start_date,end_date
1,1,1,1,1,1,0,0,20260904,20260911
2,1,1,1,1,1,0,0,20260914,20261004
```

### Why it matters

- Ingestion code that assumes `calendar.txt` exists breaks on the 10-day feed. Code that
  assumes `calendar_dates.txt` exists breaks on the 60-day feed. Both assumptions are
  common, and both fail silently by producing zero services rather than an error.
- The 10-day feed's one-service-per-date design means a trip runs on exactly one date.
  That is unusually clean for realtime matching, and may make parts of the 147 MB
  `TripIdToDate.txt` redundant for this feed. Worth measuring in POC-3 before assuming it.
- The 60-day `calendar.txt` sample confirms the Israeli work week in data:
  Sunday–Thursday = 1, Friday = 0, Saturday = 0. Journey case J25 (Shabbat) is testing a
  real property of the feed, not a guess.

### Action

The ingester must handle both shapes and must **fail loudly** when a feed defines no
services at all, rather than returning an empty result set.

---

## KDP-003 — `stop_times.txt` is larger in the 10-day feed than the 60-day feed

**Found:** Wave 0, 4 Sep 2026
**Severity:** Informational — but it confirms ADR 0003

Uncompressed sizes inside the zips:

| File | 10-day feed | 60-day feed |
| --- | ---: | ---: |
| `stop_times.txt` | **1,770,642,811 B** (1.77 GB) | 1,066,581,537 B (1.07 GB) |
| `shapes.txt` | 239,549,602 B | 229,422,513 B |
| `translations.txt` | **126,836,299 B** | 6,202,205 B |
| `trips.txt` | 61,019,564 B | 37,578,715 B |

The 10-day feed being *larger* than the 60-day feed matches
`data-access-findings.md` §1 and follows from KDP-002: one service per date means trips
are enumerated per day rather than compressed into weekly patterns.

`translations.txt` is 20× larger in the 10-day feed. That has not been explained yet and
should be inspected before anyone assumes the two files mean the same thing.

### Why it matters

A 1.77 GB `stop_times.txt` is the concrete justification for ADR 0003's decision not to
load it into Postgres. system-design §173 predicted this; the file confirms it.

---

## KDP-004 — `HEAD` returns a false `Content-Length`

**Found:** `data-access-findings.md` §1, 28 Aug 2026. Not yet re-verified in Wave 0.
**Severity:** High — silently breaks change detection

A `HEAD` on `israel-public-transportation.zip` returned `Content-Length: 3382` against an
actual file of ~164 MB.

### Action

Change detection uses `GET` plus zip validation. Agent A re-verifies this and records the
current numbers as corpus check E01.
