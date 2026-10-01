# Phase 2 client design

**Proposal, 1 October 2026; not implemented.** Implementation starts under the October 1 [gate revision](../PRD.md): once M2–M4 are accepted locally and the private H-0/H-1 deployment begins. Realtime and alerts remain deferred. The client labels every time as scheduled and shows unavailable live data as unavailable, never as an empty success.

## Constraints from the current API

- No CORS, and `Cache-Control: no-store` on every response. Serve the client from the API origin.
- Only `POST /v1/journeys` has typed OpenAPI response models. Places, stops, routes, departures, trips and status are untyped, so validate them with schemas checked against recorded fixtures.
- `placeRef` is bound to one generation and returns `422 INVALID_PLACE_REF` after a refresh. Favourites store coordinates and labels; the ref is only a hint.
- Unavailable live data is represented inconsistently: journey `alerts: null`, trip `alerts: "not_enabled"`. Decide capability from `meta.capabilities` and `/v1/status` only.
- `walkingDistanceMeters` and a walk leg's `distanceMeters`/`geometry` can be null: an interior transfer MOTIS cannot street-route keeps its time (`geometryUnavailableReason: street_path_unavailable`, journey warning `TRANSFER_STREET_PATH_UNAVAILABLE`). Render a time-only walk instead of inventing a distance or line.
- The trip link is `leg.transit.engineTripId`, used as `GET /v1/trips/{tripRef}`. Verify encoding against real IDs; an ID containing `/` would not route.
- The PRD requires perceived startup under 2 s, local-only favourites, no account, and MapLibre with OSM data. It has no offline requirement. Target WCAG 2.2 AA, Hebrew-first RTL with English.

## Stack and hosting

- Static SPA: Vite, React 19, TypeScript, TanStack Query, hash routing. Fragments never reach the server or its logs.
- MapLibre GL JS, lazy-loaded, with the RTL text plugin served from our origin and visible OSM/MOT attribution.
- No service worker in the preview; a web manifest only.
- H-1 hosting: the API task serves the built files at `/app/` when `OPENTRANSIT_CLIENT_DIR` is set, built in a Node stage of the API image. Same origin, inherits the ALB reviewer-IP restriction, about $0 extra. Hashed assets are `immutable`; `index.html` is `no-store`; strict CSP and `Referrer-Policy: strict-origin-when-cross-origin`.
- Rejected for now: SSR (no SEO need, extra runtime); S3 + CloudFront (needs WAF or a function for the IP restriction; revisit at public release); a separate static container (+$9–18/month); native apps (Phase 5).
- Local development: the Vite dev server proxies `/v1` to `localhost:8000`.

## Screens

| Screen | API calls |
| --- | --- |
| Home: where to, current location, Home/Work, recents, favourites, data-status banner | `GET /v1/status`, cached 5 min |
| Search | `GET /v1/places` (debounce 250 ms, at least 2 characters, cancel the previous request; `near` only if location is already granted); pick on map |
| Results | `POST /v1/journeys` with an explicit "now"; earlier and later re-send a shifted time |
| Journey detail | Cached response; map from `leg.geometry`; all stops via `GET /v1/trips/{engineTripId}` |
| Stop | `GET /v1/stops/{id}`, `GET /v1/stops/{id}/departures` (infinite list with cursor) |
| Trip | `GET /v1/trips/{tripRef}`: calls, restrictions, shape |
| Nearby / map browse | `GET /v1/stops?near=…` or `bbox` (zoom 14 or closer, at most 100 km²) |
| Lines | `GET /v1/routes?…`, `GET /v1/routes/{id}` and its patterns |
| Settings | Language, Home/Work/favourites, clear all local data, attribution, data status |

## Cross-cutting rules

- **API layer:** hand-written `Result<T>` client. Journey and problem types are generated from a committed OpenAPI snapshot; other responses are validated with zod. A pure `classify(status, code)` maps problems to UI states.
- **States:** no route, no departures and no matches are successes with empty results. Partial or unavailable search categories are shown inline. Capabilities that are `not_enabled` read "Live times and alerts unavailable". Show a stale-data banner, and a "test data" banner in fixture mode.
- **Error codes:**
  - `OUTSIDE_SERVICE_WINDOW`: show the coverage dates.
  - `INVALID_PLACE_REF`: retry once with the saved coordinate.
  - `INVALID_CURSOR`: restart the list.
  - 404: "no longer in the timetable".
  - 429: honour `Retry-After`.
  - 503/504: "temporarily unavailable", with retry.
  - Network failure: "can't reach OpenTransit".
- **Time:** always Asia/Jerusalem with an explicit offset and a "scheduled" label. Reuse the playground's DST handling and its tests.
- **i18n/RTL:** typed Hebrew and English dictionaries with key parity, Intl formatters, CSS logical properties only, `<bdi>` for line numbers and mixed-language names.
- **Accessibility:** axe on every screen in both languages, a keyboard-only planning flow, focus management, `aria-live` updates, 44 px targets, nothing conveyed by colour alone, every map fact also present as text.
- **Privacy:** no analytics, third-party fonts or CDNs. Location only on tap, one-shot, never stored. Versioned `localStorage` holds settings, favourites and at most 10 recents. Journey results stay in `sessionStorage`. No location in URLs.
- **Performance budget:** initial JS at most 150 KB gzipped, excluding the map chunk.

## Work slices

Every slice has mocked Playwright/Vitest checks (MSW, no Docker) and `@real` checks against the local API, which are skipped unless `/readyz` returns 200.

| Slice | Owns (under `apps/web/` unless noted) | Acceptance |
| --- | --- | --- |
| S0 Scaffold (first) | Tooling, `index.html`, router with placeholder screens, tokens, Playwright config, lint | Build/test/e2e pass; direction switch; dev proxy reaches `/v1/status` |
| S1 API layer | `src/api/**`, fixtures, MSW handlers, fixture recorder | Fixtures pass schemas; `classify()` table test; sanitised fixtures; `tripRef` encoding checked against the real API |
| S2 Foundations | i18n, time/format, storage, common state components | DST tests under a UTC host; key parity; storage migration and clear-all |
| S3 Map | `src/map/**` | Stubbed component tests; map chunk loads only where used; attribution visible |
| S4 Home, Search, Settings | Those screens | Hebrew/English search, partial/unavailable categories, saved places, clear data, axe |
| S5 Plan and Detail | Those screens | Routes, no route, outside window, place-ref fallback, 503/504; real Dizengoff Center → Technion |
| S6 Stop, Trip, Nearby, Lines | Those screens | Paging without duplicates, cursor restart, empty vs unavailable, 404; real stop → trip |
| S7 Serving and audit | API static mount, config, Dockerfile, its tests, real end-to-end suite | Off by default and absent from OpenAPI; cache and CSP headers; full real suite plus axe against Compose |

Order: S0; then S1, S2, S3 and the backend half of S7 in parallel; S4–S6 once S1 and S2 exist; S7 end-to-end last.

## API follow-ups (M7, non-blocking)

Add response models to the non-journey endpoints. Unify the unavailable-alerts value. Add operator and mode to departure items.

## Defaults pending user confirmation

- Name "OpenTransit" with a neutral palette.
- OpenFreeMap vector tiles for the preview, moving to a self-hosted Protomaps Israel extract before public release. The tile host sees user IPs and viewports.
- Mobile web first; native deferred.
