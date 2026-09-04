# D3 — Postgres + PostGIS for cold storage

**Status:** Accepted
**Date:** 2026-09-04

## Context

An embedded engine (DuckDB, SQLite) would be simpler to run locally. But `system-design.md`
§169 names Postgres + PostGIS as the production cold store, and a feasibility test that
passes on a substitute has not tested the thing being built.

## Decision

Postgres + PostGIS in a container, matching production. Applies to POC-1.

`stop_times` and `shapes` are **parsed and validated but not loaded** (D3a). system-design
§173: loading `stop_times` for the 60-day feed is ~100M rows and "buys nothing, because
MOTIS already answers both journeys *and* stop departures from RAM." Five tables are
loaded: routes, trips, stops, calendars, `TripIdToDate`.

## Consequences

- POC-1's database is small, so Postgres costs nothing in convenience here.
- PRD §6 still requires proving all seven files can be parsed and understood, so parse
  coverage is unchanged — only the load set is narrowed.
- DuckDB remains the right tool for Phase 4 analytics over object storage (system-design
  §297). This ADR does not exclude it there.
