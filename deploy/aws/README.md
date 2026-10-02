# AWS ECS Fargate H-0 preparation (drafts)

> **NOT DEPLOYED. NO CLOUD RESOURCES. NO SPENDING.** The images were built and the task was run
> locally on 1 October 2026 as a one-core Docker Compose emulation for generation `oct1b`
> ([evidence](../../services/api/results/h0-local-images-20261001-01.json)); nothing was pushed or run in AWS. A passing validator or local run
> is **not** a Fargate result. Region, ingress and spending remain user decisions
> ([approval request](../../PROJECT_STATUS.md#h-0-approval-request), [hosting plan](../../docs/next-steps.md#hosting-plan)).

## What is here

| Path | Purpose | Status |
| --- | --- | --- |
| `data-image/Dockerfile`, `data-image/init_generation.py` | Data-initialization image: one generation (+ Photon index) copied into task-local volumes, hashes verified, exit 0 only on success | Draft; built and run locally (4.08 GB, gzip 0.80 GB) |
| `photon-image/Dockerfile` | Pinned Temurin 21 JRE + pinned Photon 1.3.0 JAR (no index inside) | Draft; built and run locally (0.42 GB) |
| Verifier | **No separate image.** The API image runs `opentransit probe` (same digest as the API) | See "Known gaps" G1/G2 |
| `ecs/task-definition.json` | Recommended draft (proposal): 1 vCPU / 3 GiB, API + MOTIS + Photon + init + verifier | Draft |
| `ecs/variants/` | `1vcpu-4gib` (Photon, larger) and `no-addresses` (0.5 vCPU / 2 GiB, no Photon) | Draft |
| `ecs/service.json`, `ecs/cluster.json` | Rolling 100/200, circuit-breaker rollback, one on-demand task | Draft |
| `alb/` | Target group (`/readyz`, 10 s / 2 s / 2 / 2, 30 s deregistration), HTTPS-only listener, logs off | Draft |
| `iam/` | Execution role (pull four repositories, write one log group) and task role (explicit deny-all) | Draft |
| `network/security-groups.json` | ALB: 443 from reviewer range; task: 8000 from ALB group only | Draft |
| `logs/log-group.json` | `/opentransit/h0`, 7-day retention, pre-created (no auto-create) | Draft |
| `local/compose.yaml` | Generated Compose emulation of the recommended task (shared network namespace, same limits/mounts/ordering) | Draft; run locally (runs 03/04 in the evidence) |
| `tools/render_drafts.py` | Single source for the three task definitions and the Compose emulation | Tested |
| `tools/stage_bundle.py` | Verifies a generation with `verify_artifacts` and stages the image build context | Tested; staged `oct1b` (155 files, 3.95 GB) |
| `tools/validate_drafts.py` | Structural validator (see below) | Tested |

`{{TOKENS}}` are deliberate placeholders; the validator rejects unknown tokens, literal
12-digit account IDs and secret-like text. The MOTIS image digest is the one pinned in
`compose.yaml`.

## Memory and CPU budget (proposal; measured locally on one core)

Evidence: MOTIS engine-only load peak 941 MB (September; the preserved M4 serving trial read
741 MB current / 773 MB peak); Photon provider peak 429-448 MB at `-Xmx512m` under a 1 GiB cap
(index 78 MB on disk, 237,207 documents); API 122-148 MB RSS (its cgroup peak reads at its
512 MiB cap because SQLite page cache counts). **No full-stack, CPU or startup measurement
exists.** Fargate allows 0.5 vCPU with 1-4 GiB and 1 vCPU with 2-8 GiB, in 1 GiB steps.

**Local measurement, 1 October** ([evidence](../../services/api/results/h0-local-images-20261001-01.json); all containers pinned to one core,
cgroup v1 high-water including page cache, after demo, H3 sheet and 732 search requests): MOTIS
819 MiB (64% of 1280; RSS 354), Photon 407 MiB (53% of 768; RSS 353), API 512 MiB (at its cap:
reclaimable SQLite cache, `failcnt` 0; RSS 218), verifier 120 MiB (62% of 192), init 24 MiB. No OOM.
One task serves at about 1.69 GiB high-water (0.90 GiB RSS); two tasks during overlap would be
about 3.4 GiB against 6 GiB allocated. The 0.5 vCPU / 2 GiB variant's 128 MiB verifier would sit at
about 94% and is unmeasured.

Hard container limits (MiB); the sum must stay at or below the task size:

| Container | recommended 1 vCPU / 3 GiB | 1 vCPU / 4 GiB | no addresses 0.5 vCPU / 2 GiB |
| --- | ---: | ---: | ---: |
| motis | 1280 | 1536 | 1280 |
| photon (`-Xms256m -Xmx512m`) | 768 | 1024 | - |
| api | 512 | 768 | 512 |
| init (transient, root) | 192 | 256 | 128 |
| verifier (transient) | 192 | 256 | 128 |
| **sum / task size** | **2944 / 3072** | **3840 / 4096** | **2048 / 2048** |
| unallocated | 128 | 256 | 0 |

### Options against the 8 GiB aggregate ceiling

Rolling 100/200 with one desired task means two tasks overlap during replacement, so the
allocation basis is 2 x task memory. ALB memory is AWS-managed and unmeasurable (accepted gap in
the plan); a task-hosted edge component would have to fit inside the remaining headroom.
Rates are the Tel Aviv on-demand rates in the hosting plan (730 h, Linux/X86_64, 20 GiB disk
included): vCPU 0.0518144 and GB 0.0056896 per hour.

| Option | Task(s) | Overlap allocation | Ceiling headroom | Monthly compute | Delta vs 0.5 vCPU / 2 GiB ($27.22) |
| --- | --- | ---: | ---: | ---: | ---: |
| (a) Photon in task, 1 vCPU / 3 GiB | 1 x 3 GiB | 6.0 GiB | 2.0 GiB | $50.29 | **+$23.07** |
| (a) Photon in task, 1 vCPU / 4 GiB | 1 x 4 GiB | 8.0 GiB | **0 (equals ceiling)** | $54.44 | +$27.22 |
| (a) Photon in task, 0.5 vCPU / 4 GiB | 1 x 4 GiB | 8.0 GiB | 0 | $35.53 | +$8.31 (CPU almost certainly short) |
| (b) Photon as separate service | API task 0.5/2 + Photon task 0.5/1 | 4 + 2 = 6.0 GiB | 2.0 GiB | $27.22 + $23.07 | **+$26.72** with a public IPv4 (+$3.65); an internal ALB would add about $19.93; Cloud Map/Service Connect unpriced |
| (c) Addresses off in first preview | 1 x 2 GiB | 4.0 GiB | 4.0 GiB | $27.22 | $0 |

Replacement overlap, 10 min/day for 30 days (5 task-hours, with task IPv4): (a-3 GiB) $0.37,
(a-4 GiB) $0.40, baseline $0.21. A two-hour, two-task H-0 test costs about $0.30 for compute
plus about $0.07 for an ALB at these rates: far below the proposed $10 ceiling, which ECR,
logs and transfer (all unmeasured) would dominate.

| | (a) Photon in the same task | (b) Separate Photon service | (c) Addresses off |
| --- | --- | --- | --- |
| Code/contract impact | None. API already requires loopback Photon origins and a sealed binding per generation | `config.py` rejects non-loopback Photon origins; N04 says no request dependency leaves the task; needs code and an ADR amendment | None (non-composite generation; `/v1/places` reports `address` as unavailable or falls back to MOTIS geocoding, 6/22) |
| Generation consistency | Task pins one complete generation | Photon index must track the API's generation across rollouts (blue/green Photon) | n/a |
| Startup chain | init, then MOTIS and Photon, then verifier, then API | Two services, discovery, readiness across services | init, MOTIS, verifier, API |
| Operational complexity | Moderate: one more JVM, longer startup, more volumes | High: discovery, two rollouts, cross-service rollback | Lowest |
| Product value | Addresses 16/22 (below the 80% target; D4 open) | Same | Addresses stay at MOTIS quality or off; D4 constrained-release decision |

**Recommendation (a proposal for root and the user, not a decision): option (a) at 1 vCPU /
3 GiB for H-0.** It keeps the accepted one-complete-generation-per-task rule and needs no code
change, leaves 2 GiB of the 8 GiB ceiling during overlap, and costs $23.07/month more than the
original candidate. Treat 3 GiB as the first measured configuration: if any container exceeds
about 85% of its limit, is OOM-killed, or startup/CPU is unacceptable, move to 4 GiB only with a
recorded decision that the ceiling is read on measured usage, because two 4 GiB tasks consume
the whole 8 GiB ceiling by allocation. Keep option (c) as the fallback if Photon cannot meet
startup or CPU limits, or while D4 is unresolved. Option (b) is not recommended.

## Startup chain and design choices

```text
init (root, SUCCESS) -> motis (HEALTHY) -> verifier (SUCCESS) -> api (essential, :8000)
init (SUCCESS) -> photon (HEALTHY) ---------------------------^
```

* `init` verifies each file twice (hash while copying the image layer, then re-reads the
  destination), refuses non-empty volumes, checks the copied manifest ID, rejects a graph built
  for a local-engine slot (`server.port` other than 8080), and checks the Photon tree digest
  against the attestation's sealed checkpoint. It then makes `/generation` read-only (root-owned,
  0444/0555), gives Photon and scratch volumes to uid 10001, and logs one JSON line.
* It runs as root only because Fargate ephemeral volumes are not known to be writable by uid
  10001 (unverified, see U1). Capabilities are limited to CHOWN, DAC_OVERRIDE and FOWNER; every
  other container drops ALL, runs as 10001, and has a read-only root filesystem.
* The verifier is the API image running `opentransit probe` against `http://127.0.0.1:8080`,
  writing `/run/opentransit/probe.json`, which the API reads (`OPENTRANSIT_PROBE`). The probe's
  `engineOrigin` must equal the API's engine URL, which is why the report is produced in the task
  and not baked into the image. The probe corpus (`probe-queries.json`) is staged with the
  generation and its SHA-256 is recorded in the probe report.
* Photon runs the measured command (`-Xms256m -Xmx512m`, listen `127.0.0.1:2322`); its OpenSearch
  admin origin is `127.0.0.1:9201`, the origin the API verifies at startup. The API does not retry a
  failed provider binding, so Photon's `HEALTHY` gate precedes the API.
* The API command adds `--timeout-graceful-shutdown 25`; `stopTimeout` is 60. `--no-access-log`
  stays. Only the API publishes a port (8000). Logs go to `awslogs` (non-blocking); whether MOTIS
  and Photon logs may be shipped is gated on the sentinel test below.

## Known gaps found while drafting (need code or decisions outside deploy/aws)

* **G1 (resolved in code).** `opentransit probe` now verifies a composite address generation: it opens the
  reference DB with the schedule *component* ID (the ID the DB embeds) and records both the public
  `generationId` and `scheduleComponentGenerationId`. `RuntimeSnapshot.load` requires the probe's
  `generationId` to equal the public ID and, for composites, the component ID to match, plus the
  unchanged engine-origin and graph/config/reference hash bindings. Plain generations are unchanged.
* **G2 (resolved in code).** The verifier accepts exactly the source-freshness states `/readyz` serves
  (`current`, `aging`, `stale`; docs/system-design.md section 9) and rejects `expired` (7 days or more,
  or a check dated more than 5 minutes ahead). The state is recorded as `sourceFreshness` in the probe
  report, with a warning when not `current`. A task replaced from a pinned image therefore starts for
  up to 7 days after its source check; after that `/readyz` would reject it too.
* **G3 (slot ports).** Generations built with `--local-engine-slot` bake `server.port` 59081 into
  `motis/config.yml` inside the hashed graph tree. The preserved M3/M4 generations are slot builds;
  the H-0 generation must be slot-free. `opentransit build-generation` writes a slot-free config by
  construction (the October 1 acceptance generation `oct1b` is one); staging it with `stage_bundle` has not been run yet.
  `init` and `stage_bundle` reject slot builds.
* **G4 (startup cost).** The reference database (about 3.0 GB in the preserved generations) is
  hashed by init twice, by the verifier once and by the API once (twice before October 2,
  [measurement](../../services/api/results/api-startup-hash-20261002-01.json)), and `ReferenceStore` runs
  `PRAGMA integrity_check` plus a content hash in both verifier and API. **Measured locally on one
  core (before the October 2 hashing change):** compose up to `/readyz` 200 in 717 s and 658 s (init 15 s, verifier 356-361 s, API lifespan
  274-338 s). One SHA-256 of the reference takes 24.5 s; `integrity_check` takes 212 s and runs twice,
  so it dominates. `healthCheckGracePeriodSeconds` is now 1200 and the API health check tolerates
  600 s (startPeriod 300, the ECS maximum, + 10 x 30 s). Fargate startup remains unmeasured;
  skipping the API's repeat integrity check when the verifier's report binds the same reference
  hash would save about 3.5 minutes (not implemented).
* **G5 (disk).** Measured: unique uncompressed image layers 4.72 GB (data 4.08, Photon 0.42, API
  0.20 sharing the Python base, MOTIS 0.15), task volumes 3.95 GB, writable layers 0: about
  8.1 GiB, or 9.1 GiB if the 1.14 GB of compressed layers stay on disk, of 20 GiB. Fargate's own
  reservation and pull staging remain unmeasured.
* **G6 (fixed from measurement).** `stage_bundle` now stages zero-byte graph files (the manifest
  digest skips them, but MOTIS opens `routed_shapes_*.bin`), and health checks respect ECS limits
  (retries at most 10, startPeriod at most 300 s).

## Unverified assumptions (each is an H-0 check, not a fact)

* U1 Fargate ephemeral volume ownership and modes (hence root `init`); `readonlyRootFilesystem` works
  for MOTIS (needs only `/tmp`?) and Photon.
* U2 **Confirmed locally:** `curl` in the Temurin image, `wget` and `sh` in the MOTIS image; MOTIS
  defaults to uid 100 but runs as 10001 with init-owned scratch.
* U3 **Confirmed locally:** MOTIS reads its listener from `<data dir>/config.yml` and listens on
  `0.0.0.0:8080`, so the task security group is what keeps 8080 private.
* U4 `startTimeout` of 900 s is accepted for dependent containers and `startPeriod` limits are
  honored as written.
* U5 `capabilities.drop: ["ALL"]` and the explicit init drop list are accepted by Fargate.
* U6 MOTIS/Photon logs contain no coordinates, queries or paths. **Local sentinels: 0 hits** in all
  five containers for a unique coordinate and query (the API logs one metrics line per request);
  recheck on Fargate with the shipped log levels.
* U7 Public-subnet task pulling a private ECR image and logging works without NAT; mirror MOTIS
  and Temurin to private ECR with `docker buildx imagetools create` so the digest is preserved.

## Validate the drafts (no Docker, no network)

```sh
uv run --project services/api --locked python deploy/aws/tools/validate_drafts.py
uv run --project services/api --locked python deploy/aws/tools/render_drafts.py   # exit 0 = no drift
uv run --project services/api --locked pytest services/api/tests/test_deploy_aws.py -q
uv run --project services/api --locked ruff check --config services/api/pyproject.toml deploy/aws
uv run --project services/api --locked ruff format --check --config services/api/pyproject.toml deploy/aws
```

The validator checks: valid Fargate CPU/memory pair; container hard limits sum within the task;
overlap allocation within 8 GiB (warns under 1 GiB headroom); exact containers, essential flags and
an acyclic dependency graph with the specified conditions; only API port 8000 published; MOTIS URL
`http://127.0.0.1:8080` and loopback Photon origins; non-root runtimes (init alone is root, with
capabilities limited); read-only root and generation mounts; no secrets, `secrets`, host volumes
or task role; digest-pinned images and the `compose.yaml` MOTIS digest; service rolling/circuit
breaker/Fargate settings; target-group health check; load-balancer logs off; least-privilege IAM;
security-group ports; log group and retention. `tests/test_deploy_aws.py` is in the normal pytest
invocation and also exercises `init_generation.py` and `stage_bundle.py` on synthetic data.

## Local commands (heavy Docker lane; run 1 October, see the evidence)

Own prefix `ot-t5-`, API published on `127.0.0.1:58500`. Never touch other containers or volumes.
Prerequisite: a candidate generation `GEN` that is slot-free (G3) and, for the Photon variant, a
host copy of the **never-served** sealed Photon checkpoint (`PHOTON`). Export a Docker volume
read-only, for example:

```sh
docker run --rm --user 0 -v <checkpoint-volume>:/c:ro -v "$PWD/.runtime/t5-h0/photon:/out" \
  alpine sh -c 'cp -a /c/. /out/'
```

```sh
WORK=.runtime/t5-h0; mkdir -p "$WORK/jar"
cp "$RT/m4-photon-spike-20260930/photon-1.3.0.jar" "$WORK/jar/"   # RT = preserved Codex .runtime, read-only use
# A corpus whose probeTime values fall inside the generation's coverage (the raw
# services/api/tools/acceptance-probe-corpus.json has none and fails J04/J22/J23 on oct1b):
PROBE=services/api/results/acceptance-oct1b-20261001-02/acceptance-oct1b-20261001-02-probe-queries.json
# Stage on the generation's own volume so hard links work. The data-image build sends about 4 GB
# of context into Docker's disk and grew a non-sparse WSL2 disk by about 8 GB.

# 1. Stage (hard links; verifies the generation and the Photon tree first)
uv run --project services/api --locked python deploy/aws/tools/stage_bundle.py \
  --generation "$GEN" --probe-queries "$PROBE" --photon-data "$PHOTON" --output "$WORK/stage"

# 2. Build (record wall time of each)
time docker build -t ot-t5-api:local services/api
time docker build --build-context bundle="$WORK/stage" -t ot-t5-data:local deploy/aws/data-image
time docker build --build-context photon_jar="$WORK/jar" -t ot-t5-photon:local deploy/aws/photon-image

# 3. Sizes: uncompressed, layers, approximate compressed pull size, unpack time
docker image inspect --format '{{.Size}} {{.Id}}' ot-t5-data:local ot-t5-api:local ot-t5-photon:local
docker history --no-trunc --format '{{.Size}}\t{{.CreatedBy}}' ot-t5-data:local | head -20
for i in data api photon; do
  docker save ot-t5-$i:local | gzip -6 > "$WORK/$i.tar.gz"; wc -c "$WORK/$i.tar.gz"
done
docker rmi ot-t5-data:local && time docker load < "$WORK/data.tar.gz"   # unpack time only, not a registry pull

# 4. Assumptions U2/U3 in the pinned images
MOTIS=ghcr.io/motis-project/motis@sha256:6055f51eec43eeed28524037ca0161b96efe9cd05728eaa9ac04c20c2826d330
docker image inspect --format 'user={{.Config.User}} entrypoint={{.Config.Entrypoint}}' $MOTIS
docker run --rm --entrypoint sh $MOTIS -c 'id; command -v wget'
docker run --rm --entrypoint sh ot-t5-photon:local -c 'id; command -v curl'

# 5. Run the task emulation (no AWS)
time docker compose -f deploy/aws/local/compose.yaml up -d
for c in init motis photon verifier api; do
  docker inspect -f '{{.Name}} {{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} start={{.State.StartedAt}} end={{.State.FinishedAt}}' ot-t5-$c
done
docker logs ot-t5-init | tail -3                     # copySeconds, bytes, freeBytesAfter
until curl -fsS http://127.0.0.1:58500/readyz; do sleep 2; done   # time to ready from `up`
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' http://127.0.0.1:58500/readyz

# 6. Memory/CPU/disk after warm-up and a few journeys (peak = high-water mark since start)
for c in motis photon api; do
  echo $c; docker exec ot-t5-$c sh -c 'cat /sys/fs/cgroup/memory.peak 2>/dev/null || cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes'   # cgroup v2 || v1 (Docker Desktop)
done
docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}'
docker run --rm -v ot-t5-h0-recommended_generation:/g:ro alpine du -sm /g
docker system df -v | head -40

# 7. Failure simulations (one at a time, `down -v` between): corrupt a staged file, use a
#    slot-built generation (expect init exit 5), expired generation (expect verifier exit 1),
#    stop motis/photon after ready (expect /readyz 503 and the essential container to exit).

# 8. Log sentinels (U6): send a request with a unique coordinate/query, then
docker logs ot-t5-motis ot-t5-photon ot-t5-api 2>&1 | grep -c '<sentinel>'   # expect 0

# 9. Remove only this lane's resources
docker compose -f deploy/aws/local/compose.yaml down -v
docker rmi ot-t5-data:local ot-t5-api:local ot-t5-photon:local
```

Variants: `render_drafts.py --print-compose no-addresses` (also `1vcpu-4gib`) prints their emulation.
Compose cannot enforce a task-wide CPU quota: 1 vCPU variants pin all containers to one core with
`cpuset`; the 0.5 vCPU variant is uncapped, so its CPU numbers are not comparable.

## Cleanup procedure for a future bounded H-0 test

**Not authorized; none of this has been run or prepared against an account.** It applies only
after the user approves region, ingress, a reviewer IP range, a controlled DNS name and a bounded
test (proposal: at most two simultaneous tasks, two hours, $10 pre-tax ceiling; a spending alert
is not a hard cap). Use a dedicated profile and `--region il-central-1`; set a calendar stop time
before creating anything.

1. Export log streams and task/service events needed as evidence, then record start/stop times.
2. `aws ecs update-service --desired-count 0`, then `aws ecs delete-service --force`, then wait for
   `services-inactive`.
3. Delete the ALB listener, the load balancer (wait for `load-balancers-deleted`), then the target group.
4. Revoke the two security-group cross-references, then delete both groups; confirm no leftover ENIs.
5. Deregister then delete the task-definition revisions; delete the cluster.
6. Delete the `/opentransit/h0` log group after exporting evidence.
7. Delete the ACM certificate (unattached) and any validation DNS record.
8. Detach policies and delete the execution and task roles.
9. ECR: either keep the evidence-pinned and rollback generation images (record the retained size
   and monthly charge) or delete throwaway repositories; never apply an automatic lifecycle rule
   that removes evidence or rollback digests.
10. Verify nothing billable remains: no clusters, services, load balancers, target groups, ENIs,
    public IPv4 addresses or log groups; check Cost Explorer the next day and record the actual
    spend against the ceiling.

## Open questions for the user

The consolidated questions (bounded test, region/ingress, first configuration, ceiling basis,
access, reviewer range and DNS name) are in the dashboard's
[H-0 approval request](../../PROJECT_STATUS.md#h-0-approval-request).
