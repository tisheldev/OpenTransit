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

Resolved by the accepted 5 September ADR 0005 amendment: the 60-day feed plus
compatible TripIdToDate is now the executable primary. The alternatives above
are historical options, not active configuration. Ten-day data is comparison only.

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

**Found:** `data-access-findings.md` §1, 28 Aug 2026. **Re-verified Wave 1, 4 Sep 2026.**
**Severity:** High — silently breaks change detection

A `HEAD` on `israel-public-transportation.zip` returned `Content-Length: 3382` against an
actual file of ~164 MB.

### Re-verified, 4 Sep 2026 (corpus check E01)

Against `https://gtfs.mot.gov.il/gtfsfiles/TripIdToDate.zip`, seconds apart:

| | Status | `Content-Length` | `Content-Type` | Bytes delivered |
| --- | --- | ---: | --- | ---: |
| `HEAD` | 200 | **3382** | `text/html; charset=utf-8` | — |
| `GET` | 200 | 9781611 | `application/x-zip-compressed` | **9,781,611** |

The discrepancy is worse than a wrong number: `HEAD` is answered with an **HTML document**,
not a truncated zip. The edge appliance in front of the origin (it also sets a
`TS01446b9e` cookie) serves an interstitial to `HEAD` and the real bytes to `GET`. A
`HEAD`-based check therefore reports the same 3382 bytes forever and change detection never
fires.

`GET` does return usable `Last-Modified` and `ETag` headers, but POC-1 does not trust them
for decisions — content hash is the only signal used.

### Action

Change detection uses `GET` plus zip validation, implemented in `poc/gtfs/fetch.py`, which
contains no `HEAD` at all; `poc/gtfs/checks.py` greps the whole refresh path for one as a
static guard and holds the only `HEAD` in the project, as a diagnostic whose result feeds
no decision.

---

## KDP-005 — The two feeds disagree about the UTF-8 BOM

**Found:** Wave 1 (Agent A, POC-1), 4 Sep 2026
**Feeds:** `Gtfs_10_days.zip` `08c168da…`, `israel-public-transportation.zip` `f26b63c2…`,
`TripIdToDate.zip` `97a4b424…`
**Severity:** Medium — produces a silent zero-row parse, not an error

Every member of the 60-day feed starts with a UTF-8 byte-order mark. No member of the
10-day feed does. `TripIdToDate.txt` has one.

```
60-day  agency.txt   first bytes: b'\xef\xbb\xbfagency_id,agency_name'
10-day  agency.txt   first bytes: b'agency_id,agency_name,ag'
TripIdToDate.txt     first bytes: b'\xef\xbb\xbfLineDetailRecordId,OfficeLineId,Direc'
```

Measured across all 12 members of the 10-day feed: `has_utf8_bom` is false for every one.

### Why it matters

A reader opened with `encoding="utf-8"` rather than `utf-8-sig` sees the 60-day feed's
first column named with a leading U+FEFF. Every lookup by `agency_id` then returns nothing
and the parse produces zero rows *without raising*. Same failure shape as KDP-002: the
wrong answer is an empty result set, not an exception.

### Action

Read every GTFS member with `utf-8-sig`, which is correct with or without a BOM.
`poc/gtfs/zipread.py` does this and records `has_utf8_bom` per member so the difference
stays visible rather than being absorbed.

---

## KDP-006 — `routes.txt` escapes the Hebrew gershayim as `""` inside unquoted fields

**Found:** Wave 1 (Agent A, POC-1), 4 Sep 2026
**Feed:** `Gtfs_10_days.zip`, sha256 `08c168da…`
**Severity:** Medium — a display defect today, a data-cleaning decision before Phase 1

821 of 6,804 `route_long_name` values contain a doubled ASCII quote. Verbatim rows:

```
33184,25,35א,א""ת עד הלום - איזור תעשיה כבדה,,3,,,000000,1,1
16219,3,13א,6הימים/יוה""כ - מילצן,,3,,,000000,1,1
```

The field is **not** quoted, so `""` is not CSV escaping — a conformant parser returns the
two characters literally. `routes.txt` contains **821** fields with `""` and **zero** with
a single `"`.

