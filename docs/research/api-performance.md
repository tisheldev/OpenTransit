# API and client speed: research and options

**Status: research and proposals, 3 October 2026. Nothing here is implemented or accepted.**
Goal set by the user: every API operation as fast as possible, and a client that feels
instant, with no loading screens except possibly app open.

Evidence used:

- **Measured baseline:** [`api-latency-baseline-20261003-01.json`](../../services/api/results/api-latency-baseline-20261003-01.json).
  Read-only run against the local `ot-demo-*` Docker stack (generation `5eb4e43d…`, API
  source `fe5df53`), loopback, one uvicorn worker, no CPU cap. Samples are small (6–40 per
  variant) because the rate limiter was on. It ranks costs on a developer machine; it is
  not a load test, not Fargate and not acceptance evidence.
- **Code audits** of the request pipeline, journeys, reference/timetable and search paths,
  with `EXPLAIN QUERY PLAN` run read-only on the live reference database.
- **Desk research** on network, CDN, engine and client techniques. Network latencies in
  this document are estimates from assumed round-trip times, not measurements.

Labels used below: **M** measured, **C** verified in code, **E** estimate or derived,
**G** guess.

## What the baseline shows

Server time at the API process, warm, in milliseconds (p50 / p95).

| Operation | Server time | Notes |
| --- | --- | --- |
| `/healthz` | 0.2 / 0.2 | Framework floor |
| `/readyz`, `/v1/status` | 15 / 31, 17 / 21 | Each runs a real MOTIS plan |
| `/v1/stops?near` (20 results) | 7 / 10 | 8.3 KB |
| `/v1/trips/{ref}` | 8 / 10 | |
| **`/v1/stops/{id}`** | **510 / 570** | 181 KB for a large station |
| **`/v1/routes/{id}`, `/patterns`** | **470 / 490** | 1–2 KB payloads |
| **`/v1/routes?stopId=`** | **114–179 / 133–197** | |
| **`/v1/stops/{id}/departures`** | **587–971 / 628–1095** | 21 of 80 returned 504; a 24-hour window always 504 |
| `/v1/places`, full stop name | 5 | |
| **`/v1/places`, 2-character prefix** | **218 (Hebrew), 411 (English)** | Every call |
| `/v1/places`, 3–5-character Hebrew prefix | 34–39 / about 210 | Slow on first sight of a query, about 1 ms on repeat (cause not identified) |
| `/v1/places`, address (Photon) | 12–25 | |
| `/v1/places`, POI Hebrew (MOTIS) | 55 | Known tail from the M4 diagnosis |
| `/v1/journeys`, coordinates, warm | 22–99 | 6.5–68 KB; engine is 40–78% of this |
| `/v1/journeys`, first call for a new pair | 173–820 (client) | 5–26 times the warm time |
| **`/v1/journeys`, stop-id inputs** | **1,510** | 5 of 8 returned 504 |

Cross-cutting facts (all **M** or **C**):

- Every response carries `Cache-Control: no-store` (`api/middleware.py:62`); there is no
  ETag, no compression and only HTTP/1.1.
- A journey response is 84% geometry: 73.5 KB of coordinate arrays where the engine's
  encoded polylines for the same shapes are 12 KB.
- Departures and stop-id journeys run synchronous SQLite inside `async` handlers. While
  one such request runs, `/healthz` stalls for 0.4–0.95 s, so every other user waits too.
- Python serialization is not a bottleneck: about 10 ms of post-processing per journey,
  and FastAPI already serializes in Rust.

## Root causes behind the slow rows

1. **Translations query scans the whole table (M, C).** `ReferenceStore._translations`
   (`reference.py:1339`) matches `record_id=? OR (record_id='' AND field_value=?)`. All
   102,603 rows have an empty `record_id`, and the only index is `(record_id, lang)`, so
   each call reads every row: about 475 ms. `stop()` and `route()` both call it.
2. **Departures and journeys call the full `stop()` just to read a source id (C).**
   Departures inherit the 475 ms once; a stop-to-stop journey pays it twice, on the
   event loop, which is why it exceeds the 1.5 s deadline.
