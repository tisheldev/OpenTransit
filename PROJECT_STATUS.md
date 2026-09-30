# OpenTransit — project status

**Read this first.** Shared dashboard and handoff for every session.
**Last reviewed:** 2026-09-30. **Evidence baseline:** September 4–5 experiments, committed through `3398826` (September 6). A review date does not mean experiments or external access were rechecked.

## Where we stand

**M1 local scheduled API in progress; plan changes accepted September 30.**
The user deferred realtime; live alerts move with that feature wave. The user authorized applying design simplifications R1–R5 and starting implementation September 30 ([ADR 0007](poc/docs/adr/0007-schedule-api-design.md)). M1–M4 proceed alongside static validation. H3/H4, scheduled integration and static terms remain release requirements. The user prioritizes working functionality: M1 now delivers a basic local journey; CI waits for M7 and contributor/repository polish for Phase 5. The completed schedule-based API still precedes the client. Original full-scope Phase 0 evidence remains 5/10, not a v1 entry gate or a completion percentage. The local API is being implemented; real graph/HTTP validation is in progress. No deployed API or frontend exists.

| Workstream | State | Evidence / remaining gap |
| --- | --- | --- |
| Static data / POC-1 | PASS technically | 544,338 trips; 20,100,370 stop times; 10/10 integrity checks. Terms remain open separately. |
| Routing / POC-2 | PARTIAL | 24/25 structural passes; 22/25 first-itinerary passes. Human H3 review pending. |
| Capacity | Engine measured only | MOTIS p95 162.9 ms; load peak 941.3 MB under an 8 GiB serving cap. Full stack and graph replacement unproven. |
| Hosting | AWS ECS Fargate selected September 30 | API/MOTIS in one task; fixed generation in private ECR; S3 optional. Region, task resources, ingress, refresh retention and cost unverified; no deployment. [Hosting plan](docs/next-steps.md#hosting-plan). |
| Search / POC-5 | PARTIAL | Historical 68/100 top-1, 89/100 top-5; addresses 4/15. Accepted-feed rerun and H4 review pending. |
| Realtime / POC-3 | DEFERRED | Source access/sustainability, date-aware matching, arrivals, vehicles and freshness unproven. |
| Alerts / POC-4 | DEFERRED; access unresolved | No usable feed recorded; synthetic parser work remains possible. |
| Integration / POC-6 | NOT STARTED | Schedule-only search → route demonstration required before release; live enrichment deferred. |
| Data access / usage | WAITING ON MOT / terms evidence | Email sent from correct address September 21; response pending. October 19 follow-up for deferred features; static terms remain a release requirement. |

Measurements: [generated PoC report](poc/README.md), [raw results](poc/results/), [accepted-feed rerun](poc/docs/primary-feed-rerun.md). Run `python poc/poc_status.py` to inspect recorded capability status without downloads or Docker. It does not rerun experiments.

## Bigger picture

| Phase | Outcome | State / entry gate |
| --- | --- | --- |
| 0 | Static quality and scheduled integration; realtime/alerts proof deferred | Continue alongside API; required before static release |
| 1 | Scheduled API: M1 basic local journey → M2 feeds → M3 routing/departures → M4 search → M7 operations/load → M8 deployment | Python/FastAPI and R1–R5 accepted; planning gate satisfied September 30. M5/M6 deferred |
| 2 | First usable client | NOT STARTED; API must be finished first |
| 3 | Realtime/alerts integration, then realtime-aware routing | FUTURE; source access, terms and live proof required |
| 4 | Reliability intelligence | FUTURE |
| 5 | Public open-source product | FUTURE |

Scope and phase gates: [PRD](PRD.md). Implementation and acceptance criteria: [continuation plan](docs/next-steps.md). Future designs are not implemented features.

## Next work, in priority order

Use these stable IDs in session claims. READY means prerequisites permit work, not that an agent is already doing it. Access work can proceed alongside quality validation.

| ID | Task / done when | State | Dependency / owner |
| --- | --- | --- | --- |
| P0-01 | Submit MOT questions/application; record actual sent date, response and terms evidence | WAITING ON MOT | User confirms email sent from correct address September 21; response pending. 28-day checkpoint October 19; [access record](docs/data-usage-and-access.md). |
| P0-02 | Complete H3 route review; at least 9/10 required journeys judged usable with dated comparisons | READY FOR REVIEW | Agent prepares comparisons; user judges [route sheet](poc/results/journeys-h3-review.md). Older departure dates may limit comparisons. |
| P0-03 | Rerun search on accepted feed; record category/language failures and complete H4 review | READY | Unassigned; preserve historical results and human verdicts before regeneration. |
| P0-04 | Build realtime adapters/matcher; measure thousands of observations by operator/mode, including unmatched, ambiguous and stale counts | DEFERRED | H3 first; live proof requires an accessible source. Replay is development evidence only. |
| P0-05 | Build alerts parser and entity resolution; validate synthetic fixtures, then a real feed | DEFERRED | H3 before realtime/alerts wave; live PASS also requires access. |
| P0-06 | Demonstrate scheduled journey in one command and record static release verdict | REQUIRED BEFORE RELEASE | P0-02/03 and static terms; realtime/alerts explicitly deferred, not PASS. |
| API-DESIGN | Apply accepted R1–R5, POST journey contract and Fargate hosting amendment to planning docs | ACCEPTED / RECONCILED | September 30 authorization; [ADR 0007](poc/docs/adr/0007-schedule-api-design.md). Deployment validation remains open. |
| P1-01 | Implement a basic local Python/FastAPI journey using prepared MOTIS, with minimal setup and focused checks | IN PROGRESS | Planning authorized September 30; Python/FastAPI accepted in ADR 0002; see [M1 scope](docs/next-steps.md#phase-1-step-1-m1-service-skeleton). |

Before reruns, preserve input/config/corpus hashes, prior outputs and human verdicts. Verify scripts' overwrite behavior; do not casually clear evidence or graph volumes. M1 adds a dependency lock and local development runbook; full contributor onboarding remains Phase 5.

## Decisions and external blockers

| Item | Current decision / required action |
| --- | --- |
| Primary feed | ACCEPTED: 60-day product + TripIdToDate; ingest/routing rerun completed. Static key overlap is not proof of realtime matching. [ADR 0005](poc/docs/adr/0005-ten-day-gtfs-feed.md). |
| Existing PoC choices | Python, Postgres/PostGIS cold storage, MOTIS routing and initial geocoding; see [ADRs](poc/docs/adr/). |
| D2 — API runtime | ACCEPTED September 25: Python with FastAPI for API and Python ingestion; [ADR 0002 amendment](poc/docs/adr/0002-python-for-the-poc.md). Pin supported versions in M1. |
| D3 — journey contract | ACCEPTED September 30: POST JSON; local preview contract exposed in M1, complete journey features in M3. |
| D4 — search architecture | R4 accepts per-generation SQLite; measure FTS5 vs in-process search and choose address solution from M4 evidence. |
| D5 — execution/hosting package | ACCEPTED September 30: AWS ECS Fargate with API/MOTIS in one task and fixed generation in private ECR; S3 optional. Test 0.5 vCPU / 2 GiB; preserve 8 GiB aggregate serving ceiling including rollout overlap. H-0 in M2 resolves region/ingress/resources/cost; private preview after M3. M1 local; future SIRI collector alone needs MOT-approved static egress. [Hosting plan](docs/next-steps.md#hosting-plan); no cloud deployment or purchase. |
| H1/H2 — access and terms | MOT email sent September 21 from correct address per user; awaiting response. Access and terms acceptance still need evidence; [access record](docs/data-usage-and-access.md). |
| H5/H6 — fallback | Schedule-first scope accepted September 25. October 19 remains a live-feature follow-up; no automatic stop of static development or approval of a fallback. |

## Active work and session handoff

Claims are coordination notes, not locks. Check timestamps, Git status and other edits before treating an old claim as active. Preserve other sessions' rows and changes.

| Task ID | Agent/session | Updated (UTC) | State | Files/scope | Next step / blocker |
| --- | --- | --- | --- | --- | --- |
| P1-01 / API-DESIGN | Codex / root session | 2026-09-30 09:25 UTC | IN PROGRESS | Accept R1–R5 and POST contract; reconcile planning docs; implement M1 local scheduled API and fresh graph without modifying PoC evidence | Plans reconciled; Python 3.14.6/dependencies locked; Docker stale socket fixed by preserving/renaming run directory. Build fresh isolated graph, run focused tests and verify real HTTP journey. |

On completion, remove the claim and add a concise outcome below. Paused work keeps its row with an exact resume step. Next: complete P1-01 fresh-graph and HTTP verification, then M2; prepare fresh H3/H4 sheets alongside development. User obtains written static GTFS terms. MOT response is only a deferred-feature dependency; follow-up October 19.

## Recent outcomes

Keep only the latest five material outcomes; Git preserves older history.

- **2026-09-30 — HOST-01 complete:** Recorded user-selected ECS Fargate, private ECR generation images and optional S3 in ADR 0007, PRDs, architecture/design, continuation plan, decision/access records and this dashboard. Replaced VM hosting guidance; production uses complete task rollout/readiness/draining while local M2 keeps pointer/reload. 8 GiB remains an aggregate ceiling, not minimum allocation; future SIRI static egress is collector-only and subject to MOT approval. User requested committing hosting and supporting planning docs; M1 code/runtime files excluded. Validation: 110 local links/anchors and code fences across eleven docs passed, superseded-hosting reference scan and `git diff --check` passed. No code, experiments, cloud resources or evidence changed by this session. Next: finish local M1; at M2 H-0 prepare AWS region/ingress/resources/cost proposal and verify startup/load/storage; durable refresh retention and MOT terms remain open.

- **2026-09-25 — API-PLAN drafted:** At the user's request, added a step-level M1–M4 plan, a hosting plan (provider options with September 2026 prices, host layout, supporting services, sequence H-0 to H-3) and a non-code workstream (S1–S9) to the continuation plan. Added design simplifications R1–R5 (blue/green activation, stable source IDs, one package, per-generation SQLite, deferred scale controls) to system design §0 as proposals; underlying sections are unchanged until accepted. Validation: local links/anchors and diff whitespace checked; no code, experiments or purchases. Next: user reviews the proposals and hosting timing.

- **2026-09-25 — API-DESIGN priority revised:** User put working functionality before open-source polish. Release A/M1 now returns a real local coordinate/depart-at journey using a verified prepared graph; M3 completes the broader routing feature set. CI/schema automation moves to M7; contributor onboarding, portable demos and community tooling to Phase 5. Aligned API/root PRDs, continuation plan, design and decision notes. Validation: local links/anchors, JSON examples and diff whitespace checked; no code or experiments. Next: continue PRD/design review before implementation; static release requirements unchanged.

- **2026-09-25 — API-DESIGN drafts complete:** Added API-specific PRD with phased scope, 14 stories, endpoint inventory and release gates; replaced system design with Python structure, UML, data/identity contracts, activation, security, operations and expansion design. Reconciled root PRD, architecture, continuation/decision docs. No application code or evidence changes. Validation: local links/anchors, JSON, offline diagram structure and diff whitespace checked. Visual rendering unverified: automatic approval review rejected loading external CDN code with local docs. Next: review API PRD, then design; D3/D4/defaults remain proposals.

- **2026-09-25 — P1-01 runtime decision complete:** User selected Python; recorded Python/FastAPI production scope in ADR 0002 and aligned PRD, decision pack and continuation plan. M1 is not implemented. Validation: local links and diff whitespace checked; no code/tests or experiment changes. Next: implement M1 service skeleton and pin supported runtime/dependencies. Static release checks and deferred realtime access remain unresolved.


## Where details belong

| Need | Read / update |
| --- | --- |
| Current state, priorities, assignment, handoff | **This file**; procedure in [AGENTS.md](AGENTS.md) |
| Product requirements and phase gates | [PRD](PRD.md); detailed [API PRD and stories](docs/api-prd.md) |
| Milestone implementation and acceptance | [Continuation plan](docs/next-steps.md) |
| User decisions, Ministry application, terms | [Decision pack](docs/decision-pack/README.md), [access record](docs/data-usage-and-access.md) |
| Accepted choices / known feed problems | [ADRs](poc/docs/adr/), [data problems](poc/docs/known-data-problems.md) |
| Results and reproduction | [PoC status](poc/README.md), [routing runbook](poc/routing/README.md), [rerun report](poc/docs/primary-feed-rerun.md) |
| Code structure, UML, contracts and operations | [System design](docs/system-design.md), [architecture overview](docs/architecture.md); review drafts, not implementation evidence |

Removed historical planning material is recoverable from Git at `3398826`; do not recreate an archive folder or a separate session-report document. Historical experimental comparisons remain under `poc/comparisons/` because they support measured claims.
