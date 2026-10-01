# Scheduled data and generation contracts

This documents the provisional local M2 contract. [PROJECT_STATUS.md](../PROJECT_STATUS.md) records implementation and evidence; [API PRD](api-prd.md) governs acceptance. Realtime and alerts remain deferred.

[Domain language](../CONTEXT.md) distinguishes raw service clocks, effective service clocks and dated trip occurrences. [ADR 0008](../poc/docs/adr/0008-bounded-minute-schedule-interpretation.md) accepts a bounded minute interpretation for implementation; raw chronology remains recorded as failed evidence and full candidate acceptance is still pending.

## Identity

Preserve complete GTFS `stop_id`, `route_id` and `trip_id` values as strings. Do not identify a stop by its public code or a route by its displayed line number. **M2.8 decision (1 October 2026):** public reference IDs are `mot:stop:<complete stop_id>` and `mot:route:<complete route_id>`. Trip references stay the dated engine identity issued by one generation and are not durable across publications. Evidence: the [September 30 → October 1 comparison](../services/api/results/m2-id-stability-20261001-01.json) retains 35,321/35,321 stops and 7,873/7,884 routes with no metadata changes (11 routes removed). Trips retain 290,308/425,160 IDs: 134,852 removed and 134,815 added, mostly a daily `_ddmmyy` suffix roll. 284,515 retained trips change `service_id` ([field breakdown](../services/api/results/m2-id-stability-20261001-01-trip-fields.json)). Clients may store stop and route IDs and must handle a removed route. They must re-plan or re-query rather than reuse a `tripRef` from an older generation. The decision rests on one consecutive pair; the daily fetch adds pairs, and a later pair contradicting it reopens the decision.

`opentransit compare-ids` compares full IDs and selected metadata and writes a new report. Acquisition dates are caller-supplied, explicitly unverified by this command; review the underlying source events before calling the comparison consecutive-daily evidence. A normalized TripIdToDate key overlap cannot establish realtime matching or semantic ID stability.

M1 journey responses retain the pinned engine's full dated `engineTripId`, complete `sourceTripId`, service date and occurrence start time. M3 trip details use the complete dated engine identity as `tripRef` and reconcile stop/route references with the reference namespace; do not strip a trip suffix or substitute another service date.

M3 contract evidence includes the [upstream v2.11.2 OpenAPI](../services/api/tests/fixtures/motis-v2.11.2/openapi.yaml), its [source/hash provenance](../services/api/tests/fixtures/motis-v2.11.2/provenance.json) and [actual preserved-M1 response provenance](../services/api/tests/fixtures/motis-v2.11.2/responses-provenance.json) for plan, stoptimes and trip. The YAML was obtained from the release tag, not an OpenAPI endpoint exposed by the running image. Real response samples establish concrete engine behavior, without accepting the unfinished M2 candidate or H3 usability. Schedule-only stoptimes uses the documented `realtimeMode=OFF`.

## Immutable generation

M2 creates a new directory containing `manifest.json`, `config.yml`, `validation.json`, `reference.sqlite`, `motis/` and `import.log`. Inputs remain retained separately and are mounted read-only during import. The manifest includes hashes and source provenance, parser/reference schema versions, import configuration and window, pinned engine digest, artifact hashes, data mode and build outcomes. Generation identity includes every recorded interpretation input. Build resources and measurements are separate from serving capacity.

The reference database records its generation, input hash, logical content hash and schema. Ordered pattern calls retain repeated stops, sequence positions, pickup/drop-off rules, direction and headsign. Unknown accessibility and platforms remain unknown. Stop/station detail preserves parent/platform relationships. A route lookup requires at least one stop, operator or line-label selector.

Startup verifies the managed graph tree, configuration and reference hashes and the reference's input/generation identity. A separate passed candidate probe must bind those artifacts to the configured engine origin before managed routing/readiness is enabled. A successful health request alone does not establish graph identity or H3 usability. M1's isolated legacy graph remains an explicit compatibility path, without full M2 readiness.

Every request captures one runtime snapshot containing generation, reference and engine client before awaiting dependencies. Local Linux activation and acknowledgement/draining are implemented with focused synthetic checks; real activation/rollback and drain proof remain incomplete. Production replaces complete Fargate tasks. A failed candidate must leave the previous snapshot serving.

## Translation linkage and controlled repair

Modern GTFS stop-name translations match the full `record_id` first; exact `field_value` is the fallback. Legacy `trans_id,lang,translation` rows use `trans_id` as the original stop-name text, never as a stop ID. Preserve exact original text when matching, apply one shared-name translation to every matching stop, and reject conflicting rows for the same selector/language. Normalization belongs in search, after source linkage.