3. **Departures fetch every trip in the window, one at a time (C).** One awaited engine
   call plus two new SQLite connections per distinct trip, before `limit` is applied.
4. **`routes(stopId=…)` scans all 7,873 routes (M)** with a correlated `EXISTS`
   (`reference.py:1366`); the equivalent join in `stop()` takes 1.4 ms.
5. **Queries shorter than three characters score all 35,321 stops in Python (M, C)**
   because the trigram index needs three characters (`stop_search.py:465`).
6. **Stop results wait for the slowest geocoder (C).** `places.py` awaits MOTIS and
   Photon before answering, so a 3 ms stop hit is delayed to 55–70 ms.

## Options for the API

### Tier 1 — small fixes, no contract or generation change

| # | Change | Gain | Risk |
| --- | --- | --- | --- |
| 1.1 | Load translations once per snapshot into dictionaries (or query the two selectors separately) | Stop/route detail, patterns: about 500 ms → about 25 ms (**E** from **M** query time) | Low |
| 1.2 | Slim `stop_ref` lookup (source id, platform, children) for departures and journeys, kept in memory per snapshot | Stop-id journeys 1.5 s → about the coordinate time (70 ms); removes loop stalls (**E**) | Low; map is bound to the snapshot |
| 1.3 | Departures: fetch trips concurrently (bounded), stop after `limit` plus a margin, move SQLite off the event loop | 0.6–1.0 s → roughly 0.1–0.3 s; 24-hour window stops timing out (**E**) | Medium: exactness checks and cursor stability must hold |
| 1.4 | Rewrite `routes(stopId=…)` to drive from `route_stops_stop_idx` | 114–180 ms → about 2 ms (**E** from **M**) | Low |
| 1.5 | Precomputed map for 1–2-character stop prefixes | 218–411 ms → a few ms (**E**) | Must equal exhaustive scoring; a test pattern exists |
| 1.6 | Gzip middleware (level 4–5, bodies over 1 KB), unless a CDN compresses | Journey 88 → about 22 KB for under 1 ms CPU (**M** on a fixture) | Low |
| 1.7 | Cap planning concurrency at 2–3 per vCPU and pass MOTIS a per-query timeout | Prevents every request timing out under a burst (**E**; today 16 are admitted and abandoned searches keep running) | Earlier honest 503s; the engine limit needs a new generation |
| 1.8 | `--timeout-keep-alive` above the ALB's 30 s idle timeout | Avoids reconnects and sporadic 502s (documented by AWS) | None |
| 1.9 | Cache the engine health result for a few seconds for `/readyz` and `/v1/status` | 15–17 ms → under 1 ms; fewer engine plans (**E**) | Readiness lags by the cache time |
| 1.10 | Move Photon address verification off the event loop; add Hebrew warm-up queries | 5–9 ms loop time per address request (**M**); cold Photon first pass 60 → about 30 ms (**M**) | None |
| 1.11 | One long-lived read-only SQLite connection with `mmap_size` and a larger cache; per-generation LRU for stop/route/pattern results | 1–3 ms per cheap request (**G**) | Low |
| 1.12 | Stop asking MOTIS for discarded work: skip `directModes` when the walk bound cannot be met; set `server.n_threads` | About 16 ms on long trips (**M** on a fixture) | Bound must be conservative |
| 1.13 | In-process cache of geocoder and stop-search results keyed by generation and normalized query | Repeated prefixes about 1 ms; hit rate unknown (**G**) | None on hit |

Items 1.1–1.5 remove every row above 100 ms in the baseline except cold journeys and the
Hebrew POI tail.

### Tier 2 — contract changes, best decided before the client is built

