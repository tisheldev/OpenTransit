# OpenTransit Israel — Product Requirements Document

**Working name:** OpenTransit Israel
**Product concept:** "BetterRail, but for all Israeli public transport."
**Status:** Initial PRD
**Primary platform:** Backend API first; mobile client second, with the same API reusable by web and other clients
**License target:** Open source

---

## 1. Product Vision

OpenTransit Israel is a fast, clean, privacy-conscious, open-source public transportation application for Israel.

Its core purpose is simple:

> Help a user get from where they are to where they want to go using Israeli public transportation, with as little friction as possible.

The product should prioritize transportation information rather than monetization, advertisements, engagement mechanics, payment flows, or unrelated functionality.

The guiding principles are:

- **Fast**
- **Reliable**
- **No ads**
- **Open source**
- **Transit information first**
- **Minimal clutter**
- **Useful realtime information**
- **Privacy-conscious by default**
- **Works well specifically in Israel**

The initial product should cover:

- Buses
- Israel Railways
- Light rail where data is available
- Walking segments
- Transfers between modes

Payment, Rav-Kav charging, fare payment, taxi ordering, scooter rental, social functionality, and advertising are explicitly outside the initial scope.

---

## 2. Problem

Existing Israeli transportation apps solve the fundamental routing problem but often combine it with:

- Advertising
- Slow interfaces
- Excessive UI
- Monetization features
- Unrelated mobility products
- Inconsistent UX
- Reliability problems
- Features that obscure the basic information a passenger needs

At the same time, much of the underlying Israeli transportation information is available through public or open infrastructure.

The opportunity is therefore not to invent a new transportation network. It is to build a substantially better interface and engineering layer on top of the existing open transportation ecosystem.

---

## 3. Primary User

A person in Israel who wants to answer:

> "What is the best way for me to get there using public transportation?"

Typical usage should require only:

1. Open app.
2. Select destination.
3. See routes.
4. Select route.
5. Follow journey.

The app should optimize for repeated everyday usage rather than tourism.

Examples:

- Home → work
- Work → home
- Home → university
- Current location → restaurant
- Tel Aviv → Haifa
- Bus → train → bus journeys
- "When should I leave?"
- "Is my bus actually coming?"

---

## 4. Product Principles

### 4.1 Transit first

The home screen should primarily answer:

**Where do you want to go?**

Not:

- advertisements
- promotions
- payment offers
- news
- marketing
- unrelated mobility products

### 4.2 Speed is a feature

Common interactions should feel nearly immediate. Targets for normal operation:

- Application startup: <2 seconds perceived
- Search results: <500 ms after backend response/cache
- Saved-place selection: immediate
- Route request: target <2 seconds
- Route screen interactions: 60 FPS where practical

### 4.3 Realtime should be understandable

The application must distinguish between:

- Scheduled time
- Realtime prediction
- Delay
- Cancelled trip
- Unknown realtime state

It should never make uncertain realtime information look authoritative.

### 4.4 Open-source architecture

Core application functionality should not require proprietary transportation APIs where an open/public alternative exists. External services should be replaceable behind interfaces. The architecture should avoid creating a hidden dependency on a single commercial provider.

### 4.5 The API is the product first

Until the backend is finished, the backend *is* OpenTransit. No client work begins until the API can plan a real multi-modal journey with live delays, fast, in production. The reasons are practical:

- Every client — mobile, web, a future watch app, a contributor's script — is a thin renderer over the same API. Building the client first would mean building the interesting half twice.
- Speed is decided in the backend. A client cannot make a slow API feel fast, but a fast API makes a mediocre client feel excellent.
- The API is testable from a terminal. The whole of Phase 1 can be verified with `curl` and a load generator, with no simulator, no app store and no UI work.

The system design that follows from this is specified in [docs/system-design.md](docs/system-design.md), which carries one hard rule: **no request on the hot path may make a call that leaves the machine.**

### 4.6 Speed targets belong to the backend

The client-side targets in §4.2 are downstream of these server-side ones, measured at the API process:

| Endpoint | p95 |
| --- | --- |
| Place search / autocomplete | 40 ms |
| Journey planning | 350 ms |
| Stop departures | 40 ms |
| Live vehicle positions | 25 ms |

A journey request must never touch a database, an external HTTP service, or another host.

---

## 5. Phase 0 — Feasibility POC

### 5.1 Purpose

