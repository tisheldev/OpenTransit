# Working in OpenTransit

## Required session workflow

1. Read `PROJECT_STATUS.md` before project work, then inspect Git status. Read only the linked requirements, decisions and runbooks relevant to the task.
2. For implementation or documentation changes, claim a task in the status file's active-work table before editing. Reuse an existing task ID; add a short new ID for work outside the queue. Record agent/session identity, UTC timestamp, scope and next step. A read-only question does not need a claim.
3. Keep the dashboard current when scope, evidence, blockers or accepted decisions change. A user instruction may revise scope; record it without silently changing other phase gates.
4. Before ending or pausing work, update the task state and handoff. Include what changed, validation actually run, unresolved issues and the exact next action. Completed work belongs in recent outcomes; paused work keeps its active row. If nothing changed during a read-only session, no status edit is needed.
5. Re-read the active table before editing it. Preserve other sessions' entries and unrelated user changes. Claims are not locks; stale claims require checking before takeover. Use narrow edits to shared files.

## One dashboard, supporting evidence

- `PROJECT_STATUS.md` is the only maintained cross-project status and session handoff. Keep it under roughly 160 lines and retain at most five recent outcomes. Replace stale summaries instead of appending transcripts.
- `PRD.md` governs product scope and phase gates. Accepted ADRs record decisions. Code and versioned results establish what exists and was measured. The dashboard summarizes these; it does not override them.
- `docs/next-steps.md` holds detailed execution/acceptance criteria, not a second status log. Design documents are proposals unless explicitly accepted.
- Do not create new `STATUS`, `TODO`, plan, agent-brief, cleanup-report or session-summary documents to describe the same work. Update the existing artifact. Add a document only for a distinct durable purpose and link it from the dashboard's document map or the relevant runbook.
- Preserve source, raw results, corpora, hashes, human reviews and accepted decisions. Git is the archive for superseded prose; do not create another archive directory. Do not delete downloaded feeds, prepared application files or runtime artifacts merely because they are ignored.

## Honest completion and safe reproduction

- Separate implemented, tested, human-approved and proposed. Never promote structural routing checks to H3 approval or search scores to H4 approval.
- `python poc/poc_status.py` reads recorded results without downloads or Docker. Run it when evaluating feasibility status. It is not a fresh experiment or external-access check.
- After changing result evidence, regenerate `poc/README.md` with `python poc/poc_status.py --write`; do not edit its generated tables manually. Update the dashboard summary with evidence dates and links.
- Preserve previous evidence and human verdicts before reruns. Inspect overwrite/volume-reset behavior, pin feed/config/corpus provenance, and keep historical comparisons attributable.
- Use the accepted 60-day feed plus TripIdToDate. Preserve full trip identity and service dates; normalized key overlap alone does not establish realtime correctness.
- Distinguish build and serving measurements. Record serving under the intended 8 GiB cap; do not raise the cap just to produce a passing result. Engine-only measurements are not full-stack capacity.
- Synthetic/replay data must stay labelled. Missing, stale and unavailable live sources must not appear as live or as an empty successful alerts feed.
- Phase 0 acceptance precedes production API implementation; the completed API precedes the client, unless the user explicitly revises those gates. H3 precedes the realtime/alerts wave in the continuation plan.
- Application drafts do not imply sent requests or accepted terms. Record actual send dates and explicit decisions; keep credentials and signed/personal application files out of Git.

## Before handing back changes

- Run checks appropriate to the change. For documentation cleanup, check local links, removed-path references and `git diff --check`; do not rerun expensive experiments merely for prose edits.
- Update `PROJECT_STATUS.md`, then summarize the outcome, validation and material remaining blockers to the user. If status cannot be updated, say why and provide the handoff in the response.
