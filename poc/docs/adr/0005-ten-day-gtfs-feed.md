# D5 — The 60-day GTFS feed is the primary input

**Status:** Accepted amendment, 5 September 2026, by explicit user instruction.
The historical filename is retained so existing links continue to resolve.

`israel-public-transportation.zip` plus `TripIdToDate.zip` is the executable
primary feed for ingestion, MOTIS routing and geocoding. `Gtfs_10_days.zip`
is an explicit comparison input only. There is no fallback to it.

The sampled 60-day product has 246,042/246,042 normalized mapping keys in
TripIdToDate; the ten-day sample has zero overlap. Preserve full GTFS trip IDs;
strip the `_ddmmyy` suffix only for mapping lookup. Normalized keys are not
unique journey identities.

Ingest and graph build reject incomplete key coverage and absent or disjoint
date windows before loading. Input hashes are pinned together. This proves
content compatibility, not identical publication versions or successful realtime
matching: TripIdToDate contains no publication identifier, and per-service-date
mapping ambiguity remains an integration check.

Derive the corpus and graph window from `calendar.txt` plus
`calendar_dates.txt` exceptions. Do not require `feed_info.txt`; the sampled
primary lacks it. Use `Asia/Jerusalem` for local departure offsets. Disable
calendar extension. The sampled actual window is 2026-09-04..2026-10-04;
the product name does not guarantee sixty days of service.

The original results and corpus are preserved in
`poc/comparisons/ten-day-2026-09-04/`. Current ingest/routing results and the H3
sheet are generated from the primary. See [rerun findings](../primary-feed-rerun.md).
H3 route quality and H4 search quality still require human review.
