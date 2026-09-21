# From PoC to API implementation

**Execution reference, reconciled 21 September 2026.** Read [PROJECT_STATUS.md](../PROJECT_STATUS.md) for current state, priorities, ownership and session handoff. This document defines implementation scope and acceptance; proposals remain open unless explicitly accepted.

The accepted baseline is the 60-day feed plus TripIdToDate (ADR 0005). Ingest/routing reruns are complete; see [measured results](../poc/docs/primary-feed-rerun.md). Search/H4 and realtime integration still need that baseline. Static mapping-key overlap is not a realtime matching rate.

## The immediate next step: close Phase 0

PRD §§5–13 and accepted ADR 0001 require feasibility before production development. H3 gates the realtime/alerts wave; H4 remains required for final acceptance. “Step 1” below means Phase 1 M1; the work immediately available is this completion sequence.

1. **Primary feed accepted and ingest/routing rerun.** Use the 60-day feed plus `TripIdToDate` (ADR 0005). Historical ten-day evidence is preserved in `poc/comparisons/ten-day-2026-09-04`. Complete search/H4 and realtime integration against this generation; H3 is ready for human review.
2. **Complete H3 and H4.** H3 is already regenerated against that baseline; regenerate H4 after the search rerun. Record dated comparisons for the ten required route classes, including after-midnight, Shabbat, transfers and genuine no-route cases. Review ambiguous search results against source evidence. Identify which failures are corpus defects versus engine behavior.
3. **Implement POC-3.** After the H3 human routing review, build source adapters, replay fixtures and a matcher using trip identity, service date, route, stop and sequence. Do not resolve a trip using a stripped ID alone. Measure several thousand observations by operator and mode, including unmatched, ambiguous and stale counts with explicit denominators. Use Stride as an experimental source only until its production suitability is explicitly accepted. Pin fixture time and feed generation.
4. **Implement POC-4.** Build protobuf decoding and route/stop/trip resolution against synthetic fixtures; label them synthetic. A real feed remains necessary for PASS. Record empty-but-successful feeds separately from unavailable feeds.
5. **Implement POC-6 and decide Go/No-Go.** One command resolves Dizengoff Center → Technion and emits walking, transit, geometry, live timing and alerts with honest source states. Replay supports development but does not establish live feasibility. Regenerate status and record an explicit verdict against all ten PRD capabilities.

H1 (MOT request) was deferred on September 4; no later sent-date is recorded. Preparing code does not start its four-week clock. The request needs SIRI access, alerts URL, egress/IP requirements and usage terms. H2 needs the terms and source/date recorded. Neither is assumed complete, and this repository review sends no email.

## Phase 1, Step 1: M1 service skeleton

**Outcome:** a contributor can start the API from a fresh checkout, inspect its contract and health, and run CI checks without a MOT key. M1 creates the service boundary and development workflow. Real nationwide routing arrives in M3.

**Entry:** explicit Phase 0 acceptance and API runtime decision. Starting production M1 sooner would require an explicit revision to the PRD gate; the current plan does not silently waive it.

Implement:

- One API application with configuration validation, graceful shutdown, request IDs and structured logs that omit exact locations and credentials.
- `GET /healthz` for process liveness, `GET /readyz` for the configured dependency/data readiness, and a served OpenAPI document. Readiness must distinguish a healthy process from a missing or unusable graph; fixture readiness must be visibly identified as fixture mode.
- A small internal domain model and concrete modules for journeys, places, realtime and alerts. Put replaceable boundaries around MOTIS, realtime/alerts sources and the clock. Avoid empty packages for every future PRD capability.
- Deterministic synthetic/replay adapters with a pinned clock. Test missing and stale data without implying synthetic observations are live.
- Root development Compose configuration, environment example without secrets, dependency lock, and a fresh-checkout runbook. Keep the recorded PoC Compose configuration separate. Pin the tested engine image by digest when introducing the new configuration.
- CI that validates the OpenAPI contract, checks formatting/static analysis, exercises health/readiness and fails cleanly on invalid configuration. Include a startup smoke check; live MOT and full feed downloads are not CI prerequisites.

**M1 acceptance:** one documented startup command works; health/readiness accurately distinguish ready and unavailable dependencies; OpenAPI is served and validated; deterministic checks pass from a fresh checkout; no credential is needed; no journey endpoint is advertised as implemented before it exists.

Do not add production Redis, Photon, cloud hosting, accounts, mobile/web clients, historical analytics or a nightly nationwide builder just to finish M1. PoC Postgres remains useful cold-path evidence; production components are introduced when their milestone needs them.

## The rest of Phase 1

