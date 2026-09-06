# Phase 0 POC — Autonomous Execution Plan

> **Historical execution plan:** Waves 0–1 produced the September 4 evidence; H3/H4 remain pending. Use [the current continuation plan](next-steps.md) for remaining work. ADR 0005 now accepts the 60-day primary with TripIdToDate compatibility enforced.

**Status:** Proposed
**Governs:** PRD §5–§13 (POC-1 … POC-6) and the Go/No-Go table in PRD §12
**Operating model:** Subagents do the building; the developer sends one email, makes six decisions, and judges route quality
**Written:** 4 September 2026

---

## 1. What this plan is

`docs/phase-0-mvp-plan.md` proposed a vertical-slice Phase 0 in which every milestone
improves a visible client. That conflicts with the PRD's hard rule (§5.1) that frontend
development does not begin until Phase 0 passes. **This plan follows the PRD.** Phase 0
produces a `/poc` tree and a CLI, no client. The vertical-slice plan is deferred whole
to Phase 1, where it is a good fit.

The output of Phase 0 is not an application. It is a green or red Go/No-Go table
(PRD §12) plus an honest list of known data problems.

### Operating model

The developer is not in the build loop. Agents write code, run it against committed
test corpora, and record results as data. The developer appears at seven checkpoints
(§6), five of which are decisions and two of which are judgment calls that cannot be
automated.

Two constraints shape the agent design:

- **Subagents cannot be resumed in this session.** Each spawn starts cold. Therefore
  every agent brief is self-contained, reads its context from files on disk, and writes
  its output to files on disk. No agent depends on another agent's conversation.
- **Long imports do not belong inside agents.** A full-Israel MOTIS import may run
  30–90 minutes. Those run as monitored background commands, not as agent work, so a
  timeout cannot lose the result.

---

## 2. Constraints discovered

### Machine (verified 4 Sep 2026)

| Resource | Value | Implication |
| --- | --- | --- |
| RAM | 31.8 GB total | Enough to *build* the graph — but see the warning below |
| CPU | i9-13900, 24C/32T | Import parallelism is not the bottleneck |
| Disk free | 67.3 GB | Adequate; GTFS + OSM + MOTIS graph ≈ 15–25 GB |
| Docker | 27.4.0 + Compose v2.31 | MOTIS and Postgres run containerised |
| Node | v22.17.0 | Available |
| Python | 3.13.14 | Available; one of the two H0 candidates |

**This machine is four times the production box.** system-design §320 puts serving on
8 GB. Every serving-side measurement in this plan is therefore taken inside a
memory-capped container, never against the bare host. A result that only holds on
32 GB is not a result.

**Open item:** Docker Desktop on Windows caps container memory via WSL2 (commonly ~50%
of host RAM). If the MOTIS import OOMs, raise the limit in `.wslconfig` before
concluding anything about MOTIS. This is a configuration trap, not a finding.

### Data access (from `docs/data-access-findings.md`)

| Input | State |
| --- | --- |
| Static GTFS | Open HTTP, no key, nightly updates — verified |
| `TripIdToDate.zip` | Separate download; required for realtime matching |
| OSM Israel extract | Open (Geofabrik) — needed by MOTIS for walking legs |
| SIRI-SM | Gated: MOT-issued key **and** network-restricted endpoint |
| Service Alerts | Gated: no public URL exists at all |
| Open Bus Stride | Live, raw SIRI, no GTFS linkage — usable to build the matcher |

`HEAD` on the GTFS zip returns a bogus `Content-Length` (3382 vs 164 MB actual).
Change detection must use `GET` plus zip validation.

---

## 3. Decisions

### 3.1 Pre-made defaults — agents proceed on these unless overruled

| # | Decision | Default | Rationale |
| --- | --- | --- | --- |
| D1 | Which Phase 0 doc governs | PRD POC-1…6 | PRD §5.1 hard rule; vertical-slice plan is unratified |
| D2 | POC language | **Python 3.13** | Developer's fastest, per the system-design §3 decision rule. Scoped to the POC: it does **not** bind the Phase 1 API. system-design §136 independently makes Python the better tool for the cold path — polling, JSON, reconciliation joins — which is most of what Phase 0 is, so the ingest and analytics code plausibly carries forward even if the API lands on .NET |
| D3 | Cold storage | Postgres + PostGIS, in a container | system-design §169: the named production cold store. The POC uses the production component, not a local substitute |
| D3a | What goes in it | routes, trips, stops, calendars, `TripIdToDate` | system-design §173: `stop_times` stays out — ~100M rows for the 60-day feed, and MOTIS answers journeys *and* departures from RAM |
| D4 | Routing engine | MOTIS | PRD §7 initial candidate; Transitous proves Israeli coverage |
| D5 | GTFS feed | `israel-public-transportation.zip` + `TripIdToDate.zip` | Accepted ADR 0005 amendment; ten-day comparison only |
| D6 | Geocoder | MOTIS built-in first | Avoids a second service; Nominatim only as bounded comparison |