| # | Change | Gain | Risk |
| --- | --- | --- | --- |
| 2.1 | `geometry=encoded\|none\|geojson` on journeys | Response 70–80% smaller (**M**: 73.5 → 12 KB of geometry) | Public contract |
| 2.2 | Include intermediate calls in each transit leg (the engine already returns them; the adapter discards them) | Route details and navigation need no per-leg trip request | Larger payload unless paired with 2.1 |
| 2.3 | Journey paging: pass through the engine cursors, add `searchWindowMinutes`, allow up to about 10 results | "Earlier/Later" answered locally | Cursors must be generation-bound |
| 2.4 | Cache headers by data type: generation ETag plus `private, max-age=60` on reference and departures; short `max-age` on status; journeys and places stay `no-store` | Revalidation in a few ms with no database work | The freshness gate must run before a 304; `requestId`/`generatedAt` in the body prevent byte-stable responses |
| 2.5 | Per-generation reference bundle (all stops, routes, localities) at a content-addressed URL, `immutable` | Stop search, nearby and line lists need no network. Stops alone: 0.64 MB brotli (**M**, computed from `oct1b`) | Bundle names can lag; expiry must still come from `/v1/status` |
| 2.6 | `meta.sourceCheckedAt` (or the freshness transition times) and `meta.referenceHash` | Lets the client age cached views honestly offline | Small |
| 2.7 | Separate rate-limit buckets for places and journeys; `RateLimit` headers | Typeahead plus speculative requests fit; today both share 30 per minute and carrier NAT pools users | Abuse budget needs re-tuning |
| 2.8 | Deadline-bounded geocoders returning partial results | Caps places p95 near 35–40 ms | High: at least 30 of 248 Hebrew POI requests would lose results; `partial` changes meaning |

### Tier 3 — infrastructure, needs the user's spending or Region decision

Assumed round trips: Israel to Stockholm about 130 ms on mobile, Israel to a Tel Aviv
edge about 35 ms. All figures are estimates.

| # | Option | Gain | Cost / constraint |
| --- | --- | --- | --- |
| 3.1 | CloudFront in front of the ALB (Tel Aviv edges, HTTP/3, brotli, persistent origin connections) | Cold connection about 400 → 105 ms; cached GET about 35 ms; warm uncached requests and journeys about even | Free tier likely covers it; a custom domain needs an ACM certificate in `us-east-1`, which the project rules may not allow |
| 3.2 | Edge caching of reference reads and the bundle, keyed by generation | Popular stops served from Tel Aviv | Needs 2.4/2.5; CDN logs must stay off for privacy |
| 3.3 | 2 vCPU / 4 GiB task | Better tail under concurrency, shorter startup (not measured) | About +$33 per month (**E**); fits the 8 GiB rule by allocation |
| 3.4 | Serve from `il-central-1` | About 90 ms off every uncached call | Not creatable in the current AWS project |
| 3.5 | ARM64 Fargate | About 20% cheaper compute | New image digests, rebuilt generation, graph portability unproven |

### Tier 4 — generation format, needs an ADR

- **Precomputed departure boards per (stop, service day)** would take the engine out of
  the departures path (5–20 ms, **G**) but changes the engine-agreement guarantee.
- **Slimmer reference schema.** About 1.3 GB of the 3.03 GB file is
  `clock_profiles.canonical_json` and its unique index, which serving never reads (**M**).
  Dropping it shortens startup hashing and the image, and changes the content identity.
- **Own POI index** (per-generation SQLite FTS from the same OSM extract) would remove the
  50–70 ms Hebrew POI tail but replaces the H4-approved ranking; a full 183-variant replay
  and a new human review would be required.
- **Engine tuning** (`searchWindow`, `algorithm`, `maxTravelTime`, `timetableView`) may
  save 10–50% of engine time (**G**) but can change which itineraries are found, so it
  needs an H3-style comparison.

### Considered and not recommended

- More uvicorn workers: one vCPU, and the limiter and activation assume one process.
- orjson/msgspec, free-threaded Python: Python is about 10 ms of a journey.
- Binary formats: compressed JSON already fits in one congestion window.
- A cacheable GET alias for journeys: near-zero hit rate, and coordinates would enter
  URLs and logs.
- Disabling MOTIS geocoding: POI search depends on it.
- Streaming partial itineraries: the engine returns all results at once.

## Options for the client

The [client design](../client-design.md) is a static React SPA with TanStack Query and a
lazy MapLibre map, no service worker, journeys in session storage.

