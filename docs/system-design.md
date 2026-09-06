# OpenTransit Israel — System Design

> **Post-PoC status — 5 September 2026:** Read [the current plan](next-steps.md) before implementing this proposal. ADR 0005 now accepts the 60-day feed plus TripIdToDate; see the current rerun evidence. MOTIS routing/search are PARTIAL pending quality review; Latin addresses need work. Full-stack capacity, 4 GB viability, pricing and daily-user estimates below are unverified. The API runtime, GET/POST journey contract and search solution remain open. No cloud purchase is implied.

**Status:** Design proposal, v1
**Scope:** the backend. The API *is* the product until it is finished; clients come after.
**Written:** 28 August 2026

---

## 0. The one rule

> **No request on the hot path may make a call that leaves the machine.**

Every design decision below follows from that sentence. Journey planning, stop departures, place search and realtime enrichment are all answered from memory or from a process on loopback. Nothing on the hot path talks to Postgres, to S3, to MOT, or to another availability zone.

Everything slow — downloading feeds, building graphs, polling SIRI, archiving snapshots — happens on the cold path, on a schedule, and its only output is a data structure the hot path can read with a pointer dereference.

That split is what makes a transit API feel instant, and it is the thing most transit apps get wrong.

---

## 1. Latency budget

The targets from the PRD (route request under 2s) are far too loose for a backend. These are the real numbers to build against, measured server-side at the API process, Israel region to Israeli client:

| Endpoint | p50 | p95 | p99 |
| --- | --- | --- | --- |
| `GET /v1/places` (autocomplete) | 8 ms | 40 ms | 90 ms |
| `GET /v1/journeys` | 90 ms | 350 ms | 800 ms |
| `GET /v1/stops/{id}/departures` | 6 ms | 40 ms | 90 ms |
| `GET /v1/vehicles?bbox=` | 5 ms | 25 ms | 60 ms |
| `GET /v1/alerts` | 2 ms | 10 ms | 25 ms |

Where the journey budget goes:

```
parse + validate            1 ms
resolve from/to (cached)    2 ms
MOTIS query over loopback  40–250 ms   ← the only expensive step
realtime overlay            1 ms       ← hash lookups on an in-memory snapshot
alert overlay              <1 ms
rank + serialize            5 ms
─────────────────────────────────────
                           50–260 ms server time
```

Add ~15–25 ms RTT for an Israeli mobile client to an Israeli region, and the user sees results in well under half a second. That is the difference between an app that feels like a tool and one that feels like a website.

**Non-negotiable consequences:**

- The routing engine runs on the same host as the API. Not in another cluster, not behind a load balancer.
- Realtime is a pointer to an immutable in-memory object, not a database query.
- The geocoder for transit stops is in-process. Only free-text street addresses may touch a heavier index.
- Postgres is *not* on the hot path at all.

---

## 2. Component map

```
                          Israeli users
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Cloudflare (TLS,     │   free tier
                    │  cache, WAF, IL PoP)  │
                    └───────────┬───────────┘
                                │
╔═══════════════════════════════▼══════════════════════════════════╗
║  APPLICATION HOST — Israel region, one box to start              ║
║                                                                  ║
║   ┌──────────────────────────────────────────────────────────┐   ║
║   │  Transit.Api   (.NET or Python — see §3)                 │   ║
║   │  ├─ in-memory realtime snapshot   (immutable, swapped)   │   ║
║   │  ├─ in-memory alert set           (immutable, swapped)   │   ║
║   │  ├─ in-memory stop/station index  (~30k stops)           │   ║
║   │  └─ LRU caches: geocode results, journey shells          │   ║
║   └───────┬──────────────────────┬────────────────┬──────────┘   ║
║           │ loopback             │ loopback       │ loopback     ║
║   ┌───────▼────────┐   ┌─────────▼──────┐  ┌──────▼─────────┐    ║
║   │ MOTIS          │   │ Photon         │  │ Redis          │    ║
║   │ routing graph  │   │ ONLY IF NEEDED │  │ pub/sub + cache│    ║
║   │ + geocoding    │   │ (see §3)       │  │                │    ║
║   │ + tiles        │   │                │  │                │    ║
║   │ (~2 GB RAM)    │   │                │  │                │    ║
║   └────────────────┘   └────────────────┘  └──────▲─────────┘    ║
║                                                   │              ║
║   ┌───────────────────────────────────────────────┴──────────┐   ║
║   │  Transit.Ingest — SINGLE process, the only MOT client    │   ║
║   │  ├─ SIRI poller      every 15–30 s                       │   ║
║   │  ├─ Alerts poller    every 5 min                         │   ║
║   │  └─ GTFS builder     nightly                             │   ║
║   └───────┬──────────────────────────────────┬───────────────┘   ║
╚═══════════│══════════════════════════════════│═══════════════════╝
            │ needs a stable, whitelisted IP   │
            ▼                                  ▼
   ┌──────────────────┐              ┌──────────────────────┐
   │ MOT SIRI + Alerts│              │ Object storage (S3)  │
   │ moran.mot.gov.il │              │ feeds, snapshots,    │
   │ gtfs.mot.gov.il  │              │ graphs, parquet      │
   └──────────────────┘              └──────────┬───────────┘
                                                │
                                     ┌──────────▼───────────┐
                                     │ Postgres + PostGIS   │
                                     │ history, analytics,  │
                                     │ NOT the hot path     │
                                     └──────────────────────┘
```

