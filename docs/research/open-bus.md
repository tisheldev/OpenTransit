# Open Bus (Hasadna) — data, linkage and reuse

**Researched:** 1 October 2026, by the Open Bus session, using read-only anonymous HTTP requests. Raw responses were not saved as repository evidence; repeat a measurement before relying on its numbers. **Status:** research note. Nothing here is implemented, accepted or human-approved, and none of it is realtime-matching evidence for POC-3.

Labels used below: **Measured** (we ran the request), **Documented by Hasadna** (their code or write-ups; not verified by us), **Proposed** (our idea; see [next steps](../next-steps.md#proposed-open-busderived-reliability-features)).

## 1. What Hasadna runs (documented by Hasadna)

The [Hasadna GitHub organisation](https://github.com/hasadna) lists 17 Open Bus repositories; the code is MIT-licensed. Relevant ones:

| Repository | Role |
| --- | --- |
| [open-bus-siri-requester](https://github.com/hasadna/open-bus-siri-requester) | Downloads the MOT SIRI snapshot about every 60 s (MOT key, fixed-IP tunnel) |
| [open-bus-siri-etl](https://github.com/hasadna/open-bus-siri-etl), [open-bus-gtfs-etl](https://github.com/hasadna/open-bus-gtfs-etl) | Load SIRI snapshots and daily GTFS into the database |
| [open-bus-stride-db](https://github.com/hasadna/open-bus-stride-db) | Postgres schema (`DATA_MODEL.md`) |
| [open-bus-stride-etl](https://github.com/hasadna/open-bus-stride-etl) | Hourly jobs: ride durations, SIRI↔GTFS ride matching, ride-stop↔GTFS-stop matching, nearest vehicle location per stop, ride aggregations |
| [open-bus-stride-api](https://github.com/hasadna/open-bus-stride-api) | Public API ([docs](https://open-bus-stride-api.hasadna.org.il/docs)) |
| [open-bus-map-search](https://github.com/hasadna/open-bus-map-search) | [Public site](https://open-bus-map-search.hasadna.org.il): gaps/missed trips, gap patterns, single-line map, velocity heatmap, operator, vehicle, complaints, train |
| [open-bus-backend](https://github.com/hasadna/open-bus-backend) | Node service; forwards citizen complaints to government forms; MOT lookup endpoints |
| [open-bus-api-client](https://github.com/hasadna/open-bus-api-client) | Generated TypeScript client (`@hasadna/open-bus-api-client`) |
| [open-bus-hackathon-26](https://github.com/hasadna/open-bus-hackathon-26) | `algorithms/` write-ups (section 5) |

Also present: open-bus-tools, open-bus-rides-history and an early open-bus-stride-clickhouse.

## 2. Public S3 archive (measured)

Bucket `openbus-stride-public` (eu-west-1) allows anonymous listing and reads.

- **Raw SIRI:** `stride-siri-requester/YYYY/MM/DD/HH/MM.br` (brotli-compressed JSON), year prefixes 2021–2026. The 2026-09-30 06:00 UTC file is about 233 KB compressed / 4.18 MB raw, so a month is roughly 10 GB compressed. Content is a SIRI-SM 2.8 `StopMonitoringDelivery` of `MonitoredStopVisit` records with `RecordedAtTime`, `LineRef`, `FramedVehicleJourneyRef` (`DataFrameRef` date + `DatedVehicleJourneyRef`), `OperatorRef`, `OriginAimedDepartureTime`, `VehicleLocation`, `Bearing`, `Velocity`, `VehicleRef` and `MonitoredCall` (`StopPointRef`, `Order`, `DistanceFromStop`). There is **no `ExpectedArrivalTime` or other prediction** — positions only.
- **Daily GTFS:** `gtfs_archive/YYYY/MM/DD/` holds `israel-public-transportation.zip`, `TripIdToDate.zip`, `Tariff.zip` and `ClusterToLine.zip`; years 2022–2026; September 2026 has all 30 days.

## 3. Measurements, 1 October 2026

**A — archive ID join (ID existence only).** The 2026-09-30 06:00 UTC snapshot had 8,539 visits and 7,132 unique `DatedVehicleJourneyRef`; 7,063 (99.0%) occur as `TripId` in that day's archived `TripIdToDate` (918,492 TripIds). Service date, departure time and full trip identity were **not** checked, so this is not a realtime match rate (AGENTS.md: key overlap alone does not establish realtime correctness).

**B — Stride ride-level linkage.** `siri_rides` with scheduled start 06:00–06:30 +03:00:

| Service day | With `gtfs_ride_id` |
| --- | --- |
| 2026-09-30 | 4,187 / 4,366 (95.9%) |
| 2026-09-23 | 4,430 / 4,629 (95.7%) |
| 2026-08-30 | 0 / 4,276 (0%) |

All matches came from the route/time strategy (`journey_gtfs_ride_id` null). This supersedes the 28 August finding of zero linkage for recent rides but not for older ones: at least one August day remains unlinked. **Stop-level linkage is unconfirmed:** one sampled matched ride (Egged line 22, 2026-09-30) had `gtfs_stop_id` and the nearest vehicle location null on its first ride stops; an 8-ride sample failed when the API reset the connection.

**C — Stride operations.** The latest snapshot (2026/10/01/16/10 UTC) was still loading at 16:21 UTC (about 11 minutes lag); about 6,600 vehicle locations per minute snapshot. The API rejected `limit` above 15,000 ("due to abuse") although its docs say 500,000, and reset the connection after a few modest queries. Conclusion: do not put product traffic on the Stride API; copy the S3 archive and compute ourselves.

**D — planned vs observed rides.** `gtfs_rides_agg/group_by` operator totals for 2026-09-01..28 give actual/planned ≈ 0.66 for several operators (operator 3: 257,425 / 390,256; operator 5: 126,385 / 190,186). Hasadna's siri-coverage write-up attributes such gaps largely to tracking (GPS/cellular) failures; a ride that never ran and a ride that ran untracked look the same. A "missed" ride must therefore never be labelled "cancelled".

Other Stride endpoints seen: `route_timetable`, `stop_arrivals` (currently planned times only), `rides_execution`, `siri_velocity_aggregation`, `gtfs_rides_agg`.

**E — OB-01 pilot on the raw archive, service day 2026-09-15 (measured; [result](../../services/api/results/ob01-pilot-20260915-03.json)).** 1,784 of 1,800 archive minutes present (the 16 gaps return 404). Corrections to the reading above:

- `DatedVehicleJourneyRef` is usually **not** the prefix of that day's GTFS `trip_id`: only 12,957 of 117,596 matched rides. Measurement A's 99% is TripIdToDate key existence only. MOT's documented join, `LineRef` = `route_id` plus `OriginAimedDepartureTime` = first departure, matches 117,596 of 135,454 SIRI rides to exactly one trip running that day. Of the 17,858 unmatched, 15,870 have fewer than 3 pings. TripIdToDate (OfficeLineId-Direction-Alternative + DepartureTime) agrees with that match for 114,796 rides; the disagreements seen were `24:00`/`00:00` spellings.
- `MonitoredCall.DistanceFromStop` is cumulative metres from the journey start, on the GTFS `shape_dist_traveled` scale. `Order` names the stop **most recently reached**: when it advances, the new stop lies within ±100 m of the bracketing pings in 90.7% of changes, and otherwise typically 180–680 m ahead (switched on approach).
- 116,388 of 122,254 scheduled trips (95.2%) were observed. Stride's 66% observed/planned (measurement D, a different date range) therefore cannot be explained by tracking gaps alone; Stride's own matching may lose rides. Do not reuse Stride's planned/actual counts as reliability figures.
- About 19% of pings are repeats from overlapping snapshots (1.56 M of 8.35 M service-date pings). Most operators stop reporting before the terminal: final-stop arrivals were inferred for 13,647 trips, 13,024 of them from agency 3.
- Halving ping density moves inferred stop times by a median of 4 s (p90 21 s).

The pilot's per-hour medians (+3.8 min at 07, +8.0 min at 08, +7.6 min at 16, p90 up to 29 min) come from one day and are not validated. The slowest segment ratios (10–30×, all in Jerusalem near the Old City and the Shuafat/Anata checkpoints, 3–5 samples each) are unverified: they may be real congestion during the Selichot season or artefacts.

## 4. Hackathon-26 algorithm notes (documented by Hasadna, not verified)

- **bus-arrival-reliability:** arrival = closest geometric approach interpolated between pings; about ±30 s precision at 1-minute pings; actual/planned up to 2.5× on bottleneck segments at 07–09 and 16–18; about 1–2 minutes per line through the API.
- **service-violations:** SIRI reports a parked vehicle against its next ride about 5 or 30 minutes before departure; use the first *moving* ping, otherwise about 90% of departures look early. Thresholds (>1 min early, >5 min late) are illustrative, not official MOT penalty rules.
- **siri-coverage:** coverage ranges from under 40% to 95%+ by line and hour.
- **Known defects:** about 10% duplicate pings from overlapping snapshots; stop-level aggregates lag ingestion (about 3 days cited); no "doors closed" signal.

## 5. data.gov.il ridership (measured metadata; join not verified)

Dataset [`ridership`](https://data.gov.il/dataset/ridership) ("נסועה בקווי אוטובוס"), licence field "Other (Open)", one resource per year; the 2026 resource `7b126b6d-3411-4438-89c3-8eceea61c2db` has 5,356 rows, published quarterly. Columns include `RouteID` (MOT OfficeLineId/makat), direction, agency, cluster, average passengers per ride by daypart for weekdays/Friday/Saturday, `AverageSpeed`, `AverageTripDuration` and `DailyRides`. `TripIdToDate` carries `OfficeLineId`, so a join path likely exists; it has not been tested.

## 6. Data terms (open)

Hasadna states no data licence for the archive or API; the underlying data is MOT's. The code licence (MIT) does not cover the data. Public display of statistics derived from the archive needs terms evidence: ask MOT at the October 19 follow-up ([access record](../data-usage-and-access.md)) and ask Hasadna (`#open-bus` Slack). Neither question has been sent.

## 7. What this changes (proposed)

- The SIRI↔GTFS matcher remains ours to write: Stride links rides, not (confirmed) stops; it is a volunteer service with about 11 minutes lag and a fragile API.
- The S3 archive enables offline, history-based work that needs no MOT SIRI key: delay distributions, transfer risk, reliability badges and matcher development against replay data (OB-01, OB-02, OB-03, OB-06). It does not replace live MOT access for realtime features.
- The daily GTFS archive supports longitudinal ID-stability evidence (OB-05; supplementary to M2.8, which still needs genuinely consecutive daily feeds).

Proposed items, gates and acceptance criteria: [next steps](../next-steps.md#proposed-open-busderived-reliability-features). Earlier access findings: [data access findings §3](../data-access-findings.md#3-the-fallback-is-thinner-than-assumed).