`stops.txt` in the same zip does the opposite: **2,295** fields carry a single `"` (the
Hebrew gershayim, used correctly) and exactly **one** carries `""`:

```
109,107,גן טכנולוגי/א""ס הפועל,Street: דרך אגודת ספורט הפועל City: ירושלים Platform:  Floor:,31.749363,35.18528,107,0,,Asia/Jerusalem,,,
```

The 60-day feed's `stops.txt` contains neither form — it writes the same abbreviations with
two ASCII apostrophes instead, as in `בי''ס בר לב/בן יהודה`.

### Why it matters

`א""ת עד הלום` reaches the database, and any UI, with a doubled quote where the source
plainly means `א"ת עד הלום`. Three conventions for one character are in use across two
files of a single publication.

### Action

**No transformation is applied in POC-1.** Names are stored byte-for-byte, which is what
corpus check E03 asserts. Collapsing `""` to `"` is probably right for both files, but
that is a cleaning rule, and PRD §13 wants cleaning rules written down before they are
applied rather than discovered later in a diff. Decision for the developer.

---

## KDP-007 — Every row of `TripIdToDate.txt` has one field more than its header

**Found:** Wave 1 (Agent A, POC-1), 4 Sep 2026
**Feed:** `TripIdToDate.zip`, sha256 `97a4b424…`
**Severity:** Low — but it breaks a strict reader on the first data row

The header declares nine columns. All **1,961,317** data rows carry ten fields, because
each ends with a trailing comma. Verbatim:

```
LineDetailRecordId,OfficeLineId,Direction,LineAlternative,FromDate,ToDate,TripId,DayInWeek,DepartureTime
1,67001,1,#,01/09/2026 00:00:00,10/09/2026 00:00:00,1,1,05:10,
1,67001,1,#,01/09/2026 00:00:00,10/09/2026 00:00:00,13711613,4,08:45,
```

The tenth field is empty in every row observed. The file also uses `dd/mm/yyyy HH:MM:SS`
dates, unlike GTFS's `yyyymmdd`.

### Action

`poc/gtfs/zipread.py` counts field-count mismatches instead of dropping the rows and keeps
the surplus under `_extra`. The count is reported (1,961,317 of 1,961,317), so the anomaly
cannot pass unnoticed.

---

## KDP-008 — `TripIdToDate.zip` does not belong with the 10-day feed at all

**Found:** Wave 1 (Agent A, POC-1), 4 Sep 2026
**Feeds:** `Gtfs_10_days.zip` `08c168da…`, `israel-public-transportation.zip` `f26b63c2…`,
`TripIdToDate.zip` `97a4b424…` — all retrieved 4 Sep 2026 within nine minutes of each other
**Severity:** High — this is the file `data-access-findings.md` §3 says makes realtime
matching possible, and it cannot be joined to the feed ADR 0005 chose

Measured overlap of trip identifiers:

| Feed | Distinct join keys | Present in `TripIdToDate.TripId` | Match |
| --- | ---: | ---: | ---: |
| `Gtfs_10_days.zip` | 892,451 | **0** | **0.0000%** |
| `israel-public-transportation.zip` | 246,042 | **246,042** | **100.0000%** |

The 60-day feed writes trip ids as `<TripId>_<ddmmyy>`, for example `584872860_200926`;
stripping the suffix yields exactly the id space `TripIdToDate.txt` uses. The 10-day feed
writes a bare numeric id such as `1684794342`, drawn from a different id space entirely.
`TripIdToDate.txt` holds 773,670 distinct ids and not one of them is a 10-day trip id.

### Why it matters

- ADR 0005's stated consequence — "`TripIdToDate.zip` must be versioned in lockstep with
  whichever feed is loaded" — **cannot be satisfied for the 10-day feed**. There is no
  lockstep to be in: MOT does not appear to publish a TripIdToDate for that product.
- KDP-002 suspected the file "may make parts of the 147 MB `TripIdToDate.txt` redundant for
  this feed". The measurement is stronger than that: it is not redundant, it is unjoinable.
