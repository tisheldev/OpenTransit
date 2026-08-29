# OpenTransit Israel — System Architecture

**Status:** Proposed architecture, v1
**Scope:** the whole system — backend, data planes, boundaries and their contracts
**Written:** 28 August 2026

### How this document relates to the others

| Document | Answers |
| --- | --- |
| [PRD.md](../PRD.md) | *What* the product is, and which phases gate which |
| [docs/system-design.md](system-design.md) | *How much, how fast, how deployed* — latency budget, hosting, cost, build order |
| **this document** | *What shape the system is, and why that shape* — components, boundaries, invariants, flows |

Where the three disagree, the PRD wins on scope, the system design wins on numbers, and this document wins on structure.

---

## 1. What the system actually is

Strip away the framing and OpenTransit is one thing:

> **An in-memory answering machine for Israeli transit, wrapped in an HTTP API, kept current by a single background process.**

Not a database application. Not a proxy in front of the Ministry of Transport. The system's entire job is to hold a correct, current picture of Israeli public transport in RAM, and to answer questions against that picture without going anywhere to do it.

Everything difficult about the architecture is the word *current*. A schedule that changes nightly and a realtime feed that changes every 15 seconds have to be folded into one picture that a request can read in microseconds, without the request ever waiting on either feed.

That produces the single organizing idea of the whole system.

---

## 2. The organizing idea: two paths, one direction of flow

The system is split in two, and every component belongs to exactly one side.

```
COLD PATH — slow, scheduled, allowed to fail
    downloads feeds, validates them, builds graphs, polls SIRI,
    reconciles trips, archives history
                    |
                    |  produces immutable data structures
                    v
HOT PATH — fast, per-request, never allowed to block
    reads those structures with a pointer dereference
    and serializes an answer
```

Data flows one way across that line. The hot path never asks the cold path for anything; it only ever reads what the cold path has already finished building. There is no request-time fetch, no lazy load, and no cache miss that goes to the network.

Two rules make it real, and they are the two worth defending in code review:

1. **No request on the hot path may make a call that leaves the machine.** Not to Postgres, not to object storage, not to MOT, not to another availability zone.
2. **Nothing on the hot path mutates shared state.** New data arrives as a whole new immutable object that atomically replaces the old one. Readers never lock, never coordinate, and never see a half-updated world.

Almost every specific decision below is downstream of those two sentences. If a proposed change violates either, it is the change that is wrong, not the rule.

### Why this is worth the discipline

A transit app is used in a doorway, in the rain, with one thumb, deciding whether to run for a bus. The felt quality of the product is almost entirely latency and honesty. Conventional architecture — query the database, call the upstream, cache the result — puts a network round trip and a cache-miss cliff in front of every one of those moments. Holding the country in memory removes the cliff entirely: Israel's transit network is small enough that the fast version is also the simple version.

---

## 3. The four data planes

It helps to stop thinking about components for a moment and think about the four kinds of data the system holds. Each has a different lifetime, a different failure mode, and a different owner.

| Plane | Contents | Changes | Lives in | If it goes stale |
| --- | --- | --- | --- | --- |
| **Schedule** | GTFS: routes, trips, stops, calendars, shapes | nightly | MOTIS graph + in-process stop index | journeys are wrong by a timetable revision — serious, slow-moving |
| **Realtime** | SIRI: vehicle positions, predicted calls, delays | every 15–30 s | immutable snapshot in RAM | the API must stop claiming "live" and say `scheduled` |
| **Disruption** | GTFS-RT service alerts | every 5 min | immutable alert set in RAM | journeys lose warnings but stay correct |
| **History** | archived SIRI observations, rollups | append-only | object storage + Postgres | nothing user-visible; analytics only |

The planes are deliberately not merged. The schedule plane is large and slow; the realtime plane is small and fast. Keeping them separate is what lets the expensive one be rebuilt nightly while the cheap one is replaced every 15 seconds. A journey response is the *join* of the first three planes, performed per request, in memory, in about a millisecond.

