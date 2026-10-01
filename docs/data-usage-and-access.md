# Data usage and access record

**Updated:** 21 September 2026. **State:** user confirms MOT email sent today from the correct address; awaiting response. 28-day checkpoint: 19 October 2026. Terms acceptance and credentials remain unrecorded.

**Scope revision — 25 September 2026:** The user chose a schedule-based first release. SIRI and live alerts access are deferred feature requirements and no longer block system development. October 19 remains a follow-up checkpoint for those features. Static dataset terms still need recorded review before release; this decision grants no data-use permissions.

## Verified application evidence

The [official SIRI receipt form](https://www.gov.il/BlobFolder/generalpage/real_time_information_siri/he/real_time_information_receipt_form.pdf) was supplied by the developer and inspected in full. Web fetch returned 403; the browser loaded and downloaded the one-page PDF successfully. It directs submission to `ptsupport@mot.gov.il`, requests a static IP and includes a liability disclaimer acknowledged by signature. The original contains no interactive form fields.

Read [the form guide](decision-pack/form-guide.md) for its exact fields and a concise description of the visible terms. The signed form must remain private. The acknowledgement is for the developer to review and sign; its preparation does not constitute acceptance.

## Questions awaiting evidence or a written answer

| Item | Current evidence | Resolution needed |
| --- | --- | --- |
| H1 request | User confirms email sent from correct address on 21 September 2026; an earlier email was sent about two weeks before from the wrong address. Awaiting response | Ticket/reference if available, and response; 28-day checkpoint 19 October 2026 |
| Applicant type | Form asks for corporation name and number | Whether an individual may apply, and correct entries when no corporation exists |
| Static IP | Explicitly requested by official form | Accepted location/provider, binding, change procedure and test access |
| SIRI access | Application route verified; no usable credentials recorded | Endpoint, requester reference/key, current protocol and rate limits |
| Alerts access | Requested in draft, not granted | Endpoint, authentication, schema, limits and terms |
| Static GTFS terms (H2) | Original data-access report did not retrieve exact terms | Authoritative terms text/version, attribution and permitted uses; reviewed decision |
| Redistribution | Not expressly settled by the one-page form | Public display, processed API responses, raw redistribution separately |
| Storage/fixtures | Not expressly settled by the one-page form | Retention of observations and permission for public test samples |
| Sustainable fallback | Stride used as an experimental candidate in planning | Separate terms, availability and dependency decision before production reliance |
| Derived statistics from Hasadna's archive | Added 1 October 2026: Hasadna's public archive of MOT SIRI and GTFS states no data licence ([research note](research/open-bus.md)) | Question to ask at the October 19 follow-up (not sent): may statistics derived from archived MOT realtime data (delay distributions, reliability figures) be displayed publicly, and with what attribution? Ask Hasadna separately |

The old `https://data.gov.il/he/terms-of-use` URL returned 404 during this review. Do not treat the old link as evidence of an accepted licence. This record does not replace reading authoritative terms or obtaining the outstanding answers.

## Submission record

**Hosting decision — 30 September 2026:** the API will use ECS Fargate with a private ECR generation image; no S3 bucket is required initially. This is not MOT approval of AWS, its region or any address. For future SIRI, only the collector needs fixed outbound access: a private-subnet collector routed through a public NAT Gateway with an Elastic IP is the default pattern; a small EC2 collector with an Elastic IP is an alternative to assess for cost. Do not substitute the API's domain/load-balancer address for outbound IP evidence. Confirm provider/geography, binding, multiple-IP and change rules before allocation. No IP, NAT Gateway, credentials or source access was acquired; realtime remains deferred. See [hosting plan](next-steps.md#hosting-plan).

Request sent: 21 September 2026 from the correct email address, per user confirmation that day. An earlier email was sent about two weeks before from the wrong address; its exact date is not recorded. Use the September 21 submission as the request baseline. Response: pending. Email variant, attachments and ticket/reference: not recorded. Follow-up decision date: 19 October 2026 (September 21 + 28 days). Terms accepted: pending evidence. Approved egress: pending. Credential storage: pending local configuration; never paste keys here. Approved data uses and evidence: pending.

The four-week threshold comes from the project's PRD, not an MOT response-time guarantee. It triggers a project decision, not automatic approval of a fallback.

Ready communications: [Hebrew email drafts](decision-pack/mot-email-he.txt). [Decision pack](decision-pack/README.md).
