# Scheduled API operations

**The H-1 private preview runs on AWS (below); the restore drill, load and fault injection
(M7) are not yet exercised.** Other cloud resources are drafts. Use [deploy/aws/README.md](../deploy/aws/README.md) for image
staging, dependency ordering, task variants, IAM, ingress and bounded-test cleanup.
See [development](development.md) for local setup and [policies](policies/privacy.md)
for the proposed logging contract. Do not infer deployment/spending authorization.

## H-1 private preview (eu-north-1, running since 31 October 2026)

One ECS service `opentransit-h1` (cluster of the same name) runs one 1 vCPU / 3 GiB task
behind an internet-facing ALB on **HTTP:80, reachable only from `93.173.37.36/32`** (no domain,
so no HTTPS). Rolling deployments allow one extra task (maximum 200 %, minimum healthy 100 %,
circuit breaker with rollback), so at most 6 GiB is allocated, under the 8 GiB ceiling. Every
resource and measurement is in the [H-1 evidence](../services/api/results/h1-preview-20261031-01.json);
tooling is in [deploy/aws](../deploy/aws/README.md#h-1-private-preview-31-october-2026). Commands
below run from the repository root with the `opentransit` profile (`aws login --profile
opentransit` when it has expired); `H1`, `PUB` and the variables stand for:

```sh
H1="uv run --project services/api --locked python deploy/aws/tools/h1_preview.py"
PUB="uv run --project services/api --locked python deploy/aws/tools/publish_generation.py"
A=$(aws --profile opentransit sts get-caller-identity --query Account --output text)
TARGET="--region eu-north-1 --cluster opentransit-h1 --service opentransit-h1 --profile opentransit"
```

* **Check health.** `curl -s http://<alb>/readyz` (200 or 503 with reason codes) and
  `$H1 probe --label <label> --queries services/api/results/h0-fargate-20261031-01/probe-queries.json`
  (readiness, status, demo, ten journeys, latency; appended to the evidence). `$H1 tasks` lists task
  and container states; ECS service events: `aws --profile opentransit --region eu-north-1 ecs
  describe-services --cluster opentransit-h1 --services opentransit-h1 --query 'services[0].events[:5]'`.
* **Read logs.** Log group `/opentransit/h1` (14 days), one stream per container
  (`api/api/<task>`, `verifier/...`, `init/...`, `motis/...`, `photon/...`): `aws --profile opentransit
  --region eu-north-1 logs tail /opentransit/h1 --since 1h`, or `$H1 export-logs --output <dir>`.
* **Deploy** (normally the daily job does this): `$PUB publish ... --output D:/ot/releases/<stamp>
  --previous-release <serving release-registered.json>` then `$PUB push --plan <dir>/release-plan.json
  --registry $A.dkr.ecr.eu-north-1.amazonaws.com --execution-role-arn
  arn:aws:iam::$A:role/opentransit-h1-execution --vpc-cidr 10.80.0.0/16 $TARGET --execute-aws --wait`.
  A replacement task takes about 12–15 minutes to pass `/readyz`; the old task serves until then.
  Update `D:/ot/releases/current.json` (`release`, `previous`) after a manual deploy.
* **Roll back** to the retained previous revision: `$PUB rollback --current <serving
  release-registered.json> --previous <previous release-registered.json> --execute-aws --wait
  $TARGET`. It refuses expired freshness or coverage (exit 1) and deletes nothing. If a new task
  never becomes healthy the circuit breaker rolls back on its own.
* **Pause to save cost.** `$H1 pause` sets desired count 0 (Fargate and task IPv4 stop; the ALB,
  about $4/week, keeps billing); `$H1 resume` starts one task (about 12 minutes to ready). Disable
  the scheduled task while paused, or the next refresh will wait for a deployment that cannot start.
* **Clean up.** `$H1 --dry-run cleanup` prints the teardown; `$H1 cleanup` deletes the service,
  ALB, target group, every `opentransit-h1` revision, cluster, VPC and its parts, log group and
  execution role, then `$H1 inventory --label after`. ECR repositories and images are kept. Also
  disable the scheduled task `OpenTransit H-1 daily refresh`.

**Daily refresh.** Once registered (`powershell -ExecutionPolicy Bypass -File D:/ot/src-<commit>/deploy/aws/scheduler/register-task.ps1`, which also disables the old fetch-only task; not yet done), Windows Task Scheduler on the operator machine runs
`D:/ot/src-<commit>/deploy/aws/scheduler/daily-refresh.cmd` at 06:30 local (task
`OpenTransit H-1 daily refresh`): fetch → validate → build-generation (only if the
GTFS/TripIdToDate pair changed) → local probe (new builds only) → publish/push → ALB probe →
`prune --dry-run`, stopping at the first failure. Logs: `D:/ot/logs/daily-<UTC stamp>.log` and
`.json`, and `D:/ot/logs/daily-scheduler.log`. An unchanged pair renews freshness without a
rebuild: the new revision carries the day's paired check, which the in-task verifier writes to
`/run/opentransit/source-check.json` and the API applies at startup (`OPENTRANSIT_SOURCE_CHECK`).
The job needs the machine on, Docker Desktop running and a valid `opentransit` login; a failed
day leaves the previous revision serving, and an unchanged generation stays serviceable for
7 days after its last renewal.

**Archive (decision, 31 October 2026).** Generations stay on `D:/ot/` (`generations/`, `src/`,
`releases/`, `logs/`), images in ECR (never deleted automatically), evidence in Git. S3 is deferred.

## Incident checks and evidence

Record UTC onset, symptom, release/task revision, all image digests, public generation
and schedule-component IDs, source-check date, coverage, last healthy synthetic probe,
container exit/OOM reason and sanitized logs in the retained operator evidence archive.
Keep inputs, manifests, hashes, failed attempts and human reviews. Never log passenger
bodies, coordinates, search text, query strings or sensitive path values; routine
sanitized logs retain seven days. Publish an outage/update on the chosen status channel.

Check `/healthz` (process only), `/readyz` (must be exactly 200; a 503 body lists safe
reason codes, see [data contracts](data-contracts.md#readiness)) and a known synthetic
scheduled journey. Preserve status/error codes and generation metadata. An empty
`200 no_route` is distinct from unavailable data. ALB can send traffic when all targets
are unhealthy: request-side rejection must remain effective. Inspect ECS service events,
stopped-task reasons, init/verifier output, MOTIS/Photon health and resource peaks.
Startup dependencies do not monitor ongoing health.

## Rate limiting

**Implemented October 2 (M7 groundwork, October 2 gate revision); not yet load-measured
or approved for publication.** The API keeps in-process token buckets per client and
request class (`opentransit.api.rate_limit`):

| Class | Requests | Default sustained / burst | Settings |
| --- | --- | --- | --- |
| Expensive | `POST /v1/journeys` and `GET /v1/places`, one shared bucket | 30 per minute / 15 | `OPENTRANSIT_RATE_LIMIT_EXPENSIVE_PER_MINUTE`, `_EXPENSIVE_BURST` |
| Standard | Every other path: reference, departures, trips, `/v1/status`, docs, unmatched | 60 per minute / 20 | `OPENTRANSIT_RATE_LIMIT_STANDARD_PER_MINUTE`, `_STANDARD_BURST` |
| Exempt | `/healthz`, `/readyz` (ALB and ECS health checks) | none | — |

The standard values are the [system design](system-design.md)'s starting quota; the
expensive class is the user's October 2 direction and replaces the design's deferred
journey subquota. Classes are independent. An over-limit request is rejected before its
body is read with `429 RATE_LIMITED` (`application/problem+json`, `Retry-After` in whole
seconds, `X-Request-ID`, `Cache-Control: no-store`) and logged as
`route=rate_limit:<class>` without any client address. Planning-capacity saturation stays
`503 SERVER_OVERLOADED`; the two are reported separately. Invalid limit settings stop
startup. `OPENTRANSIT_RATE_LIMIT_ENABLED=0` disables the limiter.

**Client identity.** By default the bucket key is the direct TCP peer and
`X-Forwarded-For` is ignored. Behind the ALB, set `OPENTRANSIT_TRUSTED_PROXIES` to the
comma-separated CIDRs the ALB connects from (the task VPC/subnet ranges, such as
`10.0.0.0/16`); otherwise every passenger shares the ALB node addresses' buckets. The
[H-0 task-definition drafts](../deploy/aws/README.md) set it to the `{{VPC_CIDR}}` token
(substituted at deployment; unresolved, the API refuses to start) with the limiter explicitly
enabled, and the drafts validator rejects a task definition without a CIDR list. Only a
trusted peer's header is read, from the right, skipping trusted hops: the first untrusted
address is the client the ALB saw; client-supplied entries to its left are never used,
and a malformed entry falls back to the nearest valid hop. A catch-all range is
rejected. The task's security group must admit the API port only from the ALB. Keep
Uvicorn's own proxy-header trust at its loopback default (do not set
`FORWARDED_ALLOW_IPS=*`), or clients could choose their own identity. IPv6 clients share
one bucket per /64. Shared carrier NAT puts many passengers behind one IPv4 address, so
tune the limits from aggregate evidence before publishing them in the
[fair-use policy](policies/fair-use.md).

**Store and privacy.** Buckets live in the single API worker's memory, keyed by a
per-process keyed BLAKE2 digest rather than the address. A bucket is dropped once it
would be full again (at most 30 seconds idle at the defaults), the table holds at most
`OPENTRANSIT_RATE_LIMIT_MAX_CLIENTS` buckets (default 10,000; least recently used are
evicted first) and everything is lost on restart. This suits one worker in one task;
during rollout overlap or with several tasks/workers each keeps its own buckets, so the
effective limit multiplies. Add a shared store or edge rule before scaling out.

**Operator measurements.** Load, capacity and acceptance runs from one generator would
measure the quota instead of the stack: run their target with
`OPENTRANSIT_RATE_LIMIT_ENABLED=0` (the acceptance runner and M2.5 activation harness set
it) and test the public 429 path in a separate run with limits on. Never disable the
limiter on public serving. Root `compose.yaml` passes `OPENTRANSIT_RATE_LIMIT_ENABLED`
(default 1) and `OPENTRANSIT_TRUSTED_PROXIES` (default empty) through from the environment, so
its defaults equal the API's and corpus tools such as `evaluate_search.py` pointed at it will
see 429s unless you start it with `OPENTRANSIT_RATE_LIMIT_ENABLED=0`.

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

`opentransit build-generation --snapshot "$SNAPSHOT" --output "$WORK/candidate-new" --first-day "$FIRST_DAY" --days 31 [--addresses --photon-jar ... --osm-reader-path ...]`
replaces the validate and build steps with one complete, verified generation (including
localities and sealed Photon addresses); see [development](development.md#one-command-complete-generation).

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

For local pointer/reload activation, use `opentransit activate`, `rollback` and
`await-retirement` inside the Linux API container ([development](development.md)); their
live Compose acceptance is still open. A complete schedule-plus-address generation is
built in one step with `opentransit build-generation` ([development](development.md)). Cloud recovery uses complete task revisions. Keep API/MOTIS
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
failed attempts and acceptance verdict. With technical choices delegated on 1 October,
use initial drill objectives of useful service restored within **15 minutes**, the
latest successfully validated retained generation with upstream paired-check age
**at most 24 hours**, and **15 minutes** of stable external observation after recovery.
These are test objectives, not an SLA or a change to serving freshness rules; preserve
all source/evidence artifacts. Measure before claiming a pass. The startup verifier
accepts the same freshness states as `/readyz` (current, aging or stale, up to seven days
since validation); an image whose source check has expired needs a new paired upstream
check and build, not a relaxed verifier.
These procedures support [M7/M8 acceptance](next-steps.md#later-milestones); load evidence
comes from [tools/load](../tools/load/README.md). Release still requires H3/H4, static
terms, integration and actual operational/deployed evidence.