The fourth plane exists only so that Phase 4 has something to learn from. It is architecturally inert: **no user-facing request may ever read it.** That constraint is what keeps a Postgres outage from being an outage at all.

---

## 4. The architecture, by layer

```
+----------------------------------------------------------------------+
|  CLIENTS      mobile . web . curl . contributor scripts              |
|               thin renderers; they hold no transport logic           |
+-------------------------------+--------------------------------------+
                                | HTTPS, /v1, OpenAPI contract
+-------------------------------v--------------------------------------+
|  EDGE         TLS, compression, edge cache, WAF, Israeli PoP         |
+-------------------------------+--------------------------------------+
                                |
================================v======================================
   HOT PATH                                   one host, Israel region

    Transit.Api  -- stateless per user, stateful per transit
      |- realtime snapshot    immutable, swapped every 15-30 s
      |- alert set            immutable, swapped every 5 min
      |- stop/station index   ~30-40k entries, he + en, rebuilt nightly
      \- LRU caches           geocode results, journey shells
               | loopback only
    MOTIS  -- timetable + street graph + geocoding, ~2-4 GB RAM
=======================================================================
   COLD PATH

    Transit.Ingest -- exactly one process, sole holder of the MOT key
      |- SIRI poller     15-30 s -> reconcile -> snapshot -> publish
      |- Alerts poller   5 min   -> decode -> resolve entities
      \- GTFS builder    nightly -> validate -> build graph -> swap
               |
    Redis -- snapshot fan-out to N API instances; never a source of
             truth. If it dies, each instance serves its last snapshot.
================================+======================================
                                |  cold path only, never per request
                +---------------+----------------+
                v               v                v
     +------------------+ +-----------+ +------------------+
     | MOT              | | Object    | | Postgres+PostGIS |
     | gtfs . SIRI . RT | | storage   | | history,         |
     | (whitelisted IP) | | S3-compat | | analytics        |
     +------------------+ +-----------+ +------------------+
```

Read that as a statement about *permission*, not only topology. Anything below the second double line is something the hot path is forbidden to touch while a request is in flight.

---

## 5. The components, and what each is forbidden to do

Describing a component by its prohibitions turns out to be more useful than describing it by its features, because the prohibitions are what the architecture is actually made of.

### Transit.Api

The only public surface. Resolves places, calls MOTIS, overlays realtime and alerts, ranks, serializes.

- *Holds:* hundreds of megabytes of transit state in RAM, deliberately.
- *Never:* opens a database connection, calls MOT, calls object storage, or keeps per-user state on a request path.
- *Never:* leaks an upstream structure. No SIRI field name and no MOTIS type appears in a response body. The normalized model is the product; the upstreams are implementation detail, and one of them will eventually be replaced.

### MOTIS

The routing engine, as a sidecar on loopback. Holds the timetable and street graph, answers RAPTOR queries in tens of milliseconds, and probably also serves geocoding and tiles from data it has already loaded.

- *Never:* reached over a network hop. It sits on `127.0.0.1` because it is the only genuinely expensive step in a journey request, and every millisecond of transport added to it is a millisecond added to the product's slowest endpoint.
- *Replaceable:* behind `IJourneyPlanner`. OpenTripPlanner is the standing alternative. This is the largest single dependency in the system, so it is the one most deliberately wrapped.

### Transit.Ingest

One process. The only component holding the MOT key.

- *There is exactly one.* MOT permits one poll per 15 seconds on a single key; a second poller risks the key, and the key is a relationship with a government office rather than a credential that can be reissued at will.
- *Never:* serves a request. It writes snapshots and artifacts; it does not answer questions.
- *Owns reconciliation.* SIRI↔GTFS matching happens here, once per snapshot, not per request.

### Redis

