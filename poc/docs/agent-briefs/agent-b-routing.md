# Agent B — POC-2, Public transportation routing

**Wave:** 1 | **Depends on:** Wave 0 (complete) | **Runs parallel with:** Agent A
**Blocks:** Agent C (needs MOTIS serving)

## Read first

- `PRD.md` §7 — the ten required journeys, the 9/10 PASS bar, the FAIL/STOP condition
- `docs/system-design.md` §320 and §331 — **the 8 GB production box**. This brief exists
  because of that paragraph.
- `docs/poc-execution-plan.md` §3.1a — the production-spec principle
- `poc/docs/adr/0004-motis-as-routing-engine.md`
- `poc/corpora/journeys.json` — all 25 cases, with per-case expectations
- `poc/data/manifest.json` — the exact bytes you are working from

## Scope

Prove Israeli GTFS can be turned into a working journey-planning graph that answers
`walk → transit → transfer → transit → walk` where appropriate.

## Two measurements. Do not conflate them.

This is the single thing this brief exists to enforce.

### 1. Build — uncapped, on the full 32 GB machine

system-design §320: *"build the graph on the dev machine or a spot instance and ship the
artifact."* Using the whole machine here is the **designed path**, not cheating.

Run via the `build` profile: `docker compose --profile build run --rm motis-build`.

Record: wall time, peak RSS, graph size on disk.

### 2. Serving — capped at 8 GB

system-design §320: *"the production box is 8 GB, not 32."* The `motis` service in
`poc/docker-compose.yml` is capped at `mem_limit: 8g` for exactly this reason.

**Do not raise that cap.** If the graph will not serve Israel in 8 GB, that is a finding
about system-design §331's cost tiers and the recommended production shape — it is one of
the most valuable things Phase 0 can discover. Report it. Raising the limit to get a green
result would produce a number that is true only on your desk.

Record: steady RSS holding the graph, and whether the 25 journey cases answer under the
cap.

Run via `docker compose --profile serve up -d motis`, port 58080.

## Inputs

- `poc/data/Gtfs_10_days.zip` — primary feed (ADR 0005)
- `poc/data/israel-and-palestine-latest.osm.pbf` — walking legs

The import is long (plausibly 30–90 minutes). **Run it as a monitored background command,
not as foreground agent work**, so a timeout cannot lose it. Sample resource usage while it
runs — that sampling is the deliverable, not a nicety.

## Before blaming MOTIS

Docker Desktop on Windows caps container memory through WSL2, commonly at ~50% of host
RAM. If the *build* OOMs, raise the limit in `.wslconfig` and retry **before** concluding
anything. This is a configuration trap, not a finding. ADR 0004 is explicit that switching
to OpenTripPlanner is a decision for the developer, not a fix you may apply — if the build
genuinely fails after a real memory raise, stop and write up the failure.

The compose file's MOTIS image tag and command verbs (`import`, `server`) are a Wave 0
scaffold and were **not verified**. Check them against the current MOTIS docs and correct
`poc/docker-compose.yml` if they are wrong — that is expected work, not a surprise.

## Running the corpus

All 25 cases in `poc/corpora/journeys.json`, against the **capped serving container**.
Resolve the `depart` rules against the feed's active service window using the
`depart_rules` block in that file.

**Structural checks only.** You are not judging route quality — that is checkpoint H3, a
human comparison against Moovit, Google Maps and BetterRail, and PRD §7 says so explicitly.
Check per case:

- `outcome` — a route returned, or correctly refused for `no-route` cases
- leg sequence is well-formed; times are monotonic and non-overlapping
- every stop id resolves against the static feed
- duration falls inside `min_duration_min` / `max_duration_min`
- `modes_any_of` / `modes_all_of` / `min_transfers` / `max_transfers` / `max_walk_m` honoured

Record the **full response** for every case, not just pass/fail. H3 needs the itineraries.

Three cases deserve attention because they encode real traps:

- **J22** (02:30 departure) — the GTFS after-midnight trap. A route or a clean no-route
  both pass. A crash, a silent empty result, or a route departing 20 hours later is a FAIL.
- **J23** (Mitzpe Ramon → Metula at 02:30) — must return **no route**. An itinerary here
  means the engine is inventing service.
- **J25** (Shabbat noon) — national rail and most buses do not run. A confident full
  itinerary is almost certainly wrong; check it against `calendar_dates.txt`.

## Deliverables

- `poc/routing/` — compose corrections, import runner, corpus runner
- `poc/results/poc-2.json`
- `poc/results/journeys-h3-review.md` — the human review sheet for checkpoint H3: one
  section per case, the returned itinerary rendered readably, and a blank verdict line.
  This is what the developer sits down with.

### Result schema

```json
{
  "poc": 2,
  "name": "Public transportation routing",
  "status": "PASS | PARTIAL | FAIL",
  "generated": "ISO date",
  "headline": "one line for the status table",
  "feed_sha256": "from manifest.json — mandatory",
  "capabilities": { "route_gtfs": true, "walk_transit_transfer": true },
  "metrics": {
    "build": { "wall_seconds": 0, "peak_rss_mb": 0, "graph_size_mb": 0, "memory_cap": "uncapped (32 GB host)" },
    "serving": { "steady_rss_mb": 0, "memory_cap_gb": 8, "fits_in_8gb": true },
    "journeys": { "answered": 0, "structural_pass": 0, "total": 25 }
  },
  "cases": [
    { "id": "J01", "outcome": "route", "structural": "pass", "duration_min": 0,
      "transfers": 0, "modes": ["bus"], "response_file": "..." }
  ],
  "notes": []
}
```

`walk_transit_transfer` is true only if at least one case actually returned a
walk → transit → transfer → transit → walk shape. PRD §7 asks for that shape specifically.

## Done when

- Both measurements recorded **separately**, with the serving figure stated against the
  8 GB target.
- All 25 cases have a recorded response.
- `poc/results/journeys-h3-review.md` exists and is readable by a human who has not seen
  the code.
- `python poc/poc_status.py` reflects POC-2.

## Rules

- **Never write a capability `true` that a test did not demonstrate.**
- Structural pass is not quality pass. Do not claim POC-2 PASS — the PRD's 9/10 bar is a
  human judgment (H3). Set `status` to `PARTIAL` with structural results recorded, and say
  in `headline` that H3 is pending.
- If serving does not fit in 8 GB, record `fits_in_8gb: false` and keep going. That is a
  finding, not a failure to route.