---

## 3. What each piece is, and why that one

### Transit.Api — the language is an open choice, not a .NET requirement

Nothing in this architecture requires a specific runtime, and the PRD is explicit about it (§25: "Implementation language is not a product requirement"). An earlier draft of this document picked ASP.NET Core partly because the PRD's module naming is already .NET-shaped, which is circular — `Transit.Api` is a rename, not a constraint.

The genuine requirements are narrower than a language choice:

- hold hundreds of megabytes of transit state in one address space and read it per request without a lock
- keep the API's *own* work inside roughly 10 ms on the journey path and 20 ms on the search path
- parse and serialize JSON at 50 rps on one box without becoming the bottleneck

Two candidates satisfy those, with different failure modes.

**ASP.NET Core (.NET 9), minimal APIs.** Kestrel, source-generated `System.Text.Json`, `ArrayPool`, spans, and optional native AOT if startup time ever matters. One process, real threads, and an atomic exchange on a snapshot reference is a genuinely free lock-free swap — the pattern in §4 is native to the runtime rather than worked around. The cost lands on the cold path, where the work is Parquet, joins and statistics and the tooling is thinner.

**Python (FastAPI or Litestar, on uvicorn or Granian), with `msgspec` or `orjson`.** It satisfies the architecture too, and the costs are concentrated in exactly two places rather than spread everywhere:

| Concern | What actually happens |
| --- | --- |
| `/v1/journeys` | Safe. MOTIS owns 40–250 ms of a 350 ms budget, so the API's own overhead growing from ~10 ms to ~40 ms disappears into it. |
| `/v1/places` (40 ms) and `/v1/vehicles` (25 ms) | The exposed endpoints, because they are pure in-process work. Needs a real index — `marisa-trie`, or a sorted array plus `bisect` — and numpy for the bbox scan, rather than naive iteration. |
| One address space holding the snapshot | The GIL pushes CPython toward N worker processes, so N copies of the snapshot and the stop index. The Redis fan-out in §4 already treats workers as instances, so this costs RAM, not a redesign. A free-threaded build (supported since 3.14) removes the duplication, at the cost of a less settled C-extension ecosystem. |
| The swap itself | Ports cleanly. Rebinding an attribute is atomic under the GIL, so `state.snapshot = new_snap` gives readers the same old-or-new guarantee, with no torn reads. |

**Where Python is the better tool regardless of the API decision.** The cold path is HTTP polling, JSON parsing, reconciliation joins and Parquet writing on a seconds-scale budget — `orjson`, `pyarrow` and `polars` beat the .NET equivalents on both ergonomics and contributor familiarity. The Phase 4 reliability statistics are Python territory outright: DuckDB, notebooks, the lot.

**The decision rule.** This is a solo open-source project whose stated success metric (PRD §37) is whether the developer uses it every day. A backend written in a language the author is slow in does not get finished, and that risk dwarfs 20 ms on autocomplete. Pick the faster language for whoever is writing it, and mitigate that language's two known weaknesses deliberately.

