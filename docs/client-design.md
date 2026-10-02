# Phase 2 client design

**Proposal, 1 October 2026; interface direction chosen 2 October 2026; not implemented.** Implementation starts under the October 1 [gate revision](../PRD.md): once M2–M4 are accepted locally and the private H-0/H-1 deployment begins. Realtime and alerts remain deferred. The client labels every time as scheduled and shows unavailable live data as unavailable, never as an empty success.

## Interface direction (user, 2 October 2026)

The client is a **Hebrew-first, right-to-left** mobile web app with English mirrored from it. It focuses on two jobs, with no bloat: **planning a trip** (choose where from and where to, compare the options with every fact needed to choose) and **navigating it** (know where you are, and for each step show when the vehicle leaves, where from, which platform, and the next steps). The user compared three designs and chose **Map + timeline**, then picked its **variant B** in the playable prototype: a map with a bottom sheet holds every screen; options are compared as one compact chart on a shared time axis; tapping an option shows its whole route at once; and navigation pins a high-contrast step card at the top of the sheet, near the thumb, above the whole-trip checklist.

Tokens, components (Hebrew previews), the seven-screen flow and the brand book live in the OpenTransit design system, a private claude.ai artifact (`https://claude.ai/artifact/P3US2NygmWPs1iALn555PU`, owner access). Its palette and copy derive from the API playground. It is a static CSS rendition, not implementation evidence. A playable prototype (`https://claude.ai/artifact/FVufx6zTmyzny45pzRpxb5`, private, sample data and a simulated clock) showed three variants: A, full option rows with the step card over the map; B, a compact timeline chart with the step card in the sheet; C, full rows with a large countdown. The user chose B on 2 October, with one change: tapping an option shows its route in detail immediately.

### Surface

- The map is always behind, centred on the person. It draws whatever the sheet is about, and it is never mirrored.
- The sheet has three snap points (peek 35%, half 55%, full 92%). Moving forward replaces its content in place; swiping down or the system back gesture goes back one level and keeps the trip.
- There are no tab bars, menus or overflow buttons. The only floating controls are Back and Locate.

### Plan

| # | Screen | Content | Taps |
| --- | --- | --- | --- |
| 1 | Home | Floating From/To fields: From defaults to "המיקום שלי" (my location) or the last origin; swap button. Sheet: Home, Work and favourite chips, then recents | 0 |
| 2 | Where to | Sheet at full height with results as you type (places, stops, stations, Hebrew or English), and "בחירה במפה" (choose on map) always as a row. A chip or recent skips this screen | 1 + typing |
| 3 | Compare | Now / Depart at / Arrive by inline. One compact chart: three options as bars on one time axis, earliest on the right, each labelled with its duration and rank (מומלץ / הכי מהיר / בלי החלפות). The best option is preselected and drawn on the map | 1 (2 after typing) |
| 4 | Route details | Tapping any option selects it, redraws the map, and immediately shows its whole route under the chart: leave → arrive, duration, transfers, walking, first boarding, then every step (line, headsign, platform, stops, exit stop, transfer waits). The sheet scrolls so the chart and the details are both in view. Earlier and Later follow the details. "התחלת ניווט" (Start navigation) is pinned at the bottom | +1 per option tapped |

From a saved place or a recent, navigation starts in two taps (place, Start), or three when another option is chosen. Once both ends are known, results load immediately, with the best option's details already shown; there is no Plan button.

### Navigate

| Step | Step card (pinned at the top of the sheet) | Below it in the sheet |
| --- | --- | --- |
| Walk to a stop | Instruction, distance left, countdown to the vehicle; line, departure time, exit stop; margin and next departure | The whole trip as a checklist: done, now (highlighted), next; arrival time |
| On board | Line and stops left; exit stop and time; what comes next (for example, train · platform 2) | The current item shows the stops, where you are, and the exit stop |
| Transfer | Walk to the platform; countdown to the next vehicle; destination, platform, departure | Previous legs ticked off |
| Arrive | Arrival time and Finish | All items done |

- Location is requested at Start and processed only on the device. It updates the distance and position, and advances the step on reaching the stop, boarding, and passing the exit stop. "השלב הבא" (next step) is always available; without location, a banner says steps advance manually.
- Two stops before the exit the card says "רדו בעוד 2 תחנות" (get off in 2 stops), and one stop before, "רדו בתחנה הבאה" (get off at the next stop). Android also vibrates; every platform changes the card's colour.
- The Screen Wake Lock keeps the display on. The active trip is restored from `sessionStorage`.

### Language and layout rules

- Every string is written in Hebrew first and addressed with the gender-neutral plural imperative. Units: "דק׳" (min), "מ׳" (m), "ק״מ" (km), "שע׳" (h). Use a 24-hour clock.
- The root has `dir="rtl"`. Time ranges, leg strips, the comparison axis and progress run right to left; digits, times and line numbers sit in `<bdi>` with tabular figures. Directional icons mirror; mode icons do not.
- Trains are named by destination and platform; buses by number and headsign.
- Primary actions sit at the bottom of the sheet. At 360 × 640, after an option is tapped the chart and the start of its route are both visible, and navigation shows the step card and at least the next step without scrolling.

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

Core screens (the two jobs) come first; secondary screens open from them and are built after.

| Screen | API calls |
| --- | --- |
| Home: From/To, current location, Home/Work, recents, favourites, data-status banner | `GET /v1/status`, cached 5 min |
| Search (Where to) | `GET /v1/places` (debounce 250 ms, at least 2 characters, cancel the previous request; `near` only if location is already granted); pick on map |
| Compare | `POST /v1/journeys` with an explicit "now"; earlier and later re-send a shifted time |
| Option in place | Cached response; map from `leg.geometry`; stop counts and names via `GET /v1/trips/{engineTripId}` |
| Navigate | Cached journey and trips; on-device `watchPosition`; Wake Lock; no new server calls except trips not yet fetched |
| Stop (secondary, from a stop name) | `GET /v1/stops/{id}`, `GET /v1/stops/{id}/departures` (infinite list with cursor) |
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
| S4 Home, Search, Settings | Those screens, map + sheet shell | Hebrew/English search, partial/unavailable categories, saved places, clear data, RTL layout check, axe |
| S5 Compare and route details | Timeline chart, route details on tap | Routes, no route, outside window, place-ref fallback, 503/504; tap shows details with the chart still in view at 360 × 640; real Dizengoff Center → Technion |
| S6 Navigate | Step card, checklist, ride progress, location and Wake Lock | Step advance from simulated positions, manual advance without location, get-off cues, trip restore after reload; real journey replayed |
| S7 Stop, Trip, Nearby, Lines | Secondary screens | Paging without duplicates, cursor restart, empty vs unavailable, 404; real stop → trip |
| S8 Serving and audit | API static mount, config, Dockerfile, its tests, real end-to-end suite | Off by default and absent from OpenAPI; cache and CSP headers; full real suite plus axe against Compose |

Order: S0; then S1, S2, S3 and the backend half of S8 in parallel; S4–S6 once S1 and S2 exist; S7 after the core flows; S8 end-to-end last.

## API follow-ups (M7, non-blocking)

Add response models to the non-journey endpoints. Unify the unavailable-alerts value. Add operator and mode to departure items.

## Defaults pending user confirmation

- Name "OpenTransit", with the teal palette from the playground as set out in the design system.
- System fonts (no third-party fonts), drawn line icons with the option of switching to a licensed open set.
- OpenFreeMap vector tiles for the preview, moving to a self-hosted Protomaps Israel extract before public release. The tile host sees user IPs and viewports.
- Mobile web first; native deferred.
