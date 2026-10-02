# Privacy notice

**DRAFT — not legal advice, pending review**

Prepared 1 October 2026 for the scheduled API. This is a proposed release notice;
hosting, retention and log sanitization still need verification before publication.
Operator: **[name required]**. Privacy contact: **[project email required]**.

We process the origin, destination, search text, selected stops and requested times
you submit to answer your request. Providing location is optional: you can use
selected stops instead. Without the required routing inputs we cannot plan a journey.
The API has no accounts, saved journey history or behavioral analytics.

Routine application logs contain a generated request ID, route template, status and
duration. The release policy excludes bodies, coordinates, search text, query strings,
sensitive path values and raw client IP addresses from those logs. Sanitized
application, engine and startup logs expire after **seven days**; aggregate performance
metrics and synthetic test evidence contain no passenger payloads. Access is restricted
to maintainers operating the service. Do not submit personal information in bug reports.

HTTPS ingress necessarily processes your IP address to deliver responses. Any M7
rate-limit identifiers must be bounded, held only in memory and expire. The implemented
method (October 2, pending approval) keys buckets by a per-process keyed digest of the
address (IPv6 by /64), drops a bucket once it would be full again (at most 30 seconds
idle at the defaults), bounds the table and keeps nothing across restarts. Uvicorn and ALB access logs are disabled in the
release design. AWS is the proposed hosting/log processor; region, processor terms and
cross-border transfers remain to be reviewed. We do not sell request information or
use it for advertising. Legally required disclosure must be assessed by the operator.

The optional local playground requests map tiles directly from OpenStreetMap, exposing
your IP and viewed map area to that provider; its [privacy policy](https://osmfoundation.org/wiki/Privacy_Policy)
applies. This notice does not describe a future product client.

Contact the privacy address to ask about access to or correction of personal information,
or to raise a concern. Applicable rights and response procedures require review under
Israel's Privacy Protection Law, including Amendment 13
([Privacy Protection Authority guidance](https://www.gov.il/he/pages/tikun13_qa)).
Before publication, fill the operator/contact, verify every log sink and deletion policy,
choose rate-limit expiry and hosting region, and have the notice reviewed. Effective
date: **pending approval**. See [terms](terms.md) and [fair use](fair-use.md).
