# Data usage and access record

**Updated:** 5 September 2026. **State:** evidence collected; no acceptance, credentials or sent request recorded.

## Verified application evidence

The [official SIRI receipt form](https://www.gov.il/BlobFolder/generalpage/real_time_information_siri/he/real_time_information_receipt_form.pdf) was supplied by the developer and inspected in full. Web fetch returned 403; the browser loaded and downloaded the one-page PDF successfully. It directs submission to `ptsupport@mot.gov.il`, requests a static IP and includes a liability disclaimer acknowledged by signature. The original contains no interactive form fields.

Read [the form guide](decision-pack/form-guide.md) for its exact fields and a concise description of the visible terms. The signed form must remain private. The acknowledgement is for the developer to review and sign; its preparation does not constitute acceptance.

## Questions awaiting evidence or a written answer

| Item | Current evidence | Resolution needed |
| --- | --- | --- |
| H1 request | Previously deferred; this pack is unsent | Actual sent date, ticket/reference and response |
| Applicant type | Form asks for corporation name and number | Whether an individual may apply, and correct entries when no corporation exists |
| Static IP | Explicitly requested by official form | Accepted location/provider, binding, change procedure and test access |
| SIRI access | Application route verified; no usable credentials recorded | Endpoint, requester reference/key, current protocol and rate limits |
| Alerts access | Requested in draft, not granted | Endpoint, authentication, schema, limits and terms |
| Static GTFS terms (H2) | Original data-access report did not retrieve exact terms | Authoritative terms text/version, attribution and permitted uses; reviewed decision |
| Redistribution | Not expressly settled by the one-page form | Public display, processed API responses, raw redistribution separately |
| Storage/fixtures | Not expressly settled by the one-page form | Retention of observations and permission for public test samples |
| Sustainable fallback | Stride used as an experimental candidate in planning | Separate terms, availability and dependency decision before production reliance |

The old `https://data.gov.il/he/terms-of-use` URL returned 404 during this review. Do not treat the old link as evidence of an accepted licence. This record does not replace reading authoritative terms or obtaining the outstanding answers.

## Record after the developer acts

Request sent: pending. Follow-up decision date: actual sent date + 28 days. Terms accepted: pending. Approved egress: pending. Credential storage: pending local configuration; never paste keys here. Approved data uses and evidence: pending.

The four-week threshold comes from the project's PRD, not an MOT response-time guarantee. It triggers a project decision, not automatic approval of a fallback.

Ready communications: [Hebrew email drafts](decision-pack/mot-email-he.txt). [Decision pack](decision-pack/README.md).
