# Agent A — POC-1, Static Israeli transportation data

**Wave:** 1 | **Depends on:** Wave 0 (complete) | **Runs parallel with:** Agent B

## Read first

- `PRD.md` §6 — the POC-1 test, PASS bar, and FAIL/STOP condition
- `docs/data-access-findings.md` §1 — verified feed behaviour and its traps
- `docs/poc-execution-plan.md` §3.1a — the production-spec principle
- `poc/docs/adr/0003-postgres-postgis-for-cold-storage.md` — what to load, what not to
- `poc/docs/adr/0005-ten-day-gtfs-feed.md` — which feed is primary
- `poc/corpora/edge-cases.json` — the ten integrity checks you must answer
- `poc/data/manifest.json` — the exact bytes you are working from

## Scope

Prove the nationwide feed can be downloaded, parsed, understood, queried and refreshed
automatically, with no manual editing. That sentence is PRD §6's PASS bar; it is also
kill criterion #1.

### Parse everything, load five

PRD §6 requires proving all seven file groups can be parsed and understood: agencies,
routes, trips, stops, stop_times, calendar/service, shapes. **Parse and validate all
seven**, and record row counts for each.

**Load only five into Postgres**: routes, trips, stops, calendars, `TripIdToDate`.
`stop_times` and `shapes` are parsed, counted, integrity-checked, then discarded —
system-design §173 is explicit that loading `stop_times` "buys nothing, because MOTIS
already answers both journeys *and* stop departures from RAM." Do not load them because
it feels more complete. That is the decision in ADR 0003.

### Infrastructure

Postgres + PostGIS via `poc/docker-compose.yml` (`docker compose up -d postgres`),
port 55432, db `opentransit_poc`, user/password `poc`/`poc`. Do not substitute SQLite
or DuckDB — see ADR 0003 for why that would invalidate the result.

## The traps, all of which are known and none of which are optional

1. **`HEAD` lies.** It returned `Content-Length: 3382` against a 164 MB file. Change
   detection uses `GET` plus zip validation. If `HEAD` appears in the refresh path, the
   check has failed.
2. **Times exceed 24:00:00.** `25:30:00` means 01:30 on the *next* calendar day within
   the *same* service day. Never truncate, never error.
3. **Hebrew encoding corrupts silently.** Assert round-trip on ≥20 Hebrew names through
   download → extract → parse → Postgres → read, including names with quotes,
   apostrophes and mixed Hebrew/Latin/digits.
4. **`TripIdToDate` is a separate download** and must be versioned in lockstep with the
   feed. A mismatched pair must be rejected, not silently used.
5. **The two feeds are different products.** Load the 10-day feed. Row-count the 60-day
   feed for comparison so ADR 0005 is evidenced.

## Deliverables

- `poc/gtfs/` — the ingester, in Python 3.13 (ADR 0002)
- A single refresh entry point that works from an empty data directory
- `poc/results/poc-1.json` — see schema below
- `poc/docs/known-data-problems.md` — every problem found, quoted verbatim, not
  paraphrased. PRD §13 requires this and it is one of Phase 0's durable outputs.

### Result schema

```json
{
  "poc": 1,
  "name": "Static Israeli transportation data",
  "status": "PASS | PARTIAL | FAIL",
  "generated": "ISO date",
  "headline": "one line for the status table",
  "feed_sha256": "from manifest.json — mandatory",
  "capabilities": {
    "download_gtfs": true,
    "parse_gtfs": true,
    "usage_terms_confirmed": false
  },
  "metrics": {
    "rows_parsed": { "stop_times": 0, "trips": 0, "stops": 0, "routes": 0, "...": 0 },
    "rows_loaded": { "routes": 0, "trips": 0, "stops": 0, "calendar": 0, "trip_id_to_date": 0 },
    "cold_refresh_seconds": 0,
    "peak_rss_mb": 0
  },
  "validation_examples": {
    "tel_aviv": true, "jerusalem": true, "haifa": true,
    "israel_railways": true, "multiple_bus_operators": true
  },
  "edge_case_results": [
    { "id": "E01", "result": "pass | fail | not_observed", "detail": "..." }
  ],
  "notes": []
}
```

`usage_terms_confirmed` stays `false`. It is checkpoint H2 — a human must read the
gov.il licence text, which returns 403 to automated fetches. Do not set it true.

## Done when

- A cold run from an empty `poc/data/` reaches a queryable Postgres database with zero
  manual steps, and the wall time is recorded.
- `poc/results/poc-1.json` validates against the schema above and carries a real
  `feed_sha256`.
- All ten `edge-cases.json` checks have a recorded result. `not_observed` is a valid and
  useful answer; a missing result is not.
- `python poc/poc_status.py` shows POC-1 green for `download_gtfs` and `parse_gtfs`.

## Rules

- **Never write a capability `true` that a test did not demonstrate.** The status table
  is the project's honesty mechanism; an optimistic flag defeats the whole design.
- If the feed cannot be sustainably consumed, that is kill criterion #1 and a
  **successful** Phase 0 outcome (PRD §38). Report it plainly; do not work around it.
- Snap each `poc/corpora/stops.json` entry to its nearest real stop and write back
  `resolved_stop_id`. Leave `expect_routes` null — a human fills that, per the corpus's
  own provenance note. Do not invent line numbers.
