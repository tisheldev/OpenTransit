# Human quality review: prepared queue

**H3 is ready for review:** [the regenerated route-quality sheet](../../poc/results/journeys-h3-review.md) uses the accepted 60-day primary. See [changed results](../../poc/docs/primary-feed-rerun.md). H4 search results still require a new generation and human review.

## What I can decide and verify

Check stop/trip identity against the actual source, geometry continuity, transfer timing, operating calendars, service-day boundaries, valid no-route cases, input-coordinate errors and whether a search result is actually the requested feature. Recheck repeated coordinates together; do not widen tolerance merely to improve a score.

## What you judge after the rerun

For each route: would you take it, and is any transfer or walk unreasonable? For each ambiguous search result: does it select the intended destination/entrance? Record `reasonable`, `not reasonable` or `unsure` plus one short reason. No blanket acceptance is inferred from approving the technical package.

The route packet will cover the PRD's ten requirements:

| Required case | What I will show you |
| --- | --- |
| Tel Aviv → Ramat Gan | Exact departure, itinerary, walking and alternatives |
| Tel Aviv → Petah Tikva | Same, with mode/transfer explanation |
| Tel Aviv → Haifa | Rail/bus alternatives and arrival comparison |
| Tel Aviv → Jerusalem | Mode and access/egress tradeoffs |
| Bus → train | Actual transfer locations and time margin |
| Train → bus | Connection and destination access |
| At least one transfer | Why the connection is usable |
| Late-night journey | Services actually operating that night |
| Service-day boundary | Calendar date plus GTFS time beyond 24:00 |
| Genuine no-route | Verified inaccessible endpoint, without confusing a walking cap with no service |

Each populated row will include feed/config/corpus hashes, exact request time, a normalized timeline, comparison evidence against Moovit/Google/BetterRail as relevant, and a blank human verdict. Comparisons must use matching dates/times where supported; unavailable comparison dates remain a limitation, not an invented agreement.

## Search judgments likely to need you

| Existing case | Reason for review |
| --- | --- |
| P012, airport | Centroid versus usable terminal/boarding access |
| P023 | Satellite stop versus intended place |
| P065, Herzl 50 Haifa | Corpus coordinate is uncertain; engines agreeing does not prove the house number |
| P081 | Plausible engine answer versus approximate ground truth |
| Chain venues / near-pairs | Intended branch and location bias; multiple branches may all be legitimate candidates |

Existing evidence: [route sheet](../../poc/results/journeys-h3-review.md), [place sheet](../../poc/results/places-h4-review.md), [venue sheet](../../poc/results/venues-h4-review.md). These remain historical and unapproved. The next run will keep generated evidence separate from the human verdict file so regeneration cannot erase your decisions.
