# Local schedule API development

M1 implements `GET /healthz` and `POST /v1/journeys`, plus FastAPI's `/docs` and `/openapi.json`. Journey inputs are coordinates and an explicit-offset `departAt`; one itinerary is returned. Search, stop references, arrive-by, preferences, departures, managed refresh and cloud deployment follow in later milestones. This is a provisional local contract.

## Start the verified M1 generation

Run from the repository root with Docker Desktop's Linux engine running:

```powershell
docker compose --env-file .runtime/m1-20260930/compose.env up -d --build
curl.exe --json "@services/api/examples/journey.json" http://127.0.0.1:8000/v1/journeys
```

Open [interactive API docs](http://127.0.0.1:8000/docs). The example plans Dizengoff Center → Technion on October 1 at 08:00 Israeli time. Change `departAt` to a desired explicit-offset time inside the manifest's half-open coverage. The September 30 graph covers `[2026-09-30T00:00:00+03:00, 2026-10-31T00:00:00+02:00)`; it includes the October DST offset change, but comprehensive DST correctness is an M3 check. Timings are scheduled; predictions/delays and alerts are null, with both live capabilities `not_enabled`.

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
$env:OPENTRANSIT_TEST_URL = 'http://127.0.0.1:8000'
$env:OPENTRANSIT_TEST_DEPART_AT = '2026-10-01T08:00:00+03:00'
uv run --project services/api --locked pytest services/api/tests -m integration -q
```

The focused checks use labelled synthetic engine responses. Integration is skipped unless `OPENTRANSIT_TEST_URL` is set; its default departure is tomorrow at 08:00, and the example override above is dated. Choose a supported service date for later runs. Current Starlette emits a development-only warning about its legacy httpx TestClient fallback; the checks pass. The API's own engine client uses the pinned httpx dependency.

API logs contain generated request ID, route template, status and duration. Uvicorn access logs are disabled; no request bodies, coordinates, query strings or rejected values are logged. Errors use sanitized `application/problem+json`. Do not enable HTTP client debug logging with passenger requests.

The September 30 validation record is [M1 verification](../services/api/results/m1-20260930.json). Human H3/H4, static terms, scheduled search → journey integration, full routing semantics and operational release acceptance remain open. Docker's recurring stale OTel socket recovery is documented in the [routing runbook](../poc/routing/README.md#three-traps-that-cost-time-so-they-do-not-cost-it-twice); preserve its old runtime directory when renaming it.
