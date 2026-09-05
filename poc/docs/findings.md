# Phase 0 POC — consolidated findings

**Period:** 4–5 September 2026
**Scope:** POC-1, POC-2 and POC-5 complete. POC-3 not started, POC-4 blocked, POC-6 not started.
**Go/No-Go:** 5 of 10 capabilities green (PRD §12)
**Feed under test:** `Gtfs_10_days.zip` sha256 `08c168da…`, `israel-public-transportation.zip`
sha256 `f26b63c2…`, `TripIdToDate.zip` sha256 `97a4b424…`,
`israel-and-palestine-latest.osm.pbf` sha256 `8a34b30f…`, all retrieved 4 Sep 2026

This is the narrative record. The machine-generated status table is `poc/README.md`; the
per-item data problems are `poc/docs/known-data-problems.md` (KDP-001…016); the raw
evidence is `poc/results/*.json`.

---

## 1. The short answer

**The data is obtainable and the routing works.** Israel's nationwide GTFS parses cleanly,
MOTIS turns it into a working journey planner, and the whole thing serves comfortably on a
box a quarter the size we budgeted for. Nothing found so far triggers a PRD §38 kill
criterion.

Three things are not yet answered, and two of them are the same problem: **realtime access
depends on an email to the Ministry that has not been sent**, and the file that makes
realtime matching possible turns out not to work with the feed we had chosen.

The single most consequential finding is KDP-008: `TripIdToDate.zip` cannot be joined to
the 10-day feed at all. Combined with KDP-001, that forced a reversal of the primary-feed
decision on the first day of building.

---

## 2. Capability state

| PRD §12 capability | State | Evidence |
| --- | --- | --- |
| Download current nationwide GTFS | **PASS** | POC-1, cold run from empty directory |
| Parse GTFS | **PASS** | POC-1, 10/10 integrity checks |
| Route using Israeli GTFS | **PASS** | POC-2, 25/25 journeys answered |
| Walking + transit + transfers | **PASS** | POC-2, 20 cases returned the full shape |
| Obtain realtime arrivals | — | POC-3 not started |
| Match realtime ↔ GTFS | — | POC-3 not started |
| Obtain service alerts | **FAIL** | POC-4 blocked: no public URL exists |
| Resolve Israeli addresses/places | **PASS** | POC-5, 68/100 against a bar of 20 |
| Run full end-to-end query | — | POC-6 not started |
| Confirm acceptable data usage terms | **FAIL** | H2: a human must read the gov.il licence |

---

## 3. Static data — POC-1, PASS

A cold run from an empty directory downloads, validates, parses and loads with no manual
step, in **338 seconds at 1,269.7 MB peak RSS**.

| Parsed | Rows |
| --- | ---: |
| stop_times | 32,367,255 |
| shapes | 7,058,126 |
| translations | 1,979,930 |
| fare_rules | 1,726,708 |
| trips | 892,451 |
| stops | 30,858 |
| routes | 6,804 |
| agency | 36 |

All seven PRD §6 file groups parse. Five tables load into Postgres per ADR 0003 —
`stop_times` and `shapes` are validated then handed to MOTIS rather than stored, which
KDP-003 justifies concretely: `stop_times.txt` is 1.77 GB uncompressed.

All ten `edge-cases.json` integrity checks pass. Notably:

- **816,056 of 32,367,255 stop_times rows are at or past 24:00:00**, the largest being
  30:05:00. The after-midnight trap is not hypothetical in this feed; it affects 2.5% of rows.
- **30 Hebrew names round-tripped byte-for-byte** through download → extract → parse →
  Postgres → read, with zero mismatches.
- **No dangling references** in any counted class.
- Service is genuinely not a weekly pattern: 2026-09-05 (Sat) 18.3% of services active,
  2026-09-11 (Fri) 49.8%, 2026-09-12 (Sat) 6.2%.

### The feed structure findings

Seven of the sixteen recorded data problems come from POC-1, and they share a shape: **the
wrong answer is an empty result set, not an exception.**

- **KDP-002** — the two feeds express service days incompatibly. The 10-day feed has
  `calendar_dates.txt` and no `calendar.txt` (one `service_id` per date, the id *is* the
  date); the 60-day feed is the exact opposite. Either assumption silently yields zero
  services on the other feed.
- **KDP-005** — every member of the 60-day feed carries a UTF-8 BOM; no member of the
  10-day feed does. A reader using `utf-8` rather than `utf-8-sig` sees a first column
  named with a leading U+FEFF, and every lookup by `agency_id` returns nothing without
  raising.
