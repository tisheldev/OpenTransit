# Data access feasibility — GTFS and SIRI

**Checked:** 28 August 2026
**Question:** are the two Moovit-specific dependencies — nationwide GTFS and MOT realtime (SIRI) — actually usable by an independent open-source app?

**Short answer:** GTFS is a solved problem, verified live and open. SIRI is the real gate, and it has *two* locks, not one: an access key issued by MOT on application, and an endpoint that is network-restricted. Service alerts sit behind the same application. The volunteer fallback (Open Bus Stride) is alive but currently gives raw SIRI with no GTFS linkage.

---

## 1. Static GTFS — PASS, verified

The Ministry publishes a plain, unauthenticated HTTP directory. No key, no registration, no rate limit encountered.

`https://gtfs.mot.gov.il/gtfsfiles/` — directory listing retrieved 2026-08-28:

| File | Size | Last modified |
| --- | --- | --- |
| `israel-public-transportation.zip` | 164,212,282 B (~157 MB) | 2026-08-27 19:45 |
| `Gtfs_10_days.zip` | 261,407,983 B (~249 MB) | 2026-08-28 03:43 |
| `TripIdToDate.zip` | 7,640,228 B | 2026-08-27 19:45 |
| `RouteNetworksByDate_10_Days.zip` | 68,840 B | 2026-08-28 03:43 |
| `Tariff.zip` | 105,086 B | 2026-08-27 19:45 |
| `ClusterToLine.zip` | 24,518 B | 2026-08-27 19:41 |
| `zones_2022.zip`, `tariff_2022.zip`, `ChargingRavKav.zip` | small | older |

Observations that matter for the ingester:

- **It updates nightly.** Two of the files were rewritten at 03:43 this morning, the rest at 19:41–19:45 last night. The feed is alive, not a stale mirror.
- **`HEAD` lies.** A `HEAD` on `israel-public-transportation.zip` returned `Content-Length: 3382` while the listing shows 164 MB. Do not use `HEAD` for change detection or size checks — `GET`, then validate the zip and the row counts.
- **`TripIdToDate` is a separate download.** It is not inside the main zip. It is also the file that makes realtime matching possible (see §3), so the ingester must fetch and version it in lockstep with the main feed.
- **The 60-day feed and the 10-day feed are different products.** `israel-public-transportation.zip` is the long-horizon planned data; `Gtfs_10_days.zip` is the near-term one and is bigger. The initial preference for the 10-day feed was superseded by accepted ADR 0005: use the 60-day feed with TripIdToDate, because the sampled 10-day mapping-key overlap is zero.

**Terms:** MOT publishes official English developer documentation for the feed, and the datasets are carried on data.gov.il under the government open-data terms. This is the one item on the GTFS side that is not yet fully nailed down: I could not retrieve the gov.il HTML pages directly (they return 403 to automated fetches), so the exact licence text attached to the GTFS dataset still needs to be read and recorded by a human. Treat that as a 30-minute task, not a risk.

**Verdict:** POC-1 is not a research question. It is an afternoon of parsing work. Nothing blocks it, today.

---

## 2. SIRI — the actual gate

### Lock 1: the endpoint is not public

From MOT's own ICD for SIRI-SM 2.8 (§7.4, §7.7.3):

> The Request address will be given to the Developer by Email, with his RequestorRef (the user name).

and the URL carries an access key "which received from MOT". There is no published base address, no signup page, no self-service portal. You apply, a human at MOT decides, and they email you a base address + RequestorRef + Key.

The application address is documented in the Service Alerts ICD (§4.4): **`ptsupport@mot.gov.il`**.

### Lock 2: the endpoint is network-restricted

Reachability test from this machine, 2026-08-28:

| Host | DNS | TCP 443 |
| --- | --- | --- |
| `moran.mot.gov.il` (SIRI prod) | 34.165.60.250 | **refused** |
| `moran-t.mot.gov.il` (SIRI test) | 34.165.161.216 | **refused** |
| `gtfs.mot.gov.il` (control) | 34.165.243.229 | connected |
| `example.com`, `api.github.com` (control) | — | connected |

