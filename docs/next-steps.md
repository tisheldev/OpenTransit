# From PoC to API implementation

**Execution reference, reconciled 30 September 2026.** Read [PROJECT_STATUS.md](../PROJECT_STATUS.md) for current state, priorities, ownership and session handoff. This document defines implementation scope and acceptance; proposals remain open unless explicitly accepted.

The accepted baseline is the 60-day feed plus TripIdToDate (ADR 0005). Ingest/routing reruns are complete; see [measured results](../poc/docs/primary-feed-rerun.md). Search/H4 and realtime integration still need that baseline. Static mapping-key overlap is not a realtime matching rate.

## The immediate next step: implement M1

The accepted September 25 scope revision in [PRD](../PRD.md#accepted-scope-revision--25-september-2026) permits M1–M4 development while static validation continues. Realtime and live alerts are deferred. This supersedes the original Phase 0-before-M1 sequencing; it does not declare H3/H4 or the full PoC passed. API completion before client development remains required.

1. **Implement M1 with Python/FastAPI after applying the accepted design.** The user authorized R1–R5 and implementation September 30; [ADR 0007](../poc/docs/adr/0007-schedule-api-design.md) records this. [API PRD](api-prd.md) and [system design](system-design.md) now incorporate the changes. The user selected Python on September 25; [ADR 0002](../poc/docs/adr/0002-python-for-the-poc.md) records the production scope. No MOT credential or completed live-data proof is required.
2. **Continue static quality work alongside M1–M4.** Preserve historical evidence, rerun search on the accepted 60-day feed plus TripIdToDate, and complete H3/H4. H3 still requires at least 9/10 usable representative routes, including service-day boundaries, transfers and no-route cases. Resolve or explicitly constrain search failures before release.
3. **Demonstrate scheduled integration before release.** One command resolves Dizengoff Center → Technion with scheduled times, walking, transfers and geometry. Explicitly report realtime and alerts as unavailable. Record a schedule-first verdict separately from the original ten-capability report; do not mark deferred capabilities PASS.
4. **Complete static release requirements through M7/M8.** Record acceptable usage terms for included datasets, freshness and rollover behavior, error handling, rollback, full-stack capacity under the intended 8 GiB serving cap, and deployed performance.
5. **Add realtime and alerts later.** Retain POC-3/4 and M5/6 as deferred work. Before shipping them, prove sustainable source access, acceptable terms, date-aware matching over thousands of observations by operator/mode, freshness and actual alerts-feed integration. Synthetic/replay evidence remains labelled and cannot establish live feasibility. H3 still precedes this wave.

The MOT request was sent September 21 per user confirmation; response is pending and October 19 remains the follow-up checkpoint. This is no longer a v1 development blocker. Static usage terms remain unresolved separately; see the [access record](data-usage-and-access.md).

## M1–M4 delivery plan

**Accepted for implementation 30 September 2026.** This plan incorporates R1–R5 in [system design §0](system-design.md#0-review-proposals--simplifications) and the AWS Fargate hosting amendment in [ADR 0007](../poc/docs/adr/0007-schedule-api-design.md#hosting-amendment--accepted-30-september-2026). M1 stays local; no cloud purchase is needed for it. Effort figures are rough estimates in focused working days for one developer. They are not dates or commitments. Each milestone ends the same way: record a demo command in `docs/development.md`, pass the focused tests, and update the dashboard.

| Milestone | Outcome you can demonstrate | Rough effort | Needs first | Non-code work alongside |
| --- | --- | --- | --- | --- |
| M1 | `POST /v1/journeys` returns a real scheduled itinerary from a fresh local graph | 3–5 days | September 30 authorization; fresh graph | S2 static terms |
| M2 | One command builds, validates and activates a feed generation; stop/route/pattern/status endpoints | 10–15 days | M1 | Hosting spike H-0, S2 terms, S5 licence |
| M3 | Complete scheduled routing, departures and dated trips; H3 sheet regenerated through the API | 10–15 days | M2 | S3 H3 review, preview host H-1 |
| M4 | Hebrew/English place search feeding journey planning; H4 evidence | 10–20 days (address risk) | M3; P0-03 rerun | S3 H4 review, S4 policies |

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
| M2.1 | `fetch`: GTFS, TripIdToDate and the Geofabrik OSM extract into `inputs/<date>/` with SHA-256 and acquisition time. Skip unchanged content; a successful unchanged check still renews freshness. OSM weekly is enough. | Re-running is idempotent |
| M2.2 | `validate`: extract the ten POC-1 integrity checks as reviewed functions (no script imports). Check pairing/service-window overlap and compute actual coverage. Failure exits nonzero and leaves the active generation untouched. | A corrupted fixture is rejected |
| M2.3 | `build`: memory-capped MOTIS import into `generations/<id>/motis`. Build the reference file `generations/<id>/reference.sqlite` (R4): stops, parent stations, routes, agencies, translations, route–stop links and patterns (ordered stops plus pickup/drop-off rules). Write `manifest.json`. | Build reproducible from recorded inputs |
| M2.4 | `probe`: start the idle blue/green MOTIS on the candidate; run about ten fixed journeys from the H3 corpus; compare stop/route counts with the active generation (a large drop blocks activation). | Bad candidate blocked with a clear report |
| M2.5 | Local `activate`/`rollback`: atomic `current` symlink rename, API reload signal, old engine stopped after a fixed grace period. Rollback re-checks coverage first. Production packages a fixed generation into an image and replaces whole ECS tasks; see hosting plan. | In-flight request completes on old data; next uses new locally; production task rollout verified at H-1/M7 |
| M2.6 | Retention: keep the active generation, the previous one and evidence-pinned ones; `prune --dry-run` lists candidates; deletion is manual. | Nothing deleted implicitly |
| M2.7 | Endpoints: `/v1/stops` (near or bbox), `/v1/stops/{id}`, `/v1/routes`, `/v1/routes/{id}`, `/v1/routes/{id}/patterns`, `/v1/status`, `/readyz`. | Loop and parent-station fixtures pass |
| M2.8 | ID-stability check (R2): compare `stop_id`/`route_id`/`trip_id` across two consecutive daily feeds; choose the public ID scheme from that evidence; write `docs/data-contracts.md`. | Decision recorded with counts |
| M2.9 | A small hand-written synthetic GTFS fixture (about ten stops, a loop, an after-midnight trip) for build/validate tests. | Tests run without downloads |

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

### M4 — place search

M4 carries the most uncertainty: addresses scored 4/15 historically. Evidence comes first.

| Step | Work | Done when |
| --- | --- | --- |
| M4.0 | P0-03: rerun search on the accepted feed, preserving historical results; expand weak corpus cells (addresses, English, POIs). | Per-category/language baseline recorded |
| M4.1 | Stop/station search from the reference file (SQLite FTS5 or an in-process list; measure both). Hebrew normalization: niqqud, geresh/gershayim, punctuation. Include public stop codes and translations; deduplicate by parent station. | Stop category meets the proposed threshold |
| M4.2 | POIs/addresses: MOTIS geocoder first (ADR 0006). If addresses still fail, time-box a self-hosted Photon spike with its memory measured inside the 8 GiB cap, then record D4. | Addresses fixed, or constrained release explicitly approved |
| M4.3 | Merging: category routing, optional `near` bias, `matchedTypes`/`unavailableTypes`/`partial`. | A down category is reported, not silently empty |
| M4.4 | `GET /v1/places`; journeys accept place references. | Search → plan works end to end |
| M4.5 | p95 <40 ms at the API process; H4 sheet prepared for the user. | Latency recorded with provenance |

### Later milestones

| Milestone | Implement | Acceptance emphasis |
| --- | --- | --- |
| M5 (deferred) | Single realtime ingester, immutable snapshots, departures and vehicles | Per-leg truth states, coverage and age; no external request on the user path |
| M6 (deferred) | Alert snapshots and journey association | Unavailable is distinct from no active alerts |
| M7 | Activation under load and fault injection, CI/contract automation, simple rate limiting, load evidence, restore drill | Old-or-new generation consistency, stale degradation, whole stack and replacement headroom under the intended cap |
| M8 | Public deployment, public docs, status page, operational runbook | Real deployed journey with labelled scheduled times; repeated weekday-evening p95 <400 ms per PRD §14 |

The internal journey target remains p95 <350 ms (PRD §4.6); the deployed acceptance target is <400 ms. Specify measurement boundaries separately. M5/M6 are excluded from v1 acceptance. Build the client against the completed schedule-based API.

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
| HTTPS ingress | Proposed Application Load Balancer + ACM; finalize at H-0 | Include recurring edge cost; only API target is public; suppress sensitive access-log fields |
| DNS/domain | Existing registrar/DNS or Route 53; finalize with ingress | DNS and HTTPS do not supply static outbound SIRI IP |
| Builds/refresh | Operator build first; scheduled builder/publisher before H-1 acceptance | Separate serving/build limits; durable source retention and last-successful upstream validation recorded |
| Secrets/access | IAM task/execution roles; parameter/secret store if needed | No credentials in Git or images; non-root runtimes and read-only artifacts where supported |
| Logs/monitoring | CloudWatch logs with bounded retention; readiness and scheduled synthetic journey probe | Omit coordinates, bodies, query strings and sensitive path values; disclose logging in policies |
| Rate limits | Simple in-app limiter in M7 | Measure actual overload behavior; no journey CDN cache |
| Backup/evidence | Retained operator source/evidence workspace initially | Before automated cloud builds, select durable archive; S3 is an option |
| Deployed performance | Locust/k6 from Israel on weekday evenings | Measure network/TLS separately from API duration and preserve provenance |

**Cost is not yet established.** Estimate the selected region's Fargate CPU/RAM runtime, transient deployment overlap, ECR storage, ingress, public IPv4, logs, builds and transfer; add NAT only for required egress. A cheap compute-only quote is not the monthly bill. No account, task, load balancer, NAT Gateway or purchase was created by this decision.

AWS references checked September 30: [task storage](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-storage.html), [task networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-networking-awsvpc.html), [task replacement](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-type-ecs.html), [supported regions](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate-Regions.html), [Fargate pricing](https://aws.amazon.com/fargate/pricing/) and [network pricing](https://aws.amazon.com/vpc/pricing/).

### Hosting sequence

| Step | When | Work | Done when |
| --- | --- | --- | --- |
| H-0 | During M2 | Prepare a concrete AWS estimate, region/ingress and task layout; then run a bounded Fargate test with a private ECR generation image. Verify feed reachability for the builder, image pull/startup, local filesystem behavior, readiness, CPU/RAM/disk and latency from Israel. | Recorded evidence selects region/task resources; cost includes ingress/networking; cloud provisioning requires deployment authorization |
| H-1 | After M3 | Private ECS preview: scheduled generation image builds, candidate readiness, task rollout/rollback and uptime probe; retained sources and provenance | A week of unattended refreshes; replaced tasks recover entirely from pinned images |
| H-2 | M7 | Load/soak on Fargate, failed-candidate and draining tests, restore drill from task definitions/ECR/evidence, rate limiting | N01–N03/N05/N06 evidence; aggregate overlap measured under 8 GiB serving ceiling |
| H-3 | M8 | Domain live, policies published, status page, runbook complete | Static release gate |

## Non-code workstream

Run these alongside coding. Several are release requirements that no amount of code satisfies.

| ID | Task | When | Done when |
| --- | --- | --- | --- |
| S1 | MOT follow-up (P0-01); also ask about GTFS terms and any IP restrictions | October 19 checkpoint | Response or fallback decision recorded |
| S2 | Static data terms (H2): MOT GTFS terms; OSM ODbL attribution ("© OpenStreetMap contributors" in API metadata/docs); no public distribution of derived graph/database files without an ODbL review; Geofabrik download etiquette | Before M8 | Terms evidence in the [access record](data-usage-and-access.md) |
| S3 | Human reviews: H3 after M3.7, H4 after M4.5. Budget a few focused hours each. | M3, M4 | User verdicts recorded |
| S4 | Public policies: privacy notice (what is logged, 7-day retention, IP handling under Israel's Privacy Protection Law), terms of use and schedule disclaimer, API fair-use policy, attribution page. A short professional review is worthwhile; this plan is not legal advice. | Before M8 | Published with the API |
| S5 | Code licence and repository visibility; check dependency licences (MOTIS is MIT; OSM data licensing is separate from code). Public visibility also unlocks free 16 GB CI runners. | Before M7 CI | Decision recorded |
| S6 | Account hygiene: project email; MFA/recovery on AWS, GitHub and selected registrar/DNS; least-privilege deployment access and billing alerts | Before H-0 | Checklist done |
| S7 | `docs/operations.md`: expired feed, failed build, disk full, engine down, rollback, lost host; timed restore drill | M7 | Drill time recorded |
| S8 | Calendar-aware review: holiday timetables, Shabbat no-service cases and the 2026-10-25 DST change in H3 dates and fixtures | M3 | Cases present in the corpus |
| S9 | Optional outreach: Hasadna's open-bus project already collects MOT realtime data and may help the deferred realtime wave or H4 corpus feedback | Any time | Not a gate |

## Decisions to make

| Decision | Recommendation / evidence | Needed by |
| --- | --- | --- |
| Primary feed (ADR 0005) | Accepted 60-day + mapping; ingest/routing rerun; H3 quality pending | See rerun report |
| MOT request and source fallback | Correct-address email sent September 21; record response, with October 19 checkpoint; choose a sustainable source before adding live features | Deferred POC-3/4 |
| Data usage terms (H2) | Record exact dataset/source terms, attribution, redistribution/fixture constraints and reviewer decision; no legal acceptance inferred from a download | Static release; live terms before deferred features |
| Route/search quality (H3/H4) | Complete review sheets; do not promote structural results to quality approval | Static release; H3 before deferred realtime wave |
| API language | ACCEPTED September 25: Python with FastAPI; ADR 0002 amended for production API scope | Pin supported versions and dependencies in M1 |
| Journey HTTP contract and privacy | API PRD/design draft recommends POST for precise origin/destination data, superseding the earlier GET proposal; D3 still needs review before publishing the contract | M1 contract design |
| Time and identity | Explicit-offset API times, Asia/Jerusalem service dates, feed-scoped trip IDs, date-aware mapping and generation-consistent snapshots | POC matcher; M2/M3 |
| Walking limits and search ambiguity | Retain labelled 15/30-minute comparisons until reviewed; return candidates for ambiguous branches; location should be optional | H3/H4; M3/M4 |
| Address geocoding | Benchmark a same-host alternative/normalization approach on failed categories; Photon is a candidate, not a proven fix | Before M4 |
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

These are planned deliverables, not claims that those files already exist. Write each alongside the behavior it specifies; do not create a second speculative architecture document.