- **KDP-009** — `translations.txt` is a different schema in each feed: GTFS-official and
  row-addressed in the 10-day feed, MOT-legacy and string-keyed in the 60-day. This
  explains the 20× size difference. The 10-day feed's contains **no Hebrew at all**, which
  is correct: `feed_lang=He`, so Hebrew is the base value and only EN and AR are translations.
- **KDP-004** — `HEAD` on the feed returns `Content-Length: 3382` with
  `Content-Type: text/html` while `GET` delivers the real 9.8 MB zip. An edge appliance
  answers `HEAD` with an interstitial. A `HEAD`-based change check reports the same 3,382
  bytes forever and never fires. The ingester contains no `HEAD` at all, enforced by a
  static guard.
- **KDP-006** and **KDP-007** — Hebrew gershayim escaped as `""` inside unquoted fields,
  and every row of `TripIdToDate.txt` carrying one field more than its header.

### The finding that changed the plan

**KDP-008 — `TripIdToDate.zip` cannot be joined to the 10-day feed.**

| Feed | Distinct join keys | Present in `TripIdToDate` | Match |
| --- | ---: | ---: | ---: |
| 10-day | 892,451 | 0 | **0.0000%** |
| 60-day | 246,042 | 246,042 | **100%** |

The 60-day feed writes trip ids as `584872860_200926`; strip the `_ddmmyy` suffix and you
have exactly the id space `TripIdToDate.txt` uses. The 10-day feed uses bare numeric ids
from a different space entirely. MOT does not appear to publish a `TripIdToDate` for that
product.

`data-access-findings.md` §3 identifies this file as what makes realtime matching possible.
So the 10-day feed cannot support realtime matching — and **KDP-001** had already shown it
does not cover the current day (`feed_start_date=20260905`, downloaded 4 Sep), so it cannot
answer PRD §39's `--depart-now` either.

Two independent failures against core product requirements. ADR 0005 was reversed on 4 Sep:
**the 60-day feed is now the primary input.** The ingester refuses the mismatched pair by
default rather than loading it silently.

---

## 4. Routing and capacity — POC-2, PARTIAL

MOTIS v2.11.2 built a graph over 892,451 trips and 30,858 locations and answered all 25
corpus journeys. `PARTIAL` is deliberate: 21/25 is a *structural* result, and PRD §7's bar
of 9/10 is a human judgment (checkpoint H3, still open).

### Build and serving are different questions

| | Build, uncapped | Serving, capped at 8 GB |
| --- | ---: | ---: |
| Wall time | 40 s | — |
| Peak RSS | 3,738.6 MB | 1,129.5 MB under load |
| Steady RSS | — | 937.8 MB |
| Graph on disk | 910.8 MB | — |
| | | **13.8% of the cap** |

Load test at the cap: **20,632 requests, all HTTP 200, p50 62 ms, p95 257 ms**, no OOM kill,
no restart. The cap was verified as 8,589,934,592 bytes on the running container and was
never raised.

**This is the most useful architectural number Phase 0 has produced.** system-design §320
sets the production box at 8 GB and §331 allots 2–4 GB to these rows. The measured MOTIS
footprint for all of Israel — timetable, street graph and geocoder in one process — is
about 1.2 GB. On this evidence the 8 GB tier is generous rather than tight, and the 4 GB
shape may be viable.

Caveats that keep this from being the final word: the graph carries a 10-day feed rather
than a full year, no realtime feed was attached, and no API, Redis or Postgres shared the
container.

### The calendar cases passed, which validates the KDP-002 work

- **J22, after midnight.** Requested 02:30, departs 02:39 via bus 445 and the 03:53 airport
  night train. Not 20 hours later — the classic after-midnight failure did not occur.
- **J25, Shabbat.** Nothing offered during Shabbat; first itinerary 18:50 Saturday, by bus
  rather than rail. The calendar is being read correctly.

### A real deployment constraint

The first import died after 3.7 seconds with `unable to import: resize error`, leaving
every `.bin` file at zero length. Cause: the graph directory was bind-mounted from the
Windows filesystem. MOTIS stores its graph in cista memory-mapped vectors that grow by
`ftruncate` and re-`mmap`, which Docker Desktop's file-sharing layer does not support.
Moving to a named volume on ext4 inside the VM fixed it.

**Carry-forward:** system-design §320's "build the graph on a dev box and ship the
artifact" step must land the artifact on a real filesystem — never a shared folder, a
network mount, or an object-storage FUSE mount.

Two further environment traps, both resolved and neither attributable to MOTIS or to
Israeli data: a stale AF_UNIX socket preventing Docker Desktop from starting at all, and
the WSL2 VM memory ceiling (raised to 24 GB *before* the first build, as ADR 0004 requires,
so the recorded build figure measures the build and not a ceiling).

