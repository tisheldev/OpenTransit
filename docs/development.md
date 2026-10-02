# Local schedule API development

Maintainer runbook, updated 1 October 2026. The API implements the scheduled contract through M4: `GET /healthz`, `/readyz`, `/v1/status`, reference routes, `POST /v1/journeys`, dated trips and departures, and `GET /v1/places` with place references. Realtime and alerts report `not_enabled`. Command examples are provisional operator interfaces, not a deployment package. Status and acceptance live in [PROJECT_STATUS.md](../PROJECT_STATUS.md); criteria in the [continuation plan](next-steps.md).

Contents: [machine layout](#machine-layout-and-windows-notes) · [command map](#command-map) · [run an API](#run-an-api) · [demo and test client](#demo-and-test-client) · [fetch and build](#fetch-and-build-a-generation) · [probe, select, activate](#probe-select-activate-and-roll-back) · [retention and ID checks](#retention-and-id-checks) · [acceptance tools](#acceptance-tools) · [checks](#edit-and-check-the-api) · [readiness and errors](#readiness-errors-and-logs) · [request examples](#request-examples) · [preserved evidence](#preserved-development-evidence)

## Machine layout and Windows notes

Heavy artifacts are not in Git. On the current developer machine:

- `<repo>/.runtime/` (ignored by Git): the M1 generation `m1-20260930`, fetched source snapshots (`sources/snapshots/<stamp>-<hash>`) and local evidence. Do not delete feeds, graphs or Docker volumes to save space; `prune --dry-run` only reports.
- `D:/ot/` holds the October 1 builds with short paths: `generations/oct1a` (shakedown), `generations/oct1b` (acceptance, about 4 GB), frozen source copies `src-<commit>` and per-commit virtual environments used by the acceptance runner.
- `C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/.runtime` is the **preserved Codex runtime**. Treat it as a read-only data store: it supplies the pinned `photon-1.3.0.jar`, the pyosmium reader (`osm-reader-20260930`), earlier generations and probe corpora. Do not move, edit or delete anything there.

Windows rules: `opentransit fetch` fails early with a clear message when its longest evidence path would exceed `MAX_PATH` (259 characters); choose a short `--output` directory such as `D:/ot/src`. Keep generation and result paths short for the same reason. `.gitattributes` pins LF line endings (and CRLF for a few evidence files whose recorded hashes need it); after changing `core.autocrlf` re-checkout rather than hand-editing, or recorded SHA-256 values stop matching. Linux-only operations (the `current` pointer lock, `SIGUSR1`) run inside the Linux API container, not on the Windows host. Always `uv run --project services/api --locked …` from the repository root; no `PYTHONPATH` is needed.

## Command map

| Command | Purpose | Section |
| --- | --- | --- |
| `opentransit fetch` | Full-GET GTFS, TripIdToDate and OSM into a validated immutable snapshot | [Fetch and build](#fetch-and-build-a-generation) |
| `opentransit validate` | Validate a GTFS/mapping pair; writes a new report | same |
| `opentransit build-generation` | One command for a complete generation (validate, reference, MOTIS, optional Photon addresses, verify) | same |
| `opentransit build` | Single-stage build (graph and reference) with separate controls | same |
| `opentransit prepare-m1` | Preserved M1 isolated-volume build | [Run an API](#run-an-api) |
| `opentransit probe` | Structural journey probe of a running candidate engine | [Probe, select, activate](#probe-select-activate-and-roll-back) |
| `opentransit select-generation` | Select a probed generation as `current` (Linux) | same |
| `opentransit activate` / `rollback` / `await-retirement` | Local activation operator inside the Linux API container | same |
| `opentransit prune --dry-run` | Retention report; never deletes | [Retention](#retention-and-id-checks) |
| `opentransit compare-ids` | Full stop/route/trip ID comparison of two feeds | same |
| `opentransit repair-reference` | Clone a sealed generation with corrected legacy translations (historical repair) | same |
| `opentransit demo` | Dizengoff Center → Technion against a running API | [Demo](#demo-and-test-client) |
| `tools/acceptance_run.py` | Live acceptance of a complete generation | [Acceptance tools](#acceptance-tools) |
| `tools/h3_review.py`, `check_walk_caps.py`, `replay_search.py` | H3 sheet, walking-cap conformance, offline search replay | same |
| `tools/activation_compose_harness.py` | M2.5/M2.6 Compose harness | [Probe, select, activate](#probe-select-activate-and-roll-back) |

## Run an API

**Preserved M1 generation (simplest).** With Docker Desktop's Linux engine running, from the repository root:

```powershell
docker compose --env-file .runtime/m1-20260930/compose.env up -d --build
curl.exe --json "@services/api/examples/journey.json" http://127.0.0.1:8000/v1/journeys
```

Open [interactive API docs](http://127.0.0.1:8000/docs). The example plans Dizengoff Center → Technion at 08:00 Israeli time on October 1; change `departAt` to an explicit-offset time inside the manifest's half-open coverage (the September 30 graph covers `[2026-09-30T00:00:00+03:00, 2026-10-31T00:00:00+02:00)`). Timings are scheduled; predictions, delays and alerts are null. This graph has geocoding disabled, so it cannot serve place search. MOTIS and API bind only to loopback with 3 GiB and 1 GiB limits (import capped at 6 GiB); that and one successful request are not capacity evidence.

**A complete generation with search (current).** The supported way to run a complete generation (MOTIS + sealed Photon + API with probe binding) is the acceptance runner; add `--keep-stack` to leave `ot-acc-<run-id>-*` containers running on a host port in 8500–8599, then `docker rm -f` them yourself. See [Acceptance tools](#acceptance-tools).

**Host-edit workflow** (fast code iteration against a running engine):

```powershell
docker compose --env-file .runtime/m1-20260930/compose.env stop api
docker compose --env-file .runtime/m1-20260930/compose.env up -d motis
$env:OPENTRANSIT_MANIFEST = '.runtime/m1-20260930/manifest.json'
$env:OPENTRANSIT_MOTIS_URL = 'http://127.0.0.1:58081'
$env:OPENTRANSIT_PLAYGROUND = '1'
uv run --project services/api --locked uvicorn opentransit.api.app:create_app --factory --reload --no-access-log
```

**Build a fresh M1-style graph** (legacy path; use a new output directory every time):

```powershell
uv sync --project services/api --locked
uv run --project services/api --locked opentransit prepare-m1 --output .runtime/m1-new
docker compose --env-file .runtime/m1-new/compose.env up -d --build
```

`prepare-m1` refuses existing directories, downloads the accepted 60-day feed plus TripIdToDate and OSM with full GET, records hashes, runs archive/calendar/pairing preflight and imports with the pinned MOTIS v2.11.2 digest into a new named volume. The September 30 run explicitly reused the preserved September 4 OSM snapshot (`--osm-path poc/data/israel-and-palestine-latest.osm.pbf`), recorded in its manifest; omitting the flag downloads current OSM. Each output holds `inputs/`, `config.yml`, `manifest.json`, `import.log` and `compose.env`. Failed builds, volumes and PoC evidence are preserved; `docker compose down` removes only this project's containers and network.

## Demo and test client

With an API running, from the repository root:

```powershell
uv run --project services/api --locked opentransit demo --api-url http://127.0.0.1:8000 --depart-at 2026-10-05T08:00:00+03:00
```

`--depart-at` takes an ISO time with an explicit offset (default: tomorrow 08:00 Israel time, so pick a date inside coverage); `--results` (1–5) and `--lang` are optional. The summary shows generation and coverage, each journey and leg with a `[scheduled]` label and service date, and the realtime/alerts capabilities as reported (`not_enabled`). Exit 0: routes found; 1: successful empty search; 2: connection, HTTP or response error.

The opt-in [journey playground](http://127.0.0.1:8000/playground/) is a manual test harness requested September 30; it is not Phase 2. Enable it with `OPENTRANSIT_PLAYGROUND=1` (Compose does). Keep the Dizengoff → Technion example or enter coordinates/click the map; pick an Israel-time departure inside coverage (during the repeated autumn hour choose +03:00 or +02:00 explicitly); expand **Inspect request and response** to copy exact JSON for a report. A successful response is not H3 approval. The page stores nothing in the browser and talks only to the same API; street tiles load directly from OpenStreetMap, and routes still render if tiles fail. [Verification](../services/api/results/test-client-20260930.json).

The same switch also serves the [API explorer](http://127.0.0.1:8000/playground/explorer.html) (requested October 2), a manual client for every public endpoint: health, readiness and status; place search with type, language and `near`; stops by `near`/`bbox` with pagination and stop detail; departures; routes by stop, operator or line, route detail and patterns; dated trips; journeys with coordinate, stop or place endpoints, depart-at or arrive-by, modes, result count, language and the three walk caps; and a raw request form with invalid-input examples for checking problem responses. Returned IDs are links: a stop opens its detail, departures or routes; a departure or transit leg opens its trip; place results can become a journey's origin or destination. Blank optional fields are omitted, so server defaults apply; browser form validation is off, so out-of-range values reach the API and its 422 is shown. Fixture-generation responses are labelled SYNTHETIC, and the status pill is green only for current, real data. It shows the exact (encoded) request and response and keeps a per-tab history in memory only. Like the playground, it is a test harness: not Phase 2, not H3/H4 evidence.

## Fetch and build a generation

```powershell
uv run --project services/api --locked opentransit fetch --output D:/ot/src
uv run --project services/api --locked opentransit validate --gtfs '<snapshot>/israel-public-transportation.zip' --mapping '<snapshot>/TripIdToDate.zip' --output D:/ot/validation-new.json
```

`<snapshot>` is the canonical snapshot path printed by `fetch`. `fetch` performs full-GET change detection, retains source events and objects, validates the GTFS/mapping pair and creates a snapshot only on success; unchanged bytes renew upstream freshness only after successful paired validation, and revalidating old local inputs cannot renew it. OSM is reused weekly with its original acquisition time. The daily 06:30 fetch on the developer machine adds the consecutive-day pairs needed to re-confirm M2.8. Evidence commands refuse to overwrite existing reports; use new paths.

### One-command complete generation

`opentransit build-generation --snapshot <snapshot> --output <new dir> --first-day D --days N [--addresses --photon-jar <photon-1.3.0.jar>] [--osm-reader-path <dir containing osmium>] [--localities | --no-localities] [--memory-gib 6] [--photon-memory-gib 2]` runs, in order: the OSM context scan (one pyosmium pass for named streets and admin-level-8 localities, written once and reused), paired validation, the reference SQLite with OSM localities, geocoding-enabled MOTIS import and graph export, hashing; with `--addresses` also the Photon house export, source enrichment, address catalog, Photon import (2 GiB cap, no network) and seal (one 1 GiB loopback serving container, write block and flush, then a host copy as the checkpoint), the attestation and an in-place composite manifest (public `generationId` plus `scheduleComponentGenerationId`); then full artifact, config and Photon-tree verification. The output directory must not exist. `pipeline/pipeline.json` records each stage's status and timing (logs in `pipeline/logs/`); a failure keeps everything written, names the failing stage, exits non-zero and touches no input or earlier generation. An address build holds `manifest.json` back until the composite verifies, so an incomplete build is never loadable. Containers and volumes are never removed.

**Measured, October 1 acceptance build `oct1b`** (14 stages, all passed, about 57 minutes, 4.0 GB): OSM context scan 72 s (284 localities, 113,562 streets), validation 335 s, reference 951 s, MOTIS import 41 s plus 6 s export, Photon house export 175 s, enrichment 1,776 s, address catalog 5 s, Photon import 24 s, seal 14 s, attestation and compose 17 s, verify 8 s. The shakedown `oct1a` also completed 14/14 stages. Records are in each generation's `pipeline/pipeline.json` (outside Git).

Localities default to on when `--osm-reader-path` or `--addresses` is given and off otherwise; `--localities` fails before creating output if pyosmium cannot load; `--no-localities` skips them. The choice is recorded in `pipeline.json` and, when on, the locality context hash joins the generation identity (`identity.localityContextSha256`) with provenance in the reference metadata. **Reference schema 3** adds the locality tables. Schema-2 references (every generation built before 1 October) remain loadable read-only, verified by their schema-2 content hash, with feed-derived city ranking only; unknown versions are rejected and reference reuse from schema 2 into a schema-3 candidate is refused.

The generated `config.yml` has no `server:` block (slot-free; the runtime publishes the port, for example `-p 127.0.0.1:59081:8080`) and pins `limits: street_routing_max_prepost_transit_seconds: 1800` and `street_routing_max_direct_seconds: 1800`, the API's 30-minute access/egress/direct maxima (MOTIS defaults are 3600/21600). These are in the config hash and manifest `engineLimits`. The October 1 run confirmed enforcement with `check_walk_caps.py` (8 cases, 0 violations). Do not use the older `build --local-engine-slot` option for a cloud or acceptance generation.

```powershell
$RT  = 'C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/.runtime'   # preserved Codex runtime, read-only use
$GEN = 'D:/ot/generations/<id>'                                       # must not exist
uv run --project services/api --locked opentransit build-generation --snapshot <snapshot> --output $GEN --first-day 2026-10-01 --days 31 --memory-gib 6 --addresses --photon-jar "$RT/m4-photon-spike-20260930/photon-1.3.0.jar" --photon-memory-gib 2 --osm-reader-path "$RT/osm-reader-20260930"
Get-Content "$GEN/pipeline/pipeline.json" | ConvertFrom-Json | Select-Object state, failure   # state must be complete
```

Omit `--addresses` and its options for a schedule-only generation. Check free disk first (about 5 GB plus Docker volume space). Single-stage `opentransit build --inputs <snapshot> --output <new dir> --first-day D --days N [--geocoding]` remains available; it writes the reference SQLite and imports into a new `motis/` directory with the pinned engine and never replaces the active M1 volume.

## Probe, select, activate and roll back

Candidate probe (M2.4): serve the graph slot-free on a loopback port, probe it, then stop it:

```powershell
docker run -d --name ot-<id>-motis --memory 3g -p 127.0.0.1:59081:8080 --mount "type=bind,src=$GEN/motis,dst=/generation/motis,readonly" ghcr.io/motis-project/motis@sha256:6055f51eec43eeed28524037ca0161b96efe9cd05728eaa9ac04c20c2826d330 /motis server -d /generation/motis
uv run --project services/api --locked opentransit probe --generation $GEN --engine-url http://127.0.0.1:59081 --queries <probe-corpus.json>
docker stop ot-<id>-motis
```

The probe corpus needs about ten journeys with `probeTime` inside the generation's coverage; `services/api/tools/acceptance-probe-corpus.json` is the frozen ten-journey corpus and `acceptance_run.py` redates its out-of-window departures to the same weekday and clock. The probe verifies composite generations through the schedule-component ID and records both IDs. It accepts freshness `current`, `aging` or `stale` and rejects `expired`, matching `/readyz` ([freshness rule](data-contracts.md#dates-and-freshness)).

Managed startup verifies all artifact hashes and reference identity. Set `OPENTRANSIT_MANIFEST` to the generation manifest and `OPENTRANSIT_MOTIS_URL` to its engine. `OPENTRANSIT_PROBE` must name a passed probe bound to that generation's artifacts and engine origin before journeys and readiness are enabled; `OPENTRANSIT_SOURCE_CHECK` optionally supplies a successful same-hash paired upstream check. A legacy M1 manifest can still serve journeys but lacks the managed proof needed for `/readyz`.

`opentransit select-generation --generation <dir> --generations-root <root> --engine-origin http://127.0.0.1:<port> [--probe <file>]` selects a probed generation as `current` using the existing binding and atomic-pointer code (Linux only; requires the passed probe).

`opentransit activate|rollback --managed-root R --ack-dir R/acks --binding R/binding-<token>.json` runs inside the Linux API container. A binding may name its generation's own Photon (`photonOrigin` and `photonAdminOrigin`, loopback with explicit ports, both or neither); the worker then verifies and queries that Photon instead of the fixed `OPENTRANSIT_PHOTON_*` origins, which is what lets two separately built address composites switch blue/green. It verifies the binding, re-checks coverage and freshness (`--now` simulates a clock; `--check-only` reports eligibility), swaps the `current` symlink atomically, signals the single worker and waits for its acknowledgement; a rejected or unacknowledged candidate restores the pointer while the worker keeps its old snapshot. `rollback` re-checks the older generation first: it accepts current, aging or stale but refuses expired freshness or coverage before touching the pointer. `opentransit await-retirement` waits for the worker's retirement acknowledgement (at least ten request deadlines after activation); stop the old engine only after it succeeds.

Compose harness (M2.5/M2.6): `uv run --project services/api --locked python services/api/tools/activation_compose_harness.py --run-id <id> --codex-runtime <.runtime dir> [--results-out services/api/results/<new file>.json]` starts `ot-t2-*` containers from `services/api/tools/activation-compose.yaml` (API 1g, two MOTIS 3g, host port 8300), mounts two existing generations read-only, exercises activation under load, failed reload, rollback refusal and success, retirement gating and `prune --dry-run`, exports logs to `.runtime/t2-activation/<id>/` and removes its own containers. It needs no image build or download. Without further options it uses the Codex-era legacy generations. For two complete composites add `--old-generation D:/ot/generations/oct1a --new-generation D:/ot/generations/oct1b --source-check <successful same-hash check> --probe-corpus <in-coverage corpus> --prefix ot-t2b`: the overlay `activation-compose-composite.yaml` then binds each generation's own graph and catalog, starts one Photon per generation (1g, run-private copy of its sealed checkpoint) behind loopback forwarders, and the bindings carry each Photon's origins. Each reload rehashes about 3 GB over the Windows share (10–16 minutes); a full run takes about 1.5 hours. The harness also warms both engines before probing and queries them directly every 15 s, because a reload's hashing otherwise evicts an idle engine and its first request misses the 1.2 s engine timeout. **On 1 October run `r06` (oct1a → oct1b, commit `a319cea`) passed all 10 live checks** ([record](../services/api/results/m2-activation-compose-20261001-03.json)); the earlier attempts are preserved: r03 7/10 ([record](../services/api/results/m2-activation-compose-20261001-01.json)), r04 stopped at a cold-engine probe, r05 8/10 with 504s from catalog verification on the event loop ([record](../services/api/results/m2-activation-compose-20261001-02.json)). Raw logs are in `.runtime/t2-activation/r0N/`.

## Retention and ID checks

`opentransit prune --generations-root <root> --active <id> --previous <id> [--pin <id>] [--draining <id>] --dry-run --output <new file>` reports candidates only and never deletes. Active, previous, evidence-pinned and draining generations must be retained. The only deletion so far was a user-authorized trim of two byte-identical duplicate reference files from failed builds ([record](../services/api/results/storage-trim-20261001-01.json)).

`opentransit compare-ids --previous <feed> --candidate <feed> --previous-date D --candidate-date D --output <new file>` compares full IDs and selected metadata of two feeds. Dates are caller-supplied and unverified by the command; check the underlying source events before calling a pair consecutive-daily evidence. The October 1 decision is in [data contracts](data-contracts.md#identity).

## Acceptance tools

All write new files only and refuse to overwrite.

- **`services/api/tools/acceptance_run.py`** starts one slot-free MOTIS (2 GiB cap), the generation's sealed Photon checkpoint (1 GiB; copied into a run-private volume because its index must be writable) and the API (1 GiB) in one network namespace on a host port in 8500–8599, then runs: the structural probe in a verifier container, API binding, `/readyz` ×50 with MOTIS `VERIFY FAIL` counts, walking-cap conformance, `opentransit demo`, the H3 sheet (`--allow-past`; cases outside coverage are listed as not generated) and the full search corpus with log-correlated API-process timings and the H4 sheet. Containers are `ot-acc-<run-id>-*`; logs are exported and containers removed at the end (`--keep-stack` keeps them; `--attach --steps …` reuses a kept stack). It uses the existing `opentransit-api` image with the current source bind-mounted, so nothing is built or pulled.

  ```powershell
  uv run --project services/api --locked python services/api/tools/acceptance_run.py --generation D:/ot/generations/<id> --run-id <id> --results-prefix services/api/results/acceptance-<id>-<date>-01
  ```

  Outputs are `<prefix>-<name>` files; `<prefix>-summary.json` holds each check's PASS/FAIL/ERROR/SKIPPED, values, generation IDs, image digests, source commit and timings. Exit 0: every check passed; 1: a product check failed; 2: runner/infrastructure error or skipped steps. Passing is mechanical only: neither H3 nor H4 approval. Startup hashes the ≈3 GB reference twice (verifier and API) over the Windows bind mount, so API readiness takes about 9 minutes. Run it from a frozen copy of the source (as `D:/ot/src-<commit>`) so the summary's commit is attributable. [Run `-02`](../services/api/results/acceptance-oct1b-20261001-02/acceptance-oct1b-20261001-02-summary.json) is the current record.
- **`services/api/tools/h3_review.py`** generates the H3 route sheet through `POST /v1/journeys` from `poc/corpora/journeys.json`: concrete Israel-time departures inside coverage, extra Friday, Saturday, holiday, DST-day and repeated-hour cases, raw request/response evidence and a Markdown sheet. It never fills "Usable?" or "Notes"; those are the user's verdicts. `--plan-only --first-day D --last-day D` prints the dates without API calls. The dated Moovit comparison beside run `-02` was produced from that sheet; Moovit plans only about seven days ahead, so later rows need rechecks.
- **`services/api/tools/check_walk_caps.py`** `--api-url <url> --depart-at <ISO with offset> --output <new file>` asks a running API for journeys at several cap values and checks every returned walk against its cap (exit 0: no violation found, 1: violation, 2: error). It is real-engine evidence only when pointed at a real generation.
- **`services/api/tools/replay_search.py`** `--reference <reference.sqlite> --saved-run <evaluate_search result> --output <new file> [--compare NAME=PATH] [--locality-probe]` recomputes stop search in-process against a saved API run, with no HTTP or Docker. It is a projection with stated limits, never a fresh API run or H4 verdict.

## Edit and check the API

```powershell
uv run --project services/api --locked ruff check services/api/src services/api/tests
uv run --project services/api --locked ruff format --check services/api/src services/api/tests
uv run --project services/api --locked pytest services/api/tests -m 'not integration' -q
node --test services/api/tests/playground.test.mjs services/api/tests/explorer.test.mjs
$env:OPENTRANSIT_TEST_URL = 'http://127.0.0.1:8000'
$env:OPENTRANSIT_TEST_DEPART_AT = '2026-10-05T08:00:00+03:00'
uv run --project services/api --locked pytest services/api/tests -m integration -q
```

The focused suite uses labelled synthetic engine responses; `pyproject.toml` sets `pythonpath` and `testpaths`, so no `PYTHONPATH` is needed. At `6ed3f5b` it was 693 passed, 20 skipped, 0 failed. Integration tests are skipped unless `OPENTRANSIT_TEST_URL` is set; their default departure is tomorrow 08:00, so choose a supported service date. Starlette emits a development-only warning about its legacy httpx TestClient fallback; checks pass. For the AWS drafts see [deploy/aws](../deploy/aws/README.md#validate-the-drafts-no-docker-no-network).

## Readiness, errors and logs

`/healthz` is process liveness only. `/readyz` returns 200 only for a complete usable generation and otherwise `503 NOT_READY` with one safe `{condition, reason}` per failing condition: `generation UNAVAILABLE`; `coverage OUTSIDE_COVERAGE`; `freshness SOURCE_CHECK_EXPIRED`; `routing PROBE_UNVERIFIED`; `engine ENGINE_UNAVAILABLE`/`ENGINE_TIMEOUT`; `reference UNAVAILABLE`; `search_index SEARCH_INDEX_BUILDING`/`SEARCH_INDEX_UNAVAILABLE`; `address_search ADDRESS_PROVIDER_WARMING`/`ADDRESS_PROVIDER_UNAVAILABLE`; `place_search PLACE_PROVIDER_WARMING`/`PLACE_PROVIDER_UNAVAILABLE`. The stop index is built and each enabled geocoder warmed (one fixed non-personal query) before a snapshot is published at startup or activation. Expired coverage or an `expired` source check returns `503 FEED_EXPIRED` on schedule requests; `current`, `aging` and `stale` (under 7 days) are served with warnings. A date outside an otherwise usable graph returns 422, an engine failure 503, a timeout 504 and a successful empty search `200 no_route`. A journey whose interior transfer lacks a street path returns that walk with null distance, `walkingDistanceMeters: null` and warning `TRANSFER_STREET_PATH_UNAVAILABLE`.

Logs contain a generated request ID, route template, status and duration. Uvicorn access logs are off; no bodies, coordinates, search text, query strings or rejected values are logged. Errors use sanitized `application/problem+json`. Do not enable HTTP client debug logging with passenger requests. Docker's stale OTel socket recovery is in the [routing runbook](../poc/routing/README.md#three-traps-that-cost-time-so-they-do-not-cost-it-twice); preserve the old runtime directory when renaming it.

## Request examples

Against any API serving a complete generation (replace the port; use `8000` for Compose or the acceptance runner's port). Dates must be inside coverage.

```powershell
curl.exe --json "@services/api/examples/journey.json" http://127.0.0.1:8000/v1/journeys
curl.exe --get --data-urlencode "q=25609" --data-urlencode "type=stop" http://127.0.0.1:8000/v1/places
curl.exe --get --data-urlencode "from=2026-10-05T08:00:00+03:00" --data-urlencode "horizonMinutes=60" --data-urlencode "limit=2" http://127.0.0.1:8000/v1/stops/mot:stop:13583/departures
curl.exe http://127.0.0.1:8000/v1/trips/<tripRef from a journey leg or departure>
```

Follow a departure's cursor with identical query parameters. Search candidates carry `locationRef`; copy it into a journey's `from` or `to`. Stop references keep full source IDs; POI and address selections contain generation-bound coordinates and reject stale references with `422 INVALID_PLACE_REF`. Street-only addresses keep `addressLevel: street`. Trip references are generation-scoped: re-plan rather than reuse one after a new generation. Reference routes are `/v1/stops`, `/v1/stops/{id}`, `/v1/routes`, `/v1/routes/{id}` and `/v1/routes/{id}/patterns`; nearby stops need `near=latitude,longitude` or `bbox=west,south,east,north`, route lists need a stop, operator or line-label filter, and cursors bind query and generation.

## Preserved development evidence

The September 30 – October 1 functional slices ran in Codex-era named containers (`opentransit-api…`, ports 8001/8002 inside a preserved Docker network namespace) from frozen sources under the Codex runtime's `m3-functional-evidence-20260930` and `m4-functional-evidence-20260930`. That is no longer how the API is run; any such containers still on the machine are preserved and not required. Their reports remain the attributable evidence: [runtime report](../services/api/results/m3-m4-functional-api-runtime-20260930-01.json), [22-check HTTP report](../services/api/results/m3-m4-functional-http-20260930-01.json) with [saved-body assertions](../services/api/results/m3-functional-http-body-assertions-20260930-01.json), [English integration](../services/api/results/m4-english-functional-http-20260930-03.json), [prefilter runtime](../services/api/results/m4-stop-prefilter-runtime-20260930-01.json), the [M1 verification](../services/api/results/m1-20260930.json) and [test-client verification](../services/api/results/test-client-20260930.json). Human H3/H4, static terms, operational acceptance and deployment remain open as recorded in the dashboard.