- POC-3 must therefore match realtime against the 60-day feed, or find another key. That
  choice is now recorded in the accepted primary-feed amendment in ADR 0005.

### Action

The ingester and graph preflight require complete normalized key coverage and
an overlapping known date window (`FeedPairingError`, E05). The old unpaired-load
flag and wrapper bypass are removed. Current primary pairing is accepted; the
ten-day comparison is rejected. This does not establish realtime matching or
per-service-date mapping uniqueness.

---

## KDP-009 — `translations.txt` is a different file in each feed, and carries no Hebrew

**Found:** Wave 1 (Agent A, POC-1), 4 Sep 2026
**Feeds:** both, `08c168da…` and `f26b63c2…`
**Severity:** Medium — resolves the open question left by KDP-003

|  | 10-day feed | 60-day feed |
| --- | --- | --- |
| Header | `table_name,field_name,language,translation,record_id,record_sub_id,field_value` | `trans_id,lang,translation` |
| Schema | GTFS official Translations | MOT legacy |
| Rows | 1,979,930 | 102,514 |
| Languages | `EN` 989,989 / `AR` 989,941 | `HE` 36,913 / `AR` 32,806 / `EN` 32,795 |
| Uncompressed | 126,836,299 B | 6,202,205 B |
| Malformed rows | 0 | 0 |

This explains the 20× size difference KDP-003 flagged as unexplained: the files are not two
versions of one thing, they are two different formats. The 10-day feed's is row-addressed
(`record_id` points at a `trips` or `stops` row); the 60-day feed's is keyed by the Hebrew
string itself.

The 10-day feed's `translations.txt` contains **no Hebrew rows at all**. That is correct
rather than missing — `feed_info.txt` declares `feed_lang=He` and `default_lang=He`, so
Hebrew is the base value in `stops.txt` and `routes.txt`, and only EN and AR are
translations.

### Why it matters

A translation lookup written against either schema returns nothing against the other, with
no error. Anything reading translations must branch on which feed produced them.

### Action

No sanitisation applied. Nothing in either file needed cleaning to parse and both parsed
with zero malformed rows (corpus check E04). Recorded so that the branch is deliberate.

---

## KDP-010 — A stop named after a railway station is usually the bus stop outside it

**Found:** Wave 1 (Agent A, POC-1), 4 Sep 2026
**Feed:** `Gtfs_10_days.zip`, sha256 `08c168da…`
**Severity:** High for POC-5 (geocoding) and POC-2 (routing) — a name search returns
the wrong stop, plausibly, with no error

Israel Railways' own stops carry short plain names. The bus stops *outside* those
stations carry the long descriptive names that contain the words a person would search
for. Measured by resolving the ten `poc/corpora/stops.json` entries twice — once on name
and distance only, then again using the `route_type` observed calling at each candidate:

| Corpus entry | Name + distance only | Adding observed mode |
| --- | --- | --- |
| S01 Tel Aviv Savidor | `14966` `ת. רכבת תל אביב - סבידור/הורדה` — **bus**, 162 m | `10945` `תל אביב מרכז` — rail, 19 m |
| S02 Tel Aviv HaShalom | `13316` `ת. רכבת השלום` — **bus**, 53 m | `10949` `השלום` — rail, 76 m |
| S04 Haifa Center HaShmona | `30113` `תחנת רכבת חיפה מרכז השמונה` — **bus**, 117 m | `10934` `חיפה מרכז` — rail, 226 m |
| S06 Ben Gurion Airport | `19719` `שדה תעופה בן גוריון/טרמינל 1` — **bus**, 2103 m | `10971` `נתב"ג` — rail, 1961 m |

Four of the six rail entries snapped onto a bus stop. In every case the bus stop is the
*better* string match: `תחנת רכבת חיפה מרכז השמונה` contains every token of "Haifa Center
HaShmona" while the actual railway station is called just `חיפה מרכז`.

The same trap runs the other way for abbreviations. Ben Gurion Airport's railway station
is `נתב"ג`, which shares no token at all with `נמל תעופה בן גוריון`; only the
route-type filter finds it.