**Phase 0 is mandatory.**

No production app should be developed until the fundamental transportation-data stack has been proven. The purpose of this phase is to answer:

> Can an independent application actually obtain enough usable Israeli transportation data to reproduce the core journey-planning functionality?

This POC should intentionally have almost no UI. A CLI, Swagger page, test harness, or extremely basic debug webpage is sufficient.

#### Hard rule

**Frontend product development does not begin until Phase 0 passes — and then not until the API of Phase 1 is finished.** Phase 0 proves the data can be had; Phase 1 turns it into a fast service; only Phase 2 draws a screen.

### 5.2 Access prerequisites (added 28 Aug 2026)

Phase 0 is not one sequence. It splits into a track that needs nobody's permission and a track gated on a human at the Ministry answering an email. See [docs/data-access-findings.md](docs/data-access-findings.md) for the evidence.

- **Static GTFS is open and verified.** `https://gtfs.mot.gov.il/gtfsfiles/` serves the nationwide feed over unauthenticated HTTP, updated nightly. POC-1, POC-2 and POC-5 are unblocked and can start immediately.
- **SIRI and Service Alerts are not public.** Both require an application to MOT at `ptsupport@mot.gov.il`, which returns a base address, a RequestorRef and an access key by email. The SIRI hosts additionally refuse connections from non-permitted networks, so the realtime ingester likely needs a whitelisted (probably Israeli) egress IP.
- **Blocking first action:** send that request now, asking in the same email for (a) SIRI-SM 2.8 access, (b) the Service Alerts feed URL, (c) whether the key is bound to a source IP, and (d) the usage terms for an open-source, publicly distributed application.
- **Decision deadline:** if there is no usable answer within four weeks, Phase 0 must explicitly choose between Open Bus Stride as a permanent dependency, a static-only planner, or stopping under kill criterion #3.

---

## 6. POC-1 — Static Israeli transportation data

### Source

Primary source: **Israeli Ministry of Transport GTFS**

The Ministry currently publishes nationwide GTFS data containing planned transportation information such as trips, stops, routes, schedules and related data.

### Test

Automatically:

1. Download latest GTFS.
2. Extract it.
3. Parse:
   - agencies
   - routes
   - trips
   - stops
   - stop times
   - calendar/service information
   - shapes
4. Insert/query the data.
5. Verify that several known Israeli lines and stations exist.

### Required validation examples

Verify data for at least:

- Tel Aviv
- Jerusalem
- Haifa
- Israel Railways
- Multiple bus operators

### PASS

The latest official dataset can be downloaded, parsed, understood, queried and refreshed automatically, without manual editing.

### FAIL / STOP

The project does not continue if nationwide schedule data cannot legally and technically be consumed reliably.

### Status — 28 Aug 2026

Access confirmed. `https://gtfs.mot.gov.il/gtfsfiles/` is an open HTTP directory, no key required; `israel-public-transportation.zip` (~157 MB) and `Gtfs_10_days.zip` (~249 MB) were both rewritten within the last 24 hours. Two implementation notes: `HEAD` on the zip returns a bogus `Content-Length`, so use `GET` plus zip validation for change detection; and `TripIdToDate.zip` is a separate download that must be versioned in lockstep with the main feed, because it is the key to realtime matching. The only open item is recording the exact licence text attached to the dataset.

---

## 7. POC-2 — Public Transportation Routing

The system must prove that Israeli GTFS can be converted into an actual journey-planning graph.

### Preferred approach

Use an existing open-source routing engine rather than writing transit routing from scratch.

- Initial candidate: **MOTIS**
- Alternative: **OpenTripPlanner**

The routing engine should be self-hostable.

Transitous currently operates a FOSS public-transport routing platform using MOTIS and already has working Israeli static GTFS coverage, making it useful as both reference architecture and comparison implementation.

### Required test

Given:

```text
Origin coordinates
Destination coordinates
Departure time
```

the routing engine must return:

```text
Walk → Transit → Transfer → Transit → Walk
```

where appropriate.

### Test journeys

At minimum test:

1. Tel Aviv → Ramat Gan
2. Tel Aviv → Petah Tikva
3. Tel Aviv → Haifa
4. Tel Aviv → Jerusalem
5. A bus → train journey
6. A train → bus journey
7. Journey with at least one transfer
8. Journey late at night
9. Journey crossing a service-day boundary
10. Journey where no reasonable transit route exists