| # | Technique | What the user sees | Needs from the API |
| --- | --- | --- | --- |
| C1 | Home rendered from local storage before the framework mounts; map chunk loaded after first paint; route-level code splitting | Usable plan sheet on the first frame | Nothing |
| C2 | Service-worker app shell with navigation preload | Repeat opens in under about 300 ms, even offline | Nothing; a user decision (the design has no service worker) |
| C3 | Connection warm-up: fetch `/v1/status` at boot | First real request skips the handshake | Nothing; better with 3.1 |
| C4 | Optimistic list → detail: open stop, line and trip pages from the summary already in memory, keep previous data while refetching | Pages open in under 100 ms | Nothing |
| C5 | Departure board as one multi-hour fetch that ticks locally; no polling | Board opens instantly and counts down by itself | Works today once 1.1–1.3 land; 2.4 helps |
| C6 | Journey request fired on touch-down or when the second endpoint is chosen, aborted if cancelled | Options appear 100–300 ms sooner | Fits today's limiter if capped; 2.7 makes it safe |
| C7 | Same origin and destination again: show the cached result minus departed options, marked "updating" | Results at 0 ms | Nothing; never splice across generations |
| C8 | Local "leave in X min" countdowns and expiry | Live-feeling list without network | 2.6 for clock-skew correction |
| C9 | Chart first, map second: straight dashed leg lines until geometry arrives | Options before the map | 2.1 |
| C10 | Two parallel places calls (stops, then addresses and POIs) | Stop matches in 3–15 ms instead of waiting for the geocoders | Nothing |
| C11 | On-device stop index from the bundle, in a worker; local nearby stops | Typeahead under 16 ms per keystroke, offline; location never leaves the device | 2.5 |
| C12 | Wide journey window paged locally | Instant "Earlier/Later" | 2.3 |
| C13 | Route details and navigation from the journey payload alone | No request when opening an option | 2.2 |
| C14 | Self-hosted map tiles (PMTiles) on the same origin | Cached map, no third party sees viewports | Static hosting |

Rules that keep this honest: cache keys include the generation (or reference hash); a
response from a newer generation discards older derived views; cached results are labelled
scheduled and aged with the local freshness clock; speculative requests are limited to one
in flight and about three per minute and never retried.

Proposed definition of "instant" (p75, throttled to 150 ms round trip and 4× CPU):
warm open ≤ 600 ms, cold open ≤ 2 s, keystroke to local results ≤ 50 ms, cached
interaction ≤ 100 ms, network reference read ≤ 400 ms, journey options ≤ 1 s.

## Suggested order

1. Tier 1 items 1.1–1.5, then re-measure with the same baseline script.
2. The rest of Tier 1 (1.6–1.13).
3. Decide Tier 2 before client slice S0, since 2.1–2.3 and 2.5 shape the client's data
   layer; build C1, C4, C5, C6–C8 and C10 regardless.
4. Decide CloudFront (3.1) together with the H-0 Region question.
5. Tier 4 only if measurements after steps 1–4 still miss a target.

## Open questions for the user

1. On-device stop search ranks locally and will not match the H4-approved server ranking
   exactly. Acceptable, with server results merged in?
2. Service worker and offline shell before public release?
3. Prefetch Home↔Work journeys at app open (sends those coordinates on every launch):
   off, opt-in or on?
4. Keep journey results beyond the session for instant reopen (on-device history)?
5. May the device remember the last map viewport?
6. Opt-in anonymous timing beacons, or lab-only measurement?
7. CloudFront at H-1 or only at public release, given the certificate Region limit?

## Limits of this research

- The baseline has small samples, ran on a 16-CPU Docker VM over loopback with the
  reference bind-mounted from Windows, and other sessions may have been using the API.
- Gains marked **E** or **G** are not measured; each fix needs a re-run of the baseline.
- The 3–5-character first-sight cost (about 210 ms, then about 1 ms) and the cold
  first-journey cost are measured but not explained.
- No Fargate, CloudFront or mobile-network measurement exists; network figures rest on
  assumed round-trip times.
- Search ranking changes (1.5, 2.8, the POI index, on-device search) need a replay of the
  183-variant corpus before they can claim parity with H4.
