# ADR 0008 — bounded minute schedule interpretation

**Status:** Accepted technical interpretation for implementation; full-feed policy validation passes, managed candidate acceptance remains open. **Date:** 30 September 2026.

The user delegated routine technical decisions while retaining the existing acceptance criteria. Preserve raw source chronology failures and separately validate the pinned engine's minute interpretation. Rejecting every subminute reversal would exclude usable schedules already interpreted at minute precision; an arbitrary tolerance, unbounded clamping or silently rewriting source rows would obscure their meaning. This decision permits only the precision-derived bounds below and requires attributable parity evidence.

The accepted MOTIS v2.11.2 image is `sha256:6055f51eec43eeed28524037ca0161b96efe9cd05728eaa9ac04c20c2826d330`. Its release source `061857d38a375248ae62b4ce722753368a75e474` [dependency lock](https://github.com/motis-project/motis/blob/061857d38a375248ae62b4ce722753368a75e474/.pkg.lock) pins Nigiri `0a08a1c09dad25c5d892b2fd7166b03e82d62970`. The [time parser](https://github.com/motis-project/nigiri/blob/0a08a1c09dad25c5d892b2fd7166b03e82d62970/src/loader/gtfs/parse_time.cc) discards seconds; the [flattened event projection](https://github.com/motis-project/nigiri/blob/0a08a1c09dad25c5d892b2fd7166b03e82d62970/include/nigiri/loader/gtfs/local_to_utc.h#L211-L230) takes a cumulative maximum. This source interpretation is checked against the pinned binary, rather than treating its import success as proof.

## Interpretation and bounds

For policy `motis-minute-bracket-v1`, flatten calls in original numeric stop sequence as first departure, next arrival, next departure, continuing through final arrival. First arrival and final departure remain raw validated fields but are excluded effective engine events. For raw service seconds `r[i]`, calculate:

```text
q[i] = max(q[i-1], 60 * floor(r[i] / 60))
60 * floor(r[i] / 60) <= q[i] <= 60 * ceil(r[i] / 60)
abs((q[i] - q[i-1]) - (r[i] - r[i-1])) < 60 seconds
```

Use zero as the initial predecessor. Both bounds apply to every effective event/adjacent interval, not only detected anomalies. Exact-minute events cannot move, cumulative drift cannot exceed an event's own bracket, and interval distortion cannot exceed ordinary minute quantization. The rule is independent of the observed 2–40-second decreases. Malformed times, same-call departure-before-arrival, invalid sequence/reference/calendar/pairing/coverage and identity loss remain errors. Do not wrap a day, sort calls by time, delete calls or derive service dates from suffixes. Missing fields need a separately verified interpolation policy; do not guess effective clocks.

Preserve raw rows, hashes, acquisition times and raw chronology verdicts. Record effective chronology separately; this decision does not turn raw integrity failures into a new PoC pass. Include policy/version/source pins in generation identity and the hashed source-call index. Expose transit timetable resolution as 60 seconds, separately from walking duration/geometry. Any engine/parser change requires renewed conformance. Revalidation or projection cannot renew upstream freshness.

## Evidence and remaining acceptance

[Raw diagnosis](../../../services/api/results/chronology-diagnostic-20260930-02.json) records 832 decreases across 168 full trip definitions; 111 are active in the candidate window. [Projection evidence](../../../services/api/results/chronology-projection-20260930-02.json) checks all 5,388 effective events of those trips: no bracket or interval-bound violations; engine-minus-raw clocks range from −59 to +1 seconds. This targeted measurement is not a full-feed run.

[Actual image parity](../../../services/api/results/chronology-image-parity-20260930-01.json) matches all 38 effective events of the cross-minute-clamped active trip on October 5 and October 25; its dormant counterpart returns 404 without rebasing. [Full-feed audit 5](../../../services/api/results/m2-validation-attempt5-20260930.json) checks all 425,160 profiles and 31,308,378 effective events with zero policy errors; it preserves the raw diagnostic failure, and does not establish build or memory acceptance. Pure boundary checks pass. Source-index/engine trip and departure parity, generation build/probe and activation remain required before candidate acceptance. Human H3/H4, static terms, deployment/capacity and API-before-client gates are unchanged. Realtime and alerts remain deferred.