Both SIRI hosts resolve and both refuse the connection, while a sibling MOT host and the open internet connect fine from the same machine. That is filtering on MOT's side, not a local egress problem.

This is corroborated by the reference implementation: Hasadna's `open-bus-siri-requester` calls
`https://moran.mot.gov.il/Channels/HTTPChannel/SmQuery/2.8/json?Key=…&MonitoringRef=AllActiveTripsFilter&StopVisitDetailLevel=normal`
using an `OPEN_BUS_MOT_KEY`, and routes the request through an **SSH tunnel to a fixed server IP** (`OPEN_BUS_SSH_TUNNEL_SERVER_IP`). You do not tunnel a public API.

**Consequence for architecture:** the realtime ingester probably has to run from a whitelisted — most likely Israeli — egress IP. That is a hosting decision, and it should be settled during Phase 0, not discovered in Phase 2. Ask MOT explicitly whether the key is bound to a source IP.

### What you get once you are through

Worth knowing, because it determines whether the chase is worth it. It is:

| Filter | Contents | Regenerated |
| --- | --- | --- |
| `AllActiveTripsFilter` + `normal` | every vehicle currently on an active trip, with position, no predictions | every 15 s |
| `AllActiveTripsFilter` + `calls` | same, plus predicted arrivals for every stop the vehicle has not yet visited | every 30 s |
| `AllPlannedTripsFilter` | trips scheduled to depart within the next 4 hours, with predictions | every 60 s |

Plain HTTP GET, JSON, one nationwide request per poll, minimum 15 s between polls. MOT's own document says these are equivalent to GTFS-Realtime *VehiclePositions* and *TripUpdates* in a different wire format. That is precisely what the product needs — arrivals, delays and live vehicle positions for the whole country.

### Reconciliation is documented, not guesswork

The ICD (§4.4) publishes the SIRI↔GTFS field mapping:

| SIRI | GTFS |
| --- | --- |
| `LineRef` | `route_id` |
| `OperatorRef` | `agency_id` |
| `DirectionRef` (1,2,3) | `direction_id` (0,1,2) |
| `PublishedLineName` | `route_short_name` |
| `StopPointRef` / `DestinationRef` / `OriginRef` | `stop_code` |
| `Order` | `stop_sequence` |
| `FramedVehicleJourneyRef` (`DataFrameRef` + `DatedVehicleJourneyRef`) | `TripId` in **`TripIdToDate.txt`** |
| `OriginAimedDepartureTime` | `departure_time` in `stop_times.txt` |

This materially de-risks POC-3: the trip identity join has an official answer, via the `TripIdToDate` file. The open question is match *rate* in practice, not whether a mapping exists.

---

## 3. The fallback is thinner than assumed

Open Bus Stride is live right now — a query at 18:09 UTC returned SIRI rides with `scheduled_start_time` of 18:05 today and populated `vehicle_ref`. Raw realtime is flowing.

But the GTFS linkage is not there:

- `siri_rides` sampled at −8 hours, −3 days and −30 days: **300/300, 40/40 and 300/300 records with `gtfs_ride_id = null`**. Zero matched in every window.
- `siri_ride_stops` returns `gtfs_stop_id = null`.
- `/gtfs_rides/list` returns HTTP 500.

So today the public Stride API is a source of *unmatched* SIRI, not of reconciled journeys. It may be an API-layer problem rather than a pipeline one — worth asking Hasadna directly before concluding anything about their project. Either way, the planning consequence is firm:

> **Prototyping on Open Bus does not save you the reconciliation work.** The GTFS↔realtime matcher is ours to write regardless of which source we use, exactly as the PRD assumed. That is good news for portability and bad news for anyone hoping Stride was a shortcut.

---

## 4. Service alerts — same door as SIRI

