# Technical decisions ready for acceptance

D1 was accepted September 5; D2 September 25; D3 and design simplifications R1–R5 September 30 ([ADR 0007](../../poc/docs/adr/0007-schedule-api-design.md)). Other proposals remain pending except that the September 25 PRD revision supersedes D5 feasibility-first sequencing. Approving the recommended package in the decision-pack README authorizes these choices; it does not claim their implementation or PoC acceptance is complete.

## D1: integrated feed baseline

**Accepted decision:** use `israel-public-transportation.zip` plus `TripIdToDate.zip` for the next integrated baseline. Preserve the previous ten-day experiment. Recorded in the ADR 0005 amendment.

**Evidence:** the sampled mapping file overlaps 0/892,451 distinct join keys in the ten-day feed versus 246,042/246,042 normalized distinct keys in the sixty-day feed. The ten-day sample also starts the day after download. The ten-day results are archived; current ingest/routing evidence uses the 60-day primary.

**Follow-through (ingest/routing completed; search and integration remain):**

1. Add explicit feed/config/corpus-generation arguments; remove coupled hardcoded names/dates together.
2. Store each run under a unique run directory with feed, mapping, OSM and corpus hashes; engine digest; config; machine; and timestamps. Never clear the historical volume as part of a default rerun.
3. Strengthen pairing checks to reject absent/disjoint service windows and insufficient overlap, then verify mappings for each service date. Preserve full trip IDs; normalized mapping keys are not unique journey identities.
4. Build a separate graph volume and run ingestion, routes, search, negative cases and capped load tests on the same generation.
5. Regenerate H3/H4 from that generation; preserve human verdicts separately from generated sheets.

**Return to decision if:** usable routing deteriorates, current-day service disappears, mapping is ambiguous on service dates, or the full stack exceeds the agreed envelope. No silent dual-feed fallback.

## D2: API runtime

**Accepted September 25:** Python for API and ingestion; FastAPI for the first API skeleton. See [ADR 0002 amendment](../../poc/docs/adr/0002-python-for-the-poc.md). Python is already the developer's selected PoC language. Runtime/framework/dependencies will be pinned to supported versions during setup and checked against their official documentation before installation.

**Boundary:** this is an implementation choice, not an assertion that every endpoint meets its budget. MOTIS owns routing computation. Measure API overhead, snapshot memory and worker duplication; do not add worker processes without measuring the copies of state they create.

**Alternative considered:** .NET API plus Python ingestion; Python was selected. Do not rewrite the PoC just to match the API language.

## D3: journey request and privacy

**Accepted September 30:** POST `/v1/journeys`, body containing origin, destination and explicit-offset time. No raw place text is implicitly geocoded on the routing path. GET remains suitable for non-sensitive public metadata; search/location-bearing GET requests must have their own log/cache controls.

Example of the intended contract, not an implemented endpoint:

```json
{
  "from": {"type": "coordinate", "lat": 32.0757, "lon": 34.7748},
  "to": {"type": "coordinate", "lat": 32.7775, "lon": 35.0219},
  "departAt": "2026-09-09T18:30:00+03:00",
  "locale": "he",
  "maxWalkMinutes": 15,
  "results": 3
}
```

The example is illustrative, not a promised itinerary or verified endpoint coordinate. Precise coordinates, request bodies and credentials are omitted from normal logs. Operational metrics contain aggregate dimensions. `NO_ROUTE_FOUND` must be distinct from an unavailable or expired feed.

**Contract work after acceptance:** align PRD/system-design, specify mutually exclusive `departAt`/`arriveBy`, input bounds, per-leg scheduled/expected fields, typed errors and reference/cursor behavior. M1 exposes its implemented basic coordinate/depart-at journey and health schemas through generated docs; the remaining journey features stay planned until M3.

## D4: search and walking

**Proposed decision:** retain MOTIS as the first engine and measure SQLite FTS5 against an in-process stop index during M4 (per-generation SQLite accepted in R4). Evaluate address normalization and a same-host geocoder against the failed categories before adopting another service. Public Nominatim is not the production autocomplete backend.

Keep 15-minute and 30-minute walking results as separate labelled profiles for review. No global walking-policy change is needed before the rerun. Nearby/chain searches return a candidate list; location is optional and should not be silently required for unique names. Test intent and boarding access points rather than only geographic centroids.

## D5: scope and deployment envelope

**Accepted sequencing:** schedule-first development is authorized, with the planning gate satisfied by September 30 authorization. Static validation continues alongside development. **Hosting accepted September 30:** AWS ECS on Fargate, API and MOTIS in one task, prepared generation in a private ECR image, S3 optional. Keep M1 local. Preserve the intended 8 GiB aggregate serving ceiling including task replacement overlap; test a smaller task allocation rather than treating 8 GiB as a minimum. Region, ingress, refresh automation/source retention and total cost await H-0/H-1 evidence. See [ADR 0007 amendment](../../poc/docs/adr/0007-schedule-api-design.md#hosting-amendment--accepted-30-september-2026) and [hosting plan](../next-steps.md#hosting-plan).

M1 delivers a real basic local journey through FastAPI and the prepared MOTIS graph, with minimal configuration, dependency pins, generated docs, safe errors and focused checks. CI/schema automation follows in M7; contributor onboarding and repository polish are Phase 5. It does not require a fixture platform, Redis, an extra geocoder, hosting or product UI.

Graph activation in production replaces complete ECS task revisions, each pinned to a consistent graph, static identifiers and search index. Readiness/probes precede traffic; old requests drain before old tasks stop. Matching state is added with the deferred live wave. A passing engine-only test cannot establish memory headroom for overlapping tasks and edge components. Future SIRI static egress applies to its collector (normally NAT Gateway + Elastic IP); MOT must confirm provider/geography and binding. No NAT or VM is required for static development merely to prepare for SIRI.

## Remaining decisions are deliberately scheduled later

- **Realtime quality:** propose freshness/coverage and per-mode match thresholds before POC-3 scoring, with sample counts, denominators and ambiguous-match handling visible. The old 90% warning/70% paging values do not automatically become acceptance thresholds.
- **Walking default:** decide from regenerated H3 evidence.
- **Additional geocoder:** decide from the address comparison and measured resource cost.
- **Hosting implementation and retention:** Fargate/ECR selected; resolve region, task resources, HTTPS ingress, durable automation archive and actual cost from measured deployment evidence. S3 remains optional; source evidence must not live only on ephemeral task disk.
- **Fallback or static-only product:** decide only if direct access remains unavailable; this is not included in the recommended package.