D2 was settled by the developer on 4 Sep 2026: Python for the POC, revisitable for the
Phase 1 API. The language does not gate any Phase 0 PASS/FAIL — no kill criterion in
PRD §38 turns on it — which is why it is the one production-spec deviation that costs
nothing.

### 3.1a Principle: the POC runs the production spec

A feasibility test that passes on a convenient local substitute has proved nothing about
the thing being built. Where the target architecture names a component or a limit, the
POC uses that component and is measured against that limit:

| Target spec | Source | How the POC honours it |
| --- | --- | --- |
| Postgres + PostGIS for cold storage | system-design §169 | POC-1 loads Postgres, not an embedded engine |
| `stop_times` never enters the database | system-design §173 | POC-1 loads five tables; MOTIS owns the timetable |
| **Serving box is 8 GB, not 32** | system-design §320 | POC-2 measures serving RSS under an 8 GB cap, not just import success |
| Graph is built on a dev box and shipped as an artifact | system-design §320 | Import may use the full 32 GB; that is the designed build path, and is reported separately from serving |
| Object storage via S3 API only | system-design §175–191 | Local MinIO, never a filesystem shortcut, wherever the POC touches object storage |

The one deliberate exception is the SIRI source: MOT's endpoint is unreachable, so
POC-3 measures against Open Bus Stride and reports the number as Stride-measured.

Each default is recorded as a one-page ADR under `poc/docs/adr/`. Overruling any of
them is cheap before Wave 1 and expensive after.

### 3.2 Yours to make — work stops or forks without you