The one split worth considering on its merits: **Python for `Transit.Ingest` and the Phase 4 analytics even when the API is .NET.** The hot/cold boundary in §0 is already hard, and the two sides communicate only through Redis and object storage, both language-neutral — so a seam there costs nothing architecturally. What it does cost is two toolchains in one repository, which for a solo maintainer is not nothing.

Rules for this service, whichever language wins:

- Stateless with respect to *user* data, stateful with respect to *transit* data. It holds hundreds of megabytes of transit state in RAM deliberately.
- No ORM on the hot path. No ORM at all until Phase 4 analytics.
- Every response is generated from immutable snapshots, so no locks and no GC pressure from per-request allocation of shared state.
- Brotli compression, HTTP/2, ETags on everything cacheable.

### MOTIS — routing engine

Runs as a sidecar container, queried over `127.0.0.1`. It holds the timetable and street graph in RAM and answers RAPTOR queries in tens of milliseconds. Alternative kept in the interface: OpenTripPlanner, which is slower and hungrier but more familiar. `Transit.Routing` defines `IJourneyPlanner`; MOTIS is one implementation, so swapping engines is a Phase-0 decision, not a rewrite.

### Geocoding — probably free with MOTIS, and Photon only if it is not

MOTIS ships geocoding and map tiles alongside routing, from the same OSM and GTFS data it has already loaded. If its geocoder handles Hebrew queries and Israeli addressing well enough, an entire Elasticsearch dependency and several gigabytes of RAM disappear from the design.

So search is tiered, cheapest first:

1. **Tier 1, in-process (~90 % of queries):** every GTFS stop, station and major POI — roughly 30–40k entries for Israel — in a prefix/trigram index in memory, Hebrew and English, with `stop_code` and station aliases. Single-digit milliseconds. Rebuilt when the feed rolls over. This is a few hundred lines of code and it covers the overwhelming majority of what people actually type into a transit app.
2. **Tier 2, MOTIS geocoding on loopback:** free-text street addresses. No new dependency, no new container.
3. **Tier 3, Photon — only if tier 2 proves inadequate for Hebrew:** ~2–4 GB of RAM and an Elasticsearch process, which is why it is a contingency rather than a default.

Evaluate tier 2 during the Phase 0 routing bake-off, since MOTIS is being stood up anyway. The public Nominatim endpoint is never used in production — its policy forbids exactly the autocomplete pattern this product needs.

### Redis — fan-out, not storage

Two jobs: distribute the realtime snapshot from the single ingester to any number of API instances via pub/sub, and hold short-TTL caches shared across instances. It is deliberately not the source of truth for anything. If Redis dies, the API keeps serving from its last in-memory snapshot and degrades to schedule-only when that snapshot ages out.

### Postgres + PostGIS — cold storage

Static GTFS metadata, historical realtime, and the Phase-4 reliability statistics. Explicitly off the hot path: a journey request never opens a database connection. This keeps the instance small and means a Postgres outage degrades analytics, not the product.

Note on size: do not blindly load `stop_times.txt` for the 60-day feed into Postgres — that is on the order of a hundred million rows and buys nothing, because MOTIS already answers both journeys *and* stop departures from RAM. Load routes, trips, stops, calendars and `TripIdToDate`; leave the giant table to the routing engine.

### Object storage — S3-compatible, provider-agnostic

Everything durable and immutable lands here, addressed by content hash:

```
s3://opentransit/
  feeds/gtfs/raw/{sha256}.zip              the exact bytes MOT served
  feeds/gtfs/normalized/{sha256}/*.parquet  cleaned, typed, queryable
  feeds/tripidtodate/{sha256}.zip
  graphs/{feed_sha256}/motis-graph.bin      built once, reused on redeploy
  siri/raw/{yyyy}/{MM}/{dd}/{HH}/{ts}.json.zst   rolling 7-day retention
  siri/compacted/{yyyy}/{MM}/{dd}/observations.parquet
  alerts/{yyyy}/{MM}/{dd}/{ts}.pb
  fixtures/                                 recorded data for contributors
```

Accessed through the S3 API only, so it runs on AWS S3, Cloudflare R2, Backblaze B2, Hetzner Object Storage or MinIO locally without a code change. `Transit.Infrastructure` exposes `IObjectStore`; nothing above it knows the provider.

### Transit.Ingest — the single privileged process

