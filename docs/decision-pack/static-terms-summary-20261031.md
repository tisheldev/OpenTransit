# Static GTFS terms — summary for your decision

**DRAFT — not legal advice.** Prepared 31 October 2026 for H2 and item 5 of the [static release gate](../api-prd.md#static-release-gate). It records what the published sources say and what decisions remain. It does not accept any terms on your behalf; only you can do that.

The sections below are labelled **Documented** (what a source says, read on the date shown), **Interpretation** (our reading, which may be wrong) and **Proposal** (options for you to decide).

## 1. What the sources say (documented, read 31 October 2026)

Pages were read in the built-in browser. `curl` received HTTP 403 from both gov.il and data.gov.il. Wording is paraphrased; the links are the authoritative text.

### MOT GTFS page

[מידע סטטי - GTFS](https://www.gov.il/he/pages/gtfs_general_transit_feed_specifications) (National Public Transport Authority, under its senior projects and technology division). The page shows published 07.02.2021 and updated 10.09.2026. Its terms-of-use section says:

- Using the page, accessing its information or downloading a GTFS file means agreeing to the terms of use. The Ministry may change the terms at any time without prior notice. Anyone who does not agree may not use the page or download a GTFS file.
- Downloading confirms that the user has read the terms "and the restrictions detailed below". No further restrictions follow on the page, only disclaimers.
- The Ministry is not liable for any damage, loss or expense from using the page or its data. It is not responsible for errors, omissions or out-of-date information.
- The Ministry reserves the right to change the terms at any stage.

The page **does not** contain a licence grant, an attribution requirement, a statement on public display, processed results or redistribution, or a retention clause.

Other facts from the page:

- Static-data support is offered at `gtfs-support@avivamcg.com`.
- A "related" link points to the data.gov.il home page, not to a dataset.
- The developer documentation is now `Gtfs_Documentation_v4.pdf`; [data-access-findings](../data-access-findings.md#sources) cites v3. The v4 PDF was **not reviewed**, because opening it starts a download, which needs your approval.

### data.gov.il licence

[תנאי שימוש — Data.gov.il](https://data.gov.il/he/terms-of-use) shows published 01/01/2018 and updated 30/08/2025. It loaded on 31 October, although the earlier review recorded a 404. The licence covers datasets **published on data.gov.il**, and a licence attached to an individual dataset prevails over it. Its terms:

- **Grant:** worldwide, royalty-free, unlimited in time and non-exclusive. Permitted uses are copying, distribution, making available to the public, broadcasting, technical changes and derivative works, commercial or not. It does not limit uses allowed by law, including fair use and the use of facts and data themselves.
- **Prohibited uses:** misleading or distorting presentation, unlawful use, harming privacy (including by cross-matching sources), and implying access to identified personal data.
- **Attribution:** the source must be credited. This is not required for data extracted from the source when the original selection and arrangement are not preserved.
- **Other terms:** no implied endorsement; data is provided "as is" without warranty. The terms in force when data was taken govern its use. The State may change the licence or withdraw data at any time.

### data.gov.il catalogue

A CKAN API query on 31 October (`package_search`, organisation `ministry_of_transport`) returned 192 datasets. **None is the GTFS feed or TripIdToDate.** Two datasets matched "gtfs" only in their descriptions: `tikufim_station_2022` and `alhakav`, both licensed "Other (Open)". Other MOT transit datasets, such as `bus_stops` and [`ridership`](../research/open-bus.md), carry "Other (Open)" or `cc-by`.

### Feed directory

The [gtfs.mot.gov.il/gtfsfiles](https://gtfs.mot.gov.il/gtfsfiles/) directory listing has no licence or readme file. `israel-public-transportation.zip` and `TripIdToDate.zip` are dated 29 October 2026.

### Hasadna archive

The archive states no data licence. This comes from the [research note](../research/open-bus.md#6-data-terms-open) and was not re-read today.

## 2. Interpretation

- **The MOT page binds users but grants nothing explicit.** It makes use conditional on agreement and disclaims liability. It neither permits nor forbids display, API responses or redistribution, so silence is not documented permission.
- **The data.gov.il licence is not shown to apply.** The GTFS feed is not a data.gov.il dataset, and the GTFS page only links to the site's home page. Government open-data policy makes it plausible that MOT intends similar openness, but that is not recorded evidence. Question 1 of the [follow-up draft](mot-followup-draft-20261031.md) asks MOT directly.
- **Processed results and raw files carry different risk.** Journeys, departure times and stop names returned by the API are facts derived from the feed. Republishing the zip files, or a database that keeps their selection and arrangement, is closer to redistributing the work itself. The data.gov.il licence draws a similar line in its attribution clause, but that clause may not apply here.
- **The terms can change without notice.** Each generation should be able to point to the terms in force when its feed was downloaded, so a dated capture matters.
- **Other services' public use is not evidence.** Other apps and Hasadna publish services built on this feed. That suggests tolerance, not permission, and none of it has been verified here.
- **OSM is a separate issue.** The OSM/ODbL obligations in the [licence audit](../licence-audit.md#datasets-and-derived-artifacts) apply whatever MOT answers.

## 3. What the project needs

| Stage | Needs (interpretation of the PRD) |
| --- | --- |
| **Private preview** (H-0/H-1, a few reviewers, private ECR) | The October 1 gate revision lets the preview start before static terms are settled. Downloading and processing the feed falls under the published page terms. Since use implies agreement, **you** should explicitly confirm that you accept the page terms for this use; an agent cannot. Do not publish raw files, derived databases or images. |
| **Public release** | Gate item 5: "static dataset/OSM terms and attribution have recorded evidence". For MOT, that means the terms text and version captured with a date; a recorded decision that public display of processed results (web, app, public API) is acceptable; attribution wording; a decision on raw redistribution and fixtures (excluded, or permitted in writing); and the OSM attribution and ODbL review. |

## 4. Evidence that would satisfy the gate (proposal; your decision)

1. **Strongest: a written MOT answer** to questions 1–4 of the follow-up, recorded in the [access record](../data-usage-and-access.md) with its date.
2. **Without an answer: a dated capture plus your recorded decision.** This file, plus a saved copy of the page kept privately or committed if you choose, plus an explicit decision from you. For example: "public display of processed schedule results with MOT attribution is acceptable under the published terms; no raw-file or derived-database redistribution." The PRD asks for documented acceptable terms, and whether this option meets that is for you to judge. Agents must not mark the gate passed on their own reading.
3. **Optional: independent legal advice** on option 2, if you want more assurance.

## 5. Options if MOT never answers (proposal)

| Option | What it means | Trade-off |
| --- | --- | --- |
| A. Proceed on the published terms (evidence option 2) | Public release limited to processed results with attribution. No raw or derived-database redistribution. Fixtures stay synthetic or private. Re-check the page wording with each release | Fastest. Relies on silence, and MOT can change the terms without notice |
| B. Escalate for a written position | Ask the National Digital Agency (data.gov.il) whether its licence covers the GTFS feed, or file a freedom-of-information request with MOT about the feed's licence | Slower, but can produce documented evidence. Neither request is drafted yet |
| C. Private preview only until there is an answer | Keep H-0/H-1 private and hold the public release | No terms risk, but the public product waits indefinitely |
| D. Legal review first, then A or C | Advice on display versus redistribution under Israeli law | Costs money; gives the strongest basis short of an MOT answer |

The realtime side of the PRD §5.2 four-week decision (Stride, static-only or stop) is separate. It is recorded in the [access record checkpoint](../data-usage-and-access.md#checkpoint-result--19-october-2026).
