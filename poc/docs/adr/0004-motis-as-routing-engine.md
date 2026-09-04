# D4 — MOTIS as the routing engine

**Status:** Accepted
**Date:** 2026-09-04

## Context

PRD §7 names MOTIS as the initial candidate and OpenTripPlanner as the alternative, and
requires the engine be self-hostable. Transitous already runs MOTIS with Israeli static
GTFS coverage, which is direct evidence the combination works.

## Decision

MOTIS. OTP stays documented as the fallback.

## Consequences

- Switching to OTP is a **decision**, not a fix an agent may make unilaterally. If the MOTIS
  import fails, the agent stops and writes up the failure.
- A genuine WSL2 memory raise must be attempted before any import failure is attributed to
  MOTIS — Docker Desktop's default cap is a configuration trap, not a finding.
- MOTIS also provides geocoding (D6), avoiding a second service in Phase 0.
