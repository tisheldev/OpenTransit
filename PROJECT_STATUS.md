# OpenTransit — project status

**Read this first.** Shared dashboard and handoff for every session.
**Last reviewed:** 2026-09-21. **Evidence baseline:** September 4–5 experiments, committed through `3398826` (September 6). A review date does not mean experiments or external access were rechecked.

## Where we stand

**Phase 0 — feasibility: NOT YET complete; 5/10 recorded capabilities green.**
Static ingestion passes; routing awaits human quality review. Search is partial. Realtime, alerts access, usage terms and the end-to-end demonstration remain unresolved. No production API or frontend exists. This is not a percentage of overall product completion.

| Workstream | State | Evidence / remaining gap |
| --- | --- | --- |
| Static data / POC-1 | PASS technically | 544,338 trips; 20,100,370 stop times; 10/10 integrity checks. Terms remain open separately. |
| Routing / POC-2 | PARTIAL | 24/25 structural passes; 22/25 first-itinerary passes. Human H3 review pending. |
| Capacity | Engine measured only | MOTIS p95 162.9 ms; load peak 941.3 MB under an 8 GiB serving cap. Full stack and graph replacement unproven. |
| Search / POC-5 | PARTIAL | Historical 68/100 top-1, 89/100 top-5; addresses 4/15. Accepted-feed rerun and H4 review pending. |
| Realtime / POC-3 | NOT STARTED | Source access/sustainability, date-aware matching, arrivals, vehicles and freshness unproven. |
| Alerts / POC-4 | BLOCKED on access | No usable feed recorded; synthetic parser work remains possible. |
| Integration / POC-6 | NOT STARTED | Search → route → realtime → alerts demonstration required. |
| Data access / usage | BLOCKED on decisions/access | No sent MOT request or terms acceptance recorded. |

Measurements: [generated PoC report](poc/README.md), [raw results](poc/results/), [accepted-feed rerun](poc/docs/primary-feed-rerun.md). Run `python poc/poc_status.py` to inspect recorded capability status without downloads or Docker. It does not rerun experiments.

## Bigger picture

| Phase | Outcome | State / entry gate |
| --- | --- | --- |
| 0 | Demonstrate data, routing, search, realtime and alerts; explicit go/no-go | IN PROGRESS |
| 1 | API: M1 skeleton → M2 feeds → M3 routing → M4 search → M5 realtime → M6 alerts → M7 operations/load → M8 deployment | NOT STARTED; Phase 0 acceptance and API runtime decision required |
| 2 | First usable client | NOT STARTED; API must be finished first |
| 3 | Realtime-aware routing | FUTURE |
| 4 | Reliability intelligence | FUTURE |
| 5 | Public open-source product | FUTURE |

Scope and phase gates: [PRD](PRD.md). Implementation and acceptance criteria: [continuation plan](docs/next-steps.md). Future designs are not implemented features.

## Next work, in priority order

Use these stable IDs in session claims. READY means prerequisites permit work, not that an agent is already doing it. Access work can proceed alongside quality validation.