| Milestone | Implement | Acceptance emphasis |
| --- | --- | --- |
| M2 | Download/validate/version the selected GTFS + mapping pair; serve stops from read state | Current service coverage, date-aware mapping, rejected-feed behavior, reproducible artifacts |
| M3 | Same-host MOTIS adapter; normalized schedule journeys | Correct times and transfers, bounds/timeouts/cancellation, explicit no-route versus dependency error |
| M4 | Stop/POI search and an evidence-backed address solution | Hebrew/English category-level quality and p95 <40 ms at API process |
| M5 | Single realtime ingester, immutable snapshots, departures and vehicles | Per-leg truth states, coverage and age; no external request on the user path |
| M6 | Alert snapshots and journey association | Unavailable is distinct from no active alerts |
| M7 | Coordinated feed/graph/index/snapshot activation, rollback, status and load evidence | Old-or-new generation consistency, stale degradation, entire stack and replacement headroom under the intended cap |
| M8 | Deployment, public docs and operational runbook | Real deployed journey with live delays; repeated weekday-evening p95 <400 ms per PRD §14 |

The internal journey target remains p95 <350 ms (PRD §4.6); the deployed acceptance target is <400 ms. Specify measurement boundaries separately. The engine-only benchmark establishes neither full-API target nor a daily-user capacity estimate.

## Decisions to make

| Decision | Recommendation / evidence | Needed by |
| --- | --- | --- |
| Primary feed (ADR 0005) | Accepted 60-day + mapping; ingest/routing rerun; H3 quality pending | See rerun report |
| MOT request and source fallback | Record whether H1 remains deferred; record actual send date if sent; choose Stride/static-only/stop explicitly if access cannot be secured | POC-3/4 and final gate |
| Data usage terms (H2) | Record exact dataset/source terms, attribution, redistribution/fixture constraints and reviewer decision; no legal acceptance inferred from a download | Phase 0 acceptance |
| Route/search quality (H3/H4) | Complete review sheets; do not promote structural results to quality approval | Before realtime wave / final gate |
| API language | Python is a reasonable default given the developer's recorded PoC preference; .NET remains an option. ADR 0002 only binds the PoC | Before M1 |
| Journey HTTP contract and privacy | Propose POST for precise origin/destination data; current PRD/design specify GET. Record decision and align both before publishing the contract | M1 contract design |
| Time and identity | Explicit-offset API times, Asia/Jerusalem service dates, feed-scoped trip IDs, date-aware mapping and generation-consistent snapshots | POC matcher; M2/M3 |
| Walking limits and search ambiguity | Retain labelled 15/30-minute comparisons until reviewed; return candidates for ambiguous branches; location should be optional | H3/H4; M3/M4 |
| Address geocoding | Benchmark a same-host alternative/normalization approach on failed categories; Photon is a candidate, not a proven fix | Before M4 |
| Realtime semantics and matching threshold | Define fresh/stale/unknown/scheduled/cancelled, per-leg coverage and acceptable match rates by operator/mode before scoring POC-3. Existing 90% warning/70% paging values are operational proposals, not acceptance evidence | POC-3; M5 |
| Hosting and 4 GB versus 8 GB | Keep the proposed 8 GB envelope; measure the complete stack and overlapping generations before downsizing. Provider, price and IP requirements need a fresh check at deployment time | M7/M8 |

## Documents we need

Keep the existing PRD, architecture, system design, KDP register and raw evidence. The root dashboard is the current entrypoint. Superseded execution plans and agent briefs were removed from the working tree; Git at `3398826` preserves them.

| Artifact | Contents | When |
| --- | --- | --- |
| ADR 0005 + rerun report | Completed for ingest/routing; extend evidence for search and integration with their own provenance | Alongside new experiments |
| `docs/data-usage-and-access.md` | Terms evidence, attribution/redistribution obligations, H1 state/send date, source sustainability and access requirements; no keys | Before Phase 0 acceptance |
| Completed H3/H4 sheets + Phase 0 verdict | Human route/search decisions and all ten capability gates with evidence | Before M1 |
| API runtime ADR | Chosen language/framework, reason, dependency/runtime pins | Before M1 |
| `docs/api/openapi.yaml` | Health endpoints first; staged v1 requests/responses, examples, errors and implemented/planned distinction | M1, extended per milestone |
| `docs/data-contracts.md` | Feed generation, identifiers, service-day/time rules, snapshot schema, freshness, ambiguity and alert semantics | Matcher work, finalized before M2/M5 |
| `docs/development.md` | Prerequisites, locked install, Compose startup, fixture clock, tests, safe regeneration commands | M1 |
| `docs/validation.md` | Functional acceptance, load mix/concurrency, cold/warm runs, error rates, provenance and measurement boundaries | M1 baseline, extended M3–M7 |
| `docs/operations.md` | Feed activation/rollback, readiness, outages, retention, credential rotation and deploy procedure | Before M7/M8 |

These are planned deliverables, not claims that those files already exist. Write each alongside the behavior it specifies; do not create a second speculative architecture document.