Fan-out and short-TTL shared cache.

- *Never:* the source of truth for anything. Its complete failure degrades the system to "each API instance serves the last snapshot it received" — a mild, bounded, self-healing condition.

### Postgres + PostGIS

Cold storage: static metadata, archived realtime, Phase 4 reliability statistics.

- *Never:* on the hot path, in any phase, for any endpoint.
- *Deliberately incomplete:* the 60-day feed's `stop_times` is on the order of a hundred million rows and is not loaded, because MOTIS already answers both journeys and departures from RAM. Loading it would buy nothing and cost the instance size.

### Object storage

Everything durable and immutable, addressed by content hash: raw feeds exactly as MOT served them, normalized Parquet, built graphs, SIRI archives, alert packages, contributor fixtures.

- *S3-compatible, never S3-specific.* Reached through `IObjectStore`, so R2, B2, Hetzner or a local MinIO substitute without a code change.
- *Content-addressed on purpose.* A graph built from feed `a1b2…` is reusable on redeploy, buildable on a laptop, shippable to production, and impossible to confuse with a graph built from a different feed.

---

## 6. Modules, and the seams that matter

The PRD's module list (§25) maps onto the architecture like this:

```
Transit.Api             HTTP surface, contract-first from OpenAPI
Transit.Journeys        orchestration + ranking       <- the product's own logic
Transit.Routing         IJourneyPlanner               <- MOTIS | OTP
Transit.Realtime        IRealtimeSource               <- MotSiri | Replay
Transit.Alerts          IAlertSource                  <- MotGtfsRt | Replay
Transit.Geocoding       IGeocoder                     <- Motis | Photon
Transit.Search          in-process stop/POI index
Transit.GTFS            download, validate, normalize, version
Transit.Infrastructure  IObjectStore, clock, config, telemetry
```

Four interfaces carry essentially all of the architectural risk, and they exist because each has a live chance of needing to be swapped:

- **`IJourneyPlanner`** — the routing bake-off is still open (system-design §11).
- **`IRealtimeSource`** — MOT access is not yet granted; Open Bus Stride and replayed fixtures are the alternatives, and choosing between them is Phase 0's headline decision.
- **`IGeocoder`** — whether MOTIS's own geocoder handles Hebrew addressing well enough decides whether an entire Elasticsearch dependency exists.
- **`IObjectStore`** — provider independence is a stated principle, and it is only real if it is compiled.

Everywhere else, prefer concrete types. An interface with exactly one implementation and no plausible second one is a cost, not a design.

`Transit.Journeys` deserves its own note: it is the only module containing original product logic rather than integration. Ranking — Phase 1 lightly adjusted, Phase 3 realtime-aware, Phase 4 reliability-aware — is where OpenTransit stops being a pleasant frontend for a routing engine. It lives in the backend because that is where the realtime state already is.

---

## 7. How a request flows

### `GET /v1/journeys`

```
 1  parse + validate                        ~1 ms
 2  resolve from/to                         ~2 ms   in-process index -> LRU -> geocoder
 3  MOTIS query over loopback            40-250 ms  <- the only expensive step
 4  overlay realtime                        ~1 ms   hash lookups into the snapshot
 5  overlay alerts                          <1 ms   entity match against the alert set
 6  rank                                    ~1 ms
 7  serialize normalized response           ~5 ms
                                       -------------
                                        50-260 ms
```

Step 3 being the only slow step is the point of the whole design: performance work has exactly one target, and it is a component already optimized by other people for exactly this workload.

### `GET /v1/stops/{code}/departures`

One dictionary lookup into the current snapshot, which already holds pre-sorted departure boards keyed by stop code, merged against the schedule. No routing, no query planning — single-digit milliseconds.

### `GET /v1/places`

Tiered, cheapest first: the in-process index of every Israeli stop and station covers roughly 90 % of what people type into a transit app; free-text street addresses fall through to the geocoder on loopback. The public Nominatim service is never used in production, because its policy forbids precisely the autocomplete pattern this product needs.