This is the only component with the MOT key, and there must be exactly one of it. MOT permits a poll no more often than every 15 s on a single key; running two pollers is a good way to lose access.

It is a plain worker with three schedules, and it is the piece that must run on a whitelisted, stable-IP host.

---

## 4. The hot path in detail

### The realtime snapshot swap

The pattern that makes realtime free at request time:

```
every 15–30 s:
    fetch AllActiveTripsFilter (calls) from MOT      ~1–3 MB gzipped JSON
    parse into a NEW immutable snapshot object
        Dictionary<TripKey, TripRealtime>            keyed by (service_date, DatedVehicleJourneyRef)
        Dictionary<StopCode, StopVisit[]>            pre-sorted departure boards
        Dictionary<VehicleRef, Position>             for the map
        recordedAt, sourceLag, coverageStats
    validate: entity counts within tolerance of the previous snapshot
    publish to Redis  →  every API instance rebuilds its local copy
    atomically swap the snapshot reference            ← the swap
```

Readers take a local reference to the current snapshot and are done. No locks, no async, no allocation, no contention. The old snapshot is collected once in-flight requests finish. Peak memory for a nationwide snapshot of active trips is tens of megabytes.

**Staleness is a first-class field.** Every response carries the snapshot's `recordedAt` and a per-leg realtime state of `live | stale | scheduled | unknown`. When the snapshot ages past a threshold — 90 s is a sensible default — the API stops claiming live data and says so, rather than serving confident nonsense. That is PRD §4.3 made mechanical.

### Trip reconciliation

Runs inside the ingester, not per request. The join is the documented one:

```
SIRI FramedVehicleJourneyRef (DataFrameRef + DatedVehicleJourneyRef)
    → TripIdToDate.txt → GTFS trip_id
fallbacks, in order:
    (LineRef → route_id) + (OperatorRef → agency_id)
        + DirectionRef + OriginAimedDepartureTime ≈ first departure_time
    then: nearest scheduled trip on the same route within ±N minutes
```

Every snapshot records `matched / unmatched / ambiguous` counts, and that ratio is a monitored SLI — it is the single best early warning that a feed change has broken something. Unmatched trips are not discarded; they are kept as vehicle positions without journey context, and archived for offline analysis of *why* they failed to match.

### Journey request flow

```
GET /v1/journeys?from=…&to=…&departAt=…

 1  resolve endpoints            in-process index, then LRU, then Photon
 2  MOTIS query on loopback      returns candidate itineraries (schedule-based)
 3  overlay realtime             per leg: snapshot lookup by trip key
 4  overlay alerts               per route/stop/trip entity match
 5  rank                         Phase 1: engine order, lightly adjusted
                                 Phase 3: realtime-aware (see PRD §28)
 6  shape response               normalized model, never a leaked SIRI or MOTIS structure
```

Step 2 is the only step that can be slow, which means performance work has exactly one target — and MOTIS is already fast for a single small country.

---

## 5. The cold path

### Nightly GTFS build, with an atomic swap

```
03:30  GET gtfs.mot.gov.il/gtfsfiles/israel-public-transportation.zip        (GET, not HEAD — see findings)
       GET .../TripIdToDate.zip
       sha256 → already seen? stop.
       archive raw bytes to S3
       validate:   zip integrity, required files present,
                   row counts within ±20 % of the active feed,
                   known landmark stops and lines resolve,
                   service dates actually cover today+10
       normalize:  encoding, translations.txt sanitation, coordinate sanity
       build MOTIS graph → S3 under the feed hash
       start a second MOTIS container on the new graph
       health check it with a fixed suite of ~20 known journeys
       flip the API's routing upstream            ← the atomic swap
       drain and stop the old container
       rebuild the in-process stop index
```

If any step fails, nothing is swapped, the previous graph keeps serving, and an alert fires. **A bad feed must never be able to take the service down** — the failure mode of a validation error is "yesterday's data", not "no data".

Building a graph needs headroom, so either the box is sized for two graphs at once, or the build runs on a temporary machine and only the artifact is shipped.

### SIRI archiving and compaction

At the highest useful rate the volume is real:

| | estimate |
| --- | --- |
| Poll interval | 30 s (`AllActiveTrips` + `calls`) |
| Snapshots/day | 2,880 |
| Compressed size each | ~1–3 MB (zstd) — **measure in Phase 0** |
| Raw per day | ~3–8 GB |
| Raw retention | 7 days → ~25–55 GB standing |
| Daily Parquet rollup | ~100–300 MB/day |
| Rollup per year | ~40–110 GB |

