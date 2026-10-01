# From PoC to API implementation

**Execution reference, reconciled 1 October 2026 (evening).** Read [PROJECT_STATUS.md](../PROJECT_STATUS.md) for current state, priorities, ownership and session handoff. This document defines implementation scope and acceptance; proposals remain open unless explicitly accepted.

The accepted baseline is the 60-day feed plus TripIdToDate (ADR 0005). Ingest/routing reruns are complete; see [measured results](../poc/docs/primary-feed-rerun.md). Search/H4 and realtime integration still need that baseline. Static mapping-key overlap is not a realtime matching rate.

## The immediate next step: complete scheduled API functionality

The accepted September 25 scope revision in [PRD](../PRD.md#accepted-scope-revision--25-september-2026) permits M1–M4 development while static validation continues. Realtime and live alerts are deferred. This supersedes the original Phase 0-before-M1 sequencing; it does not declare H3/H4 or the full PoC passed. API completion before client development remains required.

1. **Finish journeys, dated trips/departures, then search.** Reuse completed validation and preserved inputs; finish generation/reference preparation where it directly blocks a feature. The September 30 sequencing revision moves non-blocking operational hardening after functional coverage while retaining every M2–M8 acceptance criterion. [M1 HTTP evidence](../services/api/results/m1-20260930.json) records a real scheduled journey, not H3 or release approval. Preserve its generation and the PoC artifacts. The user authorized R1–R5 and implementation September 30; [ADR 0007](../poc/docs/adr/0007-schedule-api-design.md) records this. No MOT credential or completed live-data proof is required.
2. **Continue static quality work alongside M1–M4.** Preserve historical evidence, rerun search on the accepted 60-day feed plus TripIdToDate, and complete H3/H4. H3 still requires at least 9/10 usable representative routes, including service-day boundaries, transfers and no-route cases. Resolve or explicitly constrain search failures before release.
3. **Demonstrate scheduled integration before release.** One command (`opentransit demo`, implemented and run in the October 1 acceptance run) resolves Dizengoff Center → Technion with scheduled times, walking, transfers and geometry. Explicitly report realtime and alerts as unavailable. Record a schedule-first verdict separately from the original ten-capability report; do not mark deferred capabilities PASS.
4. **Complete static release requirements through M7/M8.** Record acceptable usage terms for included datasets, freshness and rollover behavior, error handling, rollback, full-stack capacity under the intended 8 GiB serving cap, and deployed performance.
5. **Add realtime and alerts later.** Retain POC-3/4 and M5/6 as deferred work. Before shipping them, prove sustainable source access, acceptable terms, date-aware matching over thousands of observations by operator/mode, freshness and actual alerts-feed integration. Synthetic/replay evidence remains labelled and cannot establish live feasibility. H3 still precedes this wave.

The MOT request was sent September 21 per user confirmation; response is pending and October 19 remains the follow-up checkpoint. This is no longer a v1 development blocker. Static usage terms remain unresolved separately; see the [access record](data-usage-and-access.md).

## M1–M4 delivery plan

**Accepted for implementation 30 September 2026.** This plan incorporates R1–R5 in [system design §0](system-design.md#0-review-proposals--simplifications) and the AWS Fargate hosting amendment in [ADR 0007](../poc/docs/adr/0007-schedule-api-design.md#hosting-amendment--accepted-30-september-2026). M1 stays local; no cloud purchase is needed for it. Effort figures are rough estimates in focused working days for one developer. They are not dates or commitments. Each milestone ends the same way: record a demo command in `docs/development.md`, pass the focused tests, and update the dashboard.

| Milestone | Outcome you can demonstrate | Rough effort | Needs first | Non-code work alongside |
| --- | --- | --- | --- | --- |
| M1 | `POST /v1/journeys` returns a real scheduled itinerary from a fresh local graph | 3–5 days | September 30 authorization; fresh graph | S2 static terms |
| M2 | One command builds, validates and activates a feed generation; stop/route/pattern/status endpoints | 10–15 days | M1 | Hosting spike H-0, S2 terms, S5 licence |
| M3 | Complete scheduled routing, departures and dated trips; H3 sheet regenerated through the API | 10–15 days | M2 verified generation/reference for features; complete M2 acceptance remains required | S3 H3 review, preview host H-1 |
| M4 | Hebrew/English place search feeding journey planning; H4 evidence | 10–20 days (address risk) | M3 functional path; P0-03 rerun; consistent search generation | S3 H4 review, S4 policies |

M7 (hardening, CI, load) and M8 (public deployment) follow as already defined; the hosting section below covers what they deploy onto.

**Repository shape (R3):** one Python package, `services/api/src/opentransit/`, containing `api/` (routers and HTTP schemas), `core/` (models, time and IDs; does not import FastAPI), `motis.py`, `reference.py` and `build/` (the feed CLI). Use one `pyproject.toml` with a `uv` lock, pytest and ruff. At M1 setup, pick the newest CPython version that every dependency supports and pin it. Pin the tested MOTIS image by digest: the PoC used v2.11.2, `sha256:6055f51e…d330`.

### Phase 1, Step 1: M1 service skeleton

**Outcome:** the developer calls the local FastAPI service with two coordinates and an explicit departure time and receives one real scheduled itinerary. M1 includes a narrow routing slice previously reserved for M3; M3 completes the full routing feature set.

**Entry:** user authorized implementation September 30. Python/FastAPI and schedule-first scope are accepted. **Coverage concern:** the prepared PoC graph's service window ends 2026-10-04. M1 therefore starts by building a fresh graph. Historical dates must be labelled, never presented as current service.

| Step | Work | Done when |
| --- | --- | --- |
| M1.0 | Download the current 60-day feed plus TripIdToDate; run `motis import` with the pinned digest into a **new** named volume. Write a small `manifest.json` with input hashes, coverage and engine digest. Never touch the PoC `motisgraph` volume or results. | Graph loads; manifest records coverage covering today |
| M1.1 | Package skeleton, settings from environment, `GET /healthz`, generated `/docs`. Root `compose.yaml` with `motis` and `api` for local development; production later uses ECS task definitions with the same pinned runtime images. | `docker compose up` serves docs |
| M1.2 | Async `httpx` MOTIS client with a timeout; call the pinned plan endpoint; normalize walk/transit legs, explicit-offset times, operator/route/headsign, stops, trip ID with service date when exposed, and GeoJSON geometry. | Normalized output checked against one real response |
| M1.3 | `POST /v1/journeys` with coordinates and `departAt`. Validate the Israel bounding box, explicit offsets and manifest coverage. Return a 200 `no_route` outcome, 422/503/504 problem+json errors, `timingState: scheduled` and realtime `not_enabled`. | Distinct responses for each case |
| M1.4 | Log request ID, route template, status and duration. Never log bodies or coordinates. | Sentinel coordinate absent from logs |
| M1.5 | Focused tests: one real route (integration marker), invalid input, no-route, engine down and timeout (mocked transport). | Tests pass locally |
| M1.6 | `docs/development.md`: start command plus a Dizengoff Center → Technion coordinate `curl` example. | Another session can reproduce it |

**M1 acceptance:** the real local HTTP request works against a declared valid graph/time window; returned stops/times/legs can be inspected; failures are honest; startup/request steps are recorded. H3/H4 and deployed performance remain release checks. No CI, fixture framework or contributor onboarding in M1.

### M2 — feed generations and reference data

**Outcome:** `opentransit build` turns fresh sources into a validated generation, and `opentransit activate` switches to it without downtime (R1). The API serves reference data from that generation. Basic activation is in M2 because a 60-day feed needs routine rebuilds anyway, and R1 makes the swap small. M7 keeps the under-load and fault-injection proof.

| Step | Work | Done when |
| --- | --- | --- |
| M2.1 | `fetch`: GTFS, TripIdToDate and the Geofabrik OSM extract into retained input snapshots with SHA-256 and acquisition time. Use full GET and archive validation for MOT change detection; do not trust HEAD metadata. Skip rebuilding unchanged content; only successful paired validation renews static freshness. OSM weekly is enough. | Re-running is idempotent; partial/failed fetches preserve prior inputs and freshness |
| M2.2 | `validate`: implement reviewed production safeguards derived from the ten POC-1 checks (no script imports), with explicit applicability/evidence mapping below. Check references, ranges, sequences, extended-hour times, calendars, pairing/service-window overlap and actual coverage. Failure exits nonzero and leaves the active generation untouched. | Corrupt, orphaned and mismatched fixtures are rejected; every applicable check has a result |
| M2.3 | `build`: memory-capped MOTIS import into `generations/<id>/motis`. Build the reference file `generations/<id>/reference.sqlite` (R4): stops, parent stations, routes, agencies, translations, route–stop links and patterns (ordered stops plus pickup/drop-off rules). Write `manifest.json`. | Build reproducible from recorded inputs |
| M2.4 | `probe`: start the idle blue/green MOTIS on the candidate; run about ten fixed journeys from the H3 corpus; compare stop/route counts with the active generation (a large drop blocks activation). | Bad candidate blocked with a clear report |
| M2.5 | Local `activate`/`rollback`: atomic `current` symlink rename and single-worker reload in Linux Compose; stop the old engine only after acknowledgement plus at least ten request deadlines. Rollback re-checks coverage/freshness first. Production packages a fixed generation into an image and replaces whole ECS tasks; see hosting plan. | In-flight request completes on old data; next uses new locally; failed reload preserves old serving state; production task rollout verified at H-1/M7 |
| M2.6 | Retention: keep the active generation, the previous one and evidence-pinned ones; `prune --dry-run` lists candidates; deletion is manual. | Nothing deleted implicitly |
| M2.7 | Endpoints: `/v1/stops` (near or bbox), `/v1/stops/{id}`, `/v1/routes`, `/v1/routes/{id}`, `/v1/routes/{id}/patterns`, `/v1/status`, `/readyz`. | Loop and parent-station fixtures pass |
| M2.8 | ID-stability check (R2): compare `stop_id`/`route_id`/`trip_id` across two consecutive daily feeds; choose the public ID scheme from that evidence; write `docs/data-contracts.md`. | Decision recorded with counts |
| M2.9 | A small hand-written synthetic GTFS fixture (about ten stops, a loop, an after-midnight trip) for build/validate tests. | Tests run without downloads |

**Status, 1 October 2026** (evidence in [PROJECT_STATUS.md](../PROJECT_STATUS.md); criteria above unchanged). M2.1 implemented, with a clear Windows MAX_PATH failure and a daily 06:30 fetch scheduled on the developer machine. M2.2 passes the [full-feed audit](../services/api/results/m2-validation-attempt5-20260930.json) under ADR 0008. M2.3 is implemented as `build` and the one-command `build-generation` (14 stages, about 57 minutes for the October 1 generation `5eb4e43d…`, including OSM localities and sealed Photon addresses). M2.4 passes 10/10 on that generation through composite-generation probe identity. **M2.5 passed its local acceptance on 1 October:** the Compose harness run `r06` switched between the two complete composite generations `oct1a` → `oct1b` under load and passed all 10 live checks ([record](../services/api/results/m2-activation-compose-20261001-03.json)). Reaching it needed per-binding Photon origins (two sealed address indexes cannot share one fixed Photon), catalog verification off the event loop (r05: 5 × 504 during reloads, [record](../services/api/results/m2-activation-compose-20261001-02.json)) and standby-engine warming in the harness. The production task-rollout part of the M2.5 criterion stays with H-1/M7. M2.6 `prune --dry-run` is implemented; nothing is deleted implicitly. M2.7 endpoints and `/readyz` (with reason codes) are implemented; `/readyz` returned 200 on 50/50 requests after the whole-second engine-time fix. M2.8 is decided from one consecutive pair ([data contracts](data-contracts.md)); later daily snapshots can confirm or reopen it. M2.9 fixtures exist under `services/api/tests/fixtures/gtfs`.

**M2 execution sequence:** fetch/provenance and reviewed parsing/validation can proceed independently; integrate their result contract before building SQLite and the memory-capped MOTIS graph. Then verify the complete manifest/artifact hashes, probe the candidate, expose reference endpoints and prove local activation/rollback. Root integration owns shared CLI, manifest and response contracts; parallel implementation scopes use disjoint modules/tests. Retain `prepare-m1` compatibility until the managed pipeline is verified. Stream stop-times into staging storage rather than materializing the nationwide table in Python. Pattern identity includes ordered stops and pickup/drop-off rules; loop calls retain sequence positions.

**POC-1 applicability:** E02/E04/E05/E07/E08/E09 supply time, translation, pairing, calendar, reference and grouping safeguards. E03's encoding round-trip must be verified through the new SQLite store, without relabelling the historical Postgres result. E01's live HEAD diagnostic and E06's historical 10-day comparison are supporting evidence, not prerequisites for every build; production enforces full-GET change detection and accepted-feed selection. E10 requires an actual cold pipeline run reaching queryable data. Record absent optional observations explicitly; fixture tests and production checks do not constitute a new PoC 10/10 verdict.

**Static pairing contract:** [ADR 0005](../poc/docs/adr/0005-ten-day-gtfs-feed.md) requires complete normalized mapping-key coverage and known, overlapping GTFS/TripIdToDate date windows before loading. Missing keys, absent windows or disjoint windows block the scheduled build. Preserve full trip IDs, active service dates, mapping ranges and weekday flags. Report per-trip/service-date occurrence gaps and ambiguity separately as deferred realtime integration evidence; neither a static pairing pass nor a normalized-key join proves successful live matching. Requiring every scheduled occurrence to have a unique dated mapping would add an unaccepted realtime gate. This distinction does not excuse invalid schedules: chronology regressions still require affected-trip/date diagnostics and a justified, tested resolution before candidate activation; a successful MOTIS import alone supplies no such resolution.

**Immutable identity and fresh checks:** generation identity includes source hashes, engine/config digest, import window and parser/normalization/reference-schema versions. Keep successful upstream check records separate from the immutable build manifest. Unchanged GTFS/mapping bytes renew freshness only after both archives and their pairing are validated; failed or partial checks do not. Coverage remains the graph's measured imported coverage. Reused OSM retains its original provenance and is not labelled newly downloaded.

**Activation seam:** each request captures one immutable runtime snapshot containing generation, reference access and that generation's engine client before any await. Reload replaces the complete snapshot, never just the manifest beside a global engine client. Verify pointer/signal/filesystem mechanics in Linux Compose; do not depend on Windows symlink privileges or signals. Candidate verification precedes pointer replacement; failed reload restores the pointer while old requests retain the old snapshot. M7 proves crash recovery and activation under traffic. Source-ID acceptance still requires two genuinely consecutive daily feeds with retained hashes and comparison counts; a historical feed pair or a comparator unit test cannot satisfy M2.8.

### M3 — complete scheduled routing, departures and trips

| Step | Work | Done when |
| --- | --- | --- |
| M3.1 | Read the pinned image's own OpenAPI for plan, stop-times and trip endpoints; save representative responses as conformance fixtures. | Adapter tests fail if the engine contract drifts |
| M3.2 | Full journey contract: stop references as locations, `arriveBy`, mode selection, 1–5 results, deduplication, ranking-policy metadata. Verify how MOTIS enforces walking limits. If it cannot enforce a per-leg limit, change the contract honestly rather than approximating. | Each advertised constraint has a test |
| M3.3 | Time correctness: service dates, times over 24:00, previous-date services after midnight. Fixtures around the DST change (clocks go back 2026-10-25, inside the fresh feed window). | DST and midnight fixtures pass |
| M3.4 | `GET /v1/stops/{id}/departures` from MOTIS stop-times; drop pickup-prohibited calls; cursor pagination (R2). | No duplicates/skips at equal times |
| M3.5 | `GET /v1/trips/{tripRef}`: ordered calls, restrictions, shape. | Loop trips keep distinct calls |
| M3.6 | Bounds: 1.5 s journey deadline, one concurrency semaphore (16), 16 KiB body limit. | Overload returns 503, not a hang |
| M3.7 | Regenerate the H3 review sheet **through the API** so review covers the product path; the user reviews it (P0-02). | Sheet ready; verdicts recorded by the user only |
| M3.8 | One-command scheduled demo, Dizengoff Center → Technion by coordinates (part of P0-06). | Output shows scheduled labels and disabled realtime |

**Status, 1 October 2026.** M3.1–M3.6 are implemented and tested; walking-cap conformance ran against the real engine (8 cases, 0 violations) and the 1.5 s deadline, 16 KiB body limit and overload bounds have tests. M3.7: the API-path H3 sheet (34 cases, 0 errors, 0 mixed-generation) and a dated [Moovit comparison](../services/api/results/acceptance-oct1b-20261001-02/h3-moovit-comparison.md) exist; **H3 passed 1 October: the user judged 9 of 10 required journeys usable (J11 unsure; [verdicts](../services/api/results/h3-verdicts-20261001-01.json)).** Follow-up: street access from Haifa Center HaShmona station (J11 last mile). M3.8: `opentransit demo` is implemented and recorded (three scheduled-labelled journeys). The J09/J24 "no route" outcomes are corpus-coordinate issues ([diagnosis](../services/api/results/h3-no-route-diagnosis-20261001-01.json)).

### M4 — place search

M4 carries the most uncertainty: addresses scored 4/15 historically. Evidence comes first. M1 disabled MOTIS geocoding; build and verify a new geocoding-enabled generation with consistent reference/graph/provenance before testing POI/address search. Preserve prior results, corpus hashes and human verdicts before accepted-feed reruns. Category/language scores are measured evidence; H4 verdicts remain human decisions.

| Step | Work | Done when |
| --- | --- | --- |
| M4.0 | P0-03: rerun search on the accepted feed, preserving historical results; expand weak corpus cells (addresses, English, POIs). | Per-category/language baseline recorded |
| M4.1 | Stop/station search from the reference file (SQLite FTS5 or an in-process list; measure both). Hebrew normalization: niqqud, geresh/gershayim, punctuation. Include public stop codes and translations; deduplicate by parent station. | Stop category meets the proposed threshold |
| M4.2 | POIs/addresses: MOTIS geocoder first (ADR 0006). If addresses still fail, time-box a self-hosted Photon spike with its memory measured inside the 8 GiB cap, then record D4. | Addresses fixed, or constrained release explicitly approved |
| M4.3 | Merging: category routing, optional `near` bias, `matchedTypes`/`unavailableTypes`/`partial`. | A down category is reported, not silently empty |
| M4.4 | `GET /v1/places`; journeys accept place references. | Search → plan works end to end |
| M4.5 | p95 <40 ms at the API process; H4 sheet prepared for the user. | Latency recorded with provenance |

**Status, 1 October 2026:** M4.0–M4.5 have results and the user approved H4 the same day. Address accuracy (16/22, below the 80% target) and p95 (above 40 ms) are accepted known limits under M4.2's constrained release; the API PRD thresholds are not retroactively met. Revisit after launch.

**M4 evidence summary (condensed 1 October; full prose in Git at `5296819`):**

- *Stop search:* generation-scoped in-memory SQLite FTS5 trigram index with a complete short-token fallback scan ([comparison](../services/api/results/m4-stop-search-benchmark-20260930-04.json)); bounded long-token prefilter preserves rankings ([check](../services/api/results/m4-stop-prefilter-runtime-20260930-01.json)). English stop aliases were discarded by the legacy importer for 32,661 stops ([diagnosis](../services/api/results/m4-legacy-translation-diagnostic-20260930-01.json)); the immutable parser-v2 [repair](../services/api/results/m4-translation-repair-20260930-01.json) and [English search → journey](../services/api/results/m4-english-functional-http-20260930-03.json) pass.
- *Addresses:* MOTIS geocoding alone scored 6/22. A house-only Photon trial worsened original addresses to 3/15; a source-enriched Photon index (125,857 houses + 111,350 streets, 237,207 documents, provider peak ≈429 MB under a 1 GiB cap) reaches 16/22 ([trial](../services/api/results/m4-photon-enriched-trial-20261001-01.json), [six-failure diagnosis](../services/api/results/m4-photon-enriched-diagnosis-20261001-01.json)). The generation-bound Photon adapter/catalog passes [72 focused and 13 real HTTP checks](../services/api/results/m4-photon-bound-api-functional-20261001-01.json), including EN/HE address → journey, honest street precision and stale-ref rejection. Runtime origins support one opt-in candidate; distinct Photon blue/green origins and activation/rollback proof remain.
- *Current measurement* (October 1 acceptance run [`-02`](../services/api/results/acceptance-oct1b-20261001-02/acceptance-oct1b-20261001-02-summary.json), generation `5eb4e43d…`; the earlier Photon-bound API run at 130/183 top-1 is preserved but superseded): 148/183 top-1, 165/183 top-5; stations 20/20, addresses 16/22, misspellings 7/10, translated stops 1/2. API-process p95 42.5 ms across all 732 requests and 46.2 ms first pass (target 40 ms). October 1 search work added rail-station handling, joined spellings, OSM locality ranking, concurrent geocoders, stop search off the event loop and a startup index build plus geocoder warm-up that gates `/readyz` (reason codes `SEARCH_INDEX_*`, `ADDRESS_PROVIDER_*`, `PLACE_PROVIDER_*`).
- *Decision, 1 October 2026:* the user approved H4 on the [October 1 acceptance run](../services/api/results/acceptance-oct1b-20261001-01/acceptance-oct1b-20261001-01-h4-review.md) ("good enough for now"): 148/183 top-1, 165/183 top-5. Addresses 16/22 (below 80%) ship as a documented limitation under M4.2; API p95 42.7 ms all requests / 52.1 ms first pass (target 40 ms; tail is MOTIS Hebrew POI search) is accepted as a known limit. Revisit both after launch.

### Later milestones

| Milestone | Implement | Acceptance emphasis |
| --- | --- | --- |
| M5 (deferred) | Single realtime ingester, immutable snapshots, departures and vehicles | Per-leg truth states, coverage and age; no external request on the user path |
| M6 (deferred) | Alert snapshots and journey association | Unavailable is distinct from no active alerts |
| M7 | Activation under load and fault injection, CI/contract automation, simple rate limiting, load evidence, restore drill | Old-or-new generation consistency, stale degradation, whole stack and replacement headroom under the intended cap |
| M8 | Public deployment, public docs, status page, operational runbook | Real deployed journey with labelled scheduled times; repeated weekday-evening p95 <400 ms per PRD §14 |

The internal journey target remains p95 <350 ms (PRD §4.6); the deployed acceptance target is <400 ms. Specify measurement boundaries separately. M5/M6 are excluded from v1 acceptance. Build the client against the completed schedule-based API.

**Execution sequencing — revised by the user September 30:** prioritize complete functional scheduled journeys, dated trips/departures, then search. M2/M3/M4 work may proceed before non-blocking M2 operational acceptance, but each feature must preserve full trip identity, service dates, UTC/DST semantics, generation consistency and honest unavailable/error behavior. Infrastructure comes first only when it directly blocks the next feature: for departures/trips, finish the source-clock/reference index paired with a queryable generation; for POI/address search, use a correctly identified geocoding-enabled graph. Reuse retained inputs and matching completed audits. Preserve M1 and existing volumes, artifacts and human verdicts.

Work in bounded slices: implement one capability, run focused tests and one meaningful integration check, retain attributable evidence, then proceed. Repeat passing checks only after relevant changes or for unresolved failures. Use smart models for bounded planning, difficult diagnosis and final acceptance; lighter models implement with disjoint file ownership. Escalate after two unsuccessful attempts at the same problem. Root owns shared integration and the dashboard; avoid overlapping investigations and repeated broad plans.

After functional coverage, perform consolidated milestone acceptance, finish refresh/activation/rollback and consecutive-daily ID proof, run fault/load/restore and full-stack capacity checks including replacement overlap, then verify deployment. This is sequencing, not a waiver: M2.1–M2.9, M3.1–M3.8, M4.0–M4.5, M7/M8 and every referenced acceptance criterion remain required. Prepare H3 through the API and H4 with measured category/language evidence; only the user records human verdicts. Resolve required failures before claiming API completion. Deployment preparation may produce images, task definitions, runbooks and the H-0 cost/network proposal locally; paid tests require deployment/spending authorization. H-1's week of unattended refreshes and M8's repeated deployed measurements require actual dated evidence. H3/H4, static terms and static integration remain release gates; the product client follows the completed and deployed API. Realtime and alerts remain deferred.

**M3 implementation decisions from pinned-contract inspection:** use explicit access/egress/direct walking caps mapped to the engine's `maxPreTransitTime`, `maxPostTransitTime` and `maxDirectTime`; reject the earlier proposed per-leg cap and disclose that transfer walking is unbounded. Preserve feasible engine order and deduplicate dated alternatives. **Revised 1 October from live H3 evidence:** an interior stop-to-stop transfer the engine cannot street-route keeps its timetable time with null distance/geometry, `walkingDistanceMeters` null and warning `TRANSFER_STREET_PATH_UNAVAILABLE`; a first/last or direct walk without a street path still omits that alternative with a warning. These are routine technical choices under M3.2, with actual boundary/conformance tests still required. UTC comparisons determine elapsed time and request bounds; Jerusalem conversion is display only. [Actual M1 engine fixtures](../services/api/tests/fixtures/motis-v2.11.2/responses-provenance.json) and the release-tag OpenAPI are distinct evidence, without accepting M2 or H3.

## Continuation execution plan — 1 October 2026

**Adopted by the user 1 October.** Continues the September 30 goal after the Codex session stopped mid-M4. Its uncommitted work is preserved on `backup/codex-m2-m4-20261001` and continues on `feat/scheduled-api-m2-m4`. Its runtime generations, Photon data and Docker volumes stay read-only in the Codex worktree's `.runtime/` (`C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/.runtime`); do not move or delete them. No acceptance criterion above is waived.

**Roles.** A high-reasoning root session (Opus) plans each slice, owns shared contracts, `PROJECT_STATUS.md`, this document and merges, performs hard diagnosis and accepts slices. Sonnet agents implement bounded slices in isolated Git worktrees with disjoint files and return a short report plus one evidence file. Haiku agents do mechanical checks: links, evidence summaries, inventories.

**Rules.**
1. One heavy Docker lane (graph build, MOTIS, Photon, full-corpus runs) at a time, scheduled by root; the host has 15.8 GiB RAM. Unit tests and code run in parallel.
2. Each agent uses its own port range and `ot-<track>-` container prefix, exports logs into evidence before removing its own throwaway containers, and never touches other containers or volumes.
3. Two unsuccessful attempts at the same problem stop the agent; root diagnoses or escalates to the user.
4. One evidence file per accepted slice and one dashboard outcome line; replace superseded prose rather than appending.
5. Agents never edit the dashboard, this plan or existing evidence; root integrates.

| Step | Work | Owner | Done when |
| --- | --- | --- | --- |
| 0 | Adopt snapshot branch; baseline tests; fix test collection and Windows failures; split `api/app.py` into per-area routers; condense docs; start daily feed fetch for M2.8 | Root + Sonnet T0-A/T0-B | Suite green with recorded counts; routers merged; first daily snapshot retained |
| 1 | Parallel tracks: **T1** M3.2 walking-limit conformance, M3.6 deadline/body/overload, M3.8 one-command demo. **T2** M2.5 Linux Compose activation/rollback, M2.6 retention, readiness diagnosis (Opus). **T3** search quality (stations, translated stops, misspellings) then p95 — Opus diagnoses, Sonnet implements, two attempts per cell. **T4** M3.7 H3 sheet through the API; final H4 sheet. **T5** H-0 local preparation: images, task definition with Photon inside the memory budget, IAM/network drafts, no cloud | Sonnet per track; root accepts | Each slice's acceptance row above has evidence |
| 2 | Consolidated M2–M4 acceptance from one fresh generation after the October rebuild (current graph ends October 30; DST October 25); M2.8 from two consecutive daily feeds | Root | Every M2.1–M4.5 row has a result |
| 3 | Bounded H-0 Fargate test as soon as local images are measured, then start the H-1 private preview week | Root; user approval | H-0 evidence; H-1 week running |
| 4 | **During the H-1 week:** M7 (CI after S5, rate limiting, activation under load, fault injection, restore drill, full-stack capacity including Photon under the 8 GiB aggregate cap) and the Phase 2 product client against the private deployment | Sonnet tracks; root accepts | M7 evidence; client usable against preview |
| 5 | M8 public deployment: repeated weekday-evening p95, policies, status page, static terms | Root; user decisions | Static release gate |

**Faster sequence, adopted by the user 1 October:** M7 and the client run during the H-1 week rather than after M8 (PRD gate revision). Public release gates are unchanged.

**Progress, end of 1 October.** Step 0 is done. Step 1: T1 done (walking caps, bounds, demo); T2 done (M2.5 harness 10/10 on 1 October; readiness root cause fixed); T3 done (H4 approved with known limits); T4 done (H3 passed 9/10, user, 1 October); T5 drafts (images, task definition, IAM/network, Photon sizing proposal 1 vCPU / 3 GiB) validated structurally only. Step 2: the consolidated live acceptance ran on the October 1 generation and passed mechanically (runs `-01`, `-02`); M2.5 passed locally on 1 October (`r06`, 10/10); M2.8 over further daily pairs stays open. Next: H-0 image build/measure, then ask the user for H-0 approval (Step 3).

**User inputs:** H3/H4 verdicts after T4; constrained-address decision if T3 exhausts its attempts; code licence and repository visibility before CI; AWS access and bounded H-0 spending approval; static GTFS terms before release; MOT follow-up October 19.

## Hosting plan

**AWS ECS on Fargate selected by the user 30 September 2026; deployment not implemented or verified.** The first private deployment carries its prepared data generation in a private ECR image. S3 is optional. This replaces the September 25 Hetzner/VM proposal; Docker Compose remains the local development path. [ADR 0007 hosting amendment](../poc/docs/adr/0007-schedule-api-design.md#hosting-amendment--accepted-30-september-2026) records the decision. M1 and the static/API-before-client release gates are unchanged.

### Capacity to measure

| Need | Evidence / estimate |
| --- | --- |
| Serving memory | September engine-only peak 941 MB; API, reference/search, startup and replacement remain unmeasured. Test 0.5 vCPU / 2 GiB per task first; increase from evidence. The aggregate 8 GiB ceiling includes old/new serving tasks and serving edge components; it is not an 8 GiB reservation per task. |
| Build memory | Accepted graph build sampled peak 3272.7 MB (historical comparison 3738.6 MB); builds run separately from serving and have their own measured limit. |
| Local task disk | Accepted graph 681.2 MB. Fargate Linux platform 1.4.0+ includes 20 GiB ephemeral storage, shared by image layers and task volumes. Measure pulled/compressed/uncompressed images, reference files and any copied working graph; replacement tasks reconstruct from pinned images. No 160 GB server disk is required. |
| Durable retention | Preserve original sources, manifests, hashes/config, reports and reviewed evidence in a retained operator workspace initially; keep active, previous and evidence-pinned ECR generation images. Task disk is disposable. Select automation's durable archive before unattended cloud builds; S3 may be added then. |
| Latency/region | Deployed p95 <400 ms from Israel. Tel Aviv (`il-central-1`) is a candidate; Fargate supports it. Region is not selected until H-0 verifies source reachability, startup, latency and total cost. |
| Future realtime | Static outbound IP applies to the future SIRI collector, not every API task. MOT provider/geography, IP binding and change procedure remain unresolved. |

### Runtime and generation releases

1. Build and validate a fresh generation outside the serving task using the accepted sources and pinned MOTIS/config. M1's local artifacts and PoC evidence remain separate. Initially an operator can build/publish; scheduled automation follows before unattended preview acceptance.
2. Package the graph, manifest and later reference SQLite into a private ECR generation image, with the pinned MOTIS runtime or a data-initialization container. The latter copies files into a task-local shared volume and must complete successfully before dependent containers start. Choose and verify the filesystem layout at H-0; never mount S3 as the graph filesystem.
3. Run FastAPI and MOTIS in the **same Fargate task**; the API calls MOTIS over localhost. Each task pins one complete generation. Passenger requests never fetch feeds, images, S3 objects or an off-task engine. Expose only the API through HTTPS ingress; MOTIS stays private.
4. Pin runtime and generation image digests in an ECS task-definition revision. Validate hashes, coverage, reference/graph agreement and a routing probe before readiness. Fargate task replacement restores data from the image; there is no persistent host directory or shared `current` symlink in production.
5. A feed refresh publishes a new immutable generation image and deploys a new task revision. Probe the candidate, allow healthy old/new tasks to overlap, route only to ready tasks, then drain old requests before stopping them. Failed candidates leave the old revision serving; configure and test deployment rollback. During rollout different requests may see old or new generation metadata, but a request must never mix them.
6. Roll back to the retained previous task/image revision only after checking its coverage/freshness. Pin evidence images against registry cleanup; do not prune sources or reviewed evidence. M7 proves failure behavior, request draining and aggregate replacement memory. Local M2 activation still uses the pointer/reload design.

This retains local filesystem access for MOTIS without maintaining a VM. Image size/pull time and startup must be measured; Fargate suitability is a selected design, not a passed experiment. No Kubernetes, serving Postgres or S3 dependency is required for the initial deployment.

**S3 remains optional:** use it later if code/data releases need independent cadence or automated builders need a durable artifact/source archive. ECR holds deployable images, not the only copy of source evidence. A bucket-based variant would download and verify a generation at startup, never on passenger requests. The non-code task ID S3 below means human reviews, not an AWS bucket requirement.

**Future SIRI egress:** route only the collector's outbound requests through a public NAT Gateway with one Elastic IP when MOT-approved static egress is required. Multiple gateways/IPs need explicit MOT approval. NAT hourly/data processing and public IPv4 charges are additional to Fargate. A small EC2 collector with its own Elastic IP is a cost alternative requiring a later decision; it does not change the API host. Confirm accepted cloud/geography and IP-change rules with MOT before allocation. Realtime/alerts stay deferred.

### Supporting services

| Purpose | Selected / implementation choice | Constraint |
| --- | --- | --- |
| Container runtime | ECS service on Fargate, initially one steady serving task | Task sizing and rollout overlap verified in H-0/M7; one task is not an HA claim |
| Images and data | Private ECR repositories with digest pins | No public derived-data image; retain rollback/evidence generations; dataset terms remain a release gate |
| HTTPS ingress | Proposed Application Load Balancer + ACM; finalize at H-0 | Include recurring edge cost; only API is targeted; leave request/access logging disabled until its privacy contract is verified |
| DNS/domain | Existing registrar/DNS or Route 53; finalize with ingress | DNS and HTTPS do not supply static outbound SIRI IP |
| Builds/refresh | Operator build first; scheduled builder/publisher before H-1 acceptance | Separate serving/build limits; durable source retention and last-successful upstream validation recorded |
| Secrets/access | IAM task/execution roles; parameter/secret store if needed | No credentials in Git or images; non-root runtimes and read-only artifacts where supported |
| Logs/monitoring | CloudWatch logs with bounded retention; readiness and scheduled synthetic journey probe | Omit coordinates, bodies, query strings and sensitive path values; disclose logging in policies |
| Rate limits | Simple in-app limiter in M7 | Measure actual overload behavior; no journey CDN cache |
| Backup/evidence | Retained operator source/evidence workspace initially | Before automated cloud builds, select durable archive; S3 is an option |
| Deployed performance | Locust/k6 from Israel on weekday evenings | Measure network/TLS separately from API duration and preserve provenance |

### H-0 candidate for local preparation

**Proposal checked 30 September 2026; no region, ingress or expenditure approval inferred.** Prepare `il-central-1`, Linux/X86_64, Fargate platform 1.4.0, task `cpu: 512` / `memory: 2048`, 20 GiB default disk, desired count one, rolling deployment minimum healthy 100% / maximum 200%, and rollback on deployment failure. This allows two 2 GiB tasks during replacement; container allocations must fit the task limit. Do not choose ARM, Spot, autoscaling or larger allocations without image compatibility and load evidence. Fargate supports Tel Aviv and this CPU/RAM combination. [Regions](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate-Regions.html), [task sizing](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html), [rolling deployment](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-ecs.html).

**Photon amendment (proposal, 1 October; unmeasured):** the M4 address provider adds a Photon container (loopback `127.0.0.1:2322`, `-Xms256m -Xmx512m`; provider peak ≈429–448 MB under a 1 GiB cap) that the 0.5 vCPU / 2 GiB candidate cannot hold. [Local drafts](../deploy/aws/README.md) propose 1 vCPU / 3 GiB with limits MOTIS 1280, Photon 768, API 512, init/verifier 192 MiB each: 6 GiB allocated during two-task overlap, about $50.29/month for Fargate (+$23.07 over the 2 GiB baseline). Keep 0.5 vCPU / 2 GiB with addresses disabled as the fallback while D4 is open; a separate Photon service conflicts with the loopback-origin design. The verifier is the API image running `opentransit probe` in-task against `http://127.0.0.1:8080`; API startup depends on verifier SUCCESS plus MOTIS and Photon HEALTHY. Prerequisites: composite-generation probe identity, verifier/readiness freshness alignment and slot-free builds are resolved in code (`build-generation`); measured startup hashing/disk for the ≈3 GB reference file is still needed (the acceptance API took about 9 minutes to become ready on a Windows bind mount; since October 2 the API hashes the reference once, and `ReferenceStore`'s integrity check and content hash dominate the remainder ([measurement](../services/api/results/api-startup-hash-20261002-01.json)); Fargate is unmeasured).

**Filesystem and startup:** prefer a private ECR data-initialization image containing one complete generation, separate pinned API/MOTIS runtime images, and a task-local shared generation volume. The nonessential initializer verifies/copies artifacts and exits successfully; MOTIS depends on its `SUCCESS`. A nonessential verifier then depends on MOTIS `HEALTHY`, checks generation/config/reference/graph hashes and runs the bounded routing probe against the actual localhost engine; API startup depends on verifier `SUCCESS`. Both serving containers are essential. Mount generation data read-only and provide only measured scratch paths; verify MOTIS permissions locally. Pin all three image digests and the verifier's digest, config, source-check provenance and probe identity in the release definition. Startup dependencies only establish startup ordering; ongoing `/readyz` and request rejection must detect expired coverage, stale checks and engine failure. [Dependency semantics](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ContainerDependency.html).

Keep the API's existing non-root user and one Uvicorn worker; set its engine origin to `http://127.0.0.1:8080`, matching MOTIS's task-local listener and probe. Do not publish 8080. Disk accounting includes compressed/uncompressed image layers plus the copied graph/reference files, scratch and Fargate's own reservation; measure cold pull and post-copy high-water use rather than equating the 681 MB historical graph with task disk usage. Disposable storage is reconstructed from pinned images; retain active, previous and evidence-pinned generations in ECR and retain original inputs/reports separately. Avoid an automatic registry lifecycle rule that deletes evidence or rollback digests. [Ephemeral storage](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-storage.html).

**Ingress options:** ALB + a non-exported ACM public certificate is the concrete Tel Aviv candidate. Use two public subnets in distinct availability zones, an IP target group on API port 8000 and HTTPS 443. Private H-0 access allows only the reviewer's IP range at the ALB security group; the task security group accepts 8000 only from the ALB group and no external MOTIS port. For inexpensive image/log egress, the task may occupy a public subnet with an assigned public IPv4 and internet-gateway route while its inbound rules remain restricted. This avoids NAT; it does not provide stable SIRI egress. Private-subnet tasks instead need priced NAT or the required ECR/log/S3 endpoints. [ALB subnets](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/application-load-balancers.html), [Fargate networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html), [ACM pricing](https://aws.amazon.com/certificate-manager/pricing/).

Use `/readyz`, exact HTTP 200, initially 10-second checks, 2-second timeout and two success/failure thresholds; tune the startup grace from cold-start measurements. ALB fails open when all targets are unhealthy, so the API must reject passenger requests when its snapshot is invalid even then. Initially propose a 30-second target deregistration delay, a 25-second API graceful-shutdown limit and 60-second ECS stop timeout; prove draining rather than treating these settings as evidence. [Health checks](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-health-checks.html), [deregistration](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/edit-target-group-attributes.html).

A same-task HTTPS proxy could remove the ALB charge while keeping API/MOTIS on loopback; only proxy port 443 would accept the reviewer's IP range. It needs a trusted certificate, retained certificate state and verified endpoint/DNS replacement, readiness and connection draining. Fargate replacement changes the task endpoint; DNS updates alone do not prove uninterrupted rollout. Keep this a private-test alternative until those obligations pass. HTTP API + VPC Link + Cloud Map offers managed HTTPS without ALB where supported, but AWS's current VPC Link v2 availability table **omits Tel Aviv**. Do not infer support from the existence of Tel Aviv HTTP API pricing. Frankfurt is listed; considering it requires regional latency/cost evidence and a later region choice. Cloud Map must expose only API IP/port, with health registration and discovery/draining proved; its registration/discovery charges and any private DNS zone are extra. [Private integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-private.html), [VPC Link regions](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-vpc-links-v2.html), [Cloud Map pricing](https://aws.amazon.com/cloud-map/pricing/).

**IAM and privacy:** the execution role may pull only the approved private repositories and write only the pre-created log groups; ECR authorization-token permission has its required broader scope. Keep the serving task role absent or without AWS permissions initially; the separate publisher receives limited build/push/deploy permissions. No source credentials are required by passenger serving. Keep Uvicorn and ALB request/access logs disabled: ALB's standard logs contain client IP and full request URL, so post-storage redaction cannot satisfy the no-sensitive-request-logging rule. Ship sanitized application/engine/startup logs with seven-day retention; test coordinate/body/query/path sentinels, including engine logs. Record metrics and synthetic-probe results without passenger payloads. [Execution role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html), [ALB log fields](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-access-logs.html).

### Preliminary monthly estimate

USD on-demand Linux/X86_64, 730 task/ALB hours, one steady task, no credits or commitments, before tax. These are verified Tel Aviv rates, with explicit example usage, not an approved bill. The public regional catalogs were read without an AWS account: ECS/ECR versions `20260911124425`, ELB `20260911124544`, CloudWatch `20260922021715`, API Gateway `20260921231404`.

| Component | Rate and assumption | Estimated monthly USD |
| --- | --- | ---: |
| Fargate CPU + RAM | `730 × (0.5 × 0.0518144 + 2 × 0.0056896)`; default 20 GiB disk included | 27.22 |
| Task public IPv4 | One address × 730 hours × 0.005 | 3.65 |
| ALB runtime | 730 hours × 0.02646 | 19.32 |
| ALB public IPv4 | Two addresses × 730 hours × 0.005; scaled address count can grow | 7.30 |
| ALB capacity | Assumed average 0.1 LCU × 730 hours × 0.0084; measure actual usage | 0.61 |
| Private ECR | Assumed 10 billed GB retained × 0.10/GB-month; measure retained compressed layers | 1.00 |
| CloudWatch logs | Assumed 1 GB/month ingested × 0.50, plus approximately 7/30 GB average retained × 0.03 | 0.51 |
| **Illustrative subtotal** | Existing DNS, without builds/transfer/additional monitoring | **59.61** |

Rate sources: [Tel Aviv Fargate catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/current/il-central-1/index.json), [ELB catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/il-central-1/index.json), [IPv4 pricing](https://aws.amazon.com/vpc/pricing/), [ECR catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECR/current/il-central-1/index.json), [CloudWatch catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/il-central-1/index.json). New Route 53 DNS adds $0.50/zone-month plus applicable queries; ALB alias queries are free. Non-exported ACM public certificates integrated with ALB have no additional certificate charge. [DNS pricing](https://aws.amazon.com/route53/pricing/), [certificate pricing](https://aws.amazon.com/certificate-manager/pricing/).

Ten minutes of daily replacement overlap for 30 days adds five task-hours, about $0.21 CPU/RAM/IPv4, before logs/pulls/transfer. A hypothetical direct HTTPS task has a $30.87 compute/IPv4 base plus proxy load, images, logs, DNS/certificate handling and replacement infrastructure; it is not yet an equivalent release solution. Tel Aviv HTTP API is $1.22 per million requests for the first 300 million, but no working Tel Aviv VPC Link quote/design is established. [HTTP API catalog](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonApiGateway/current/il-central-1/index.json).

Exclude tax/currency conversion, internet and cross-region/AZ transfer, external build compute, domain registration, extra log/query/metric/alarm usage, image scanning, support and optional archives from the subtotal; price them from measured volumes before spending approval. Exact applicable Tel Aviv transfer and builder quotes remain missing. Additional task disk above the included 20 GiB is $0.0001464/GB-hour. A higher CPU/RAM choice, recurring preview or private-subnet egress changes the estimate. No cloud account, resource, deployment or purchase was accessed or created for this proposal.

### H-0 evidence and later authorization

Prepare the pinned images, task-definition/network/IAM drafts and cleanup procedure locally first. At the proposed task limits, record cold-start/pull/copy/probe timing, full-stack CPU/RAM/disk and engine/reference consistency; simulate failed initializer, failed probe, expired check, all-unhealthy ingress, replacement/draining and rollback. Keep the 8 GiB aggregate serving ceiling including overlap/edge. Two proposed serving tasks account for 4 GiB, but AWS does not expose ALB process memory: that edge measurement boundary remains an explicit acceptance gap, not a full-stack pass. A measurable proxy alternative must include its memory. H-1/H-2 still require actual cloud refresh/load/restore evidence.

After the local preparation is reviewable, the essential decisions are: approve a region/ingress and a **bounded private H-0 test** (proposed maximum two simultaneous tasks, two hours, $10 pre-tax spending ceiling, explicit cleanup and retained-image charges); supply the chosen AWS project access, reviewer IP range and controlled DNS name for certificate validation. A spending alert is not a hard cap; the test must stop and remove billable ingress/tasks on schedule. Recurring preview spending and public release require separate approval after their evidence, H3/H4, scheduled integration and static terms are ready. Do not ask for these decisions merely to finish local implementation, and do not treat a private test as release authorization.

### Hosting sequence

| Step | When | Work | Done when |
| --- | --- | --- | --- |
| H-0 | During M2 | Prepare a concrete AWS estimate, region/ingress and task layout; then run a bounded Fargate test with a private ECR generation image. Verify feed reachability for the builder, image pull/startup, local filesystem behavior, readiness, CPU/RAM/disk and latency from Israel. | Recorded evidence selects region/task resources; cost includes ingress/networking; cloud provisioning requires deployment authorization |
| H-1 | After M3 | Private ECS preview: scheduled generation image builds, candidate readiness, task rollout/rollback and uptime probe; retained sources and provenance | A week of unattended refreshes; replaced tasks recover entirely from pinned images |
| H-2 | M7 | Load/soak on Fargate, failed-candidate and draining tests, restore drill from task definitions/ECR/evidence, rate limiting | N01–N03/N05/N06 evidence; aggregate overlap measured under 8 GiB serving ceiling |
| H-3 | M8 | Domain live, policies published, status page, runbook complete | Static release gate |

## Proposed: Open Bus–derived reliability features

**PROPOSAL, 1 October 2026 — not accepted, not scheduled.** Source facts and measurements: [Open Bus research note](research/open-bus.md). Each item keeps its PRD gate: realtime is Phase 3 ([PRD §29](../PRD.md#29-phase-3--realtime-aware-routing)), reliability intelligence Phase 4 ([§30](../PRD.md#30-phase-4--reliability-intelligence)), and any public display also needs data-terms evidence for MOT data obtained through Hasadna's archive (the archive has no stated data licence). OB-01–OB-03 need no live MOT SIRI key, so the user **may** choose to pull them ahead of their phase; that is a user decision and this section changes no gate.

Rules for every item: copy the S3 archive and compute offline — never put product traffic on the Stride API; label all output historical/replay with source dates and coverage; an untracked ride is "not tracked", never "cancelled"; preserve full trip identity and service dates (`DataFrameRef` + `DatedVehicleJourneyRef` against the same day's `TripIdToDate`).

| ID | Work | Gate | Done when |
| --- | --- | --- | --- |
| OB-01 | Monthly offline batch over the S3 SIRI archive (about 10 GB compressed per month): infer stop arrivals per ride, then travel-time and delay distributions per route segment × hour × day type; serve "usually X–Y min late" on legs | Phase 4; terms before public display | Batch reproducible from pinned archive paths and hashes; handles parked pre-departure pings (first moving ping), about 10% duplicate pings, ±30 s precision and coverage gaps, each with tests; per-segment sample size and coverage published beside every figure; a held-out month validates the distributions; output labelled historical |
| OB-02 | Transfer-risk estimate ("this N-min transfer is missed about X% of the time") from OB-01 distributions | Phase 4 (PRD §28 ranking); after OB-01 | Method documented with its independence assumptions; checked against observed connections in a held-out month; low-sample transfers show no figure rather than a guess |
| OB-03 | Reliability badges per line and hour: on-time %, early-departure %, bunching; "often not tracked" where coverage is low | Phase 4; terms before public display | Definitions and thresholds written down (not presented as MOT penalty rules); minimum coverage and sample per badge; badges hidden below threshold; no "cancelled" label anywhere |
| OB-04 | Coarse crowding hint by daypart from data.gov.il `ridership` (quarterly) | Phase 4; dataset licence recorded | `RouteID`/OfficeLineId join to `TripIdToDate` verified with a match count; licence text recorded in the [access record](data-usage-and-access.md); hint labelled with quarter and daypart |
| OB-05 | Longitudinal ID-stability evidence from the archived daily GTFS/TripIdToDate (M2.8 supplementary) | M2 (supplementary only) | Tracked by the `M2.8-ARCHIVE` claim on the dashboard; cannot replace the genuine consecutive-daily M2.8 requirement |
| OB-06 | Develop and measure the SIRI↔GTFS matcher offline against archived SIRI (POC-3 groundwork) | Phase 3 groundwork; H3 passed | Date-aware match rate by operator/mode over thousands of archived observations, with unmatched reasons; labelled replay; POC-3 live proof still requires MOT access |
| OB-07 | "Report this bus" deep link to the government complaint form, as open-bus-backend does | Client feature; privacy review (S4) | Privacy review recorded; link passes no personal data in URL parameters; user confirms before anything is sent |

Also: contact Hasadna (`#open-bus` Slack) about data terms for the archive and stop-level linkage (non-code, S9). Not yet done.

**OB-01 status, 1 October 2026 (user revision: start now; display gates unchanged).** The offline pipeline is implemented in `opentransit.history` (archive parsing, route + origin-time matching, distance-along-route arrival inference with from-rest departures, distributions) and in `services/api/tools/ob01_pilot.py`, with offline tests. The optional `history` dependency group adds `brotli`. The one-day pilot is [`ob01-pilot-20260915-03`](../services/api/results/ob01-pilot-20260915-03.json): 95.2% of scheduled trips observed, 3.87 M stop times inferred, interpolation check median 4 s; findings are in the [research note](research/open-bus.md) (measurement E). Runs `-01` (TripId-prefix matching, 10.6% coverage, wrong) and `-02` (double-counted 1,208 trips) are kept as superseded. Not yet done against the criteria above: a month batch with pinned archive paths and hashes, a held-out validation month, per-figure coverage rules, holiday/season handling and a review of the outlier segments. Distribution tables stay outside Git under `D:/ot/open-bus-archive/ob01/`.

## Non-code workstream

Run these alongside coding. Several are release requirements that no amount of code satisfies.

| ID | Task | When | Done when |
| --- | --- | --- | --- |
| S1 | MOT follow-up (P0-01); also ask about GTFS terms, any IP restrictions and public use of statistics derived from Hasadna's archive of MOT data | October 19 checkpoint | Response or fallback decision recorded |
| S2 | Static data terms (H2): MOT GTFS terms; OSM ODbL attribution ("© OpenStreetMap contributors" in API metadata/docs); no public distribution of derived graph/database files without an ODbL review; Geofabrik download etiquette | Before M8 | Terms evidence in the [access record](data-usage-and-access.md) |
| S3 | Human reviews: H3 after M3.7, H4 after M4.5. Budget a few focused hours each. | M3, M4 | User verdicts recorded |
| S4 | Public policies: privacy notice (what is logged, 7-day retention, IP handling under Israel's Privacy Protection Law), terms of use and schedule disclaimer, API fair-use policy, attribution page. A short professional review is worthwhile; this plan is not legal advice. | Before M8 | Published with the API |
| S5 | Code licence and repository visibility; check dependency licences (MOTIS is MIT; OSM data licensing is separate from code). Public visibility also unlocks free 16 GB CI runners. | Before M7 CI | Decision recorded |
| S6 | Account hygiene: project email; MFA/recovery on AWS, GitHub and selected registrar/DNS; least-privilege deployment access and billing alerts | Before H-0 | Checklist done |
| S7 | `docs/operations.md`: expired feed, failed build, disk full, engine down, rollback, lost host; timed restore drill | M7 | Drill time recorded |
| S8 | Calendar-aware review: holiday timetables, Shabbat no-service cases and the 2026-10-25 DST change in H3 dates and fixtures | M3 | Cases present in the corpus |
| S9 | Optional outreach: Hasadna's open-bus project already collects MOT realtime data and may help the deferred realtime wave or H4 corpus feedback; ask about archive data terms and stop-level linkage ([proposals](#proposed-open-busderived-reliability-features)) | Any time | Not a gate |

## Decisions to make

| Decision | Recommendation / evidence | Needed by |
| --- | --- | --- |
| Primary feed (ADR 0005) | Accepted 60-day + mapping; ingest/routing rerun; H3 passed 1 October | See rerun report |
| MOT request and source fallback | Correct-address email sent September 21; record response, with October 19 checkpoint; choose a sustainable source before adding live features | Deferred POC-3/4 |
| Data usage terms (H2) | Record exact dataset/source terms, attribution, redistribution/fixture constraints and reviewer decision; no legal acceptance inferred from a download | Static release; live terms before deferred features |
| Route/search quality (H3/H4) | H4 approved by the user 1 October with documented limits. H3 passed 1 October (9/10, user); do not promote structural results to quality approval | Static release; H3 before deferred realtime wave |
| API language | ACCEPTED September 25: Python with FastAPI; ADR 0002 amended for production API scope | Pin supported versions and dependencies in M1 |
| Journey HTTP contract and privacy | ACCEPTED September 30: POST JSON for journey planning (D3), superseding the earlier GET proposal; body/location logging remains prohibited | Implemented M1; complete contract in M3/M4 |
| Time and identity | Explicit-offset API times, Asia/Jerusalem service dates, feed-scoped trip IDs, date-aware mapping and generation-consistent snapshots | POC matcher; M2/M3 |
| Walking limits and search ambiguity | Retain labelled 15/30-minute comparisons until reviewed; return candidates for ambiguous branches; location should be optional | H3/H4; M3/M4 |
| Address geocoding | DECIDED 1 October (D4): generation-bound Photon with source enrichment, 16/22, accepted as a known limit | Revisit after launch |
| Realtime semantics and matching threshold | Define fresh/stale/unknown/scheduled/cancelled, per-leg coverage and acceptable match rates by operator/mode before scoring POC-3. Existing 90% warning/70% paging values are operational proposals, not acceptance evidence | POC-3; M5 |
| Hosting and task resources | ACCEPTED September 30: ECS Fargate, private ECR image carrying a fixed generation, S3 optional. Test 0.5 vCPU / 2 GiB; region, ingress, retention automation and cost remain to validate. Preserve the 8 GiB aggregate serving ceiling. See [hosting plan](#hosting-plan) | H-0 in M2; private preview after M3; operational proof M7/M8 |

## Documents we need

Keep the existing PRD, architecture, system design, KDP register and raw evidence. The root dashboard is the current entrypoint. Superseded execution plans and agent briefs were removed from the working tree; Git at `3398826` preserves them.

| Artifact | Contents | When |
| --- | --- | --- |
| ADR 0005 + rerun report | Completed for ingest/routing; extend evidence for search and integration with their own provenance | Alongside new experiments |
| `docs/data-usage-and-access.md` | Terms evidence, attribution/redistribution obligations, H1 state/send date, source sustainability and access requirements; no keys | Static release; extend for deferred sources |
| Completed H3/H4 sheets + schedule-first verdict | Human route/search decisions, scheduled integration and static terms; deferred capabilities remain unproven | Before static release |
| API PRD and system design | Complete review drafts: phased features, stories, contract, UML, implementation structure and acceptance | Review before coding |
| API runtime ADR | ADR 0002 amendment records Python/FastAPI and rationale; add tested runtime/dependency pins during setup | Decision complete; pins in M1 |
| `docs/api/openapi.yaml` | Health endpoints first; staged v1 requests/responses, examples, errors and implemented/planned distinction | Generated docs M1; checked-in compatibility snapshot M7 |
| `docs/data-contracts.md` | Feed generation, identifiers, service-day/time rules, snapshot schema, freshness, ambiguity and alert semantics | Matcher work, finalized before M2/M5 |
| `docs/development.md` | Short maintainer run/request instructions first; expand as needed. Polished contributor onboarding is Phase 5 | Basic notes M1; contributor package later |
| `docs/validation.md` | Functional acceptance, load mix/concurrency, cold/warm runs, error rates, provenance and measurement boundaries | M1 baseline, extended M3–M7 |
| `docs/operations.md` | Feed activation/rollback, readiness, outages, retention, credential rotation and deploy procedure | Before M7/M8 |

`docs/data-contracts.md`, `docs/development.md` and `docs/operations.md` now exist (operations is an unexercised draft); `docs/api/openapi.yaml` and `docs/validation.md` do not. Write each alongside the behavior it specifies; do not create a second speculative architecture document.