---

## 8. How data flows

### Every 15–30 seconds — the snapshot swap

```
fetch SIRI (all active trips, with calls)
    -> parse
    -> reconcile against TripIdToDate and the active feed
    -> build a NEW immutable snapshot
          trip key   -> realtime state
          stop code  -> sorted stop visits
          vehicle    -> position
          recordedAt, lag, matched/unmatched/ambiguous counts
    -> sanity-check entity counts against the previous snapshot
    -> publish to Redis  ->  each API instance rebuilds its local copy
    -> atomically exchange the pointer
```

Readers do `var snap = _current;` and are finished. The old snapshot is collected once its in-flight requests drain. This is why realtime enrichment costs about a millisecond instead of a network call.

### Every 5 minutes — alerts

Fetch, decode protobuf, resolve affected routes/stops/trips against the active feed, build a new immutable alert set, swap. Same pattern, slower clock.

### Nightly — the graph build, with an atomic swap

```
download feed + TripIdToDate  ->  hash  ->  seen before? stop
archive the raw bytes
validate      zip integrity . required files . row counts within +/-20 %
              . landmark stops and lines resolve . service dates cover today+10
normalize     encoding . translations sanitation . coordinate sanity
build graph   -> store under the feed hash
start a second MOTIS on the new graph
health-check it against ~20 known journeys
flip the routing upstream                       <- the swap
drain the old container . rebuild the stop index
```

**A bad feed must never be able to take the service down.** The failure mode of a validation error is "yesterday's data plus an alert", never "no data". This is the same invariant as the realtime snapshot on a nightly clock: build the new thing completely, prove it, then swap a pointer.

### Continuously — the archive

Raw SIRI snapshots land compressed in object storage on a rolling 7-day window and roll up daily into one Parquet row per (trip, stop): scheduled, observed, delay, vehicle, match status. That rollup is the entire input to Phase 4, it is small enough to query with DuckDB directly against object storage, and it starts accumulating in Phase 1 — years before it is needed — because it cannot be backfilled.

---

## 9. Truthfulness as an architectural property

PRD §4.3 asks the product never to make uncertain realtime look authoritative. That is not a UI concern; it is a data-model concern, and it is enforced in the backend:

- Every snapshot carries `recordedAt` and its own coverage statistics.
- Every transit leg carries `scheduled`, `expected`, `delaySeconds` and `realtimeState ∈ {live, stale, scheduled, unknown}`.
- `expected` is never silently set equal to `scheduled`. If there is no live data, the state says so and the client renders it differently.
- When the snapshot ages past its threshold — 90 seconds by default — the API stops claiming live data across the board rather than serving confident nonsense.
- `/v1/status` is public, because a service people rely on to physically get somewhere should be honest about its own state.

The reconciliation match rate is the most important single number in the system. It is the share of SIRI observations successfully joined to GTFS trips, it is reported per snapshot, and it is the earliest possible warning that an upstream change has quietly broken the product. Below 90 % it warns; below 70 % it pages.

---

## 10. Failure is a designed-for state

External transport data is unreliable by nature: missing realtime, malformed GTFS, duplicated trips, unexpected identifiers, impossible coordinates, stale positions. The architecture assumes this and degrades in defined steps instead of failing.

| What breaks | What the user sees |
| --- | --- |
| Realtime stale | schedule-based times, every leg marked `scheduled`, state visible in `/v1/status` |
| Alerts feed down | journeys without warnings, `alerts: degraded` |
| Geocoder down | stop and station search still works from the in-process index; street addresses return a typed error |
| Redis down | nothing — each API instance serves its own last snapshot |
| Postgres down | nothing at all |
| New GTFS invalid | nothing — the previous graph keeps serving, the operator is paged |
| MOT key revoked | the ladder above, plus an immediate page; this is the one that needs a human |
| MOTIS down | a real outage — which is exactly why it sits on the same box with nothing between it and the API |