The rollup keeps one row per (trip, stop): scheduled time, observed time, delay, vehicle, match status. That is the entire input to Phase 4 reliability intelligence, and it is small enough to query with DuckDB against object storage without a data warehouse.

Cost sanity: on R2 or B2 this is a few dollars a month; on S3 Standard, roughly $1–3/month for the rollups plus a little for the rolling raw window. Storage is not the constraint — deciding to keep raw data forever would be.

---

## 6. Deployment and cost

### Correcting an oversized first estimate

An earlier draft of this document specified 32 GB of RAM and landed at $230–310/month. That was wrong, for one reason: MOTIS is far more memory-efficient than assumed. Its routing core is built around compact, serialize-once data structures, and the project reports loading a whole country's full-year timetable in **under 2 GB**. Israel alone is a small dataset by that standard.

Real memory budget:

| Component | RAM |
| --- | --- |
| MOTIS timetable (Israel, full year) | ~1–2 GB |
| MOTIS street graph (Israel OSM extract) | ~1–2 GB |
| Transit.Api + realtime snapshot + stop index | ~0.5 GB |
| Redis | ~0.2 GB |
| OS and headroom | ~1 GB |
| **Total** | **~4–6 GB** |

So the production box is **8 GB, not 32**. Graph builds want transient headroom, and the answer is not a bigger server all year — build the graph on the dev machine or a spot instance and ship the artifact, which the content-addressed storage layout already supports.

Dropping Photon in favour of MOTIS's own geocoder (§3) removes another 2–4 GB. Those two corrections take the bill down by roughly a factor of five.

### What each price range actually buys

| Budget | Shape | What runs | What you cannot do | Right when |
| --- | --- | --- | --- | --- |
| **$0** | Dev machine, Docker Compose | Entire stack on localhost: GTFS ingest, MOTIS graph, routing, geocoding, API, realtime replayed from fixtures | Nothing is reachable from a phone; no live SIRI unless MOT whitelists your own IP; it dies when the laptop sleeps | All of Phase 0 Track A, and API milestones M1–M4 |
| **~$5** | + smallest Israeli VPS, 1 vCPU / 1–2 GB | The SIRI ingester alone, 24/7, from a stable Israeli IP — polling, archiving snapshots to object storage, alerts | Cannot hold the routing graph or serve the API; it is a collector, not a service | The day the MOT key arrives. Start the history archive immediately — SIRI cannot be backfilled, and Phase 4 is worth nothing without it |
| **~$15–25** | 1 box, 2 vCPU / 4–8 GB, Israel | The whole stack, publicly reachable, with live realtime: journeys, places, departures, vehicles, alerts | No headroom — graph builds must happen off-box; a reboot is downtime; no staging; tight if the 60-day feed is used | Private beta and dogfooding — the "I use this instead of Moovit" milestone |
| **~$40–75** | 1 box, 2–4 vCPU / 8 GB + 100 GB + object storage + Cloudflare | Comfortable public v1. Two MOTIS containers briefly during an atomic graph swap, Postgres container, telemetry, compacted archive | Still one machine: a host failure is an outage; no staging environment; no redundancy | **The recommended free-to-the-public tier.** Handles tens of thousands of daily users |
| **~$120–160** | 2 boxes — serving + ingest/build — or one larger with managed Postgres | Graph builds never touch the serving host; blue/green deploys; a staging environment; managed backups | Still single-region and not highly available | When downtime starts costing you something other than pride |
| **~$250–400** | 2 API instances, managed Postgres, dedicated ingest, staging, paid observability | Survives a host failure; real alerting; capacity for growth spikes | — | Only once someone else's commute breaks when it goes down. This is a funded shape |

Two things worth noticing in that table. The jump from $0 to a working public service is about **$40**, not $300 — and the jump from there to redundancy is proportionally the expensive one, because redundancy means buying a second of everything.

And the thing that actually gates this project cannot be bought at any price. The MOT key costs nothing and no amount of money makes it arrive faster.

### Tier 0 — the POC. Target: $0–12/month

Phase 0 needs almost no hosting at all.