### Validate against

Compare results manually against Moovit, Google Maps, and BetterRail where rail is involved. Exact agreement is not required. The goal is to determine whether results are logically correct.

### PASS

At least **9/10 representative journeys produce reasonable usable routes.**

### FAIL / STOP

If Israeli GTFS cannot be reliably routed using a self-hostable open routing engine, investigate another engine before continuing. Do not build the mobile application while this is unresolved.

---

## 8. POC-3 — Realtime Transit Information

This is one of the most important feasibility tests.

The Ministry provides realtime information through **SIRI-SM**, including predicted arrivals for active public-transport trips. The Ministry documentation describes how SIRI identifiers correspond to GTFS identifiers.

- Preferred production source: Israeli Ministry of Transport SIRI.
- Prototype/fallback source: Open Bus Stride.

Open Bus currently exposes endpoints for, among other things: realtime rides, realtime stops, vehicle locations, stop arrivals, GTFS routes, GTFS stops and GTFS rides.

### Required test

For a known active bus:

1. Retrieve realtime information.
2. Identify: route, vehicle, relevant trip, current/predicted stop, expected arrival time.
3. Match realtime data to the corresponding static GTFS data.
4. Display:

```text
Route 18
Scheduled arrival: 18:04
Realtime arrival: 18:11
Delay: +7 min
```

### Vehicle-location test

Where available:

```text
vehicle → latitude/longitude → corresponding route/trip → map position
```

must work.

### Required architecture proof

The application must demonstrate `GTFS trip ↕ Realtime SIRI trip` matching. This reconciliation layer is part of the project's own backend and should be tested carefully.

### Production feasibility requirement

Before Phase 0 is considered fully complete, the project must have either:

**A.** Direct Ministry SIRI access suitable for the project, or
**B.** Another realtime source whose availability, terms and sustainability are acceptable for production.

Open Bus may be used immediately for experimentation, but the project should not accidentally become permanently dependent on a volunteer service without making that an explicit architectural decision.

### FAIL / STOP

If no sustainable realtime information source can be obtained, reassess the product before implementing the main application. A static-only planner may still technically exist, but it would not satisfy the intended product vision.

### Status — 28 Aug 2026

**Blocked on MOT, and this is the project's real gate.** Two locks: the SIRI base address, RequestorRef and key are issued only by email on application to `ptsupport@mot.gov.il`, and both `moran.mot.gov.il` and `moran-t.mot.gov.il` refuse TCP 443 from an ordinary internet host while `gtfs.mot.gov.il` connects from the same machine — so a whitelisted egress IP is likely also required.

Once through, the service is well suited to the product: SIRI-Lite over HTTP GET returning JSON, with `AllActiveTripsFilter` giving nationwide vehicle positions every 15 s, the same filter at `calls` detail giving arrival predictions for all onward stops every 30 s, and `AllPlannedTripsFilter` covering the next 4 hours every 60 s. Minimum 15 s between polls.

Reconciliation has an official answer rather than being guesswork: MOT documents the SIRI↔GTFS field mapping, joining `FramedVehicleJourneyRef` to `TripId` in `TripIdToDate.txt`, `LineRef` to `route_id`, `StopPointRef` to `stop_code` and `Order` to `stop_sequence`. The open question is the match rate in practice.

Note on the fallback: Open Bus Stride is live and serving current SIRI rides, but its GTFS linkage fields (`gtfs_ride_id`, `gtfs_stop_id`) came back null across sampled windows at 8 hours, 3 days and 30 days old. Prototyping there does not avoid writing the matcher ourselves.

---

## 9. POC-4 — Service Alerts

The Ministry separately distributes service changes through **GTFS-Realtime Service Alerts**.

The POC must demonstrate that it can:

1. Download/read the feed.
2. Decode protobuf messages.
3. Identify affected routes, stops and trips.
4. Associate alerts with planned journeys.

Example result:

```text
⚠ Service change
Route 18
Stops: Arlozorov A, Arlozorov B
will not be served between 18:00–21:00.
```

### PASS

An active/recent alert can be parsed and linked to transportation entities.

### Status — 28 Aug 2026

Blocked on the same email as POC-3. The alerts ICD states there is a single service URL and that its details are sent to the developer only on request to `ptsupport@mot.gov.il`. MOT regenerates the package every 5 minutes and asks that it be polled no more than 12 times per hour. Field names are identical to those inside `israel-public-transportation.zip`, so entity resolution against static GTFS is direct once the URL is in hand.

