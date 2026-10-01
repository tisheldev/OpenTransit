# OpenTransit — project status

**Read this first.** Shared dashboard and handoff for every session.
**Last reviewed:** 2026-10-01 (evening). **Evidence baseline:** the October 1 live acceptance run [`acceptance-oct1b-20261001-02`](services/api/results/acceptance-oct1b-20261001-02/acceptance-oct1b-20261001-02-summary.json) at API commit `6ed3f5b`, plus the September 4–5 PoC experiments (`poc/README.md`, unchanged since `3398826`). A review date does not mean PoC experiments or external access were rechecked.

## Where we stand

**The scheduled API is functionally complete locally and passed a full mechanical acceptance run on one real generation; two human/operational gates remain.** Branch `feat/scheduled-api-m2-m4`. The October 1 acceptance generation (`5eb4e43d…`, schedule component `8f94fea3…`; Oct 1 snapshot; coverage Oct 1–31; one-command `build-generation` including OSM localities and sealed Photon addresses) passed every live check in both runs: ten structural probe journeys, `/readyz` 50/50 with zero engine `VERIFY FAIL`, walking-cap conformance (8 cases, 0 violations), the one-command demo, a 34-case API-path H3 sheet (0 errors, 0 mixed-generation) and the 183-variant search corpus. These are structural/mechanical results, not human approval.

- **H3 is with the user.** The [H3 sheet with a dated Moovit comparison](services/api/results/acceptance-oct1b-20261001-02/h3-moovit-comparison.md) is ready; every required (★) journey is within −9…+10 minutes of Moovit's earliest arrival (J23 has no route in either), but "Usable?" verdicts are blank and **no H3 approval is recorded**. J09 and J24 "no route" outcomes trace to corpus coordinates ([diagnosis](services/api/results/h3-no-route-diagnosis-20261001-01.json)).
- **H4 was approved by the user on 1 October** with address accuracy 16/22 and search p95 42.7 ms (all requests) / 52.1 ms (first pass) accepted as documented known limits.
- **M2.5 (local activation/rollback) is not accepted.** The Compose harness passed 7 of 10 live checks; three failures were diagnosed and the rerun is pending.
- Not done: bounded H-0 Fargate test (images unbuilt, no cloud resources), M7 operations/load evidence, Phase 2 client, static data terms, week of unattended refreshes. Realtime and alerts stay deferred. The original full-scope Phase 0 evidence remains 5/10 and is not a completion percentage.