The [September 30 repair](../services/api/results/m4-translation-repair-20260930-01.json) clones the sealed parent into a new parser-version-2 generation, replacing translation rows and resealing reference/identity hashes. It preserves source acquisition/validation times, source schedules and graph/config hashes. Ordinary artifact reuse still requires exact identity; it does not quietly upgrade an old database. The [repaired candidate probe and native-volume verification](../services/api/results/m4-repaired-probe-runtime-20260930-01.json) pass; [English functional API integration](../services/api/results/m4-english-functional-http-20260930-03.json) passes; readiness remains unresolved separately, with quality/latency and final acceptance still required.

## Dates and freshness

API instants require explicit offsets. Service calendars use `Asia/Jerusalem`; extended GTFS hours belong to their originating service date. The [matching-generation HTTP check](../services/api/results/m3-m4-functional-http-20260930-01.json) and [saved-body assertions](../services/api/results/m3-functional-http-body-assertions-20260930-01.json) verify a preceding-service-date trip crossing midnight and both October 25 DST-fold occurrences. Consolidated time/constraint acceptance remains required. Declared import coverage is half-open, with actual active dates recorded; a covered no-service day can legitimately return no route.

Comparison and elapsed duration must use UTC instants, including when both display timestamps share the Jerusalem timezone. The repeated October hour can have an earlier displayed clock time and a later actual instant. Service-date identity remains independent of displayed wall time. The [September 30 timing diagnosis](../poc/docs/known-data-problems.md#kdp-017--september-30-feed-has-decreasing-adjacent-scheduled-times) is a separate source-quality issue; UTC conversion cannot repair decreasing GTFS service-day values.

`builtAt` records build completion. `validationRunAt`/`validatedAt` record local validation, while `sourceCheckedAt` records the conservative paired upstream acquisition/check time. Revalidating preserved bytes cannot make upstream data fresh. Missing source-check provenance prevents readiness. M1 preserves its original preflight timestamp compatibility.

Fetching appends immutable acquisition events. Only a successful complete GTFS/TripIdToDate validation produces a paired-check record and canonical input snapshot. `OPENTRANSIT_SOURCE_CHECK` can supply that record when loading a replacement runtime snapshot: both hashes must equal the generation inputs, both sources must have succeeded and validation must follow acquisition. This renews freshness without changing the immutable manifest or generation identity. Failed or changed-pair evidence cannot renew the old generation.

Current thresholds are under 30 hours current, 30–48 hours aging, 48 hours–7 days stale, and at least 7 days expired. A future source timestamp outside five minutes' clock tolerance is unusable. Covered aging/stale data carries warnings; expired coverage/source age returns unavailable rather than an empty success. Freshness is unrelated to live capability availability.

## Pagination and capability truth

Reference pages default to 20 items and allow at most 100. Cursors bind exact query, generation and sort position. A malformed, changed-query or previous-generation cursor returns `422 INVALID_CURSOR`; no offset pagination is promised. Nearby selectors are `near=latitude,longitude`; bbox order is `west,south,east,north`. Exactly one spatial selector is required, nearby radius is at most 5 km and bbox area is at most 100 km².

Data responses include `data`, generation/freshness/mode/attribution metadata and an optional `page.nextCursor`. Predictions and delays remain null; realtime and alerts explicitly report `not_enabled`. Human H3/H4 reviews, usage terms and operational/deployed acceptance are separate from structural validation and synthetic checks.

## Place selections

Search candidates expose a directly usable `locationRef`. Stops/stations use `{kind: stop, stopId: ...}`. POIs and addresses use `{kind: place, placeRef: ...}`; the unsigned `mot:place:v1:` token contains exact selected coordinates, generation ID, kind and candidate identity hash. It is a versioned coordinate selector, not an authenticated OSM identity. Journey planning validates its exact fields and generation, then uses those coordinates without another geocoder request; malformed or other-generation selections return `422 INVALID_PLACE_REF`.

Valid addresses may have an empty upstream ID. Their identity includes exact label, street/house number, locality and coordinates; distinct houses must not collapse. Street-only results remain labelled as such. Backend orders use deterministic alternation because their scores are incomparable; `matchedTypes` denotes successful searches, including valid empty results. Failed categories appear in `unavailableTypes`/`partial`, or a sanitized 503 when none succeed. Source-language and category quality still require measured H4 evidence.
