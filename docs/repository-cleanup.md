# Repository cleanup — 5 September 2026

## Completed

- Added a root README with project state, document precedence, navigation and a safe status command.
- Added the next-step plan covering remaining feasibility work, M1 implementation scope, decisions and required documents.
- Moved the unratified vertical-slice plan to `docs/archive/`; retained a redirect at its old path.
- Moved the three historical HTML presentations to that archive. They remain available as design history.
- Added status notes to older design/execution documents so estimates and obsolete choices are not mistaken for current results.
- Corrected the consolidated findings: POC-2/5 are partial, ADR 0005 is reopened rather than reversed, and a geocoder comparison does not establish Photon as the solution.
- Added root ignore rules for Python caches, local environment files and redirected import output.
- Deleted three disposable Python cache directories and `poc/routing/run_import.out`, a four-line console summary whose measurements remain in the structured import results and full import log.

## Retained deliberately

The raw JSON responses, JSONL samples, full import log, corpora, OSM venue source sample, manifest and review sheets support the measured results or are consumed by runners. Their existing paths remain intact. Downloaded GTFS/OSM files and Docker volumes were not deleted; the historical feed bytes may no longer be obtainable from the upstream rolling URLs.

PoC source and agent briefs remain as implementation/provenance material. No production code, dependency stack, cloud deployment or external communication was introduced by this cleanup.

## Follow-up engineering work

- Lock Python dependencies and pin MOTIS in a new development configuration. The recorded PoC Compose file still uses `latest`; the exact tested image digest is preserved in `poc/results/poc-2.json`.
- Make runners write immutable run directories with input/config/corpus provenance. Current scripts overwrite fixed result paths; `run_import.py` also clears the graph volume. Preserve old evidence before a rerun.
- Remove hardcoded feed paths, dataset names and dates together when the primary-feed decision is accepted.
- Strengthen pairing validation: `check_pairing()` currently records date-window overlap but decides acceptance from key overlap alone, with a 50% default threshold. That cannot serve as production date-aware reconciliation or publication consistency validation.
- Introduce focused tests and CI with M1. This documentation cleanup does not establish runtime routing or realtime correctness.

Avoid broad rules ignoring all JSON, JSONL or logs: those would hide the project's evidence.