| # | Decision | Needed by | Consequence if late |
| --- | --- | --- | --- |
| H0 | Implementation language | ✅ Settled 4 Sep | Python for the POC (see D2). Phase 1 API language remains open |
| H1 | Send the MOT email | Deferred by developer, 4 Sep | Chosen consciously. POC-4 stays red and the four-week clock has not started; Waves 0–2 are unaffected |
| H2 | Accept the GTFS licence terms | Before Wave 3 | Kill criterion #5 unresolved; gov.il returns 403 to automated fetch, so a human must read it |
| H3 | Judge POC-2 route correctness | End of Wave 1 | PRD §7 requires human comparison vs Moovit/Google/BetterRail |
| H4 | Judge POC-5 search quality | End of Wave 1 | "Correct enough to start routing" is a judgment call |
| H5 | Stride as a permanent dependency? | If MOT declines | Forks POC-3 |
| H6 | The four-week MOT decision | +4 weeks from H1 | Stride / static-only / stop (kill criterion #3) |

---

## 4. The verification spine

This is what makes autonomy possible, and it is built before any POC code.

An agent cannot self-verify against prose. "Several known Israeli lines exist" is not
checkable; a committed list of 25 journeys with expected qualitative outcomes is.
Every POC is therefore scored against versioned corpora in `poc/corpora/`:

| Corpus | Size | Source |
| --- | --- | --- |
| `journeys.json` | 25 cases | PRD §7 ten journeys plus the MVP plan's category mix |
| `places.json` | 100 queries | Hebrew/English, addresses, stops, POIs, misspellings, transliterations |
| `stops.json` | 10 stops | With expected upcoming services |
| `edge-cases.json` | — | After-midnight, service-day boundary, no-route, long-distance |

**Ground-truth honesty.** Commercial planners are recorded as comparison evidence,
never as automatic pass/fail. Each journey case therefore carries two kinds of check:

- *Structural, machine-checked:* a route is returned or correctly refused; the leg
  sequence is well-formed; times are monotonic; stop IDs resolve against static GTFS;
  duration falls within a plausible band.
- *Qualitative, human-checked:* is this the route a person would actually take?

Agents run the structural checks and produce a review sheet for the qualitative ones.
That review sheet is checkpoint H3.

### The status command

One command, `poc:status` (exact invocation follows H0), regenerates the PRD §13 dependency table and the
§12 Go/No-Go table from actual test results — never hand-edited. This is how the
developer checks progress without reading agent transcripts.

---

## 5. Waves

### Wave 0 — Foundations (no agents; ~2 hours, mostly download time)

Run directly, because everything downstream depends on it being right.

1. Scaffold `/poc` per PRD §13.
2. Write ADRs for D1–D6.
3. Acquire and checksum inputs once, to a shared path: `israel-public-transportation.zip`, `Gtfs_10_days.zip` (comparison only),
   `israel-public-transportation.zip`, `TripIdToDate.zip`, and the Geofabrik
   Israel + Palestine OSM extract. Record sizes, hashes, and retrieval timestamps.
4. Build the corpora in §4.
5. Build `poc:status` against stub results so the table exists before the data does.

**Exit:** `poc:status` prints an all-red table. Every input is on disk with a
recorded hash.

### Wave 1 — Unblocked POCs (3 agents)

| Agent | Scope | Reads | Writes |
| --- | --- | --- | --- |
| **A — GTFS ingest** | POC-1 | `poc/data/*.zip` | `poc/gtfs/`, `results/poc-1.json` |
| **B — Routing** | POC-2 | GTFS + OSM extract | `poc/routing/`, `results/poc-2.json` |
| **C — Geocoding** | POC-5 | MOTIS instance from B | `poc/geocoding/`, `results/poc-5.json` |

A and B start together. C depends on B having MOTIS serving, so it is sequenced after
B's import completes.

**Agent A brief.** Download → validate → extract → parse. All seven files are *parsed*
and their row counts and integrity recorded, because PRD §6 requires proving the feed
can be understood. Only five are *loaded* into Postgres — routes, trips, stops,
calendars, `TripIdToDate` — per system-design §173; `stop_times` and `shapes` are
parsed, counted, validated and then handed to MOTIS rather than stored. Automatic
refresh with change detection via `GET` plus zip validation, never `HEAD`. Version
`TripIdToDate` in lockstep with the main feed. Verify Tel Aviv, Jerusalem, Haifa,
Israel Railways and multiple bus operators are present. Record row counts, parse time,
and every data problem found (encoding, `translations.txt` sanitisation, malformed
rows) to `poc/docs/known-data-problems.md`.
**Done when:** a cold refresh produces a queryable Postgres database with no manual
editing, and `results/poc-1.json` records per-file row counts, the five required
validation examples resolving, and the load/parse split actually taken.

**Agent B brief.** Stand up MOTIS in Docker against the 60-day GTFS plus the OSM
extract. Two distinct measurements, and conflating them is the failure mode this brief
exists to prevent:

1. *Build*, on the 32 GB dev machine — wall time, peak RSS, graph size on disk. This
   is the designed path (system-design §320: build on a dev box, ship the artifact), so
   using the full machine here is correct, not cheating.
2. *Serving*, under an **8 GB container cap** — steady RSS holding the graph, and
   whether the 25 journey cases answer at all under that ceiling. This is the number
   that decides whether the production box in system-design §331 is real.

The import runs as a monitored background command with resource sampling. Then run all
25 journey cases against the capped serving container and record full responses.
Structural checks only.
**Done when:** `results/poc-2.json` holds a response for every case, both measurements
are recorded separately, and the serving figure is stated against the 8 GB target. If
serving does not fit in 8 GB, that is a finding for system-design §331 and the cost
tiers — report it, do not raise the cap and move on. If the *import* fails after a
genuine WSL2 memory raise, stop and write up the failure — do not silently switch to
OTP; that is a decision, not a fix.

**Agent C brief.** Run the 100 place queries against MOTIS geocoding. Score resolution
against expected coordinates within a tolerance. Report per-category hit rate: Hebrew
vs English, addresses vs stops vs POIs, misspellings, transliterations, and
`near`-dependent queries. Nominatim may be used for bounded comparison only, at
≤1 req/s, never for autocomplete.
**Done when:** `results/poc-5.json` reports ≥20 correct resolutions (the PRD §10 PASS
bar) with the per-category breakdown, plus a ranked list of failure modes.

**Gate:** checkpoints H3 and H4. Wave 2 does not start until POC-2 is judged.

### Wave 2 — Realtime and alerts (2 agents in parallel)

| Agent | Scope | Blocked? |
| --- | --- | --- |
| **D — Realtime matcher** | POC-3 | No — Stride plus `TripIdToDate` |
| **E — Alerts parser** | POC-4 | Partially — no feed URL, but the spec is public |

**Agent D brief.** This is the highest-value unblocked work in Phase 0, because kill
criterion #4 is about match *rate*, not access. Build the `GTFS trip ↕ SIRI trip`
reconciliation against `TripIdToDate`, using Open Bus Stride's raw SIRI as the live
sample source. Measure match rate broken down **by operator and by mode** — an
aggregate number hides exactly the failure that matters. Record unmatchable cases with
reasons (missing `VehicleRef`, unknown trip, stale sample).
**Done when:** `results/poc-3.json` reports match rate by operator and mode over a
sample of at least several thousand observations, and the matcher runs against MOT
SIRI by swapping one adapter — proven by an interface test, not by assertion.

**Agent E brief.** Implement the GTFS-RT Service Alerts parser against the published
ICD 2.2 and the GTFS-RT protobuf schema, tested against synthetic fixtures. Wire
entity resolution to static GTFS IDs (field names are identical, per findings §4).
Respect the documented ≤12 polls/hour once a URL exists.
**Done when:** the parser handles fixtures correctly and `results/poc-4.json` records
`BLOCKED_ON_ACCESS` with everything except the URL demonstrably ready.

### Wave 3 — Integration and verdict (1 agent, then developer)

**Agent F brief.** Build the PRD §11 CLI:
`route --from "Dizengoff Center" --to "Technion" --depart-now`, chaining
search → coordinates → routing → realtime enrichment → alert enrichment → response,
rendering the PRD §39 output shape. Degrade honestly: a missing realtime source prints
`scheduled`, never a fabricated `live`. Then generate the `/poc` README with the
dependency table, every tested journey and its result, and the known-data-problems list.

**Then, developer:** score the §12 Go/No-Go table and record the Phase 0 verdict. If
MOT has not answered, the verdict is taken with POC-3 on Stride and POC-4 red, under
checkpoint H6.

---

## 6. Where you are needed

```text
Now          H1  Send the MOT email                    5 minutes, blocking
Wave 0       —   Review corpora before agents use them 30 minutes
End Wave 1   H3  Judge 25 routes vs Moovit/Google      1–2 hours, unautomatable
End Wave 1   H4  Judge search quality                  30 minutes
Before W3    H2  Read and record the GTFS licence      30 minutes
+4 weeks     H6  The MOT decision                      forks the project
```

Everything else runs without you.

---

## 7. Repo layout

```text
poc/
  corpora/          journeys.json places.json stops.json edge-cases.json
  data/             downloaded feeds plus hashes (gitignored, manifest committed)
  gtfs/             POC-1
  routing/          POC-2
  realtime/         POC-3
  alerts/           POC-4
  geocoding/        POC-5
  integration/      POC-6 CLI
  results/          poc-N.json — machine-written, never hand-edited
  docs/adr/         D1–D6
  docs/known-data-problems.md
  docker-compose.yml
  README.md         generated by poc:status
```

---

## 8. Risks

| Risk | Response |
| --- | --- |
| MOTIS import OOMs on Windows/WSL2 | Raise `.wslconfig` memory first; only then treat it as a MOTIS finding |
| Import too slow to iterate | Import once, snapshot the graph, reuse across agents |
| Stride match rate ≠ MOT match rate | Report as Stride-measured; treat as indicative, re-measure when the key lands |
| Agent declares success on a broken result | All PASS/FAIL comes from `results/*.json` produced by test runs, never from agent prose |
| Hebrew encoding corrupts silently | Explicit round-trip assertions on Hebrew stop names in POC-1 |
| MOT never answers | H6 at four weeks, with all three options pre-costed |

---

## 9. Kill criteria mapping

| PRD §38 criterion | Detected by |
| --- | --- |
| 1. GTFS not sustainably consumable | Agent A refresh cycle |
| 2. No practical routing engine | Agent B, after a genuine memory raise |
| 3. No sustainable realtime source | H6 at four weeks |
| 4. Realtime cannot be matched reliably | Agent D match rate by operator and mode |
| 5. Datasets not legally usable | H2 licence reading |
| 6. Dependency requires unsustainable commercial service | Continuous; $25/month ceiling |

Discovering any of these is a **successful** Phase 0 outcome (PRD §38).