### Why it matters

- **POC-5.** A place search that ranks by string similarity to a station name will return
  the bus stop across the road. It looks right in a list and produces a different journey.
- **POC-2.** A journey from "Tel Aviv Savidor" that starts at stop `14966` starts on the
  bus network, not on the railway, and will be judged wrong by a human comparing against
  Moovit — for a reason that has nothing to do with the router.
- Distance does not rescue it: `13316` is *closer* to the HaShalom coordinate than the
  actual railway stop is.

### Action

`poc/gtfs/corpus.py` resolves mode-aware: candidates are ranked on name-token overlap
**and** on whether the mode asked for is observed calling there, in staged radii of 300 m,
1 km and 3 km. All ten corpus entries now resolve to a stop served by the requested mode.
Entries whose resolution is over 500 m away, or that fell back to pure distance, are
flagged `low_confidence` in `poc/corpora/stops.json` for checkpoint H4 — currently only
S06, whose corpus coordinate is ~2 km from any airport stop.

Agent D should assume the same trap applies to geocoding and not rely on name similarity
alone.

---

## KDP-011 — `parent_station` grouping is a bus-terminal construct, not a station model

**Found:** Wave 1 (Agent A, POC-1), 4 Sep 2026
**Feed:** `Gtfs_10_days.zip`, sha256 `08c168da…`
**Severity:** Informational — but it contradicts the assumption behind corpus check E09

Of 30,858 stops: 30,634 are `location_type = 0` and 224 are `location_type = 1` stations.
Only 772 stops (2.5%) name a `parent_station` at all. Zero dangling parent references.

The grouping is used for multi-level bus terminals — the largest are
`ת.מרכזית באר שבע/רציפים בינעירוני` (23 platforms),
`ת.מרכזית תל אביב קומה 6/רציפים` (21) and `ת. מרכזית ירושלים קומה 3/רציפים` (16).

**None of the six rail corpus entries resolved to a stop with platform children.** Israel
Railways stations appear as single `location_type = 0` stops: `תל אביב מרכז`, `השלום`,
`חיפה מרכז`, `נתב"ג`, `באר שבע מרכז` each have no children and no parent.

### Why it matters

E09 expects "multi-platform stations (Savidor, Tel Aviv CBS) resolve as a station rather
than as unrelated scattered platforms". That holds for Tel Aviv CBS (7 platforms grouped
under `15071`) and for Jerusalem CBS (16 under `3527`). It does not hold for Savidor,
because the feed does not model rail platforms at all — there is nothing scattered to
group. Any code that expects to walk from a rail station to its platforms will find none.

### Action

Recorded, not worked around. `poc/gtfs/queries.py` measures the grouping rather than
assuming it, and E09's evidence carries the counts.

---

## KDP-012 — Stops on a street named after a place outrank the place itself

**Found:** Wave 1 (Agent C, POC-5), 4 Sep 2026
**Feed:** `Gtfs_10_days.zip`, sha256 `08c168da…`
**Severity:** High for POC-5 and POC-6 — the wrong answer is confident, plausible and
in the wrong city

KDP-010 recorded this trap for railway stations. POC-5 shows it is not a rail problem:
it is a property of MOT stop naming in general. Israeli streets are named after the
same people, towns and landmarks that users search for, and MOT names bus stops
`<street>/<cross-street>`. A name search therefore competes against thousands of
street-derived stop names that contain the query verbatim.

Measured over the 100-query POC-5 corpus, this is the **second-largest failure cause,
6 of 32 failures**. Verbatim top-1 results, MOTIS built-in geocoder:

| Query | Meant | Returned at rank 1 | Where | Off by |
| --- | --- | --- | --- | ---: |
| `Yitzhak Navon` | Jerusalem's railway station | `Yitzhak Navon/Herzl` | מגדל העמק | 100.0 km |
| `Ichilov` | Sourasky Medical Center, Tel Aviv | `Weizmann/Ichilov` | נתניה | 29.6 km |
| `איכילוב` | the same | `ההסתדרות/איכילוב` | פתח תקווה | 9.0 km |
| `Masada` | the archaeological site | `Masada` (a street) | חיפה | 169.6 km |
| `Petah Tikva` | the city | `Petah Tikva A` (a street stop) | ירושלים | 44.2 km |
| `Akko` | the city | `Akko Road/HaGefen` | קרית ביאליק | 10.9 km |

