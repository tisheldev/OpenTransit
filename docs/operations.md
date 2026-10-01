# Scheduled API operations

**Prepared for M7/M8; procedures and restore drill are not yet exercised.** Cloud
resources are drafts. Use [deploy/aws/README.md](../deploy/aws/README.md) for image
staging, dependency ordering, task variants, IAM, ingress and bounded-test cleanup.
See [development](development.md) for local setup and [policies](policies/privacy.md)
for the proposed logging contract. Do not infer deployment/spending authorization.

## Incident checks and evidence

Record UTC onset, symptom, release/task revision, all image digests, public generation
and schedule-component IDs, source-check date, coverage, last healthy synthetic probe,
container exit/OOM reason and sanitized logs in the retained operator evidence archive.
Keep inputs, manifests, hashes, failed attempts and human reviews. Never log passenger
bodies, coordinates, search text, query strings or sensitive path values; routine
sanitized logs retain seven days. Publish an outage/update on the chosen status channel.

Check `/healthz` (process only), `/readyz` (must be exactly 200) and a known synthetic
scheduled journey. Preserve status/error codes and generation metadata. An empty
`200 no_route` is distinct from unavailable data. ALB can send traffic when all targets
are unhealthy: request-side rejection must remain effective. Inspect ECS service events,
stopped-task reasons, init/verifier output, MOTIS/Photon health and resource peaks.
Startup dependencies do not monitor ongoing health.

## Candidate recovery commands

Templates below run from the repository root in an operator-owned workspace, **only
when deliberately performing recovery**. Fetch downloads sources; build invokes Docker.
Use a unique incident stamp in every output path and a currently supported service date;
substitute the actual successful snapshot path. Never overwrite prior attempts.

```sh
uv run --project services/api --locked opentransit fetch --output "$WORK/sources"
uv run --project services/api --locked opentransit validate \
  --gtfs "$SNAPSHOT/israel-public-transportation.zip" \
  --mapping "$SNAPSHOT/TripIdToDate.zip" --output "$WORK/validation-new.json"
uv run --project services/api --locked opentransit build \
  --inputs "$SNAPSHOT" --output "$WORK/candidate-new" \
  --first-day "$FIRST_DAY" --days 31 --memory-gib 6 --geocoding \
  --validation-evidence "$WORK/validation-new.json"
uv run --project services/api --locked opentransit probe \
  --generation "$WORK/candidate-new" --engine-url "$CANDIDATE_ENGINE_URL" \
  --queries "$PROBE_CORPUS" --output "$WORK/probe-new.json"
uv run --project services/api --locked opentransit prune \
  --generations-root "$GENERATIONS" --active "$ACTIVE_ID" --previous "$PREVIOUS_ID" \
  --pin "$EVIDENCE_ID" --draining "$DRAINING_ID" \
  --dry-run --output "$WORK/retention-new.json"
```

`WORK`, `SNAPSHOT`, `FIRST_DAY`, `CANDIDATE_ENGINE_URL`, `PROBE_CORPUS` and retention IDs
must be set explicitly. Probe needs an already-running matching candidate engine and a
retained corpus with dates inside coverage. It is structural evidence, not H3 approval.
Build's 6 GiB import limit is separate from serving capacity. Add any Photon binding via
the existing generation workflow before staging a Photon release; a plain graph does
not contain that index. Fargate staging rejects local slot-port builds: do not pass
`--local-engine-slot` for a cloud generation. `prune` only reports, never deletes.

## Failure actions