From the Service Alerts ICD:

- Standard GTFS-Realtime protobuf, HTTP GET, one URL.
- §4.4: "Full details on the URL will be sent to the Developer upon request to MOT to the email **ptsupport@mot.gov.il**" — so it is not public either.
- §4.5: a new package every 5 minutes; §4.7: poll no more than 12 times per hour.
- Field names are identical to those in `israel-public-transportation.zip`, so entity resolution is direct.
- Hebrew/English/Arabic translations, plus MOT-specific "command/keyword" extensions describing added or skipped stops.

Because it is the same contact address, **one email covers both SIRI and alerts.** Ask for both at once.

---

## 5. What this changes about the plan

The PRD treats POC-1 through POC-6 as a sequence. In reality Phase 0 splits into a track that can start this afternoon and a track that is gated on somebody at MOT answering an email — with unknown latency and an unknown answer.

### Do today, blocking

Email `ptsupport@mot.gov.il` requesting:

1. SIRI-SM 2.8 access — base address, RequestorRef and Key, for a non-commercial open-source public-transport app.
2. The GTFS-Realtime Service Alerts feed URL.
3. Written answers to two questions: **is the key bound to a source IP or geography?** and **what are the usage terms for an open-source, publicly distributed application?**

Nothing else in the project can resolve these, and the calendar cost of asking late is the whole schedule.

### Track A — unblocked, needs nobody's permission

- POC-1 GTFS ingest, including `TripIdToDate` and the 10-day vs 60-day decision.
- POC-2 routing on MOTIS/OTP.
- POC-5 geocoding.
- The `TripIdToDate`-based matcher, written and unit-tested against static data.

### Track B — gated on the reply

- POC-3 realtime: against MOT SIRI if the key arrives; against Stride's raw SIRI in the meantime, to develop and measure the matcher.
- POC-4 alerts: entirely gated, no public URL exists.

### The decision that Phase 0 now has to produce

If MOT declines or does not answer within a set window — suggest four weeks — the project chooses explicitly between:

1. **Stride-backed realtime.** Works today, but it is a volunteer service, currently without GTFS linkage, and it is a permanent third-party dependency for the product's core promise.
2. **Static-only planner.** Honest, shippable, but not the product described in the PRD.
3. **Stop.** Per the PRD's own kill criterion #3.

That decision, not the code, is the real output of Phase 0.

---

## Sources

- [MOT GTFS file directory](https://gtfs.mot.gov.il/gtfsfiles/) — retrieved 2026-08-28
- [MOT GTFS developer documentation (English, PDF)](https://www.gov.il/BlobFolder/generalpage/gtfs_general_transit_feed_specifications/he/Gtfs%20Documentation%20v3.pdf)
- [MOT SIRI-SM 2.8 ICD (English, PDF)](https://www.gov.il/BlobFolder/generalpage/real_time_information_siri/he/ICD_SM_28_32.pdf)
- [MOT GTFS-Realtime Service Alerts ICD 2.2 (PDF)](https://www.gov.il/BlobFolder/generalpage/special_notices_to_developers/he/ICD_Service_Alerts_2_2.pdf)
- [MOT real-time information / SIRI page](https://www.gov.il/he/Departments/General/real_time_information_siri)
- [MOT GTFS page](https://www.gov.il/he/pages/gtfs_general_transit_feed_specifications)
- [hasadna/open-bus-siri-requester](https://github.com/hasadna/open-bus-siri-requester) — reference implementation, MOT key + SSH tunnel
- [hasadna/open-bus-stride-api](https://github.com/hasadna/open-bus-stride-api) and [the live API](https://open-bus-stride-api.hasadna.org.il/docs)
- [Open Bus SIRI data documentation wiki](https://github.com/hasadna/open-bus/wiki/Bus-Real-Time-(SIRI)-Data-Documentation)
- [data.gov.il terms of use](https://data.gov.il/he/terms-of-use)
