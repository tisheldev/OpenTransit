# OpenTransit Israel

An API-first, open-source transit planner for Israel. The repository currently contains feasibility experiments and design documents; the production API has not been implemented.

**Current state (5 September 2026): Phase 0 is NOT YET complete — 5/10 recorded capabilities green.** Routing and search remain `PARTIAL`, with human quality reviews pending. Realtime, alerts access, end-to-end integration and usage terms remain unresolved.

## Start here

**Ready for your review:** [decision and Ministry application pack](docs/decision-pack/README.md), including Hebrew email drafts, the form-completion guide and the recommended technical choices.

1. [Next steps and Phase 1 implementation plan](docs/next-steps.md) — what to build, prerequisites, decisions and completion criteria.
2. [PoC findings](poc/docs/findings.md) — interpretation of the experiments and their limits.
3. [Recorded status](poc/README.md) and [raw results](poc/results/) — machine evidence, including pending review sheets.
4. [Product requirements](PRD.md) — product scope and phase gates.
5. [System design](docs/system-design.md) and [architecture](docs/architecture.md) — proposed production shape; read their current-status notes first.
6. [Decision records](poc/docs/adr/) and [known data problems](poc/docs/known-data-problems.md) — accepted choices, reopened choices and feed quirks.

The PRD governs scope; accepted ADRs record explicit decisions; versioned results establish what was measured. Design estimates and historical plans do not override those. Recommendations in the next-step plan are not accepted decisions.

## Working with the PoC

Python 3.13 is the recorded PoC runtime. Inspect status without Docker, credentials or downloads:

```sh
python poc/poc_status.py
```

Regenerate the status report after recording new results:

```sh
python poc/poc_status.py --write
```

[Routing instructions](poc/routing/README.md) run the accepted 60-day primary with TripIdToDate compatibility enforced. Historical ten-day evidence is preserved in `poc/comparisons/ten-day-2026-09-04`. A reproducible dependency lock and fresh-checkout runbook are still required before implementation starts.

## Repository map

| Path | Purpose |
| --- | --- |
| `docs/` | Current planning and production design |
| `docs/archive/` | Superseded plan and historical HTML presentations |
| `poc/gtfs/`, `poc/routing/`, `poc/geocoding/` | Executable feasibility experiments |
| `poc/corpora/` | Test cases and their source provenance |
| `poc/results/`, recorded routing outputs | Evidence; retain with input hashes |
| `poc/data/manifest.json` | Input provenance; downloaded feeds remain local and ignored |

See the [cleanup record](docs/repository-cleanup.md) for what was removed, archived and intentionally retained.
