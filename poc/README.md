# Phase 0 POC — status

Generated 2026-09-04 12:40 UTC from `poc/results/` at commit `baacfaa`.
**Machine-generated. Do not hand-edit — run `python poc/poc_status.py --write`.**

## Dependency status (PRD §13)

| POC | Component | Status | Detail |
| --- | --- | --- | --- |
| POC-1 | Static Israeli transportation data | **NOT_STARTED** | no result file yet |
| POC-2 | Public transportation routing | **NOT_STARTED** | no result file yet |
| POC-3 | Realtime transit information | **NOT_STARTED** | no result file yet |
| POC-4 | Service alerts | **BLOCKED_ON_ACCESS** | No public feed URL exists; gated on MOT reply |
| POC-5 | Address and place search | **NOT_STARTED** | no result file yet |
| POC-6 | End-to-end journey | **NOT_STARTED** | no result file yet |

## Go / No-Go (PRD §12)

Phase 0 is PASS only when every row is PASS.

| Capability | Required | Actual | Source |
| --- | --- | --- | --- |
| Download current nationwide GTFS | yes | **—** | POC-1 |
| Parse GTFS | yes | **—** | POC-1 |
| Route using Israeli GTFS | yes | **—** | POC-2 |
| Walking + transit + transfers | yes | **—** | POC-2 |
| Obtain realtime arrivals | yes | **—** | POC-3 |
| Match realtime <-> GTFS | yes | **—** | POC-3 |
| Obtain service alerts | yes | **FAIL** | POC-4 |
| Resolve Israeli addresses/places | yes | **—** | POC-5 |
| Run full end-to-end query | yes | **—** | POC-6 |
| Confirm acceptable data usage terms | yes | **—** | POC-1 |

**0/10 capabilities green — Phase 0 verdict: NOT YET**

### Blocked on external access

- **POC-4 (Service alerts)** — The Service Alerts feed URL is issued only on request to ptsupport@mot.gov.il (ICD 2.2 §4.4). No self-service endpoint exists.; Developer deferred the MOT request on 4 Sep 2026 (checkpoint H1), so the four-week clock has not started.; Agent E can still build and test the parser against the published ICD and synthetic fixtures.

## Known data problems

See [docs/known-data-problems.md](docs/known-data-problems.md).

