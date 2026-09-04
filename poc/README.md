# Phase 0 POC — status

Generated 2026-09-04 17:47 UTC from `poc/results/` at commit `e283af9`.
**Machine-generated. Do not hand-edit — run `python poc/poc_status.py --write`.**

## Dependency status (PRD §13)

| POC | Component | Status | Detail |
| --- | --- | --- | --- |
| POC-1 | Static Israeli transportation data | **PASS** | 892,451 trips / 32,367,255 stop_times parsed, 5 tables in Postgres, 10/10 integrity checks pass; TripIdToDate unjoinable (KDP-008); licence terms unread (H2) |
| POC-2 | Public transportation routing | **PARTIAL** | MOTIS routes the Israeli feed: 25/25 cases answered, 21 structurally consistent; serving fits 8 GB with room to spare (1129.5 MB peak under load). Route quality is unjudged - checkpoint H3 pending. |
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

- `rows_parsed`: {'agency': 36, 'routes': 6804, 'stops': 30858, 'calendar': 0, 'calendar_dates': 10, 'services': 10, 'trips': 892451, 'stop_times': 32367255, 'shapes': 7058126, 'translations': 1979930, 'fare_attributes': 355, 'fare_rules': 1726708, 'networks': 73, 'levels': 4}
- `rows_loaded`: {'routes': 6804, 'trips': 892451, 'stops': 30858, 'calendars': 10, 'trip_id_to_date': 1961317}
- `cold_refresh_seconds`: 338.0
- `peak_rss_mb`: 1269.7
- `ingest_seconds_offline`: 218.4
- `seven_prd_groups`: {'agency': 36, 'routes': 6804, 'trips': 892451, 'stops': 30858, 'stop_times': 32367255, 'calendar': 10, 'shapes': 7058126}

**POC-2**

- `build`: {'wall_seconds': 40.0, 'peak_rss_mb': 3738.6, 'graph_size_mb': 910.8, 'memory_cap': 'uncapped (32 GB host; WSL2 VM ceiling raised to 23.5 GiB first - see notes)', 'detail': {'motis_version': '2.11.2', 'image_digest': 'sha256:6055f51eec43eeed28524037ca0161b96efe9cd05728eaa9ac04c20c2826d330', 'per_task_seconds': {'osr_street_graph': 4.88, 'adr_geocoder': 4.07, 'tt_timetable': 24.6, 'adr_extend': 1.14, 'matches': 2.81}, 'timetable': {'trips': 892451, 'locations': 30858, 'first_day': '2026-09-05', 'last_day': '2026-09-15'}, 'artifact_location': 'docker named volume poc_motisgraph, NOT a bind mount - see notes', 'samples': 'poc/routing/import-samples.jsonl'}}
- `serving`: {'steady_rss_mb': 937.8, 'steady_rss_pct_of_cap': 11.4, 'steady_measurement': {'condition': 'at rest, graph loaded, after serving the corpus and a 16-worker load test', 'samples': 25, 'seconds': 120, 'min_rss_mb': 916.5, 'max_rss_mb': 1062.9}, 'memory_cap_gb': 8, 'fits_in_8gb': True, 'peak_rss_mb_under_load': 1129.5, 'peak_pct_of_cap': 13.8, 'oom_killed': False, 'cap_verified_bytes': 8589934592.0, 'load_test': {'requests': 20632, 'workers': 16, 'seconds': 122.2, 'requests_per_second': 168.8, 'http_status_counts': {'200': 20632}, 'latency_ms': {'p50': 62.2, 'p90': 195.5, 'p95': 256.6, 'p99': 377.9, 'max': 670.6}}, 'samples': 'poc/routing/serving-steady-samples.jsonl, poc/routing/serving-stress-samples.jsonl, poc/routing/serving-samples.jsonl'}
- `journeys`: {'answered': 25, 'structural_pass': 21, 'total': 25, 'structural_pass_first_itinerary': 20, 'structural_pass_generous_walk_profile': 22, 'wttw_shape_cases': 20}

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

