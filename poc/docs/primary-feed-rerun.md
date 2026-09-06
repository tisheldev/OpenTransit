# Primary-feed rerun — 5 September 2026

`israel-public-transportation.zip` is the accepted executable primary (ADR 0005). The ten-day feed is comparison only. Original evidence is preserved in `poc/comparisons/ten-day-2026-09-04/`.

Primary SHA-256: `f26b63c21ac86704c1ad89ce137eee8f2d12a35aa10e34373dcbd36b0e083a93`. Calendar window: 2026-09-04 .. 2026-10-04. The product name does not guarantee sixty days of service.

Ingest passed all ten E01–E10 checks and all five query validations. 544,338 trips and 20,100,370 stop_times parsed; five tables loaded. All 246,042 normalized mapping keys match TripIdToDate; known date windows overlap. Incomplete keys and missing/disjoint dates fail before loading. This is content compatibility, not realtime matching or per-service-date uniqueness.

Cold start completed in 180.0 seconds, downloading only the primary and mapping. MOT published newer bytes for that download; its separate hashes are in poc-1-cold-run.json. The run of record and routing retain the manifest-pinned September 4 bytes.

| Metric | Ten-day historical | Sixty-day primary |
| --- | ---: | ---: |
| Structural pass (any itinerary) | 21 | 24 |
| Structural pass (first itinerary) | 20 | 22 |
| Generous-walk structural pass | 22 | 25 |
| Build wall seconds | 40.0 | 34.0 |
| Build sampled peak MB | 3738.6 | 3272.7 |
| Graph MB | 910.8 | 681.2 |
| Idle median MB | 937.8 | 726.8 |
| Load peak MB | 1129.5 | 941.3 |
| Load p95 ms | 256.6 | 162.9 |
| Load requests/second | 168.8 | 219.9 |

Load: 26,715 requests over 121.5 seconds with 16 workers; HTTP status counts {'200': 26715}. Observed cap: 8 GiB. No OOM or restart. Measurements cover MOTIS alone; they do not establish full-stack capacity.

All 25 queries answered. J09 fails at default walking limits and passes at 30 minutes. J15 and J18 have qualifying alternatives ranked below itinerary 0. The H3 sheet is regenerated and awaits human route-quality judgment.

Comparison caveat: J17/J21/J23 corpus inputs changed after the old experiment; their improvements cannot be attributed solely to the feed. The table identifies all input changes, including rebased departure dates.

| Case | Outcome old → new | Structural old → new | First duration min old → new | Changed corpus inputs |
| --- | --- | --- | --- | --- |
| J01 | route → route | pass → pass | 18.0 → 18.0 | none |
| J02 | route → route | pass → pass | 26.0 → 26.0 | none |
| J03 | route → route | pass → pass | 31.0 → 31.0 | none |
| J04 | route → route | pass → pass | 35.0 → 35.0 | none |
| J05 | route → route | pass → pass | 25.0 → 25.0 | none |
| J06 | route → route | pass → pass | 27.0 → 27.0 | none |
| J07 | route → route | pass → pass | 23.0 → 23.0 | none |
| J08 | route → route | pass → pass | 39.0 → 39.0 | none |
| J09 | no-route → no-route | fail → fail | None → None | none |
| J10 | route → route | pass → pass | 44.0 → 44.0 | none |
| J11 | route → route | pass → pass | 82.0 → 84.0 | none |
| J12 | route → route | pass → pass | 49.0 → 51.0 | none |
| J13 | route → route | pass → pass | 98.0 → 100.0 | none |
| J14 | route → route | pass → pass | 171.0 → 171.0 | none |
| J15 | route → route | pass → pass | 136.0 → 154.0 | none |
| J16 | route → route | pass → pass | 85.0 → 87.0 | none |
| J17 | no-route → route | fail → pass | None → 30.0 | to |
| J18 | route → route | pass → pass | 124.0 → 124.0 | none |
| J19 | route → route | pass → pass | 71.0 → 71.0 | none |
| J20 | route → route | pass → pass | 130.0 → 130.0 | none |
| J21 | no-route → route | fail → pass | None → 24.0 | to |
| J22 | route → route | pass → pass | 100.0 → 100.0 | none |
| J23 | route → no-route | fail → pass | 409.0 → None | from |
| J24 | no-route → no-route | pass → pass | None → None | none |
| J25 | route → route | pass → pass | 80.0 → 74.0 | none |

The full comparison JSON also records changes in transfers, modes and first-itinerary passes. Search/H4 measurements remain historical; their executable runner now targets the primary but was not rescored in this routing task.

Reproduce: `python poc/gtfs/run_poc1.py`; `python poc/routing/run_import.py`; `docker compose -f poc/docker-compose.yml --profile serve up -d motis`; both `run_corpus.py` profiles; `stress_serving.py --workers 16 --seconds 120`; `measure_steady.py --seconds 150`; `write_result.py`; `render_h3.py`; `compare_results.py`; `python poc/poc_status.py --write`.
