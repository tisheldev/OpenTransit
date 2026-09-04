# D1 — Phase 0 follows the PRD POC, not the vertical-slice plan

**Status:** Accepted
**Date:** 2026-09-04

## Context

Two documents describe Phase 0 incompatibly. `PRD.md` §5–§13 defines it as a feasibility
POC (POC-1…6) with a `/poc` tree, almost no UI, and a hard rule in §5.1: frontend
development does not begin until Phase 0 passes. `docs/phase-0-mvp-plan.md` proposes
vertical slices in which every milestone improves a visible client, and builds a client
skeleton on day one. That plan is marked "Status: Proposed" and was never ratified.

## Decision

Phase 0 follows the PRD. No client. The deliverable is the `/poc` tree, a CLI, and a
scored Go/No-Go table.

## Consequences

- The vertical-slice plan is deferred whole to Phase 1, where its premise — that a client
  reveals contract mistakes — is sound.
- Phase 0 cannot demonstrate perceived speed. That is fine: Phase 0 tests whether the data
  can be had, not whether the product feels fast.
- Work items map across cleanly. The MVP plan's D1.1/D1.2/D1.3 are POC-1 and POC-2;
  D2.1/P2.1 are POC-5. Little is thrown away by choosing the PRD framing.
