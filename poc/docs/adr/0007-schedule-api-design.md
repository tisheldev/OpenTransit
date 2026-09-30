# ADR 0007 — schedule API design and implementation entry

**Status:** Accepted · **Date:** 30 September 2026.

The user authorized applying the suggested plan changes and starting implementation after the September 25 API planning drafts. This satisfies the planning-before-code gate. Python/FastAPI and the schedule-first scope remain as previously accepted.

Use POST `/v1/journeys` with typed locations and explicit-offset time (D3). Apply R1–R5 from the [system design](../../../docs/system-design.md#0-review-proposals--simplifications): blue/green MOTIS with an atomic generation pointer and single-worker reload; source stop/route IDs conditional on daily-feed stability evidence; one Python package; a read-only SQLite file per generation; timeouts and bounded concurrency before adding scale machinery. Basic activation belongs in M2, with failure/load verification in M7. M1 uses a fixed verified generation.

The prepared PoC graph expires October 4. Build a fresh isolated graph for M1 using the accepted 60-day feed plus TripIdToDate, recorded hashes/configuration and a pinned MOTIS image. Preserve existing evidence and volumes. Numeric defaults require validation; M1 remains local.

## Hosting amendment — accepted 30 September 2026

The user selected **AWS ECS on Fargate** to run the API and MOTIS without maintaining a VM. For the first private deployment, include the prepared graph, generation manifest and later reference SQLite in a **private ECR image**. Pin images by digest and package one consistent generation per task. S3 is optional, not a prerequisite; a later change may separate data artifacts from application releases. Each feed refresh initially creates a new generation image and task-definition revision. Preserve raw inputs, hashes, configuration, reports and rollback images outside disposable task storage; ECR alone is not the source-evidence archive.

This supersedes the Hetzner/single-VM hosting proposal and adapts R1 in production: replace complete ECS tasks, verify candidate readiness and drain old requests. Each task serves one fixed generation with local MOTIS; do not implement cross-task symlink/reload control. Local Compose retains the M2 pointer/reload workflow. Concurrent old/new tasks may answer from different complete generations during rollout; N05 requires consistency within each request. Rollback rechecks the previous generation's coverage and freshness.

Test 0.5 vCPU / 2 GiB as an initial Fargate configuration; it is not a capacity claim. The 8 GiB aggregate serving ceiling, including deployment overlap and serving edge components, remains a release requirement, not a minimum allocation. Build memory is measured separately. Region, HTTPS ingress, refresh automation, retention and total cost are resolved in H-0/H-1; no cloud resources were provisioned or paid deployment authorized by this documentation request.

SIRI remains deferred. Only its future collector needs static outbound access, normally a private subnet through a public NAT Gateway with an Elastic IP. A small EC2 collector with an Elastic IP is an alternative to evaluate, not the selected API host. MOT must confirm accepted provider/geography and IP binding before allocation. See the [hosting plan](../../../docs/next-steps.md#hosting-plan) for implementation and validation criteria.

H3/H4 human review, static terms, scheduled integration and full-stack operational checks remain release requirements. The completed API still precedes the client; realtime and alerts remain deferred. Authorization to implement does not approve route/search quality or data-use terms.
