# OpenTransit web client

A Hebrew-first, right-to-left mobile web client for testing and previewing the API during the H-1 private deployment (user, 31 October 2026). It is not the product release: the native Expo / React Native app is the product client, and the pure modules here (API layer, `classify`, i18n, time and format, `plan/*`, `nav/*` logic) are built to be shared with it. Design and acceptance criteria: [docs/client-design.md](../../docs/client-design.md) and the [client tasks](../../docs/next-steps.md#phase-2-client-execution-plan); status: [PROJECT_STATUS.md](../../PROJECT_STATUS.md); latest evidence: [client-s3-s8-20261031-01](../../services/api/results/client-s3-s8-20261031-01.json).

Implemented: S0–S2 (scaffold, API layer, foundations), S3 Map, S4 shell + Home, Search, Settings, S5 Compare and route details, S6 Navigate (foreground only), S8 serving by the API at `/app/`. S7 (Stop, Trip, Nearby, Lines) is not built; those routes show placeholders.

## What a tester can do

Open `/app/` on a phone (Hebrew by default; English in Settings). A UX pass on 31 October (human-like testing at 360 × 640 against the real timetable) shaped what follows:

- **Home:** "Where to?" first; From is "my location" only where the browser can give it (a secure context), otherwise the last start or empty; Home/Work/favourite chips, recent places, a resume card at the top while a trip is active, banners for test data, ageing/expired timetable, not ready and offline.
- **Search:** stops, stations, addresses (street-level tagged) and places as you type; "choose on map"; save Home, Work or a named favourite.
- **Compare:** opens at half with the route on the map: up to three options led by their departure and arrival times, a rank pill and a shared-axis bar of line chips; one time chip (Now / Depart / Arrive, day, time, +15/+30/+60); Earlier / Later under the options. Tap an option for its itinerary timeline (boarding and exit times, stop counts, waits, walks); Start navigation.
- **Navigate:** opens at half with your leg on the map: a step card (what to do now, what comes next), Next step as the single bottom action, End trip in the card header, and the whole-trip checklist with scheduled times; tap any row to correct. Real location while the page is open (keep it open; the screen stays awake where Wake Lock exists); "מיקום מדומה (בדיקה)" plays simulated positions along the trip at ×10–×600. "Get off in 2 stops / at the next stop" cues use the positions of the two stops before each exit, fetched once at Start. A reload resumes the trip.

Known not to work: platforms (API-C2) and intermediate stop names (API-C1) are not shown; background location, a locked-phone cue and notifications are native-only; S7 screens are placeholders; swipe-down to go back is not implemented (Back works); after Earlier/Later the time control keeps the time you chose.

## Commands

Node 22.12 or later. All commands run in `apps/web`.

```bash
npm ci
npm run dev            # http://localhost:5173, /v1 proxied to the API (OPENTRANSIT_API_ORIGIN, default http://localhost:8000)
npm run dev:fixtures   # same, but MSW answers /v1 from fixtures and a "test data" banner shows
npm run lint && npm run typecheck
npm test               # Vitest under a UTC host; npm run test:tz repeats the time tests in other zones
npm run build          # dist/, base /app/ (served by the API when OPENTRANSIT_CLIENT_DIR is set)
npm run e2e            # Playwright, 360 × 640, fixtures mode; @real tests skip unless /readyz is 200
```

- Fixture scenarios: set `localStorage["ot-fixture-scenario"]` (for example `compare-no-route`, `compare-unavailable`, `compare-rate-limited`) to drive a state in fixtures mode; see `src/mocks/handlers.ts`.
- Real end-to-end: `OPENTRANSIT_API_ORIGIN=<api> npx playwright test --grep @real` (dev-server mode), or against a build served by the API: `OPENTRANSIT_API_ORIGIN=<api> OT_E2E_BASE_URL=<api>/app/ npx playwright test`. `OT_E2E_PORT` gives each worktree its own dev server.
- If Vitest misses newly added fixture files, clear `node_modules/.vite`, `node_modules/.vite-temp` and `node_modules/.vitest-cache`.
- Serving by the API, the Docker build context and the acceptance-runner `--client-dir` option: [development runbook](../../docs/development.md#serve-the-web-client).

## Structure

`src/router.ts` hash routes (no coordinates or IDs of people in URLs) · `src/shell/` map + three-snap sheet, From/To, banners · `src/map/` lazy MapLibre (OpenFreeMap tiles in real mode, an offline style in fixtures mode), scene store, journey → scene · `src/screens/<screen>/` sheet content per route · `src/plan/` draft, journey request, rank labels, chart layout, earlier/later · `src/nav/` steps, pure engine, geo, simulation, active trip · `src/api/` typed `Result` client for every endpoint, zod schemas, `classify()`, fixtures · `src/i18n/` Hebrew and English (each slice's keys in `parts/`).

## API layer and fixtures

- `src/api/endpoints.ts` has one function per public endpoint, each returning a `Result`; failures carry a UI state from `classify()`.
- Journey and problem types are generated from `openapi/openapi.json` (`npm run openapi:types`). Other responses are validated with zod (`src/api/schemas.ts`; `jitless`, because the `/app/` CSP forbids `eval`).
- Trip, stop and route IDs go through `encodePathRef()`; real engine trip IDs contain `:` and round-trip (26 checked); an ID containing `/` is refused.
- Searched places are sent as coordinates: on `oct31a` a `placeRef` and its returned coordinate routed identically in 8 of 8 cases, so the `INVALID_PLACE_REF` retry was removed.
- Fixtures in `src/api/fixtures/` are sanitised responses; `manifest.json` records each one's provenance: `recorded-*` from committed evidence, `recorded-live-*` from `npm run fixtures:record` against a ready API (refuses unless `/readyz` is 200), `synthetic-*` from the API's in-process harness. States a healthy API cannot produce (partial search, Compare failures) are derived in code from recorded fixtures and labelled there.

## Rules the code enforces

Times are Asia/Jerusalem with explicit offsets (`src/lib/time.ts`); strings live in typed Hebrew and English dictionaries with key and placeholder parity; CSS uses logical properties and the map is never mirrored; `localStorage` is versioned and holds only settings, saved places and at most 10 recents; the plan draft and the active trip live in `sessionStorage` and never hold a device position; `opentransit:lastOrigin` (outside the versioned key) only points at one of the recents; "clear all" removes all of it.