---

## 10. POC-5 — Address and Place Search

Users cannot be expected to enter coordinates. The system must prove that `"Dizengoff Center"` can become `32.075..., 34.774...`, and that `"HaShalom Station"` can resolve to the correct location.

### Requirements

Search must eventually support:

- Hebrew
- English
- Street addresses
- Transit stops
- Train stations
- Major POIs
- Current GPS location

### Initial POC

An OSM-derived geocoder may be used. The public OpenStreetMap Nominatim service may be used only for limited experimentation. Its policy has strict usage restrictions, including a maximum of 1 request/second and prohibition of client-side autocomplete. Production must therefore use a hosted provider or self-hosted geocoder rather than rely directly on the public endpoint.

### PASS

At least 20 representative Israeli queries resolve correctly enough to start routing.

---

## 11. POC-6 — End-to-End Journey

This is the actual Phase 0 acceptance test. Create one command or debug interface:

```text
route --from "Dizengoff Center" --to "Technion" --depart-now
```

The system must perform:

```text
Address search → Coordinates → Transit routing → GTFS journey
→ Realtime enrichment → Service-alert enrichment → Final journey response
```

Example:

```text
17:42  Walk 5 min
17:47  Bus 5
       Ibn Gabirol → Savidor
       Realtime: 3 min late
18:01  Walk 4 min
18:08  Train
       Tel Aviv Savidor → Haifa Center
       On time
19:12  Bus 17
       Haifa Center → Technion
19:32  Arrive

Alert: None
Realtime coverage: Bus 5 live / Train live / Bus 17 live
```

It does not have to look good. It must be **real**.

---

## 12. Phase 0 Go / No-Go Criteria

Phase 0 is considered **PASS** only when all critical dependencies have been demonstrated.

| Capability | Required |
| ---------- | -------- |
| Download current nationwide GTFS | ✅ |
| Parse GTFS | ✅ |
| Route using Israeli GTFS | ✅ |
| Walking + transit + transfers | ✅ |
| Obtain realtime arrivals | ✅ |
| Match realtime ↔ GTFS | ✅ |
| Obtain service alerts | ✅ |
| Resolve Israeli addresses/places | ✅ |
| Run full end-to-end query | ✅ |
| Confirm acceptable data usage terms | ✅ |

Only after this table is completely green should application development begin.

---

## 13. POC Deliverable

Create a repository area `/poc` containing:

```text
/poc
    /gtfs
    /routing
    /realtime
    /alerts
    /geocoding
    /integration-tests
    docker-compose.yml
    README.md
```

The README should contain:

### Dependency status

```text
MOT GTFS           ✅
Routing            ✅
Realtime SIRI      ✅
Alerts             ✅
Geocoder           ✅
OSM                ✅
```

### Tested journeys

Document every test journey and its result.

### Known data problems

```text
MOT GTFS translations.txt requires sanitization
SIRI sometimes missing VehicleRef
Some trips cannot be realtime matched
...
```

This becomes the technical foundation of the project.

---

## 14. Phase 1 — OpenTransit API v1

After POC success, the first product is **the backend API**, not an app. It is finished, deployed, documented and fast before any client exists.

Full architecture, deployment topology, cost model and build order: [docs/system-design.md](docs/system-design.md). The summary:

### What gets built

A single self-hostable backend that answers transport questions over HTTP:

```
GET  /v1/places?q=&lang=he|en&near=          address, stop and POI search
GET  /v1/journeys?from=&to=&departAt=        multi-modal journey planning
GET  /v1/stops/{stopCode}/departures         live departure board
GET  /v1/trips/{tripId}                      stop sequence with live progress
GET  /v1/vehicles?bbox=                      live positions
GET  /v1/alerts                              service alerts
GET  /v1/status                              public feed health
```

Behind it: MOTIS holding the routing graph in RAM on the same host, an in-memory realtime snapshot replaced wholesale every 15–30 seconds, an in-process index of every Israeli transit stop for fast search, and a single privileged ingester that is the only process holding the MOT key.

### Architectural rules for this phase

