# D2 — Python for the POC

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

**Scope:** this binds the POC only. The Phase 1 API language remains open.

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