---

## 5. Place search — POC-5, PARTIAL

**68/100 exact, 89/100 in the top five.** PRD §10's bar of 20 is cleared 3.4×, and both
queries the PRD names in its own prose resolve: `Dizengoff Center` to 83 m and
`HaShalom Station` to 53 m. Latency is a non-issue at p50 3.5 ms, p95 62 ms.

| Category | Top-1 | Category | Top-1 |
| --- | --- | --- | --- |
| poi_landmark | 11/12 | misspelling | 8/10 |
| neighborhood | 9/10 | poi_mall | 3/4 |
| poi_university | 8/9 | near_dependent | 3/6 |
| station | 16/20 | translit | 4/9 |
| poi_hospital | 2/5 | **address** | **4/15** |

By language: Hebrew 14/19 (74%), English 54/81 (67%). **Hebrew outperforms English** — the
opposite of the usual worry, and driven almost entirely by the address index.

### Two PRD §10 requirements are not met

**Latin-script street addresses return no address candidate at all.** Probed directly: ten
streets queried in both scripts returned **1 ADDRESS candidate in Latin and 45 in Hebrew**.
House numbers themselves work correctly — walking `דיזנגוף 1/50/100/200/300` moves the
coordinate monotonically along the street. A bounded Nominatim comparison (15 requests at
≤1/s) scores 7/15 against MOTIS's 4/15, and 4/11 against 2/11 on the Latin half, returning
house-level results where MOTIS returns none.

**This is the concrete answer to whether Phase 1 needs Photon.** It is MOTIS's index, not
the OSM data.

**The `near` bias point is inert at MOTIS's default `placeBias`.** Both near-pairs score
"one", and the half that passes is the half that would pass with no bias at all. Sweeping
the parameter shows it does work, but **no single value satisfies all six near cases**:
P095/P096 pass together only at 5, P097/P098 only at 20, and 20 breaks P100.

### Ranked failure modes

| Cause | n |
| --- | ---: |
| Latin-script addresses return no address candidate | 9 |
| A bus stop on a street named after the target outranks the target | 6 |
| A generic word (Station/Mall/Medical Center) outranks the distinctive word | 5 |
| Corpus point approximate, engine answer plausible | 2 |
| `near` bias inert at default | 2 |
| Duplicate OSM feature outranks the city | 2 |
| A satellite stop of the POI outranks the POI | 2 |

Modes 2 and 3 recur across categories and are recorded as KDP-010, KDP-012 and KDP-014.
KDP-013 records a related data problem: the feed's English stop names mix translation and
transliteration with no rule — `מרכז` becomes "Center" for 885 stops and "Merkaz" for 63,
in the same file.

### Venues — bars, restaurants and cafes

Added as a supplement because the main corpus had no venue category. 48 venues sampled
**directly from the OSM extract MOTIS indexed**, so ground truth is exact by construction
rather than hand-entered.

**40/48 exact, 44/48 in top five, and zero queries returned no candidate.**

| | Top-1 | Top-5 |
| --- | ---: | ---: |
| Hebrew-script names (25) | 20 | 23 |
| Latin-script names (23) | 20 | 21 |
| `name:en` variant (20) | 15 | 18 |

Bars 8/8, fast food 8/8, pubs 5/5, nightclubs 2/2; cafes 7/10, restaurants 8/12.

**Every one of the eight misses is a chain** — Aroma, Roladin, Golda, Landwer, Pizza Hut.
The geocoder finds them all and returns *a* branch rather than *the* branch, worst case
283 km away. A city-centre bias pulls those from 58–111 km down to ~5 km but fixes only 3
of 8; the rest land on a different branch of the same chain in the same metro area.

That is arguably the test's fault: a chain query has no single correct answer. The product
lesson is that chain searches need the user's real position and a result list, not one
answer. Recorded as KDP-016.

**Venue search is viable, and unlike addresses it works equally in both scripts.** Anyone
assuming the geocoder is transit-stops-only would be wrong.

---

## 6. Method findings

Four corpus defects were found by running the corpus, not by reading it. All are recorded
because they are evidence about how this kind of testing fails.

- **The Ben Gurion Airport coordinate was 1,532 m from the nearest stop of any kind.**
  Hand-entered in Wave 0. Corrected from GTFS stop 10971. It appeared in five cases
  (J17, J21, S06, P011, P012) and **the correction was not propagated to a sixth, P084** —
  recorded as KDP-015, because a partial fix is its own failure mode.