- **Everything runs on the dev machine** under Docker Compose. GTFS is a public download, MOTIS builds locally, the API listens on localhost. There is nothing to pay for.
- **The one exception is the SIRI ingester**, because of the IP restriction. Two cases:
  - If you are in Israel and MOT will whitelist a home or office address, this is free. A static IP from an Israeli ISP costs a few shekels a month — **ask MOT whether the key is IP-bound in the same email as everything else**, because the answer decides this line item.
  - Otherwise, the smallest possible Israeli VPS. Kamatera runs data centres in Tel Aviv, Haifa, Petah Tikva and Rosh Ha'ayin with à-la-carte sizing from around $4/month and a 30-day free trial. The ingester is a poller: ~512 MB and almost no CPU.
- **Object storage:** local disk during the POC, or Cloudflare R2's free tier (10 GB, no egress charges).

The POC is not where money goes. Anyone quoting you cloud bills for a feasibility test is solving the wrong problem.

### Tier 1 — public v1, free to use. Target: $35–75/month

One box, in Israel, doing everything.

| Item | Cost |
| --- | --- |
| 2–4 vCPU / 8 GB in Israel — AWS `t4g.large` in `il-central-1`, or a Kamatera Israel instance | ~$25–50 |
| 100 GB SSD | ~$5–12 |
| Elastic/static IP (registered with MOT) | ~$0–4 |
| Object storage — R2 or S3, feeds plus a compacted archive | ~$0–6 |
| Postgres — a container on the same box | $0 |
| Cloudflare — free plan, no bandwidth metering | $0 |
| Telemetry — Grafana Cloud free tier | $0 |
| **Total** | **~$35–75/month** |

Graviton/ARM instances price roughly 10–20 % below x86 equivalents at comparable performance, and MOTIS runs fine on ARM, as do both candidate API runtimes — take the discount.

### Tier 2 — only once someone's commute depends on it

Split the roles: a separate ingest/build host, managed Postgres, a staging environment, real alerting, maybe a second API instance behind the existing Cloudflare layer. Call it $150–400/month. This is a funded-project shape, and nothing above needs redesigning to get there — the ingester is already a separate process and storage is already content-addressed.

### The cost traps that create $300 bills

Every one of these is a default somebody accepts without noticing:

| Trap | Typical cost | Avoid it by |
| --- | --- | --- |
| **NAT Gateway** | ~$35/mo plus per-GB | put the instance in a public subnet with a static IP; you need inbound anyway |
| **Load balancer** | ~$18–25/mo | Cloudflare in front of the box's IP; Caddy terminates TLS |
| **Managed Kubernetes** | ~$70/mo for the control plane alone | Docker Compose and systemd |
| **Managed Postgres, early** | ~$25–35/mo | a container on the same box until Phase 4 analytics justify it |
| **Elasticsearch for geocoding** | forces a bigger instance | MOTIS geocoding plus the in-process stop index |
| **Keeping raw SIRI forever** | 3–8 GB/day, compounding | 7-day raw window, then daily Parquet rollup |
| **Serving map tiles from origin** | egress, the one bill that scales | PMTiles on R2 (zero egress) behind Cloudflare |
| **Multi-AZ by reflex** | doubles compute, adds per-GB transfer | one AZ; this is a journey planner, not a bank |

The decision that actually controls the bill is *one box or many*, not which cloud.

### Why "free to use" is sustainable

The expensive artifact — the routing graph — is built once and shared by every user. Cost is therefore almost flat with respect to users:

- 10,000 daily users × 5 requests ≈ 50k requests/day ≈ **0.6 req/s average**, with commute peaks perhaps 20–30 req/s. One 8 GB box absorbs that without noticing.
- A journey response is ~10–20 KB of JSON, ~3–5 KB compressed. 50k requests/day is ~7.5 GB/month of egress, most of which never reaches the origin because Cloudflare serves it.

So the running cost is roughly **$40–70/month whether the service has 100 users or 50,000**. The only thing that genuinely scales with popularity is map tiles, and PMTiles on R2 removes that bill by construction.

That is the whole economic argument for the product being free: at this scale, free-to-use costs about as much as a phone plan.

### Getting to actually zero