| Workstream | State | Evidence / remaining gap |
| --- | --- | --- |
| Local API / M1 | IMPLEMENTED / TESTED | Real Dizengoff Center → Technion journey; [verification](services/api/results/m1-20260930.json), [run instructions](docs/development.md). |
| Feed generations and reference / M2 | IMPLEMENTED; ACCEPTANCE OPEN | `fetch`, `validate`, `build-generation` (14 stages, about 57 minutes, 4.0 GB for oct1b), `probe`, `prune`, localities (reference schema 3; schema 2 still readable), reference/status/`/readyz`. [Full-feed audit](services/api/results/m2-validation-attempt5-20260930.json) passes; 832 raw timing regressions stay diagnostic ([ADR 0008](poc/docs/adr/0008-bounded-minute-schedule-interpretation.md)). `/readyz` root cause (microsecond engine times) fixed and confirmed 50/50. M2.8 decided from one consecutive pair ([data contracts](docs/data-contracts.md)); the daily 06:30 fetch (developer machine) adds pairs. Open: M2.5 rerun ([7/10 harness](services/api/results/m2-activation-compose-20261001-01.json)), consecutive-daily evidence over time, API startup of about 9 minutes on the Windows bind mount (reference hashed twice). |
| Scheduled routing / M3 | IMPLEMENTED; H3 PASSED (9/10, user, Oct 1) | Alternatives, arrive-by, modes, stop/place inputs, walking caps, dated trips/departures, deadline/body/overload bounds, `opentransit demo`. [Run `-02`](services/api/results/acceptance-oct1b-20261001-02/acceptance-oct1b-20261001-02-summary.json) all PASS. Interior transfers MOTIS cannot street-route are kept with `walkingDistanceMeters` null and warning `TRANSFER_STREET_PATH_UNAVAILABLE`. Needs the user's H3 verdicts. |
| Local test client / TEST-UI | IMPLEMENTED / TESTED | Opt-in [playground](http://127.0.0.1:8000/playground/) when an API runs; [verification](services/api/results/test-client-20260930.json). Not Phase 2. |
| Static data / POC-1 | PASS technically | 544,338 trips; 20,100,370 stop times; 10/10 integrity checks. Terms remain open separately. |
| Routing / POC-2 | PARTIAL (historical) | 24/25 structural; superseded for release by the API-path H3 sheet above. |
| Search / M4 / POC-5 | ACCEPTED WITH KNOWN LIMITS | H4 approved 1 October ([run `-01` H4 sheet](services/api/results/acceptance-oct1b-20261001-01/acceptance-oct1b-20261001-01-h4-review.md)). Latest rerun `-02`: 148/183 top-1, 165/183 top-5, addresses 16/22, p95 42.5 ms all / 46.2 ms first pass (target 40 ms; tail is MOTIS Hebrew place search). Readiness now waits for the stop index and one warm-up per geocoder (reason codes `SEARCH_INDEX_*`, `ADDRESS_PROVIDER_*`, `PLACE_PROVIDER_*`). Revisit after launch. |
| Capacity | Components sampled only | Step-boundary snapshots in the acceptance run (MOTIS 651 MB, Photon 485 MB, API 231 MB under caps 2g/1g/1g) are not peaks and not full-stack or replacement capacity. The 8 GiB cap was not raised. |
| Hosting | AWS ECS Fargate selected; local drafts only | [H-0 drafts](deploy/aws/README.md) (Photon in-task proposal 1 vCPU / 3 GiB) are validated structurally only; images unbuilt, no cloud resources or spending. [Hosting plan](docs/next-steps.md#hosting-plan). |
| M7 operations/load (drafts) | PREPARED, NOT RUN | [Operations](docs/operations.md), [policies](docs/policies/privacy.md), [k6 scenarios](tools/load/README.md), [licence audit](docs/licence-audit.md); restore drill and load evidence pending. |
| Phase 2 client | PROPOSAL | [Client design](docs/client-design.md); implementation starts per the October 1 gate revision. |
| Realtime / POC-3, Alerts / POC-4 | DEFERRED | Source access/sustainability, matching and freshness unproven; no usable alerts feed recorded. |
| Integration / POC-6 | DEMO IMPLEMENTED | `opentransit demo` returned three labelled scheduled journeys in the acceptance run; static release verdict still needs H3 and terms. |
| Data access / usage | WAITING ON MOT / terms evidence | Email sent September 21; response pending; October 19 follow-up. Static terms remain a release requirement. [Access record](docs/data-usage-and-access.md). |

Measurements: [generated PoC report](poc/README.md), [raw results](poc/results/), [accepted-feed rerun](poc/docs/primary-feed-rerun.md). `python poc/poc_status.py` reads recorded status without downloads or Docker; it is not a rerun.

## Bigger picture

| Phase | Outcome | State / entry gate |
| --- | --- | --- |
| 0 | Static quality and scheduled integration; realtime/alerts proof deferred | H3 and static terms outstanding for release |
| 1 | Scheduled API: M1–M4 (functional, locally accepted pending M2.5) → M7 operations/load → M8 deployment; M5/M6 deferred | Python/FastAPI and R1–R5 accepted |
| 2 | First usable product client | NOT STARTED. October 1 gate revision: starts once M2–M4 are accepted locally and the private H-0/H-1 deployment begins; M7 runs alongside. Public release still requires every Phase 1 acceptance item |
| 3 | Realtime/alerts, then realtime-aware routing | FUTURE; H3 first, then source access and live proof |
| 4 | Reliability intelligence | FUTURE |
| 5 | Public open-source product | FUTURE |

Scope and gates: [PRD](PRD.md). Execution and acceptance criteria: [continuation plan](docs/next-steps.md). Designs are not implemented features.

## Next work, in priority order

Use these stable IDs in session claims. READY means prerequisites permit work, not that an agent is doing it.

| ID | Task / done when | State | Dependency / owner |
| --- | --- | --- | --- |
| P0-01 | Submit MOT questions/application; record sent date, response and terms evidence | WAITING ON MOT | Sent September 21; checkpoint October 19; [access record](docs/data-usage-and-access.md). |
| P0-02 | Complete H3 route review; at least 9/10 required journeys judged usable with dated comparisons | COMPLETE — PASSED | October 1: user judged 9/10 required journeys usable, J11 unsure ([verdicts](services/api/results/h3-verdicts-20261001-01.json), [comparison](services/api/results/acceptance-oct1b-20261001-02/h3-moovit-comparison.md)). Follow-up: last-mile street access at Haifa Center HaShmona (J11). |
| P0-03 | Search on the accepted feed; complete H4 | COMPLETE | October 1: H4 approved; address and latency limits accepted. |
| P0-04 | Realtime adapters/matcher at scale | DEFERRED | H3 first; live proof needs an accessible source. |
| P0-05 | Alerts parser and entity resolution | DEFERRED | H3 first; live PASS also needs access. |
| P0-06 | Scheduled demo and static release verdict | PARTLY DONE | Demo implemented and run; verdict requires P0-02 and static terms. Realtime/alerts reported unavailable, not PASS. |
| P1-01 | M1 local journey | COMPLETE | [M1 verification](services/api/results/m1-20260930.json). |
| P1-02 | M2 generations, reference, local activation, H-0 proposal | ACTIVE: M2.5 REMAINING | Rerun the [Compose harness](docs/development.md#probe-select-activate-and-roll-back) after the three diagnosed fixes (`r04`); M2.8 re-confirmation as daily snapshots accrue. [M2 criteria](docs/next-steps.md#m2--feed-generations-and-reference-data). |
| P1-03 | M3 routing/departures/trips; API-path H3 | WAITING ON USER (H3) | Functional and mechanical acceptance done; only the H3 verdict remains. |
| P1-04 | M4 search; H4 | ACCEPTED WITH KNOWN LIMITS | No further M4 work before launch. |
| H0-IMG | Build and measure the H-0 images locally under the proposed task limits (startup, disk, memory, readiness) | READY | Follows P1-02; [drafts](deploy/aws/README.md). Then ask the user for H-0 approval: region/ingress, reviewer IP, DNS name, bounded test ($10 ceiling, two tasks, two hours). |
| M7 | CI (licence decided: MIT, public direction), rate limiting, load, fault injection, restore drill, full-stack capacity under 8 GiB | AFTER H-0 START | Runs during the H-1 week; [operations](docs/operations.md), [load](tools/load/README.md). |
| CLIENT | Phase 2 product client against the private deployment | AFTER H-0 START | [Client design](docs/client-design.md); user review of the proposal. |

Before reruns, preserve input/config/corpus hashes, prior outputs and human verdicts. Verify overwrite behavior; do not clear evidence or graph volumes.

## Decisions and external blockers

| Item | Current decision / required action |
| --- | --- |
| Primary feed | ACCEPTED: 60-day product + TripIdToDate. Key overlap is not proof of realtime matching. [ADR 0005](poc/docs/adr/0005-ten-day-gtfs-feed.md). |
| Existing PoC choices | Python, Postgres/PostGIS cold storage, MOTIS routing; see [ADRs](poc/docs/adr/). |
| D2 — API runtime | ACCEPTED September 25: Python/FastAPI; CPython 3.14.6, FastAPI 0.142.1, [uv lock](services/api/uv.lock). |
| D3 — journey contract | ACCEPTED September 30: POST JSON; implemented through M3. |
| D4 — search architecture | DECIDED October 1: per-generation SQLite stop index (FTS5 trigram + OSM localities) plus generation-bound Photon addresses and MOTIS POIs, served concurrently. Limits above accepted by the user. |
| D5 — hosting | ACCEPTED September 30: AWS ECS Fargate, API/MOTIS (and Photon) in one task, fixed generation in private ECR. Photon sizing 1 vCPU / 3 GiB is a proposal; 0.5 vCPU / 2 GiB without addresses is the fallback. 8 GiB aggregate serving ceiling including rollout overlap. No cloud deployment or purchase. |
| M2.8 — public IDs | DECIDED October 1: stop/route IDs public (`mot:stop:…`, `mot:route:…`); trip references are generation-scoped ([data contracts](docs/data-contracts.md)). One consecutive pair so far. |
| Freshness | `current` under 30 h, `aging` 30–48 h, `stale` 48 h–7 days are serviceable with warnings; `expired` (7 days or more, or a future-dated check) is not. `/readyz`, the probe and rollback share this rule. |
| H1/H2 — access and terms | MOT email sent September 21; awaiting response. Static terms still need evidence. |
| H3 — route review | PASSED October 1: user judged 9/10 required journeys usable (J11 unsure); [verdicts](services/api/results/h3-verdicts-20261001-01.json). |
| H4 — search review | APPROVED by the user October 1 with the accepted known limits. |
| H5/H6 — fallback | Schedule-first scope accepted September 25; October 19 stays a live-feature follow-up. |
| Gate revision (user, October 1) | Client and M7 run during the H-1 week; public release gates unchanged ([PRD](PRD.md)). |
| S5 — code licence and visibility | DECIDED October 1 (user): MIT for original code and docs ([LICENSE](LICENSE)); public development direction and public GitHub visibility authorized. Dataset and third-party terms stay separate ([licence audit](docs/licence-audit.md)). |

## Active work and session handoff

Claims are coordination notes, not locks. Check timestamps, Git status and other edits before treating an old claim as active.

| Task ID | Agent/session | Updated (UTC) | State | Files/scope | Next step / blocker |
| --- | --- | --- | --- | --- | --- |
| M2.5-RERUN | Unassigned (handoff from Claude Code root) | 2026-10-01 16:20 | PAUSED | Activation harness live rerun `r04` on fresh generations `D:/ot/generations/oct1a` (old) → `oct1b` (new); harness fixes merged, never re-run live | Resume: run `services/api/tools/activation_compose_harness.py` against oct1a/oct1b (add generation/source-check options if needed), record `services/api/results/m2-activation-compose-20261001-02.json`; all 10 checks must pass for M2.5. Oct 1 source check ages to "aging" ~2 Oct 15:30Z, so re-fetch first if later. |
| H0-PREP | Claude Code (Opus 5.5) H-0 images session, branch `feat/h0-local-images` (worktree `D:/ot/wt-h0-local-images`) | 2026-10-01 16:45 | ACTIVE | Build and measure local AWS images from `deploy/aws` for generation `oct1b` (data image, Photon image, API/verifier), cold start, memory, disk, failure simulations; result `services/api/results/h0-local-images-20261001-01.json`; then the H-0 approval request | Docker lane `ot-t5-` / port 58500; M2.5 rerun is paused, so only this heavy Docker job runs. No cloud resources or spending. |

On completion, remove the claim and add a concise outcome below. Paused work keeps its row with an exact resume step. September 30 goal authorization: implement/test remaining scheduled API milestones, prepare deployment, then build the client; make routine technical decisions autonomously; the user supplies human verdicts, essential access, release and spending decisions. Escalate after two unsuccessful attempts at the same problem. Continuation sequence: [execution plan](docs/next-steps.md#continuation-execution-plan--1-october-2026). Codex's interrupted work is preserved on `backup/codex-m2-m4-20261001`.

## Recent outcomes

Keep only the latest five material outcomes; Git preserves older history.

- **2026-10-01 — H3 passed:** the user judged 9 of 10 required journeys usable on the review page (J11 unsure: its 9-minute gap is the last mile at Haifa Center HaShmona, which has no street walk to the destination point). [Verdicts](services/api/results/h3-verdicts-20261001-01.json). Follow-up: station street access; Friday/Shabbat/clock-change variants need Moovit comparison from 2–3 and 18 October.

- **2026-10-01 — Live acceptance on one generation; H4 approved; H3 passed:** runs `-01` (commit `c14476a`) and `-02` (`6ed3f5b`) PASS on generation `5eb4e43d…`: probe 10/10, `/readyz` 50/50, walk caps 0 violations, demo, 34-case H3 sheet, search 148/183 top-1 and 165/183 top-5, p95 42.5 ms all requests. Run `-01` exposed transfers MOTIS cannot street-route; fixed in `1d3e896` (`walkingDistanceMeters` nullable, `TRANSFER_STREET_PATH_UNAVAILABLE`) and re-run as `-02`. The user approved H4 with addresses 16/22 and p95 above 40 ms as known limits. H3 verdicts are pending. Moovit comparison dated 1 October; future-dated rows need rechecks. No evidence or volumes were overwritten.
- **2026-10-01 — Continuation steps 0–1 implemented:** router split, test collection, `.gitattributes` line endings, Windows MAX_PATH fetch error; `/readyz` fix; composite probe identity and shared freshness rule; M2.8 ID decision; `build-generation` (shakedown `oct1a`, acceptance `oct1b`); local `activate|rollback|await-retirement` operator and Compose harness (7/10); retention; OSM localities (reference schema 3); search fixes, concurrent geocoders, startup index build and warm-up gating `/readyz`; `opentransit demo`; tools `h3_review`, `check_walk_caps`, `acceptance_run`, `replay_search`. Suite 693 passed / 20 skipped / 0 failed at `6ed3f5b`. Storage trim of duplicate reference files recorded in [storage-trim-20261001-01.json](services/api/results/storage-trim-20261001-01.json).
- **2026-10-01 — Codex work adopted; preparation drafts added:** Codex stopped mid-M4 with 182 uncommitted files; snapshot `5296819` is on `backup/codex-m2-m4-20261001`. Codex-authored operations runbook, policy drafts, k6 scenarios and licence audit were merged as drafts. AWS H-0 drafts (with the Photon sizing proposal) and the Phase 2 client design were added; none is deployed or accepted.
- **2026-09-30 — Scheduled functional coverage tested:** [full-feed audit](services/api/results/m2-validation-attempt5-20260930.json) (425,160 profiles / 31,308,378 events), [real graph build](services/api/results/m3-functional-build-attempt3-20260930.json), [ten structural probes](services/api/results/m3-functional-probe-attempt2-20260930.json) and [22 matching-generation API checks](services/api/results/m3-m4-functional-http-20260930-01.json) (overnight/DST trips, paging, search → journey). Failed attempts are preserved.
## Where details belong

| Need | Read / update |
| --- | --- |
| Current state, priorities, assignment, handoff | **This file**; procedure in [AGENTS.md](AGENTS.md) |
| Product requirements and phase gates | [PRD](PRD.md); [API PRD and stories](docs/api-prd.md) |
| Milestone implementation and acceptance | [Continuation plan](docs/next-steps.md) |
| User decisions, Ministry application, terms | [Decision pack](docs/decision-pack/README.md), [access record](docs/data-usage-and-access.md) |
| Accepted choices / known feed problems | [ADRs](poc/docs/adr/), [data problems](poc/docs/known-data-problems.md) |
| Run, build, activate and check the API | [Development runbook](docs/development.md), [API package](services/api/) |
| Live acceptance evidence | [Run `-02`](services/api/results/acceptance-oct1b-20261001-02/acceptance-oct1b-20261001-02-summary.json), [run `-01`](services/api/results/acceptance-oct1b-20261001-01/acceptance-oct1b-20261001-01-summary.json), [H3 comparison](services/api/results/acceptance-oct1b-20261001-02/h3-moovit-comparison.md), [H3 diagnosis](services/api/results/h3-no-route-diagnosis-20261001-01.json) |
| Results and reproduction | [PoC status](poc/README.md), [routing runbook](poc/routing/README.md), [rerun report](poc/docs/primary-feed-rerun.md) |
| Identity, freshness, generation contracts | [Data contracts](docs/data-contracts.md), [domain glossary](CONTEXT.md), [timing policy](poc/docs/adr/0008-bounded-minute-schedule-interpretation.md), [M2.8 evidence](services/api/results/m2-id-stability-20261001-01.json) |
| Phase 2 client (proposal) and cloud drafts | [Client design](docs/client-design.md), [deploy/aws](deploy/aws/README.md) |
| Operations, policies, load, licences (drafts) | [Operations](docs/operations.md), [policies](docs/policies/privacy.md), [load scenarios](tools/load/README.md), [licence audit](docs/licence-audit.md) |
| Code structure, UML, contracts | [System design](docs/system-design.md), [architecture overview](docs/architecture.md); designs, not implementation evidence |

Removed historical planning material is recoverable from Git at `3398826`; do not recreate an archive folder or separate session-report document. Historical comparisons remain under `poc/comparisons/` because they support measured claims.