- **J23's premise was simply wrong.** It asserted Mitzpe Ramon → Metula was unroutable and
  warned that an itinerary meant invented service. MOTIS returned a real 6h49m journey on
  real Metropoline and Egged lines. Israel is too well connected for two towns to be
  mutually unreachable. Rebuilt on Har Karkom, measured at 23,491 m from the nearest stop.
- **Seven further corpus coordinates were wrong**, found by POC-5 and each corrected against
  the feed with the `stop_id` it snapped to. The score moved 62 → 68 on corrections alone.
- **Calendar-relative departure rules go stale.** The corpus originally said "next Monday";
  the 10-day feed's window slides nightly, so those rules had to be rebased onto the feed's
  own declared window. The 60-day feed then turned out to have **no `feed_info.txt` at
  all**, so its window must come from `calendar.txt` instead.

The general lesson: **hand-entered ground truth was wrong roughly 10% of the time.**
Everything derived from the feed or the OSM extract was right. Later corpora were built by
sampling the source data rather than by typing coordinates.

---

## 7. Decisions

### Taken and holding

| | Decision | Basis |
| --- | --- | --- |
| ADR 0001 | Phase 0 follows the PRD POC, not the vertical-slice plan | PRD §5.1 hard rule |
| ADR 0002 | Python for the POC | Developer speed, per system-design §3's own rule |
| ADR 0003 | Postgres + PostGIS; `stop_times` stays out | system-design §169, §173 — confirmed by KDP-003 |
| ADR 0004 | MOTIS | Built and served without incident |
| ADR 0006 | MOTIS built-in geocoding first | Adequate for stations and landmarks; inadequate for Latin addresses |

### Reversed

**ADR 0005 — the 10-day feed is no longer the primary input.** Reversed 4 Sep on KDP-001
and KDP-008. The 60-day feed covers the current day and joins `TripIdToDate` at 100%.

### Open, and needing the developer

1. **H1 — the MOT email.** Deferred. Blocks POC-3 against the real source and POC-4
   entirely. The four-week decision clock has not started.
2. **H2 — the GTFS licence.** gov.il returns 403 to automated fetches, so a human must read
   and record the terms. This is kill criterion #5 and one of two red Go/No-Go rows.
3. **H3 — route quality.** 25 itineraries await comparison against Moovit. The review sheet
   was produced on the 10-day feed and should be regenerated on the 60-day feed first.
4. **H4 — search quality.** 32 blank verdict lines. P012, P023 and P065 are judgment rather
   than distance.
5. **The 4 GB question.** Serving used 13.8% of 8 GB. Whether to re-cost system-design §331.
6. **`placeBias`.** No single value works. Tune per query class, or treat "search near me"
   as unsupported in Phase 0.
7. **Default walking budget.** MOTIS allows 15 minutes to the first stop; Haifa's Carmel
   needs more. J09 routes cleanly at 30 minutes.
8. **KDP-013's synonym layer.** A cleaning rule; PRD §13 wants it written down before it is
   applied.

---

## 8. What Phase 0 still does not know

- **Whether realtime data can be obtained at all.** SIRI needs a MOT-issued key *and* a
  whitelisted source IP. Untested; the email is unsent.
- **The realtime match rate.** Kill criterion #4 is about rate, not access, and can be
  measured against Open Bus Stride without MOT. Not yet attempted.
- **Whether service alerts exist for us.** No public URL. Fully gated.
- **Whether the routes are any good.** Structural consistency is not quality.
- **How the graph behaves on a full-year feed.** All capacity figures come from a 10-day
  window and will grow.
- **Whether the licence permits the intended use.** Unread.

---

## 9. Evidence index

| File | What |
| --- | --- |
| `poc/README.md` | Machine-generated status and Go/No-Go table |
| `poc/docs/known-data-problems.md` | KDP-001…016, each with feed hash and action |
| `poc/docs/adr/` | Decisions 0001–0006 |
| `poc/results/poc-1.json` | Ingest metrics, 10 integrity checks, validation examples |
| `poc/results/poc-1-evidence.json` | Full per-check evidence |
| `poc/results/poc-2.json` | Build and serving metrics, 25 journey outcomes |
| `poc/results/journeys-h3-review.md` | H3 review sheet, 25 itineraries |
| `poc/results/poc-5.json` | 100 geocoding cases, per-category, `placeBias` sweep |
| `poc/results/poc-5-nominatim.json` | Bounded Nominatim comparison |
| `poc/results/poc-5-venues.json` | 48 venue cases |
| `poc/results/places-h4-review.md`, `venues-h4-review.md` | H4 review sheets |
| `poc/data/manifest.json` | Feed hashes, sizes, zip validation |
| `poc/corpora/` | Journeys, places, venues, stops, integrity checks |