1. **Nothing on the hot path leaves the machine.** Not Postgres, not S3, not MOT, not another availability zone.
2. **Realtime is a pointer swap, not a query.** The ingester builds a complete immutable snapshot and atomically replaces the previous one; readers never lock.
3. **Postgres is off the hot path entirely.** It holds history and analytics. A journey request never opens a database connection.
4. **One ingester, ever.** MOT permits one poll per 15 seconds on a single key. A second poller risks the key.
5. **The whole stack runs from fixtures.** Contributors have no MOT key, so `docker compose up` must run everything against recorded data.
6. **Storage is S3-compatible, never S3-specific.** AWS S3, Cloudflare R2, Backblaze, Hetzner or local MinIO must all work unchanged.
7. **It runs on one 8 GB box.** MOTIS loads a country's full-year timetable in under 2 GB, so the whole stack fits comfortably on a single small instance. If a design decision requires more than that, it needs a reason. Cost is a design constraint, not an afterthought — see the price-range comparison in [docs/system-design.md](docs/system-design.md#6-deployment-and-cost).

The practical consequence: **Phase 0 costs $0–12/month** (everything on the dev machine, plus at most a tiny Israeli VPS for the SIRI ingester once the key arrives), and **a free-to-the-public v1 costs $40–75/month** — roughly flat whether the service has 100 users or 50,000, because the routing graph is built once and shared.

### Milestones

| # | Milestone | Done when |
| --- | --- | --- |
| M1 | Skeleton | `docker compose up` serves `/healthz`; OpenAPI published; CI green |
| M2 | GTFS ingest | nightly download, validation and versioning to object storage; `/v1/stops` works |
| M3 | Routing | MOTIS wired; `/v1/journeys` returns schedule-only itineraries |
| M4 | Search | `/v1/places` in Hebrew and English, p95 under 40 ms |
| M5 | Realtime | snapshot swap live; delays on journeys and departures; `/v1/vehicles` |
| M6 | Alerts | `/v1/alerts` and per-journey attachment |
| M7 | Hardening | atomic graph swap, degradation ladder, `/v1/status`, load test at 50 rps |
| M8 | Deploy | live in the Israel region on the registered IP, public docs and status page |

### Phase 1 acceptance

> A plain `curl` plans Dizengoff Center → Technion with live delays in under **400 ms p95**, repeatedly, on a weekday evening, against real data — served from a deployed environment, not a laptop.

Only then does a client get written.

---

## 15. Phase 2 — Minimum Usable Product (first client)

With the API finished, build the first client that can replace Moovit for basic everyday use. The client is deliberately thin: it renders what `/v1` returns and holds no transport logic of its own.

### Home

Show `Where to?` plus:

- Current location
- Home
- Work
- Recent destinations
- Favorite destinations

No advertisements.

---

## 16. Destination Search

Search:

```text
Haifa University
Dizengoff Center
Allenby 30
Savidor
```

Results should combine addresses, POIs, transit stations and saved places. Search must support Hebrew and English.

---

## 17. Journey Results

Show approximately three useful alternatives. Each journey displays departure, arrival, total duration, walking duration, transfers, lines, realtime state, delays and service alerts.

```text
BEST
38 min
Walk 4m → 18 → 66 → Walk 2m
Leave 17:42  Arrive 18:20
Live
```

Alternative:

```text
42 min
Walk 8m → 51 → Walk 3m
No transfers
```

---

## 18. Journey Detail

Selecting a journey shows a timeline.

```text
17:42  Walk 450m
17:48  Bus 18
       Arlozorov → Namir
       Expected 17:51  (+3 min delay)
18:07  Get off, walk 180m
18:12  Bus 66
18:24  Destination
```

The user should immediately understand: where to walk, which stop, which line, direction, when it should arrive, where to exit, and the next transfer.

---

## 19. Live Journey Mode

Once a user starts a trip:

```text
NEXT
Walk 180m to Arlozorov / Ibn Gabirol
Bus 18 arriving in 4 min
```

Then:

```text
ON BUS 18
6 stops remaining
Get off: Namir / Yehuda HaMaccabi
```

GPS tracking should primarily happen on-device where practical. Server-side location history should not be required.

---

## 20. Stops

Selecting a stop displays:

```text
ARLOZOROV / IBN GABIROL
18   3 min
18   12 min
70   6 min
82   9 min
```

Clearly distinguish realtime from schedule. Allow **Favorite stop**.

---

## 21. Vehicles

Where live location exists, show the current vehicle position. This should be considered useful supplementary information rather than the main interface.

