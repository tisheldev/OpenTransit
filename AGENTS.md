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

<!-- BEGIN AWS Agent Toolkit rules -->

# AWS Guidance for the new AWS experience

This user has signed up for the new AWS experience. This experience lets you sign into AWS using a social provider and requires the following additional context.

Where this guidance conflicts with the project's own instructions, the project's instructions take precedence.

## Context

### Terminology:

- Say "project" instead of "account" — a project contains an AWS account and settings for sharing with other collaborators
- Say "team member" instead of "IAM user" — users are invited by email, not created or federated in IAM
- Say "AWS Settings" when referring to management tasks at [settings.aws.com](https://settings.aws.com/) (project management, billing, team members, spend limits). Users view their actual AWS resources in the AWS Management Console.
- Say "selected Region" when referring to the user's Region — not "home Region"
- The user has a managed IAM experience. This includes a managed service control policies (SCP) and resource control policies (RCP) that govern the use of AWS. They will still need to use IAM to create policies to let services work with each other. If there are questions about the SCPs or RCPs, go to the documentation at https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html

### Constraints:

- All projects share a single AWS Region determined by the user's contact address. Resources cannot be created in other Regions
- When developing:
  - MUST create all Regional resources in the project's assigned Region
  - You CAN create AWS WAF and Cloudwatch Logs resources in us-east-1 when there are global resources (like a global WAF instance) that require a connection to dependencies in us-east-1. You should not use these for any other reason, because resources in the selected Region will provide lower cost (due to no cross-Region traffic), increased availability (due to no cross-Region traffic), and easier manageability (due to not needing to look in another Region). When you need to do an inventory of resources, you need to look in both the selected Region and us-east-1 for Cloudwatch Logs or WAF resources.
  - MUST NOT attempt to create Lambda, API Gateway, or other Regional resources in any other Region
  - MUST direct users to confirm their Region in AWS Settings > View all projects > Overview > Additional Info > Region. If the user cannot confirm their Region, check in ~/.aws/config
  - MUST NOT use Lambda@Edge — excluded from both Lambda and CloudFront
  - MUST NOT use CloudFormation StackSets — no multi-account or multi-Region deployments
  - MUST NOT attempt cross-Region actions — no cross-Region replication for DynamoDB/S3/RDS, no multi-Region KMS keys
  - MUST NOT use Route 53 cross-Region routing — geolocation, latency-based, and failover routing policies are not available
  - CloudFront is a global service and its actions ARE allowed in `us-east-1`. A user can create a CloudFront distribution pointing to their project-region Lambda function URL or API Gateway. However, Lambda and API Gateway themselves MUST NOT be created in `us-east-1` — they must be in the project Region.
  - Reduced availability in `eu-north-1` specifically: Amazon Rekognition, Amazon Textract, Amazon Personalize, AWS App Runner are not available in that Region.
- IAM permissions for human access are managed by AWS. Don't assign roles to team members unless absolutely necessary
- The user may have a spend limit if they are on the paid plan. The limit that pauses their project if it's exceeded. If resources suddenly become inaccessible, ask if they have a spend limit configured. Only project owners can modify a spend limit.
- When developing:
  - MUST ask about spend limit status if the user reports sudden "Access Denied" errors on operations that previously worked
  - MUST direct users to check spend status in AWS Settings > Billing
  - MUST check if a user has upgraded their account to the paid plan
  - MUST ask the user if they want to clean up the successfully created resources or keep them to reduce cost
- The user sets up billing, creates spend limits, and retrieves and pays invoices in AWS Settings. The user creates budgets and optimizes their costs in the AWS Billing and Cost Management console
- Not all AWS services are available. If a service isn't working, do the following:
  1. Run the command `aws freetier get-account-plan-state`
  2. If accountPlanType": "FREE", check the [Free Tier supported services list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html#supported-services-free-tier) next,
  3. If accountPlanType": "PAID", check the [Paid Tier supported services list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html#supported-services-paid-plan).
  4. If neither list shows the service, check the [Not supported for this experience list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html#unsupported-services). The user will need to activate advanced features to access this service.
- Users can activate advanced AWS services and capabilities for their account.
- Before starting a task, check whether a relevant AWS skill is available. Load the skill with retrieve_skill and prefer its guidance over general knowledge.

### Help level

- help_level (required): LOW, MEDIUM, or HIGH. While a user is building, you MUST ask the user: "How much guidance would you like from me? Low (I only flag security risks), medium (I ask a couple of clarifying questions if something seems off), or high (I explain what I'm doing, suggest alternatives, and flag best practices)."

You CAN update this rule file to save a user's help_level.

Constraints for each level:

**LOW:**

- MUST follow all constraints in this context file
- MUST execute the user’s request without modification
- MUST NOT ask clarifying questions unless the action would create a security vulnerability
- MUST NOT suggest alternatives or improvements

**MEDIUM:**

- MUST execute the user's request
- MAY ask up to two clarifying questions per task if the request has an ambiguity or a potential issue
- MUST NOT repeat a question or suggestion the user has already dismissed
- MUST NOT explain trade-offs or alternatives unless the user asks

**HIGH:**

- MUST explain what each step does and why before executing it
- MUST suggest alternatives when a better approach exists
- MUST flag best practices and explain trade-offs
- MUST still execute the user's choice if they disagree with a suggestion

<!-- END AWS Agent Toolkit rules -->