In every one of these the correct answer exists in the index and is returned lower
down — `Yitzhak Navon Station` finds `Jerusalem – Yitzhak Navon Railway Station` at
rank 1, and `Rambam Hospital` finds the right stop where `Rambam Medical Center` does
not. The defect is ranking, not coverage.

### Why it matters

- **POC-5.** The user is offered a stop 100 km from what they typed, with a name that
  contains every word of their query. Nothing about the result looks wrong.
- **POC-6 / PRD §39.** A journey that begins at the wrong `Ichilov` is not a routing
  failure and will not be diagnosed as one.
- It is the strongest single argument for ranking transit-relevant place types
  (stations, POIs, localities) above street-derived stop names, independent of string
  similarity.

### Action

Recorded, not worked around — POC-5 scores the engine as it ships (ADR 0006). Any
Phase 1 geocoder must be evaluated on this specific behaviour, and a
`type`/`importance` prior over feature class is the obvious mitigation. **Decision for
the developer**, feeding the Phase 1 Photon question.

---

## KDP-013 — English stop names mix translation and transliteration with no rule

**Found:** Wave 1 (Agent C, POC-5), 4 Sep 2026
**Feed:** `Gtfs_10_days.zip`, sha256 `08c168da…`, `translations.txt` (1,979,930 rows)
**Severity:** Medium — a user cannot predict which English spelling the feed used

The 10-day feed's `translations.txt` supplies the EN name for each stop (KDP-009: the
Hebrew is the base value, EN and AR are the translations). Those EN values are
sometimes a translation of the Hebrew and sometimes a transliteration of it, for the
same word, with no discernible rule. Verbatim rows for four Israel Railways stops:

| stop_id | Hebrew (base) | EN translation | Treatment |
| ---: | --- | --- | --- |
| 10945 | `תל אביב מרכז` | `Tel Aviv Center` | מרכז **translated** |
| 12729 | `ת. רכבת סבידור מרכז/גשר מודעי` | `Savidor Center Train Station/Moda'i Bridge` | מרכז **translated** |
| 10949 | `השלום` | `Hashalom` | **transliterated** |
| 10971 | `נתב"ג` | `Ben Gurion Airport` | acronym **expanded** |

Counted across the whole feed — the 1,415 stops whose Hebrew name contains `מרכז`:

| EN rendering of `מרכז` | Stops |
| --- | ---: |
| `Center` / `Centre` | **885** |
| `Merkaz` | **63** |
| neither (paraphrased or dropped) | 467 |

Both forms are in the same file. `Merkazit Hamifrats/Inner-City Platforms` (47009) and
`Psagot Center` (42603) are both EN values from this feed.

### Why it matters

Israelis routinely type the transliteration. POC-5 case P083, `Savidor Merkaz`, is a
name a Tel Aviv commuter would use and it resolves to `Merkaz Horev/Pica` in Haifa,
80 km away, because the feed's Latin form of that station is `Savidor Center`. The
reverse also holds: a user typing `Tel Aviv Center` will not match a stop the feed
rendered as `Merkaz`.

An English-language index built straight from `translations.txt` inherits this
inconsistency, and no amount of fuzzy matching bridges `Merkaz` to `Center` — they
share no characters.

### Action

No transformation applied, consistent with KDP-006. A synonym layer mapping the common
Hebrew place words to both their translated and transliterated Latin forms
(מרכז → Center/Merkaz, תחנה → Station/Tachana, קניון → Mall/Kanyon, נתב"ג → Ben Gurion
Airport/Natbag) is the obvious fix and is a **cleaning rule, so PRD §13 wants it
written down before it is applied**. Decision for the developer.

---

## KDP-014 — Duplicate OSM features carry a city's name, and the wrong one wins