| Incident | Contain and diagnose | Recover and verify |
| --- | --- | --- |
| Expired feed | Distinguish coverage expiry from source freshness expiry (seven days without valid upstream paired check). Reject passenger service with `503 FEED_EXPIRED`; do not relabel old data as fresh. | Fetch accepted 60-day GTFS + TripIdToDate, validate, build and probe a new generation; deploy only after matching hashes and coverage pass. A valid successful same-hash paired upstream check may renew source freshness; local revalidation cannot. Rollback helps only if the previous release is still valid. |
| Failed build/refresh | Keep the valid active release serving; retain failed directory/logs and upstream hashes. Diagnose download, paired validation, import, permission or memory failure. | Use new paths for the corrected attempt, run validate/build/probe and stage one complete generation. Never replace active data with partial output. If active data expires meanwhile, use the expired-feed response. |
| Disk full | Stop launching candidates. Measure free space/high-water use and identify the owning workspace/task; preserve evidence before changes. Include compressed/uncompressed layers, copied artifacts, scratch and platform reservation. | Review `prune --dry-run`; protect active, previous, pinned and draining generations. It is not a cleanup command. Select only known disposable owned artifacts for deliberate cleanup; never delete raw feeds, reviews or another workspace's runtime. For Fargate, replace from pinned images; revise storage only from measured need and approved configuration. |
| Engine/provider down | Readiness fails; journeys/timetables must return bounded unavailable/timeout errors rather than empty success or live-looking data. Check essential exits, OOM, health, origins and generation binding. | Replace the entire pinned Fargate task through ECS; require init SUCCESS, engine/provider HEALTHY and verifier SUCCESS before API readiness. Verify a journey, places, departures and trip detail on the same generation. Local recovery uses only the operator's matching engine/API lane. |
| Bad release / rollback | Preserve failed candidate events/probe. Keep the old healthy task until replacement is verified and requests drain; do not swap graph/reference files independently. | Recheck the retained previous generation's coverage, source freshness and hashes. Select its complete task revision/image digest set, roll the ECS service back, wait for readiness and synthetic checks, then drain the failed task. If previous data is expired, build fresh; rollback is not a freshness bypass. |
| Lost Fargate task | Treat task volumes as lost; inspect stopped reason and ECS replacement events. One steady task is not high availability. Avoid launching duplicate manual replacements while ECS reconciles. | ECS restores the approved desired count from pinned ECR images and task definition. If replacement fails, verify digest availability, roles, subnet egress, disk, init/probe and health grace. Recover missing deployment configuration from retained definitions. No host directory or production `current` symlink is a backup. |

For local pointer/reload activation, use the implemented and verified Linux workflow
for the release being operated; this runbook does not invent an `opentransit activate`
or `rollback` subcommand. Cloud recovery uses complete task revisions. Keep API/MOTIS
(and optional Photon) in one task, engine ports private, source credentials out of
serving, and aggregate serving/replacement memory under 8 GiB. ALB memory remains an
explicit measurement boundary; task allocations alone do not prove full-stack capacity.

## Timed restore drill

Run later in an isolated authorized environment, from retained release definitions and
ECR digests, with empty task storage. Never reset production volumes to simulate loss.

1. Record UTC start and monotonic timer when the synthetic probe first detects the
   intentionally lost test task. Record generation, corpus/source hashes, region,
   task limits, desired count and cost/cleanup boundary before the failure.
2. Restore the exact task definition, roles, networking/HTTPS target configuration and
   pinned runtime/data images. Use ECS replacement; time image pull, copy/hash checks,
   provider startup, verifier, first `/readyz` 200 and first successful synthetic journey.
3. Check places, dated departures/trips, scheduled labels, generation consistency and
   absence of sensitive log sentinels. Verify failed-candidate rollback and draining
   separately, retaining both attempts. No passenger payloads belong in the drill packet.
4. End the recovery timer at the first externally verified useful journey; continue
   probes for a declared observation window and record outage duration, failures,
   memory/CPU/disk peaks and any manual steps. Preserve sources/evidence and rollback images;
   remove only this drill's disposable resources using the AWS runbook.

Record **measured restore seconds: pending (not run)**, recovery point/source-check age,
failed attempts and acceptance verdict. The user must choose RTO/RPO and observation
window; do not declare a drill passed against an invented target. An image-only restore
that now fails freshness needs a new paired upstream check/build, not a relaxed verifier.
These procedures support [M7/M8 acceptance](next-steps.md#later-milestones); load evidence
comes from [tools/load](../tools/load/README.md). Release still requires H3/H4, static
terms, integration and actual operational/deployed evidence.