1. **Sponsorship.** GitHub Sponsors or Ko-fi covering $50/month is a realistic ask for a transit app people use daily, and it keeps the project independent.
2. **Credit programmes.** AWS Activate and the Open Data programme, Google Cloud credits, Microsoft for Startups, Cloudflare's open-source plans. Oracle's Always Free tier is worth an attempt but not a plan — it was cut from 4 OCPU/24 GB to 2 OCPU/12 GB in 2026, and Ampere A1 capacity is frequently unavailable. Treat it as a lottery ticket.
3. **Partner with Hasadna, the Public Knowledge Workshop.** They already run Israeli transit infrastructure as a nonprofit, already hold MOT access, and already pay for hosting. This is the highest-leverage option on the list because it answers the hosting question and the SIRI access question at the same time. Worth a conversation regardless of the outcome.
4. **Never depend on a proprietary managed service**, so that moving to whoever is currently free is always a deployment change and never a rewrite. The design already holds this line.

### If the ingester must live apart

Should MOT's answer make an Israeli IP mandatory while cheaper compute lives elsewhere, the split is already designed for: a €4–15/month Israeli VPS runs only the ingester and publishes to Redis and object storage; the API and MOTIS run wherever is cheapest. The cost is roughly 55–70 ms of extra latency for Israeli users — survivable for journey planning, noticeable in autocomplete. Prefer a single Israeli box when the prices are this close.

### Provider independence

Nothing here requires a specific cloud. GCP `me-west1` and Azure Israel Central substitute directly, object storage is used through the S3 API only, and the whole stack is containers. MOT's own hosts happen to sit in Google's Israel range, so if whitelisting turns out to be easier from that network, moving is a deployment decision, not a redesign.

## 7. API surface, v1

Contract-first. The OpenAPI document lives in the repo and is the source of truth; handlers and clients are generated from it.

```
GET  /v1/places?q=&lang=he|en&near=lat,lon&limit=
GET  /v1/journeys?from=&to=&departAt=|arriveBy=&modes=&maxWalkMinutes=&results=
GET  /v1/journeys/{token}          re-resolve a saved plan against current realtime
GET  /v1/stops?bbox=|near=&radius=
GET  /v1/stops/{stopCode}/departures?limit=&horizonMinutes=
GET  /v1/trips/{tripId}            full stop sequence with live progress
GET  /v1/vehicles?bbox=            live positions
GET  /v1/alerts?routeId=&stopId=&active=
GET  /v1/status                    public feed health — see §8
GET  /healthz  /readyz  /metrics   operational, not public
```

Conventions that keep the client simple and the API honest:

- `from` / `to` accept `lat,lon`, `stop:{code}`, or `place:{id}` from `/v1/places`. Never a raw string — geocoding is its own call, so it can be cached and debounced independently.
- Every time is ISO-8601 with an explicit offset. Israel switches DST; a naive local time in a transit API is a bug waiting for October.
- Every transit leg carries `scheduled`, `expected`, `delaySeconds` and `realtimeState`. `expected` is never silently equal to `scheduled` — if there is no live data, the state says `scheduled` and the client renders it differently.
- Errors are typed and actionable: `NO_ROUTE_FOUND`, `PLACE_NOT_FOUND`, `FEED_UNAVAILABLE`, `OUT_OF_SERVICE_AREA` — with enough context to show a real message.
- Versioned under `/v1`. Additive changes only; a breaking change means `/v2` running alongside.

**Caching**

| Endpoint | Edge | Server |
| --- | --- | --- |
| `/v1/places` | 1 h, vary on query + lang | LRU 50k entries |
| `/v1/stops`, `/v1/trips` | 5 min | rebuilt on feed swap |
| `/v1/stops/{id}/departures` | 10 s | from the live snapshot |
| `/v1/journeys` | no edge cache | 30 s LRU keyed to the departure minute |
| `/v1/alerts` | 60 s | from the live snapshot |

---

## 8. Operations

### Health as a product surface

`/v1/status` is public, because a transit service people rely on to physically get somewhere should be honest about its own state:

```json
{
  "gtfs":    { "feedHash": "a1b2…", "builtAt": "2026-08-28T03:41Z", "ageHours": 14, "state": "healthy" },
  "realtime":{ "lastSnapshot": "2026-08-28T18:09:12Z", "lagSeconds": 8,
               "tripsTotal": 11482, "matched": 0.963, "state": "healthy" },
  "alerts":  { "lastFetch": "2026-08-28T18:05:00Z", "active": 37, "state": "healthy" },
  "routing": { "graphFeedHash": "a1b2…", "p95Ms": 180, "state": "healthy" }
}
```