---

## 22. Favorites

Store locally initially: Home, Work, favorite places, favorite stops, recent searches.

No account required. Cloud synchronization is not required for V1.

---

## 23. Map

Use an open map stack. Recommended: **MapLibre + OpenStreetMap-derived data**.

The app should display current location, walking route, transit route, stops, transfer points, destination and optional live vehicle. MapLibre provides open-source web and native map-rendering libraries.

---

## 24. Backend Responsibilities

> Detailed architecture, hosting decisions, latency budget and build order live in [docs/system-design.md](docs/system-design.md). This section states the requirement; that document states the design.

The client should not communicate directly with all external transportation providers. Create a unified backend.

```text
                   APP
                    │
                    ▼
             OpenTransit API
                    │
       ┌────────────┼─────────────┐
       ▼            ▼             ▼
    Routing      Realtime       Search
       │            │             │
       ▼            ▼             ▼
    MOTIS       MOT SIRI       Geocoder
       │
       ▼
   GTFS + OSM
```

The OpenTransit API becomes the abstraction layer.

---

## 25. Suggested Backend Modules

```text
Transit.Api
Transit.GTFS
Transit.Realtime
Transit.Routing
Transit.Alerts
Transit.Geocoding
Transit.Search
Transit.Journeys
Transit.Infrastructure
```

Implementation language is not a product requirement. Python, C#, Go, TypeScript or another suitable backend language may be chosen based on engineering goals.

---

## 26. Data Pipeline

GTFS should be downloaded automatically.

```text
MOT → download → validate → normalize → version → routing graph
```

Never silently replace the active dataset with an invalid feed. Recommended deployment model:

```text
current graph stays online
        │
        ▼
new GTFS → validate → build new graph → health check → atomic swap
```

If the new feed fails validation, continue using the previous valid version.

---

## 27. Realtime Pipeline

```text
MOT SIRI → fetch / ingest → normalize → GTFS reconciliation → cache/state → journey API
```

The backend should maintain a normalized internal representation rather than leak SIRI structures throughout the application.

```json
{
  "tripId": "...",
  "vehicleId": "...",
  "delaySeconds": 220,
  "expectedArrival": "...",
  "location": {}
}
```

---

## 28. Route Ranking

The underlying routing engine should generate candidate journeys. OpenTransit may eventually provide its own ranking layer.

Initial factors: travel duration, walking, transfers, departure time, arrival time.

Later: realtime delay, transfer risk, historical reliability, journey complexity, preferred modes, walking preference.

This is an important potential area of original engineering.

---

## 29. Phase 3 — Realtime-Aware Routing

Instead of merely displaying realtime information after route generation, use realtime state when ranking journeys.

**Candidate A** — 37 minutes, 2 transfers. But: bus delayed 9 min, transfer window = 2 min.

**Candidate B** — 42 minutes, 0 transfers, bus delayed 1 min.

The system may rank B above A. This is where OpenTransit begins providing functionality beyond a basic routing-engine frontend.

---

## 30. Phase 4 — Reliability Intelligence

Build historical transportation statistics using collected/open data.

```text
Typical delay: +4 min
Reliability: 82%
Transfer success probability: 63%
```

Later journey ranking can optimize for the *fastest realistic journey* rather than the *mathematically fastest scheduled journey*.

---

## 31. Non-Goals

The initial product will NOT include: transit payment, Rav-Kav management, credit cards, taxi ordering, scooter ordering, bike rental, car sharing, ride sharing, advertising, loyalty programs, social feeds, chat, AI assistant, user-generated posts, complex account systems.

Do not add these without a clear transportation benefit.

---

## 32. Privacy

V1 should work without an account. Prefer:

```text
location → route query → response → discard
```

Avoid unnecessary storage of continuous GPS history, commute history, home address, work address, identity.

Favorites may initially stay on-device.

---

## 33. Open Source

Suggested repository structure:

```text
opentransit-israel/
  apps/
    mobile/
    web/
  services/
    api/
    realtime/
    ingestion/
  infra/
  docs/
  poc/
```

Repository should include local development instructions, Docker Compose, architecture diagram, API specification, contribution guide, issue templates and data-source documentation.

A new contributor should eventually be able to run a development version without private knowledge from the original author.

---

## 34. Reliability Requirements

