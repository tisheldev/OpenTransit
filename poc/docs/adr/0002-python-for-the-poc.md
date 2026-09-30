# D2 — Python for the POC

> Historical references: the superseded vertical-slice and execution plans cited below were removed on 2026-09-21 and remain recoverable at Git commit `3398826`. Read [the dashboard](../../../PROJECT_STATUS.md) and PRD for current sequencing; the client follows the completed Phase 1 API. This note does not change the accepted decision.

**Status:** Accepted
**Date:** 2026-09-04

## Context

`system-design.md` §3 shortlists ASP.NET Core 9 and Python for the API and sets an explicit
decision rule: pick the faster language for whoever is writing it, because "a backend
written in a language the author is slow in does not get finished." `phase-0-mvp-plan.md`
§4.1 separately recommended TypeScript. PRD §25 says the language is not a product
requirement.

## Decision

Python 3.13 for the POC. Decided by the developer, 4 Sep 2026, on the stated grounds that
it is the faster language for them.

**Original scope (September 4):** PoC only. The September 25 amendment below extends the choice to the production API.

## Consequences

- No Phase 0 PASS/FAIL turns on the language — no kill criterion in PRD §38 mentions it —
  so this is the one deviation from "run the production spec" (plan §3.1a) that costs
  nothing in evidence quality.
- system-design §136 independently argues Python is the better tool for the cold path:
  HTTP polling, JSON parsing, reconciliation joins, Parquet writing. That is most of what
  Phase 0 is, so POC-1 and POC-3 code plausibly carries into `Transit.Ingest` even if the
  API lands on .NET.
- If the API does land on .NET, the repository carries two toolchains. system-design §140
  already weighed and accepted that seam.

## Accepted amendment — 25 September 2026

The user selected Python for the backend after comparing Python/FastAPI, C#/ASP.NET Core and TypeScript/Node.js. Use **Python with FastAPI** for the Phase 1 API, retaining Python for ingestion. This supersedes the original PoC-only scope and older documents describing the API runtime as undecided.

The choice builds on the existing Python work and the developer's recorded preference. MOTIS continues to perform routing computation. This decision does not establish API performance or approve other pending architecture choices.

During M1, select supported runtime/framework versions, verify compatibility and lock dependencies. The PoC's Python 3.13 pin is historical evidence, not an automatic production pin. Measure API overhead and worker memory as functionality is introduced; no free-threaded runtime or multi-worker topology is implied. Realtime remains deferred under the schedule-first PRD revision.