| ID | Task / done when | State | Dependency / owner |
| --- | --- | --- | --- |
| P0-01 | Submit MOT questions/application; record actual sent date, response and terms evidence | WAITING ON USER | User sends/signs; [prepared pack](docs/decision-pack/README.md). No sent date recorded; four-week clock has not started. |
| P0-02 | Complete H3 route review; at least 9/10 required journeys judged usable with dated comparisons | READY FOR REVIEW | Agent prepares comparisons; user judges [route sheet](poc/results/journeys-h3-review.md). Older departure dates may limit comparisons. |
| P0-03 | Rerun search on accepted feed; record category/language failures and complete H4 review | READY | Unassigned; preserve historical results and human verdicts before regeneration. |
| P0-04 | Build realtime adapters/matcher; measure thousands of observations by operator/mode, including unmatched, ambiguous and stale counts | WAITING | H3 first; live proof requires an accessible source. Replay is development evidence only. |
| P0-05 | Build alerts parser and entity resolution; validate synthetic fixtures, then a real feed | WAITING | H3 before realtime/alerts wave; live PASS also requires access. |
| P0-06 | Demonstrate complete journey in one command and record all ten capability verdicts | WAITING | P0-02–05, acceptable terms and sustainable source decision; explicit Phase 0 acceptance. |
| P1-01 | Implement M1 skeleton, health/readiness, OpenAPI, locked setup and CI | WAITING | P0-06 and API runtime decision; see [M1 scope](docs/next-steps.md#phase-1-step-1-m1-service-skeleton). |

Before reruns, preserve input/config/corpus hashes, prior outputs and human verdicts. Verify scripts' overwrite behavior; do not casually clear evidence or graph volumes. A reproducible dependency lock and fresh-checkout runbook are still missing.

## Decisions and external blockers

| Item | Current decision / required action |
| --- | --- |
| Primary feed | ACCEPTED: 60-day product + TripIdToDate; ingest/routing rerun completed. Static key overlap is not proof of realtime matching. [ADR 0005](poc/docs/adr/0005-ten-day-gtfs-feed.md). |
| Existing PoC choices | Python, Postgres/PostGIS cold storage, MOTIS routing and initial geocoding; see [ADRs](poc/docs/adr/). |
| D2 — API runtime | PENDING: Python/FastAPI proposed; Python acceptance currently covers the PoC only. |
| D3 — journey contract | PENDING: POST proposed; current PRD/design specify GET. Align documents when decided. |
| D4 — search architecture | PENDING: in-process stop index and evidence-backed address solution proposed. |
| D5 — execution/hosting package | PENDING proposal: local feasibility first, 8 GB test envelope, defer hosting purchase. Existing PRD phase gates still apply. |
| H1/H2 — access and terms | User action/written evidence required; [access record](docs/data-usage-and-access.md). Drafting an email is not sending or accepting terms. |
| H5/H6 — fallback | If direct access fails, explicitly choose sustainable fallback, static-only scope or stop. Four-week decision point is actual request date + 28 days. |

## Active work and session handoff

Claims are coordination notes, not locks. Check timestamps, Git status and other edits before treating an old claim as active. Preserve other sessions' rows and changes.

| Task ID | Agent/session | Updated (UTC) | State | Files/scope | Next step / blocker |
| --- | --- | --- | --- | --- | --- |
| — | — | — | No active claims | — | Next: P0-03 search rerun or P0-02 review preparation. |

On completion, remove the claim and add a concise outcome below. Paused work keeps its row with an exact resume step. Next recommended engineering task: P0-03, or prepare P0-02 comparisons. P0-01 requires user action.

## Recent outcomes

Keep only the latest five material outcomes; Git preserves older history.

- **2026-09-21 — DOC-01 complete:** Added this dashboard and root agent workflow; simplified README; removed 11 tracked superseded plans, presentations, briefs and cleanup notes. Reconciled continuation/decision-pack text with the completed primary-feed rerun and repaired historical navigation. Validation: recorded-status command, local Markdown link check and diff whitespace check. No experiment rerun or external-access check. Next: P0-03 or P0-02; access/terms remain open.

- **2026-09-05, committed September 6:** Accepted-feed ingest/routing rerun completed; H3 remains pending, search remains historical. [Report](poc/docs/primary-feed-rerun.md).

## Where details belong

| Need | Read / update |
| --- | --- |
| Current state, priorities, assignment, handoff | **This file**; procedure in [AGENTS.md](AGENTS.md) |
| Product requirements and phase gates | [PRD](PRD.md) |
| Milestone implementation and acceptance | [Continuation plan](docs/next-steps.md) |
| User decisions, Ministry application, terms | [Decision pack](docs/decision-pack/README.md), [access record](docs/data-usage-and-access.md) |
| Accepted choices / known feed problems | [ADRs](poc/docs/adr/), [data problems](poc/docs/known-data-problems.md) |
| Results and reproduction | [PoC status](poc/README.md), [routing runbook](poc/routing/README.md), [rerun report](poc/docs/primary-feed-rerun.md) |
| Architecture reference, when relevant | [Architecture](docs/architecture.md), [system design](docs/system-design.md); proposals, not completion evidence |

Removed historical planning material is recoverable from Git at `3398826`; do not recreate an archive folder or a separate session-report document. Historical experimental comparisons remain under `poc/comparisons/` because they support measured claims.