Transportation data will sometimes be incorrect. The system must expect missing realtime, malformed GTFS, delayed updates, duplicated trips, unexpected identifiers, unavailable APIs, impossible coordinates, stale vehicle positions and schedule/realtime mismatches.

External data should always be treated as potentially unreliable. The application should degrade gracefully:

```text
Realtime unavailable
Using scheduled arrival
```

rather than fail.

---

## 35. Observability

Backend should eventually track GTFS age, last successful GTFS ingestion, realtime feed health, realtime lag, matched/unmatched realtime trips, routing latency, routing failures, geocoding latency and API error rate.

Example internal health page:

```text
GTFS                      Healthy, updated 03:20
SIRI                      Healthy, last update 8 sec ago
Realtime trip matching    96.3%
Routing                   p95 840ms
Geocoder                  Healthy
```

This is important for a service people depend on to physically get somewhere.

---

## 36. Development Milestones

### Phase 0 — Feasibility (GO / NO-GO)

GTFS ingestion, routing, realtime, alerts, geocoding, end-to-end integration. Two tracks: one unblocked today, one gated on MOT granting SIRI access. No frontend, and no backend architecture work beyond what a proof requires.

Ends with: a signed-off go/no-go table, and a decision about the realtime source.

### Phase 1 — OpenTransit API v1

The backend, finished and deployed. Journey planning, place search, departures, vehicles and alerts over HTTP, fast enough to be pleasant from a terminal.

Goal:

> `curl` plans Dizengoff Center → Technion with live delays in under 400 ms p95, from a deployed environment.

No client of any kind is written during this phase.

### Phase 2 — First client, replacing Moovit for basic personal use

Mobile app, search, route planning, map, journey details, realtime arrivals, service alerts, favourites — all of it a thin renderer over `/v1`.

Goal:

> The developer can realistically use OpenTransit instead of Moovit for normal journeys.

### Phase 3 — Better realtime

Live journey mode, vehicle positions, realtime-aware ranking, better transfer handling. Ranking moves into the backend, where the realtime state already lives.

### Phase 4 — Better than schedule-based planners

Historical reliability, delay statistics, transfer confidence, smarter journey ranking — built on the archived SIRI observations the ingester has been collecting since Phase 1.

### Phase 5 — Public open-source product

Stable deployment, CI/CD, contributor documentation, public issue tracker, monitoring, scalable infrastructure, app store distribution.

---

## 37. Primary Success Metric

The most important initial success metric is not downloads. It is:

> **Can the developer use OpenTransit Israel every day without needing to open Moovit?**

If the answer is yes, the core product works.

Because the app now arrives a phase later, Phase 1 has its own single metric:

> **Is the API fast and truthful enough that a client would only have to render it?**

Concretely: journey planning at p95 under 350 ms server-side, realtime snapshot lag under 45 s, and a SIRI↔GTFS match rate above 90 % — all three visible on the public `/v1/status` endpoint rather than asserted in a document.

Secondary metrics later: route searches per active user, percentage of journeys with realtime coverage, routing success rate, crash-free sessions, route-result latency, returning users, GitHub contributors, GitHub stars, issues resolved.

---

## 38. Phase 0 Kill Criteria

The project should deliberately stop or significantly change direction if any of the following proves impossible:

1. Nationwide GTFS cannot be sustainably consumed.
2. No practical routing engine can correctly process Israeli transportation data.
3. No sustainable realtime source can be obtained.
4. Realtime data cannot be matched to static trips reliably enough to be useful.
5. Required transportation datasets cannot legally be used for the intended open-source application.
6. A fundamental dependency requires an unsustainable commercial service.

Discovering one of these during Phase 0 is a successful POC outcome. The purpose of a feasibility test is to discover fatal problems **before** months are spent building the product.

---

## 39. Definition of POC Success

Phase 0 ends with one deliberately ugly demonstration. The developer enters:

```text
From: Dizengoff Center
To: Technion
Departure: Now
```

and the system returns a legitimate multi-modal Israeli public transportation journey containing:

```text
✓ Geocoded locations
✓ Walking legs
✓ Bus/train legs
✓ Correct stops
✓ Correct scheduled times
✓ Transfers
✓ Realtime arrivals
✓ Current delays
✓ Service alerts
✓ Journey geometry
```

All data must come from services and datasets that have a credible path to use in the real application.

**Only then does development of the actual OpenTransit Israel app begin.**
