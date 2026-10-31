# OpenTransit web client

A Hebrew-first, right-to-left mobile web client for testing and previewing the API during the H-1 private deployment (user, 31 October 2026). It is not the product release: the native Expo / React Native app is the product client, and the pure modules here are built to be shared with it. Its design, slices and acceptance criteria are in [docs/client-design.md](../../docs/client-design.md); project status is in [PROJECT_STATUS.md](../../PROJECT_STATUS.md). Slices S0–S2 (scaffold, API layer, foundations) are implemented; the screens are placeholders until S3–S7.

Node 22.12 or later. All commands run in `apps/web`.

```bash
npm ci
npm run dev            # http://localhost:5173, /v1 proxied to the API (OPENTRANSIT_API_ORIGIN, default http://localhost:8000)
npm run dev:fixtures   # same, but MSW answers /v1 from fixtures and a "test data" banner shows
npm run lint && npm run typecheck
npm test               # Vitest under a UTC host; npm run test:tz repeats the time tests in other zones
npm run build          # dist/, base /app/ (served by the API in S8)
npm run e2e            # Playwright against the fixtures-mode dev server; @real tests skip unless /readyz is 200
```

## API layer and fixtures

- `src/api/endpoints.ts` has one function per public endpoint, each returning a `Result`; failures carry a UI state from `classify()` (`src/api/classify.ts`).
- Journey and problem types are generated from `openapi/openapi.json` (`npm run openapi:types`; CI checks the generated file is current). Other responses are validated with zod (`src/api/schemas.ts`).
- Trip, stop and route IDs go through `encodePathRef()`; an ID containing `/` is refused rather than sent.
- Fixtures in `src/api/fixtures/` are sanitised responses, and `manifest.json` records where each came from:
  - `recorded-*`: real API responses from committed evidence (`node scripts/extract-recorded-fixtures.mjs`, offline).
  - `synthetic-*`: the API's in-process test harness on its synthetic feed, plus the OpenAPI snapshot. From the repository root: `PYTHONPATH=services/api/tests uv run --project services/api --locked pytest apps/web/scripts/synthetic_api_fixtures.py -p conftest -q -p no:cacheprovider`.
  - `recorded-live-*`: `npm run fixtures:record` against a running, ready API. It also checks trip-ref encoding against real engine trip IDs and refuses to record if `/readyz` is not 200.

## Rules the code enforces

Times are Asia/Jerusalem with explicit offsets (`src/lib/time.ts`); strings live in typed Hebrew and English dictionaries with key and placeholder parity (`src/i18n/`); CSS uses logical properties; `localStorage` is versioned and holds only settings, saved places and at most 10 recents (`src/storage/local.ts`), and "clear all" removes them along with session data.