### SLIs worth paging on

| Signal | Warn | Page |
| --- | --- | --- |
| Realtime snapshot age | > 90 s | > 5 min |
| SIRI↔GTFS match rate | < 90 % | < 70 % |
| GTFS feed age | > 30 h | > 48 h |
| `/v1/journeys` p95 | > 500 ms | > 1.5 s |
| Routing error rate | > 0.5 % | > 2 % |
| MOT 401/403 responses | any | sustained — the key may be revoked |

That last row matters more than it looks. The key is a relationship with a government office, not a credential you can reissue yourself.

### Degradation ladder

The service is designed to lose capability in defined steps rather than fail:

1. Realtime stale → serve schedule, mark every leg `scheduled`, show it in `/v1/status`.
2. Alerts feed down → serve journeys without alerts, flag `alerts: degraded`.
3. Photon down → transit-stop search still works from the in-process index; street addresses return a typed error.
4. Redis down → each API instance serves its own last snapshot.
5. Postgres down → no user-visible impact at all.
6. New GTFS invalid → keep the previous graph, page the operator.

Only "MOTIS down" is a real outage, which is precisely why it lives on the same box with nothing between it and the API.

---

## 9. Working without a key

Contributors will not have a MOT SIRI key, and that has to be a designed-for case rather than a wall:

- `Transit.Realtime` defines `IRealtimeSource`, with `MotSiriSource` and `ReplaySource`.
- The repo ships a fixture bundle: a small GTFS extract, `TripIdToDate` rows, a few hours of recorded SIRI snapshots and a sample alerts package.
- `docker compose up` runs the whole stack against fixtures, with a clock that can be pinned to the fixture window, so tests are deterministic.
- Integration tests run entirely on fixtures in CI. Only a nightly job in the deployed environment touches live MOT.

This is also the honest hedge against kill criterion 3: if the key never arrives, the replay-based development environment is still the thing that lets the project keep moving while the decision is made.

---

## 10. Build order

Each milestone ends with something callable over HTTP. No milestone ends with "a library that will be useful later".

| # | Milestone | Done when |
| --- | --- | --- |
| M1 | Skeleton | `docker compose up` serves `/healthz`, OpenAPI published, CI green |
| M2 | GTFS ingest | nightly job downloads, validates, versions to S3; `/v1/stops` works |
| M3 | Routing | MOTIS wired; `/v1/journeys` returns schedule-only itineraries |
| M4 | Search | `/v1/places` two-tier, Hebrew and English, p95 < 40 ms |
| M5 | Realtime | snapshot swap live; journeys and departures carry delays; `/v1/vehicles` |
| M6 | Alerts | `/v1/alerts` and per-journey attachment |
| M7 | Hardening | atomic graph swap, degradation ladder, `/v1/status`, load test at 50 rps |
| M8 | Deploy | running in the Israel region on the registered IP, public docs, status page |

**Phase 1 is complete when** a plain `curl` from a phone tethered in Tel Aviv plans Dizengoff Center → Technion, with live delays, in under 400 ms p95 — repeatedly, on a weekday evening, against real data.

Only then does a client get written.

---

## 11. Open decisions

Things this document deliberately does not settle, because the answer depends on Phase 0:

1. **Primary feed:** 60-day plus TripIdToDate (accepted ADR 0005). The 10-day feed is comparison only; no dual-feed fallback.
2. **Whether MOTIS or OTP** survives the routing bake-off.
3. **Whether the ingester can run in-region** or needs a separate whitelisted host — MOT's answer decides the deployment shape.
4. **Poll rate**: `calls` detail every 30 s is the assumption; if the payload is much larger than estimated, drop to 60 s and use `normal` for positions.
5. **Whether Photon is needed at all** for v1, if transit stops plus a small POI set cover the real query distribution.
6. **The API language** — .NET or Python (§3). This one does not depend on Phase 0 at all; it depends on which language the author writes faster. It is listed here so that it is recorded as a deliberate choice rather than inherited from a first draft, and it should be settled before M1, because the skeleton milestone is the cheapest possible place to change the answer.
