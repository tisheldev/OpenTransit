# Scheduled API load scenarios

**Prepared, not run.** Use installed **k6 1.x** (legacy end-of-test JSON summary)
and Python 3.11+ for the offline join. These files do not install packages, fetch
feeds, build graphs or start the API. Run only against an authorized test origin.
[Operations](../../docs/operations.md) and [AWS drafts](../../deploy/aws/README.md)
describe the prerequisites.

Copy `fixtures.example.json` to an operator-owned file; replace every `REPLACE_` for
selected scenarios. Use offset-bearing times inside coverage, actual `mot:stop:` IDs
and dated trip refs returned by that generation's departures. Use curated public/
synthetic locations, never passenger history. Add long, short, arrive-by, valid no-route
and overnight journeys; Hebrew/English category and ambiguous searches; several stops
and trips. Preserve fixture SHA-256 and generation metadata. The example is a format
template, not a representative acceptance corpus.

From the repository root, in a POSIX shell:

```sh
RUN=/absolute/path/to/new-load-evidence
mkdir -p "$RUN"   # choose a new directory for every run
k6 version
k6 run -e BASE_URL=https://authorized-preview.example \
  -e FIXTURES=/absolute/path/to/completed-fixtures.json \
  -e SCENARIO=journeys -e JOURNEYS_RPM=60 -e DURATION=1m \
  -e CORRELATE=1 --log-format raw --log-output "file=$RUN/client.log" \
  --summary-export "$RUN/k6-summary.json" tools/load/scenarios.js
```

All four endpoints together use `SCENARIO=all` (default). Defaults offer 10 RPS:
30% journeys / 30% places / 25% departures / 15% trips. The design's proposed M7 mix
uses references/status for the final 15%; trips cover the requested endpoint here
and **do not replace that acceptance mix**. Each iteration sends one request, with no
retries or discovery traffic. For 50 RPS over 15 minutes:

```sh
k6 run -e BASE_URL="$BASE_URL" -e FIXTURES="$FIXTURES" -e DURATION=15m \
  -e JOURNEYS_RPM=900 -e PLACES_RPM=900 -e DEPARTURES_RPM=750 -e TRIPS_RPM=450 \
  -e CORRELATE=1 --log-format raw --log-output "file=$RUN/client.log" \
  --summary-export "$RUN/k6-summary.json" tools/load/scenarios.js
```

Use separate directories with `DURATION=30m` for soak; separate cold/warm and rollout
runs. Select `journeys`, `places`, `departures` or `trips` individually with `SCENARIO`.
`VUS_PER_SCENARIO`/`MAX_VUS_PER_SCENARIO` default to 10/50; record changes and generator
CPU. Arrival-rate pacing keeps offered traffic independent of slowdown; dropped
iterations fail. `TIMEOUT` defaults to 5s; `AUTH_TOKEN` is optional (environment only).
Never enable HTTP debug output: it can reveal coordinates, queries or tokens.

Console/summary JSON give per-endpoint client p50/p95 via `client_round_trip_ms`,
failure rate, partial search rate and dropped iterations. Tagged `response_status`
samples separate 429/503/504 in a raw output stream; add `--out json=$RUN/metrics.json`
when status breakdown is needed. Default thresholds are client p95 <400 ms and
<0.5% failed responses per endpoint; `MAX_CLIENT_P95_MS` is adjustable. Fast errors
remain in latency samples and fail the error threshold. Valid empty/no-route results
are success; partial search is counted separately. Envelope checks are not H3/H4,
category completeness, trip parity or mixed-generation acceptance.

## Separate server timing

The current API logs sanitized `request_id`, route template, status and `duration_ms`;
it has **no Server-Timing header**. Export those application logs only to
`$RUN/server.log` (plain lines or JSONL with `message`). Keep access logging disabled.
`CORRELATE=1` records only IDs, bounded endpoint names, status and timing:

```sh
python tools/load/server_timing.py --client-log "$RUN/client.log" \
  --server-log "$RUN/server.log" --output "$RUN/paired-timing.json"
```

The join reports p50/p95 for whole client round-trip, API middleware duration and
per-request residual. Missing server samples stay **null**, with unmatched counts;
never substitute zero or claim a server pass without enough matched samples.
Middleware duration ends at response creation, before full network/body completion.
Client time includes DNS/connect/TLS/body read and client overhead. k6
[http_req_duration](https://grafana.com/docs/k6/latest/using-k6/metrics/reference/)
excludes initial connection time; `http_req_waiting` includes network and is not server
processing time. Subtract paired samples, never independent percentiles; residual is
not pure network latency. Correlation logging can limit generator throughput.

Record offered/achieved RPS, errors, cold/warm distinction, client region (weekday
evenings from Israel for M8), UTC window, k6 version, fixture hash, API commit, image/
task digests, source freshness and generation(s). Compare server journey p95 <350 ms
and search/departures <40 ms separately from deployed client p95 <400 ms. Record
full-stack CPU/RAM/disk and task overlap under 8 GiB externally; k6 cannot prove those
limits, availability, rollback or generation consistency. Public quotas and any private
quota exemption need separate runs: the API's per-client limiter (on by default; see
[operations](../../docs/operations.md#rate-limiting)) answers one generator with `429`
within seconds, so capacity runs need `OPENTRANSIT_RATE_LIMIT_ENABLED=0` on the target and
the quota path is tested with limits on. No acceptance evidence is claimed by this toolkit.