Exactly one row of that table is a genuine outage. That is the design goal: collapse the number of ways the service can be *down* to one, and make every other failure a documented, visible reduction in capability.

---

## 11. Runtime shape, and what happens when it grows

**Today:** one 8 GB box in the Israel region, an edge in front, and object storage behind. MOTIS loads a country's full-year timetable in under 2 GB; Israel is small by that standard. The whole stack — API, routing, Redis, ingester — fits comfortably, and the cost is roughly flat between 100 and 50,000 users because the expensive artifact, the graph, is built once and shared by every request.

**Scaling, when it is needed,** happens in this order, and the architecture is already shaped for each step:

1. **More API instances behind the edge.** They are identical, stateless in the user sense, and each holds its own copy of the snapshot fed by Redis. The ingester stays singular.
2. **Split the ingester onto its own host.** Already designed for — if MOT requires a whitelisted Israeli IP while cheaper compute lives elsewhere, the ingester runs on a small Israeli VPS and publishes to Redis and object storage. It costs roughly 55–70 ms of extra latency for Israeli users; prefer one box while the prices are this close.
3. **Move graph builds off the serving box.** Content-addressed storage means a graph built on a laptop or a spot instance is byte-identical to one built in production.

What the architecture will *not* do is shard by geography or split the API into a service per endpoint. Israel is one metropolitan-scale transit network; the entire point is that it fits in memory on one machine. Distribution would add coordination cost to buy capacity nobody needs.

---

## 12. Developing without the key

Contributors will not have MOT credentials, and Phase 0 may end without them either. That is a designed-for case rather than a wall:

- `IRealtimeSource` and `IAlertSource` each have a `Replay` implementation.
- The repo ships fixtures: a small GTFS extract, `TripIdToDate` rows, a few hours of recorded SIRI snapshots, a sample alerts package.
- `docker compose up` runs the entire stack against fixtures, with a clock pinnable to the fixture window, so tests are deterministic.
- Integration tests run on fixtures in CI. Only a nightly job in the deployed environment touches live MOT.

This is also the honest hedge against PRD kill criterion 3: if the key never arrives, replay-based development is what keeps the project moving while the decision gets made.

---

## 13. What this architecture is betting on

Every design has load-bearing assumptions. These are the ones that would hurt if they turn out to be wrong, and what each would cost:

| Assumption | If wrong |
| --- | --- |
| Israel's transit graph fits in single-digit GB of RAM | the one-box model goes, and most of the cost story with it |
| MOTIS routes Israeli GTFS well | swap to OTP behind `IJourneyPlanner` — slower and hungrier, but not a rewrite |
| SIRI↔GTFS matches at a usable rate | realtime becomes decorative; PRD kill criterion 4 |
| MOT grants a key on acceptable terms | fall back to Open Bus Stride as an explicit dependency, or ship a static-only planner |
| MOTIS geocoding handles Hebrew | add Photon: +2–4 GB of RAM and an Elasticsearch process |
| A 15–30 s snapshot is fresh enough | shorten the poll, or refresh per trip on demand — the swap pattern survives either |

Three of those six are still open questions that Phase 0 exists to answer, which is the honest reason the architecture keeps them behind interfaces rather than choosing early and pretending.

---

## 14. The short version

If someone reads only one paragraph:

> The country's timetable and its live vehicle feed both live in RAM on one machine. A background process rebuilds them on their own clocks — nightly for the schedule, every 15 seconds for realtime — and each rebuild finishes completely before it atomically replaces the old copy. Requests read those copies and nothing else. Everything durable is content-addressed in object storage, everything historical is off the request path entirely, and every external dependency that might have to change sits behind an interface. Failures reduce what the API can say, and say so out loud, rather than taking it down.
