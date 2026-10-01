# Phase 0 POC — status

Generated 2026-10-01 06:43 UTC from `poc/results/` at commit `d82534d`.
**Machine-generated. Do not hand-edit — run `python poc/poc_status.py --write`.**

## Dependency status (PRD §13)

| POC | Component | Status | Detail |
| --- | --- | --- | --- |
| POC-1 | Static Israeli transportation data | **PASS** | 544,338 trips / 20,100,370 stop_times parsed, 5 tables in Postgres, 10/10 integrity checks pass; licence terms unread (H2) |
| POC-2 | Public transportation routing | **PARTIAL** | 25/25 answered; 24 structural passes (22 first itinerary); load peak 941.3 MB; H3 pending |
| POC-3 | Realtime transit information | **NOT_STARTED** | no result file yet |
| POC-4 | Service alerts | **BLOCKED_ON_ACCESS** | No public feed URL exists; gated on MOT reply |
| POC-5 | Address and place search | **PARTIAL** | 68/100 top-1 (89/100 in top-5) — clears PRD §10's bar of 20, but Latin-script street addresses do not resolve (4/15 address cases) and the `near` bias point is inert at MOTIS's default placeBias |
| POC-6 | End-to-end journey | **NOT_STARTED** | no result file yet |

## Go / No-Go (PRD §12)

Phase 0 is PASS only when every row is PASS.

| Capability | Required | Actual | Source |
| --- | --- | --- | --- |
| Download current nationwide GTFS | yes | **PASS** | POC-1 |
| Parse GTFS | yes | **PASS** | POC-1 |
| Route using Israeli GTFS | yes | **PASS** | POC-2 |
| Walking + transit + transfers | yes | **PASS** | POC-2 |
| Obtain realtime arrivals | yes | **—** | POC-3 |
| Match realtime <-> GTFS | yes | **—** | POC-3 |
| Obtain service alerts | yes | **FAIL** | POC-4 |
| Resolve Israeli addresses/places | yes | **PASS** | POC-5 |
| Run full end-to-end query | yes | **—** | POC-6 |
| Confirm acceptable data usage terms | yes | **FAIL** | POC-1 |

**5/10 capabilities green — Phase 0 verdict: NOT YET**

### Blocked on external access

- **POC-4 (Service alerts)** — The Service Alerts feed URL is issued only on request to ptsupport@mot.gov.il (ICD 2.2 §4.4). No self-service endpoint exists.; Developer deferred the MOT request on 4 Sep 2026 (checkpoint H1), so the four-week clock has not started.; Agent E can still build and test the parser against the published ICD and synthetic fixtures.

## Recorded metrics

**POC-1**

- `rows_parsed`: {'agency': 36, 'routes': 7786, 'stops': 35302, 'calendar': 63305, 'calendar_dates': 0, 'services': 63305, 'trips': 544338, 'stop_times': 20100370, 'shapes': 7139290, 'translations': 102514, 'fare_attributes': 15, 'fare_rules': 960910}
- `rows_loaded`: {'routes': 7786, 'trips': 544338, 'stops': 35302, 'calendars': 63305, 'trip_id_to_date': 1961317}
- `cold_refresh_seconds`: 180.0
- `peak_rss_mb`: 1441.7
- `ingest_seconds_offline`: 199.6
- `seven_prd_groups`: {'agency': 36, 'routes': 7786, 'trips': 544338, 'stops': 35302, 'stop_times': 20100370, 'calendar': 63305, 'shapes': 7139290}

**POC-2**

- `build`: {'wall_seconds': 34.0, 'peak_rss_mb': 3272.7, 'graph_size_mb': 681.2, 'memory_cap': 'uncapped (WSL2 VM ceiling 23.5 GiB on a 32 GB host)', 'service_window': ['2026-09-04', '2026-10-04']}
- `serving`: {'steady_rss_mb': 726.8, 'memory_cap_gb': 8, 'fits_in_8gb': True, 'peak_rss_mb_under_load': 941.3, 'cap_verified_bytes': 8589934592.0, 'load_test': {'feed_sha256': 'f26b63c21ac86704c1ad89ce137eee8f2d12a35aa10e34373dcbd36b0e083a93', 'generated': '2026-09-05T12:33:35.549633+00:00', 'workers': 16, 'seconds': 121.5, 'requests': 26715, 'requests_per_second': 219.9, 'http_status_counts': {'200': 26715}, 'latency_ms': {'p50': 57.2, 'p90': 149.3, 'p95': 162.9, 'p99': 180.4, 'max': 229.2}, 'memory_cap_gb': 8, 'cap_observed_bytes': 8589934592.0, 'peak_rss_bytes': 987024588, 'peak_rss_mb': 941.3, 'peak_rss_pct_of_cap': 11.5, 'samples': 33, 'container_state_after': {'oom_killed': False, 'status': 'running', 'restart_count': 0}}}
- `journeys`: {'total': 25, 'answered': 25, 'structural_pass_any': 24, 'structural_pass_first': 22, 'structural_pass': 24, 'structural_pass_first_itinerary': 22, 'structural_pass_generous_walk_profile': 25}

**POC-5**

- `overall`: {'correct': 68, 'total': 100, 'prd_bar': 20, 'meets_prd_bar': True, 'in_top5': 89}
- `by_category`: {'station': {'correct': 16, 'total': 20, 'in_top5': 18}, 'poi_university': {'correct': 8, 'total': 9, 'in_top5': 9}, 'poi_hospital': {'correct': 2, 'total': 5, 'in_top5': 4}, 'poi_mall': {'correct': 3, 'total': 4, 'in_top5': 4}, 'poi_landmark': {'correct': 11, 'total': 12, 'in_top5': 12}, 'address': {'correct': 4, 'total': 15, 'in_top5': 10}, 'neighborhood': {'correct': 9, 'total': 10, 'in_top5': 10}, 'misspelling': {'correct': 8, 'total': 10, 'in_top5': 9}, 'translit': {'correct': 4, 'total': 9, 'in_top5': 8}, 'near_dependent': {'correct': 3, 'total': 6, 'in_top5': 5}}
- `by_lang`: {'he': {'correct': 14, 'total': 19, 'in_top5': 18}, 'en': {'correct': 54, 'total': 81, 'in_top5': 71}}
- `near_pairs`: {'P095_P096': 'one', 'P097_P098': 'one'}
- `near_pairs_by_place_bias`: {'P095_P096': {'no_place': 'one', '1': 'one', '2': 'one', '3': 'one', '5': 'both', '10': 'one', '20': 'one'}, 'P097_P098': {'no_place': 'neither', '1': 'one', '2': 'one', '3': 'one', '5': 'one', '10': 'one', '20': 'both'}}
- `result_source`: {'osm': 24, 'gtfs': 72, 'other': 4}
- `latency_ms`: {'p50': 3.5, 'p95': 67.6, 'max': 180.6}
- `prd_named_queries`: {'P035': {'query': 'Dizengoff Center', 'scored': 'pass', 'distance_m': 83.2}, 'P003': {'query': 'HaShalom Station', 'scored': 'pass', 'distance_m': 52.7}}

## Known data problems

See [docs/known-data-problems.md](docs/known-data-problems.md).

