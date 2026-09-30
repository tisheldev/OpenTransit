# Your decision and application pack

Prepared 5 September 2026; reconciled 30 September. D1 (primary feed) is accepted and ingest/routing reruns are complete. D2 is accepted as Python/FastAPI. D3 and R1–R5 are accepted September 30; address/search selection still needs evidence. D5 hosting is now AWS ECS Fargate with a prepared generation in private ECR and optional S3; region/resources/networking/cost await validation. The user confirms the MOT email was sent from the correct address on September 21; response pending, with a 28-day checkpoint on October 19. No accepted data terms or cloud deployment is recorded. See [PROJECT_STATUS.md](../../PROJECT_STATUS.md) for current progress.

## Do this now

1. **Obtain written static GTFS usage terms and pass along MOT replies.** Implementation and Fargate/ECR hosting are selected ([ADR 0007](../../poc/docs/adr/0007-schedule-api-design.md)); static terms remain a release requirement. M1 stays local; cloud region/resources/cost still need validation.
2. **Await the MOT response; the 28-day decision point is October 19.** The September 21 email from the correct address is the request baseline. The email variant and attachments are not recorded. Keep any ticket/reference in the [access record](../data-usage-and-access.md).
3. **If MOT still requires a signed application**, use the [field-by-field instructions](form-guide.md), review the Ministry terms and enter your personal details yourself. The prepared form is at `output/pdf/mot-siri-application-draft.pdf` from the repository root. Existing [Hebrew email drafts](mot-email-he.txt) remain reference material.

The route review is ready on the accepted baseline. Search still needs rerunning before H4; [the review queue](quality-review.md) explains the remaining judgments.

## Recommended technical package

| ID | Recommend | Alternative and tradeoff | Your choice |
| --- | --- | --- | --- |
| D1 | Use the 60-day GTFS + `TripIdToDate`; retain ten-day comparison evidence | Accepted ADR 0005; ingest/routing rerun completed | Accepted |
| D2 | Use Python for the Phase 1 API and ingestion; FastAPI for the API | .NET API + Python ingestion: separate toolchains; benchmark the chosen runtime before claiming latency targets | Accepted September 25; ADR 0002 amendment |
| D3 | Use POST `/v1/journeys` with a JSON body; retain GET for public non-sensitive resources | Earlier GET alternative: coordinates can enter URL/access logs unless specifically suppressed | Accepted September 30; ADR 0007 |
| D4 | Start with MOTIS plus an in-process stop search index; benchmark address fixes before selecting an additional same-host geocoder | Adopt another geocoder now without knowing whether it fixes Hebrew/Latin/address failures or fits the host | Pending |
| D5 | ECS Fargate with API/MOTIS in one task; private ECR generation image; S3 optional; M1 local | VM proposal superseded; region, task size, ingress, retention automation and cost still need evidence; 8 GiB is an aggregate serving ceiling | Hosting accepted September 30; [ADR 0007](../../poc/docs/adr/0007-schedule-api-design.md#hosting-amendment--accepted-30-september-2026) |

D1 is justified by 0% versus 100% static mapping-key overlap in the recorded samples. That is not proof of live matching. D2 builds on the recorded developer preference in ADR 0002; production performance remains to be measured. D3 reduces URL exposure but does not make request-body logging safe: logs must still omit precise coordinates.

## Access choices you control

| Situation | Ready action |
| --- | --- |
| Applying personally; no registered corporation | Send email B asking whether an individual application is accepted and what to put in the corporation fields. Do not invent a company or registration number. |
| No static public egress IPv4 yet | Send email B asking which IPs/locations are accepted before buying anything. The official form explicitly requests a static IP. |
| Have applicant details, valid entity details where applicable, and a static public egress IPv4 | Review the purpose text and Ministry terms, complete/sign the form and send email A with the PDF attached. |
| Do not want to accept the form's terms | Do not sign. Send the specific question you want clarified, or stop the direct-MOT application. |

**Personal information to enter yourself:** full name in Hebrew, corporation name/number if applicable, email, telephone, mobile, static public egress IPv4, identity number and signature. No personal details have been inferred from the computer account name. Keep the completed/signed copy out of Git; `output/pdf/` is ignored.

## What happens after your choices

- I record accepted technical decisions and align the PRD/design documents.
- Ingest, routing and engine capacity were rerun on the accepted primary; [results](../../poc/docs/primary-feed-rerun.md) and the H3 sheet are ready.
- I preserve prior evidence, rerun search on that baseline and prepare H4 review. Per-service-date identity still needs validation for realtime matching.
- Implement the scheduled API under September 30 authorization. Matcher, live adapters and alerts are deferred; future replay/synthetic tests remain labelled.
- The access email was sent September 21 from the correct address per user confirmation. Await the response; the four-week decision point is October 19.
- When MOT replies, provide its non-secret answers on access, IPs and terms. Credentials belong in local secret configuration, not documentation or chat examples.

## Contents

- [Form guide and purpose statement](form-guide.md)
- [Ready-to-copy Hebrew emails](mot-email-he.txt)
- [Draft technical decisions and implementation handoff](technical-decisions.md)
- [Human quality-review queue](quality-review.md)
- [Access and usage evidence](../data-usage-and-access.md)
- [Full continuation plan](../next-steps.md)
