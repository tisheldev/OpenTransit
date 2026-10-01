# Local schedule API development

The verified M1 generation implements `GET /healthz` and `POST /v1/journeys`, plus FastAPI's `/docs` and `/openapi.json`. Its recorded baseline uses coordinates and explicit-offset `departAt`. The current worktree adds reference/status/readiness endpoints, journey alternatives and constraints, dated trips/departures, and stop/POI/address search with place references. [Matching-generation HTTP evidence](../services/api/results/m3-m4-functional-http-20260930-01.json) verifies the functional path. Legacy English stop-translation repair, quality/latency acceptance, managed activation and deployment remain incomplete. This is a provisional local contract.

## Start the verified M1 generation

Run from the repository root with Docker Desktop's Linux engine running:

```powershell
docker compose --env-file .runtime/m1-20260930/compose.env up -d --build
curl.exe --json "@services/api/examples/journey.json" http://127.0.0.1:8000/v1/journeys
```

Open [interactive API docs](http://127.0.0.1:8000/docs). The example plans Dizengoff Center → Technion on October 1 at 08:00 Israeli time. Change `departAt` to a desired explicit-offset time inside the manifest's half-open coverage. The September 30 graph covers `[2026-09-30T00:00:00+03:00, 2026-10-31T00:00:00+02:00)`; it includes the October DST offset change, but comprehensive DST correctness is an M3 check. Timings are scheduled; predictions/delays and alerts are null, with both live capabilities `not_enabled`.

## Try the local test client

Open the [journey playground](http://127.0.0.1:8000/playground/) after starting Compose above. This small browser harness was requested September 30 for manual M1 testing; it is not Phase 2 product acceptance.

1. Keep the Dizengoff Center → Technion example or select other example places. For arbitrary locations, enter coordinates or press **Choose origin/destination on map**, then click the map. Example coordinates identify approximate station/campus points, not an entrance guarantee.
2. Pick a departure in **Israel time**, within the graph's coverage. The default is tomorrow at 08:00. **Automatic** applies the date's Israel UTC offset; during the repeated autumn hour choose +03:00 or +02:00 explicitly. Nonexistent spring times and mismatched offsets are rejected before sending.
3. Press **Plan journey**. Check walking distances, stop names, lines, scheduled times, waits and transfers against what you expected. Walking is dashed gray, bus blue and rail purple. Click route lines to identify legs.
4. Expand **Inspect request and response** to copy the exact JSON for a reproducible report. Record the generation/request IDs, chosen date, unexpected leg and expected behavior. A successful response is not H3 human approval.

The page shows data freshness and distinguishes no-route from unavailable/expired data or engine errors. It clears the previous itinerary when inputs change. It stores nothing in the browser and sends journey requests only to the same local API. Map scripts/styles are bundled; street tiles come directly from OpenStreetMap in the browser. If tile access fails, the form, itinerary and route lines still work. Search, live delays, alerts, preferences and multiple alternatives remain later work.

Compose enables this page with `OPENTRANSIT_PLAYGROUND=1`; it is disabled by default when the API is started otherwise. For the host-edit workflow below, also set `$env:OPENTRANSIT_PLAYGROUND = '1'`. No additional frontend server or npm install is needed.

September 30 checks: 29 focused API checks, five client date/time checks and one real HTTP integration check passed. Browser verification covered the real seven-leg journey, map selection, swapping, input changes, copying JSON, an empty result, out-of-coverage errors and ambiguous departure times. The narrow in-app viewport showed no horizontal overflow; a desktop viewport and human route quality remain unverified. Details: [test-client verification](../services/api/results/test-client-20260930.json).

`/healthz` checks only process liveness. A missing/unready manifest returns `503 DATA_UNAVAILABLE`; expired coverage or seven days without source validation returns `503 FEED_EXPIRED`. A requested date outside an otherwise usable graph returns 422. An engine failure is 503, a timeout 504, and a successful empty search is `200 no_route`. A still-covered aging feed has explicit freshness/warnings. M1 does not refresh automatically; build a new generation when necessary.

MOTIS/API ports bind only to loopback. Their configured memory limits are 3 GiB and 1 GiB, respectively; the import process is separately capped at 6 GiB. These limits and one successful request are not full-stack capacity or replacement-load evidence. M7 measures that under the aggregate 8 GiB serving ceiling. Local Compose is not the selected Fargate deployment package.

## Build a fresh graph

Install uv and use the pinned Python/dependencies. From the root:

```powershell
uv sync --project services/api --locked
uv run --project services/api --locked opentransit prepare-m1 --output .runtime/m1-new
docker compose --env-file .runtime/m1-new/compose.env up -d --build
```

Use a new output directory every time. The command refuses existing directories, downloads the accepted 60-day feed plus TripIdToDate and OSM with full GET, records hashes/acquisition time and performs archive, calendar and static pairing preflight. It imports with the pinned MOTIS v2.11.2 digest into a newly named volume. Full integrity checks and date-aware matching are separate later work; join-key overlap is not realtime evidence. Geocoding is disabled in this M1 graph; M4 needs a search-enabled generation.

The verified September 30 run explicitly reused the preserved September 4 OSM snapshot via `--osm-path poc/data/israel-and-palestine-latest.osm.pbf`. That reuse is recorded in its manifest and is not a fresh OSM download. Omitting the flag downloads current OSM.

Each directory contains `inputs/`, `config.yml`, `manifest.json`, `import.log` and `compose.env`. Failed/old builds, builder containers, feeds, volumes and PoC evidence are preserved. There is no automatic pruning or volume reset. `docker compose down` stops/removes this project's serving containers and network, preserving the external graph volume; do not use destructive cleanup commands against the PoC.

## M2 managed generations under development

The managed CLI preserves M1's `prepare-m1` workflow. Run its stages separately so every failed validation or build remains attributable. Use new report/output paths; evidence commands refuse overwriting reports. Example commands from the repository root:

```powershell
uv run --project services/api --locked opentransit fetch --output .runtime/sources
uv run --project services/api --locked opentransit validate --gtfs '.runtime/sources/snapshots/<snapshot>/israel-public-transportation.zip' --mapping '.runtime/sources/snapshots/<snapshot>/TripIdToDate.zip' --output .runtime/validation-new.json
uv run --project services/api --locked opentransit build --inputs '.runtime/sources/snapshots/<snapshot>' --output .runtime/generations/candidate-new --first-day 2026-09-30 --days 31 --memory-gib 6
```

Replace `<snapshot>` with the successful snapshot path printed by `fetch`, and select the intended current service date. `fetch` performs full GET change detection, retains source events/objects, validates the complete GTFS/mapping pair and creates a canonical snapshot only on success. Unchanged bytes can renew upstream freshness only after successful paired validation. Revalidating old local inputs cannot renew it. Weekly OSM reuse preserves its original acquisition time.

`build` refuses an existing output directory. It writes the reference SQLite file and imports into a new `motis/` directory using the pinned engine; it never replaces the active M1 volume. The Docker import limit is separate from whole-build and serving memory evidence. Failed build directories and logs remain available. The September 30 preserved inputs now pass the full-feed bounded minute-policy validation, while all raw timing anomalies remain recorded. These examples describe the command interface; the [real graph build](../services/api/results/m3-functional-build-attempt3-20260930.json) and [ten-case structural probe](../services/api/results/m3-functional-probe-attempt2-20260930.json) now pass, while complete pipeline/activation acceptance remains required. [Latest audit](../services/api/results/m2-validation-attempt5-20260930.json), [timing policy](../poc/docs/adr/0008-bounded-minute-schedule-interpretation.md) and [data contracts](data-contracts.md) record the distinction.

Reference routes are `/v1/stops`, `/v1/stops/{id}`, `/v1/routes`, `/v1/routes/{id}` and `/v1/routes/{id}/patterns`. Nearby stops require `near=latitude,longitude` or `bbox=west,south,east,north`; route lists require a stop, operator or line-label filter. Cursors bind the query and generation. IDs are provisional pending consecutive daily-feed evidence.

Managed startup verifies all artifact hashes and reference identity. Set `OPENTRANSIT_MANIFEST` to the candidate's manifest and `OPENTRANSIT_MOTIS_URL` to its engine. `OPENTRANSIT_PROBE` must identify a passed structural probe bound to that generation's artifacts and engine origin before journeys/readiness are enabled. `OPENTRANSIT_SOURCE_CHECK` optionally supplies a successful same-hash paired upstream check. A legacy M1 manifest can still serve journeys, but lacks the complete managed reference/probe proof needed for `/readyz`. `/healthz` remains process liveness.

`opentransit prune --generations-root .runtime/generations --active <generation-id> --previous <previous-id> --dry-run --output .runtime/retention-new.json` only reports candidates; it never deletes files. Active, previous, evidence-pinned and draining generations must be retained. Candidate probing and Linux activation/rollback are still being verified; no refresh schedule or cloud deployment is configured.

## Edit and check the API

For rapid edits, run only MOTIS in Compose and the API on the host:

```powershell
docker compose --env-file .runtime/m1-20260930/compose.env stop api
docker compose --env-file .runtime/m1-20260930/compose.env up -d motis
$env:OPENTRANSIT_MANIFEST = '.runtime/m1-20260930/manifest.json'
$env:OPENTRANSIT_MOTIS_URL = 'http://127.0.0.1:58081'
uv run --project services/api --locked uvicorn opentransit.api.app:create_app --factory --reload --no-access-log
```

Run focused checks from the root:

```powershell
uv run --project services/api --locked ruff check services/api/src services/api/tests
uv run --project services/api --locked ruff format --check services/api/src services/api/tests
uv run --project services/api --locked pytest services/api/tests -m 'not integration' -q
node --test services/api/tests/playground.test.mjs
$env:OPENTRANSIT_TEST_URL = 'http://127.0.0.1:8000'
$env:OPENTRANSIT_TEST_DEPART_AT = '2026-10-01T08:00:00+03:00'
uv run --project services/api --locked pytest services/api/tests -m integration -q
```

The focused checks use labelled synthetic engine responses. Integration is skipped unless `OPENTRANSIT_TEST_URL` is set; its default departure is tomorrow at 08:00, and the example override above is dated. Choose a supported service date for later runs. Current Starlette emits a development-only warning about its legacy httpx TestClient fallback; the checks pass. The API's own engine client uses the pinned httpx dependency.

API logs contain generated request ID, route template, status and duration. Uvicorn access logs are disabled; no request bodies, coordinates, query strings or rejected values are logged. Errors use sanitized `application/problem+json`. Do not enable HTTP client debug logging with passenger requests.

The September 30 validation record is [M1 verification](../services/api/results/m1-20260930.json). Human H3/H4, static terms, scheduled search → journey integration, full routing semantics and operational release acceptance remain open. Docker's recurring stale OTel socket recovery is documented in the [routing runbook](../poc/routing/README.md#three-traps-that-cost-time-so-they-do-not-cost-it-twice); preserve its old runtime directory when renaming it.

## Test the verified scheduled functional slice

The preserved M1 service stays on port 8000. The isolated September 30 development slice currently serves port 8002, with an exact matching reference/graph and passed probe. Its source is frozen for attribution in the [runtime report](../services/api/results/m3-m4-functional-api-runtime-20260930-01.json). This is local functional evidence, not a deployable image or completed API acceptance.

```powershell
curl.exe --json "@services/api/examples/journey.json" http://127.0.0.1:8002/v1/journeys
curl.exe http://127.0.0.1:8002/v1/trips/20260930_23:50_mot60day_584668860_300926
curl.exe --get --data-urlencode "from=2026-10-01T00:10:00+03:00" --data-urlencode "horizonMinutes=60" --data-urlencode "limit=2" http://127.0.0.1:8002/v1/stops/mot:stop:13583/departures
curl.exe --get --data-urlencode "q=25609" --data-urlencode "type=stop" http://127.0.0.1:8002/v1/places
```

Follow the returned departure cursor with identical query parameters. Search candidates include `locationRef`; copy it into a journey's `from` or `to`. Stop references preserve full source IDs; POI/address selections contain generation-bound coordinates and reject stale references. Search reports unavailable categories explicitly. Street-only addresses retain `addressLevel: street`; a house-number label does not establish entrance precision. English stop aliases in this initial slice remain affected by the [legacy importer gap](../services/api/results/m4-legacy-translation-diagnostic-20260930-01.json).

The preserved source/launch/probe scripts are under `.runtime/m3-functional-evidence-20260930/`; they refuse to overwrite named containers or evidence. Inspect existing running containers before reusing them. The [22-check HTTP report](../services/api/results/m3-m4-functional-http-20260930-01.json) and [saved-body assertions](../services/api/results/m3-functional-http-body-assertions-20260930-01.json) cover midnight, both DST-fold occurrences, shapes, paging, search-to-journey and honest errors. Their single request times do not establish the required p95; Windows-backed reference I/O limits these serving measurements.

The repaired generation is tested in a separate container, `opentransit-api-repaired-20260930-02`, on port 8001 **inside** the preserved Docker network namespace (not the host port 8001). [English integration](../services/api/results/m4-english-functional-http-20260930-03.json) verifies search → journey, unchanged trips and stale-generation rejection. Its [runtime record](../services/api/results/m4-english-functional-runtime-20260930-03.json) pins the frozen source and native reference volume. Required readiness is intermittent and unresolved; the report is PARTIAL despite passing functional checks. The original port 8002 service and its evidence remain preserved. Search quality, p95, H3/H4 and operational/deployment acceptance are not claimed.

The prefilter-only successor, `opentransit-api-repaired-20260930-03`, currently uses that same internal port; API02 is retained stopped. Its [focused runtime evidence](../services/api/results/m4-stop-prefilter-runtime-20260930-01.json) pins the one changed source file and unchanged generation, compares three saved queries without repeating the full corpus, and separates cold index construction from warm timings. The [expanded search baseline](../services/api/results/m4-api-search-20260930-02-corrected.json) and [new H4 sheet](../services/api/results/m4-api-search-20260930-02-h4-review.md) record outstanding address quality and latency failures.
