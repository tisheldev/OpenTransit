# Data usage and access record

**Updated:** 31 October 2026. **State:** MOT email sent 21 September 2026 (request baseline). The 19 October 2026 checkpoint passed with **no response recorded**. A short follow-up asking only about SIRI access was **sent 31 October 2026, 17:00 UTC** ([record](#follow-up-sent--31-october-2026)); response pending. The published static terms wording was re-read on 31 October ([summary](decision-pack/static-terms-summary-20261031.md)). Terms acceptance and credentials remain unrecorded.

**Scope revision — 25 September 2026:** The user chose a schedule-based first release. SIRI and live alerts access are deferred feature requirements and no longer block system development. October 19 remains a follow-up checkpoint for those features. Static dataset terms still need recorded review before release; this decision grants no data-use permissions.

## Verified application evidence

The [official SIRI receipt form](https://www.gov.il/BlobFolder/generalpage/real_time_information_siri/he/real_time_information_receipt_form.pdf) was supplied by the developer and inspected in full. Web fetch returned 403; the browser loaded and downloaded the one-page PDF successfully. It directs submission to `ptsupport@mot.gov.il`, requests a static IP and includes a liability disclaimer acknowledged by signature. The original contains no interactive form fields.

Read [the form guide](decision-pack/form-guide.md) for its exact fields and a concise description of the visible terms. The signed form must remain private. The acknowledgement is for the developer to review and sign; its preparation does not constitute acceptance.

## Questions awaiting evidence or a written answer

| Item | Current evidence | Resolution needed |
| --- | --- | --- |
| H1 request | User confirms email sent from correct address on 21 September 2026; an earlier email was sent about two weeks before from the wrong address. 19 October checkpoint passed with no response recorded (checked 31 October) | Ticket/reference if available, and response; project decision triggered (see [checkpoint result](#checkpoint-result--19-october-2026)); follow-up [drafted, not sent](decision-pack/mot-followup-draft-20261031.md) |
| Applicant type | Form asks for corporation name and number | Whether an individual may apply, and correct entries when no corporation exists |
| Static IP | Explicitly requested by official form | Accepted location/provider, binding, change procedure and test access |
| SIRI access | Application route verified; no usable credentials recorded | Endpoint, requester reference/key, current protocol and rate limits |
| Alerts access | Requested in draft, not granted | Endpoint, authentication, schema, limits and terms |
| Static GTFS terms (H2) | 31 October 2026: the MOT GTFS page (updated 10.09.2026) carries a short terms-of-use clause (use implies agreement; changeable without notice; liability disclaimer) with no licence grant, attribution or redistribution wording. The GTFS feed is not listed as a data.gov.il dataset, so the data.gov.il licence is not shown to apply ([summary](decision-pack/static-terms-summary-20261031.md)) | Written MOT statement, or a recorded user decision on the published wording; attribution and permitted uses; reviewed decision |
| Redistribution | Not expressly settled by the one-page form | Public display, processed API responses, raw redistribution separately |
| Storage/fixtures | Not expressly settled by the one-page form | Retention of observations and permission for public test samples |
| Sustainable fallback | Stride used as an experimental candidate in planning | Separate terms, availability and dependency decision before production reliance |
| Derived statistics from Hasadna's archive | Added 1 October 2026: Hasadna's public archive of MOT SIRI and GTFS states no data licence ([research note](research/open-bus.md)) | Included in the [follow-up draft](decision-pack/mot-followup-draft-20261031.md) (not sent): may statistics derived from archived MOT realtime data (delay distributions, reliability figures) be displayed publicly, and with what attribution? Ask Hasadna separately |

The old `https://data.gov.il/he/terms-of-use` URL returned 404 during this review. Do not treat the old link as evidence of an accepted licence. This record does not replace reading authoritative terms or obtaining the outstanding answers.

## Submission record

**Hosting decision — 30 September 2026:** the API will use ECS Fargate with a private ECR generation image; no S3 bucket is required initially. This is not MOT approval of AWS, its region or any address. For future SIRI, only the collector needs fixed outbound access: a private-subnet collector routed through a public NAT Gateway with an Elastic IP is the default pattern; a small EC2 collector with an Elastic IP is an alternative to assess for cost. Do not substitute the API's domain/load-balancer address for outbound IP evidence. Confirm provider/geography, binding, multiple-IP and change rules before allocation. No IP, NAT Gateway, credentials or source access was acquired; realtime remains deferred. See [hosting plan](next-steps.md#hosting-plan).

Request sent: 21 September 2026 from the correct email address, per user confirmation that day. An earlier email was sent about two weeks before from the wrong address; its exact date is not recorded. Use the September 21 submission as the request baseline. Response: pending. Email variant: B (preliminary questions: applicant type, IP requirements, alerts, terms of display/API/retention/samples), from Gmail on 31 October; no attachments; ticket/reference: none received. Follow-up decision date: 19 October 2026 (September 21 + 28 days). Terms accepted: pending evidence. Approved egress: pending. Credential storage: pending local configuration; never paste keys here. Approved data uses and evidence: pending.

The four-week threshold comes from the project's PRD, not an MOT response-time guarantee. It triggers a project decision, not automatic approval of a fallback.

## Checkpoint result — 19 October 2026

Recorded 31 October 2026 from the repository record; nothing in this file, the dashboard or the decision pack logs an MOT reply, ticket or follow-up. If a reply arrived and was not passed on, record it here with its date.

- **Result:** no response recorded; no follow-up sent. The September 21 request remains the baseline.
- **What the PRD triggers:** [PRD §5.2](../PRD.md#52-access-prerequisites-added-28-aug-2026) requires an explicit project decision when four weeks pass without a usable answer: Open Bus Stride as a permanent dependency, a static-only planner, or stopping under kill criterion #3. This is a decision for the user, not approval of any fallback. The 25 September schedule-first scope already ships a static-only planner for v1 and states that an unanswered realtime application does not stop it; whether that stands as the realtime answer needs the user's explicit confirmation.
- **What it does not change:** the [static release gate](api-prd.md#static-release-gate) item 5 still requires recorded evidence of acceptable static dataset terms and attribution. The missing reply leaves that open; options are in the [static terms summary](decision-pack/static-terms-summary-20261031.md).
- **Next action:** follow-up sent 31 October (below); await the response.

## Follow-up sent — 31 October 2026

The user approved and sent a short reply in the 21 September Gmail thread to `ptsupport@mot.gov.il` at 17:00 UTC (19:00 Israel time). At the user's request it asks only what is needed to get SIRI API access and offers to complete the form. The user chose not to ask MOT the static-terms questions and will research those themselves. The longer [draft](decision-pack/mot-followup-draft-20261031.md) was therefore not sent. Text as sent, without the signature's contact details:

> שלום, רציתי לבדוק אם קיבלתם את הפנייה ששלחתי ב-21 בספטמבר (למטה) לגבי גישה לממשק ה-SIRI. אני מפתח אפליקציה בקוד פתוח לתכנון נסיעות בתחבורה ציבורית, ואשמח לדעת מה צריך כדי לקבל גישה. אני יכול למלא את הטופס ולשלוח כל מה שתצטרכו.

Monitoring (local scheduled tasks on the user's machine, which run only while the Claude app is open):
- **Daily reply watcher** (`mot-reply-watcher`): records any MOT reply here through a PR, and prepares any answer as a Gmail draft. It never sends.
- **Second follow-up** (`mot-second-followup`, 15 November 2026): if there is still no reply, it prepares a Gmail draft for the user to approve.

Static terms (H2) evidence is still open; see the [static terms summary](decision-pack/static-terms-summary-20261031.md).

Ready communications: [longer follow-up draft, 31 October (not sent; superseded by the short follow-up)](decision-pack/mot-followup-draft-20261031.md), [Hebrew email drafts](decision-pack/mot-email-he.txt). [Decision pack](decision-pack/README.md).
