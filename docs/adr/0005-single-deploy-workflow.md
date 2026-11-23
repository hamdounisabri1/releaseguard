# 0005. One deploy.yml for every environment and for rollback

- **Status:** Accepted
- **Date:** 2026-11-23
- **Jira:** none (architecture review, findings 7, 12)

## Context
The original design had `staging-deploy.yml`, `production-deploy.yml` and `rollback.yml` in the TaskFlow repo (docs/DEVELOPMENT_LIFECYCLE.md §10.2 before this review). All three do the same thing: pull an image by digest and run it in an environment. The rollback workflow would run only during incidents, so it's the least-tested path at the moment it matters most. The GitHub App also asked for Deployments RW and `workflow_job` events that nothing used.

## Decision
- TaskFlow has two workflows: `ci.yml` (lint, test, Trivy, build, push, register the release) and **`deploy.yml`**.
- `deploy.yml`: `on: workflow_dispatch` only; inputs exactly `release_id`, `image_digest`, `environment` (choice: `development|staging|production`), `deployment_id`; `run-name: deploy-${{ inputs.deployment_id }}`; the job sets `environment: ${{ inputs.environment }}`, so GitHub environment protection rules and environment-scoped secrets apply to production as a second layer. Steps: validate the digest format → pull by digest → check the pulled digest → deploy to the environment's Compose project.
- ReleaseGuard dispatches with **`return_run_details: true`** and stores the returned run id and URL. It still checks `run-name`, repository and workflow path on every `workflow_run` event.
- GitHub App: **Actions RW, Contents R, Metadata R**. Webhook events: **`workflow_run`** only.

## Alternatives considered

| Option | Complexity | Confidence in rollback | Why not |
|---|---|---|---|
| **One `deploy.yml`** (chosen) | Low | High: every deploy exercises it | — |
| Three workflow files | Medium | Low | Triplicated steps drift apart; rollback is rarely run |
| Correlate only by `run-name` polling | Medium | — | The dispatch API returns the run id since Feb 2026; polling is now only the fallback |

## Consequences
- Easier: one path to harden (`github-actions-hardening` skill), one to test; Sprint 4 needs no new workflow.
- Easier: rollback differs only in ReleaseGuard's records (`operation_type = rollback`).
- Harder: environment differences must be inputs or GitHub environment config, not separate files.
- Sources: [Workflow dispatch API now returns run IDs](https://github.blog/changelog/2026-02-19-workflow-dispatch-api-now-returns-run-ids). Check the exact response field names against the live API when implementing.
