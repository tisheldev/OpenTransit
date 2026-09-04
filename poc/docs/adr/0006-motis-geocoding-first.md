# D6 — MOTIS built-in geocoding first

**Status:** Accepted
**Date:** 2026-09-04

## Context

POC-5 must prove Israeli place search works in Hebrew and English across addresses, stops,
stations and POIs. Options: MOTIS's built-in geocoder, a self-hosted Photon/Nominatim, or a
hosted provider. PRD §10 restricts public Nominatim to limited experimentation — 1 req/s,
no client-side autocomplete.

## Decision

MOTIS built-in geocoding first. Public Nominatim only as a bounded comparison at ≤1 req/s.
No self-hosted geocoder and no paid provider in Phase 0.

## Consequences

- Avoids standing up a second service before evidence says one is needed, consistent with
  the MVP plan's rule that infrastructure follows measurement.
- If MOTIS geocoding fails the PRD §10 bar (≥20 of the corpus resolving), that is a finding
  that justifies Photon in Phase 1 — recorded with the per-category breakdown that shows
  *which* query classes failed.
- The corpus deliberately includes six `near`-dependent queries where the same string has
  different correct answers by bias point. An engine ignoring `near` cannot pass both halves.
