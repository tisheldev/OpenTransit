# D5 — The 10-day GTFS feed is the primary input

**Status:** Accepted
**Date:** 2026-09-04

## Context

MOT publishes two different products. `israel-public-transportation.zip` (~157 MB) is the
long-horizon planned feed; `Gtfs_10_days.zip` (~249 MB) is the near-term one and is larger.
`docs/data-access-findings.md` §1: "for a journey planner the 10-day feed is the accurate
one, the 60-day one is for 'will this line exist in October'."

## Decision

`Gtfs_10_days.zip` is the primary input. The 60-day feed is downloaded and row-counted for
comparison so the decision is evidenced rather than asserted (corpus check E06).

## Consequences

- Journey correctness is judged against near-term data, which is what a user experiences.
- `TripIdToDate.zip` must be versioned in lockstep with whichever feed is loaded (E05).
- Both feeds change nightly, so every result records the feed hash it was produced from.

---

## Amendment, 4 Sep 2026 — this decision is now contested

Wave 0 inspection of the real feeds found two facts that were not available when this ADR
was written:

1. **The 10-day feed does not cover the current day.** Downloaded 4 Sep, its window is
   `20260905..20260914`. The 60-day feed does cover 4 Sep. See KDP-001.
2. **The two feeds express service days incompatibly** — `calendar_dates.txt` only versus
   `calendar.txt` only. See KDP-002.

Fact 1 undercuts the premise. `data-access-findings.md` §1 argued the 10-day feed is "the
accurate one" for a journey planner, which remains true about *accuracy*, but a feed whose
window opens tomorrow cannot answer PRD §39's `--depart-now` on its own.

**Status:** the primary-input choice is reopened and belongs to the developer, not to an
agent. Until it is decided, POC-1 loads the 10-day feed as written above and additionally
row-counts the 60-day feed, so the comparison is evidenced either way. POC-2 must state
which feed produced each journey result.
