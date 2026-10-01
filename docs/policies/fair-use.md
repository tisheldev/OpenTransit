# API fair-use policy

**DRAFT — not legal advice, pending review**

Effective date: **pending approval**. Contact: **[project email required]**.
This is a proposed policy; public quotas and the M7 limiter have not been approved or verified.

Use only documented endpoints and request bounds. Reuse selected places and stop IDs
within their generation, debounce autocomplete, and avoid repeated identical requests.
Respect `Cache-Control: no-store` on passenger responses; do not retain passenger journeys
in shared caches. Generation-bound references and cursors must be renewed after refresh.

Do not evade limits by rotating IPs or identities, bulk-harvest databases, run unapproved
load tests or degrade service. Ask the operator before sustained batch or research use.
Upstream data permissions still apply; this policy grants no redistribution licence.

When a response is `429`, follow `Retry-After` if supplied; otherwise back off with jitter.
Back off on `503` overload/unavailability and `504` timeout, with bounded retries; do not
retry invalid `4xx` requests unchanged. These instructions do not promise that rate-limit
headers are already implemented. Rate limits may restrict access during overload.

Before publication, the operator must set sustained requests/second, burst allowance,
concurrency, scope (including shared-IP users), counter expiry and exception/contact
procedure from M7 measurements. Publish those numbers here and verify `429`/overload
behavior. No numeric quota or SLA is implied by this draft. See [terms](terms.md),
[privacy](privacy.md) and the [load toolkit](../../tools/load/README.md).