**Found:** Wave 1 (Agent C, POC-5), 4 Sep 2026
**Source:** OpenStreetMap, as bundled into the MOTIS v2.11.2 graph Agent B built.
**This is an OSM finding, not an MOT one** — recorded here because ADR 0006 makes OSM
the second half of the geocoder's input and the failure is indistinguishable from a
feed problem at the point of use.
**Severity:** Low — two corpus cases, but it is silent and geographically confident

Two OSM features carry the name Petach Tikva:

| OSM id | Position | Municipality reported by MOTIS |
| --- | --- | --- |
| `way/242464393` | 32.0818, 34.9203 | מועצה אזורית דרום השרון |
| `node/1683305965` | 32.0878, 34.8860 | פתח תקווה |

They are **3,300 m apart** and in different municipalities. The way outranks the node,
so `Petach Tikwa` and `Petah Tiqwa` (POC-5 P087, P088) both resolve to a point outside
the city they name; the correct node is returned at rank 3. The third spelling,
`Petah Tikva` (P086), fails differently — it is beaten by a bus stop, per KDP-012.

### Why it matters

Geocoding a city name is the coarsest, most forgiving query a planner receives, and it
is the one a user falls back to when nothing else works. Getting it wrong by 3.3 km
places the journey origin in the wrong municipality and, in Israel, plausibly in a
different fare zone.

### Action

Recorded. Not fixable in our data — it is upstream OSM. A Phase 1 geocoder should
prefer `place=city`/`place=town` nodes over ways of the same name, which both Photon
and Nominatim expose via `place_rank`. Worth re-checking against a fresher OSM extract
before treating it as permanent.

---

## KDP-015 — A corrected corpus coordinate was not propagated to its twin

**Found:** Wave 1 (Agent C, POC-5), 4 Sep 2026
**Artifact:** `poc/corpora/places.json`, generated by `poc/corpora/build_places.py`
**This is a finding about our own corpus, not about MOT data.** It is recorded here
because the corpus is the yardstick every POC score is measured against, and a wrong
yardstick produces a wrong finding about the engine.
**Severity:** Medium — it silently understates engine quality

The POC-5 corpus coordinates are hand-entered approximations. Seven of the 100 were
provably wrong against `Gtfs_10_days.zip` sha256 `08c168da…` and were corrected in the
generator during POC-5:

| Case | Query | Was | Is (GTFS stop) | Was out by |
| --- | --- | --- | --- | ---: |
| P013 | Herzliya Station | 32.1656, 34.8095 | 10943 `הרצליה` | 778 m |
| P016 | Ashdod Ad Halom | 31.7940, 34.6410 | 10961 `אשדוד עד הלום- מטרופול` | 3,244 m |
| P017 | Bat Galim | 32.8283, 34.9539 | 10935 `בת גלים` | 2,626 m |
| P020 | Petah Tikva Kiryat Arye | 32.0956, 34.8556 | 10947 `קרית אריה` | 1,386 m |
| P032 | Beilinson Hospital | 32.0870, 34.8580 | 21432 `בלינסון` | 966 m |
| P034 | Hadassah Ein Kerem | 31.7658, 35.1206 | 1794 `הדסה עין כרם` | 2,562 m |
| P084 | Ben Gurion Airoport | 32.0114, 34.8867 | 10971 `נתב"ג` | 1,961 m |

Two of these are not merely imprecise. **P016's coordinate pointed at Ashdod Central
Bus Station, a different station from the one the query names.** And **P084 carried the
identical stale Ben Gurion Airport coordinate that was already found wrong and fixed in
P011/P012 in Wave 0** — 1,961 m, the same figure recorded in P011's note — because the
correction was applied to the two cases that had been checked and not to the third case
that shared the value.

Correcting all seven moved the POC-5 score from 62/100 to 68/100. Six of the thirty-two
"failures" in the first run were the corpus being wrong, not the geocoder.

A separate sanity sweep — distance from each of the 100 corpus points to the nearest
stop of any name in the feed — independently flagged P084 (1,532 m), P034 (1,044 m) and
P017 (618 m) as sitting implausibly far from any transit at all.

### Why it matters

