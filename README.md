# OpenTransit Israel

An API-first, open-source transit planner for Israel.

## Start here

**[PROJECT_STATUS.md](PROJECT_STATUS.md) — where we stand, what to do next, blockers, and session handoffs.**

Agents must follow [AGENTS.md](AGENTS.md): read the dashboard before work, claim changes, and update it before finishing or pausing.

| Need | Document |
| --- | --- |
| Product scope and phase gates | [PRD](PRD.md) |
| Detailed implementation milestones | [Continuation plan](docs/next-steps.md) |
| Decisions and Ministry application | [Decision pack](docs/decision-pack/README.md) |
| Experiment results | [Recorded PoC status](poc/README.md) |
| Run routing experiments | [Routing runbook](poc/routing/README.md) |

Inspect recorded feasibility status without Docker, credentials or downloads:

```sh
python poc/poc_status.py
```

`poc/` contains executable experiments, corpora and evidence. `docs/` contains supporting plans, access records and design references. Current progress belongs in the root dashboard; superseded prose lives in Git history.

## Licence and public development

OpenTransit original code and documentation are licensed under [MIT](LICENSE).
Public development and unrestricted reuse are the project direction selected on
1 October 2026. Third-party code retains its own notices/licences; upstream datasets
and derived graphs/databases are not relicensed by MIT. See the
[licence audit](docs/licence-audit.md) and [source attribution](docs/policies/attribution.md).
Public source availability does not imply that the passenger API is deployed or
that dataset redistribution and release acceptance have been cleared.