Every POC scores an engine against these hand-entered points. An uncorrected corpus
does not fail loudly; it produces a plausible, slightly pessimistic number and a
failure list that sends the developer looking for a bug in the engine.

### Action

- Corrections live in `poc/corpora/build_places.py` with the GTFS `stop_id` they were
  snapped to recorded in each case's note; `places.json` is regenerated, never edited.
- `places.json`'s `provenance.corrections` now carries the audit trail.
- Coordinates are **never** fixed by widening `tol_m`. P059/P065 (`Herzl 50 Haifa`)
  were deliberately left failing: MOTIS and Nominatim independently agree on a point
  1,089 m from the corpus coordinate, but a street house number cannot be proved
  against a GTFS feed, so it is a human verdict at H4 rather than an agent's edit.
- Before any future corpus change, check whether the same coordinate appears in another
  case. That is the specific mistake P084 records.

---

## KDP-016 — Venue search works; chain-branch disambiguation does not

**Found:** POC-5 supplement, 4 Sep 2026
**Source:** `israel-and-palestine-latest.osm.pbf` sha256 `8a34b30f91a63ef9` — the same extract
MOTIS's graph was built from
**Severity:** Medium — a product-shaping limit, not a data defect

48 food-and-drink venues (bars, restaurants, cafes, pubs, fast food, ice cream, nightclubs)
were sampled directly from the OSM extract and queried by name. Because each venue is
provably in the geocoder's own source data, a miss cannot be blamed on a wrong coordinate.

| | top-1 | in top-5 | returned nothing |
| --- | ---: | ---: | ---: |
| All 48 | 40 | 44 | **0** |
| Hebrew-script names (25) | 20 | 23 | 0 |
| Latin-script names (23) | 20 | 21 | 0 |
| `name:en` variant of a Hebrew venue (20) | 15 | 18 | 0 |

By amenity: bar 8/8, fast_food 8/8, pub 5/5, nightclub 2/2, cafe 7/10, restaurant 8/12,
ice_cream 2/3.

### The finding is what the eight misses have in common

Every one is a **chain**: ארומה (Aroma), רולדין (Roladin), Golda, לנדוור (Landwer),
Pizza Hut, דדה, בית הפנקייק המקורי, Oasis. The geocoder found all of them — zero queries
returned no candidate. It simply returned *a* branch rather than *the* branch, in the worst
case 283 km away.

Supplying a location bias helps enormously but does not resolve it:

| Case | Default | With city-centre bias |
| --- | ---: | ---: |
| ארומה | 58,177 m | 4,988 m |
| Golda | 90,242 m | 4,578 m |
| Oasis | 111,673 m | **0 m** |
| לנדוור | 88,382 m | **0 m** |

3 of 8 land inside the 300 m tolerance; the other 5 land 4–9 km out — a different branch of
the same chain in the same metro area. Sweeping `placeBias` from 1 to 100 changes little
beyond 5, which matches the inertness POC-5 recorded for the main corpus.

### Why it matters

- **Venue search is viable.** Unique venues resolve reliably in both scripts, and Latin and
  Hebrew perform the same — unlike street addresses, where Latin script returns nothing at
  all (POC-5 failure mode #1). Anyone assuming the geocoder is transit-stops-only would be
  wrong.
- **A chain query has no single correct answer.** "Aroma" is not a place, it is a brand with
  dozens of branches. Ranking one 300 m hit as correct and a 4 km hit as wrong is arguably
  the test's fault, not the engine's. A real product needs the user's actual position, and
  probably a result list rather than a single answer.
- Two misses (Golda, Oasis) were beaten by a **GTFS stop** carrying the same word, which is
  KDP-010 and KDP-012 appearing again in a third category.

### Action

Developer decision, feeding the same call as POC-5's `placeBias` question: either pass the
user's real location on every query and accept branch ambiguity, or treat chain venues as a
multi-result case in the UI. Neither is a Phase 0 blocker.

Corpus: `poc/corpora/places-venues.json`. Runner: `poc/geocoding/venues.py`.
Results: `poc/results/poc-5-venues.json`, `poc/results/venues-h4-review.md`.
