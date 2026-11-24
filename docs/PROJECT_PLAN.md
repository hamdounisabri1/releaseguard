# ReleaseGuard: Project Plan

| Item | Value |
|---|---|
| Team | 1 full-stack developer (owns frontend, backend, DevOps and AI) |
| Duration | 12 weeks = 6 sprints × 2 weeks |
| Planned start | Sun 22 Nov 2026, Sprint 0 (shift all dates if the start changes) |
| Target finish | Fri 19 Feb 2027, MVP `v1.0.0` + live demo (moved one week on 24 Nov 2026; see the note under §3) |
| Spec | [ReleaseGuard_Project_Specification.pdf](../ReleaseGuard_Project_Specification.pdf) |
| Team reference | [DEVELOPMENT_LIFECYCLE.md](DEVELOPMENT_LIFECYCLE.md) (architecture, stack, data model, process) |

---

## 1. Goal

Deliver **one convincing end-to-end release path** for the TaskFlow sample app:

```text
register release → deploy to staging → request production → reviewer approves
→ dispatch GitHub Actions → verify health → (unhealthy) → manual rollback to prior digest
```

Everything must be **real**: real GitHub Actions runs, real GHCR images, real HTTP health checks. Each sprint ends with a working slice that can be demoed. The project is "done" when every [MVP acceptance criterion](#7-mvp-acceptance-checklist) is met and the [demo script](DEVELOPMENT_LIFECYCLE.md#172-demo-script--10-minutes) runs end to end on the deployed instance.

---

## 2. Scope

### In v1
- One workspace with multiple users and 4 roles (Admin, Developer, Reviewer, Viewer)
- GitHub repository integration only, through a GitHub App
- Development, staging and production environments
- Docker target apps and GHCR image references (by **digest**)
- Release registration and deployment history
- Production approval and rejection, plus an audit log
- HTTP health checks and environment health status
- Manual rollback to an earlier successful artifact
- AI failure summaries and basic release notes
- Docker Compose deployment of ReleaseGuard to one VPS

### Not in v1
Kubernetes · multiple CI/CD or cloud providers · canary and blue-green · automatic rollback · enterprise multi-tenancy and a policy language · distributed tracing and centralized logging.

### Later extensions (backlog only)
Kubernetes target · canary and blue-green · email and chat notifications · release windows and change freezes · two-person approval and staging soak-time rules · Prometheus and Grafana · automatic rollback recommendations.

---

## 3. Timeline

```mermaid
gantt
    title ReleaseGuard - 12-week solo plan
    dateFormat  YYYY-MM-DD
    excludes    weekends

    section Setup
    Sprint 0 - repos, GitHub App, tooling, ADRs :s0, 2026-11-22, 2026-11-26

    section S1 Foundation
    Backend skeleton, DB, sessions, RBAC, CSRF :s1a, 2026-11-26, 5d
    App & environment CRUD (API + UI)          :s1b, after s1a, 4d
    Frontend shell, CI lint/test               :s1c, after s1b, 3d
    M1 Sign in + configure app                 :milestone, m1, 2026-12-11, 0d

    section S2 Releases
    TaskFlow app + ci.yml (OIDC) + deploy.yml  :s2a, 2026-12-14, 3d
    Worker, jobs table, GitHub App, dispatch   :s2b, after s2a, 3d
    Webhooks, state machine, reconcile, UI     :s2c, after s2b, 4d
    M2 Real CI run creates and deploys release :milestone, m2, 2026-12-25, 0d

    section S3 Approvals
    Policy, approval service, expiry, stale    :s3a, 2026-12-28, 4d
    Idempotency, cancel, prod protection       :s3b, after s3a, 2d
    Approvals inbox, policy form, audit UI     :s3c, after s3b, 4d
    M3 Production gated by approval            :milestone, m3, 2027-01-08, 0d

    section S4 Health & rollback
    SSRF guard, scheduled checks, verification :s4a, 2027-01-11, 4d
    Rollback service (same deploy.yml)         :s4b, after s4a, 3d
    Env health UI, version comparison          :s4c, after s4b, 3d
    M4 Unhealthy release rolled back           :milestone, m4, 2027-01-22, 0d

    section S5 AI
    AIService + sanitizer + schema             :s5a, 2027-01-25, 4d
    Failure analysis + release notes jobs      :s5b, after s5a, 3d
    AI analysis UI + fallback                  :s5c, after s5b, 3d
    M5 Useful AI explanation                   :milestone, m5, 2027-02-05, 0d

    section S6 Delivery
    Prod images, CI/CD, Trivy                  :s6a, 2027-02-08, 3d
    VPS deploy, Caddy same-origin, backups     :s6b, after s6a, 3d
    Playwright E2E, dashboard, filters, demo   :s6c, after s6b, 4d
    M6 v1.0.0 live + repeatable demo           :milestone, m6, 2027-02-19, 0d
```

> **Schedule change (24 Nov 2026):** Sprint 0 ran over and was extended to Wed 25 Nov. Sprint 1 starts Thu 26 Nov and ends Fri 11 Dec, and every later sprint moved one week (Monday starts), so the MVP date is now Fri 19 Feb 2027. Sprints 1–6 were planned in Jira up front the same day (Epics SCRUM-12…17, Tasks SCRUM-18…109, board sprints with these dates). Structural changes from the checklist: the `health_checks` migration is part of SCRUM-68, "never change the original failed deployment" is part of SCRUM-71, "status vs. health visually distinct" is part of SCRUM-74, and `compare_deployment_failures` is its own `p2` Task (SCRUM-85).

> **Holidays:** Sprint 2 (14–25 Dec) ends on Christmas Day, and Sprint 3 (28 Dec – 8 Jan) includes New Year's Day. Whether to take more time off is still open. If you take time off, move every later date by the same amount rather than squeezing scope. Use the [cut list](#6-buffer-risks-and-cut-list) if the end date is fixed.

> **Design revision (23 Nov 2026):** the checklists below follow the reviewed architecture ([ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md), ADRs 0001–0007). The main changes: the worker and jobs table move to **S2** (staging dispatch needs them), TaskFlow has **one `deploy.yml`** (S4 needs no rollback workflow), approvals live on the deployment (no `approval_requests` or `rollback_events` tables), and releases register through **GitHub OIDC**.

---

## 4. Sprint breakdown

Each sprint has about **8.5 working days of planned work and 1.5 days of buffer**. Every sprint ends with a tagged release (`v0.N.0`), a 10-minute self-demo recording or notes, and a short retro note in `docs/retros/`.

### Sprint 0: Setup (Sun 22 – Wed 25 Nov 2026, extended) · Epic SCRUM-5
- [ ] SCRUM-6 Create the `releaseguard` repo (monorepo layout per [section 5.6 of the guide](DEVELOPMENT_LIFECYCLE.md#56-repository-layout)) and a separate `taskflow` repo
- [ ] SCRUM-7 Protect `main`, add PR template (draft in `.github/pull_request_template.md`), labels, and the Jira `SCRUM` board with the Sprint 0 Epic (the Epics, Tasks and board sprints for Sprints 1–6 are then created up front in one pass; see [§5](#5-work-tracking))
- [ ] SCRUM-8 Register a **development GitHub App** (Actions: read/write, Contents: read, Metadata: read; webhook event `workflow_run` only)
- [ ] SCRUM-9 Set up a webhook tunnel (smee.io or cloudflared)
- [ ] SCRUM-10 `pre-commit` with Ruff, ESLint, Prettier and gitleaks; `.editorconfig`; `.env.example`
- [ ] SCRUM-11 Write ADR-0001 (modular monolith) and ADR-0002 (deploy by digest). *Drafted 23 Nov in [docs/adr/](adr/) together with ADRs 0003–0007 from the architecture review.*

---

### Sprint 1: Foundation (Thu 26 Nov – Fri 11 Dec) → `v0.1.0` · Epic SCRUM-12
**Goal:** a user can sign in, create an application and configure its three environments.

**Backend**
- [ ] SCRUM-18 FastAPI app skeleton: `core/config.py` (pydantic-settings), `core/security.py`, `core/permissions.py`, the `api/v1` router layout, a standard error shape, and the **Origin-check CSRF middleware** ([ADR-0007](adr/0007-server-side-sessions-and-csrf.md))
- [ ] SCRUM-19 SQLAlchemy 2.0 models and the first Alembic migration: `users`, `workspaces`, `workspace_members`, `sessions`, `applications`, `environments` (health fields + `policy` JSONB + health state), `audit_logs` with the **append-only trigger**; `workspace_id` and composite FKs on every tenant table
- [ ] SCRUM-20 Auth: argon2id, server-side sessions (hashed id, idle and absolute timeout, rotate on login), `HttpOnly`/`Secure`/`SameSite=Lax` cookie, login, logout and `me`
- [ ] SCRUM-21 RBAC dependency: `require_role(Role.ADMIN, …)` plus workspace scoping on every query
- [ ] SCRUM-22 Application CRUD and archive; environment CRUD (auto-create dev, staging and prod with default policies: dev auto-deploy, staging promote from dev, prod requires approval and promotes from staging)
- [ ] SCRUM-23 Audit log helper, `record_audit(actor, action, target, details)`, used by every state-changing service
- [ ] SCRUM-24 `/healthz` and `/readyz`; request-ID middleware; structlog JSON logging
- [ ] SCRUM-25 Seed script (1 workspace, 4 users, TaskFlow app)

**Frontend**
- [ ] SCRUM-26 Next.js App Router + TypeScript + Tailwind + shadcn/ui; layout with sidebar and top bar
- [ ] SCRUM-27 API client in `services/`, types generated from OpenAPI (`openapi-typescript`), TanStack Query
- [ ] SCRUM-28 Login page; auth guard; dashboard placeholder
- [ ] SCRUM-30 Applications list (search, create, archive) and application details with environments tab
- [ ] SCRUM-31 Environment settings form (health URL, expected status, interval, timeout, threshold, verification rule)
- [ ] SCRUM-29 Shared empty, loading, error and permission-denied components

**DevOps**
- [ ] SCRUM-32 `infra/docker-compose.yml` for local development (db, backend, frontend)
- [ ] SCRUM-33 `ci.yml`: Ruff, mypy, pytest (Postgres service), ESLint, `tsc`, `next build`, Alembic check

**Tests**
- [ ] SCRUM-34 Unit tests for permission rules; API tests for login, RBAC (allowed and denied), **cross-workspace isolation**, a state-changing request with a foreign `Origin` (403), and an `UPDATE` on `audit_logs` being refused

**Definition of done:** a user signs in, creates TaskFlow and configures its three environments. A Viewer cannot edit. Another workspace's data cannot be reached. CI is green.

---

### Sprint 2: Releases and tracking (Mon 14 – Fri 25 Dec) → `v0.2.0` · Epic SCRUM-13
**Goal:** a real CI run in the TaskFlow repo registers a release, ReleaseGuard deploys it to dev automatically and to staging on request, and both deployments are tracked live.

**TaskFlow (sample app repo)**
- [ ] SCRUM-35 Minimal web app with `/health` (an env flag can force it to return HTTP 503, for the failure demo) and a Dockerfile
- [ ] SCRUM-38 `ci.yml`: lint, test, Trivy, build, push to GHCR, capture **digest**, register the release with an **OIDC token** (`id-token: write`, audience `GITHUB_OIDC_AUDIENCE`)
- [ ] SCRUM-40 `deploy.yml` for **every** environment (`workflow_dispatch`; inputs `release_id`, `image_digest`, `environment`, `deployment_id`; `run-name: deploy-${{ inputs.deployment_id }}`; job `environment: ${{ inputs.environment }}`; pull by digest and check it)
- [ ] SCRUM-39 Deploy target: TaskFlow Compose projects per environment on the VPS (or a free container host) over SSH, pulling by digest

**Backend and worker**
- [ ] SCRUM-36 Migration: `releases`, `deployments` (incl. the **partial unique index** on active statuses), `deployment_events` (append-only), `integrations`, `webhook_deliveries`, `jobs`
- [ ] SCRUM-41 Worker: entrypoint and container, job runner (`FOR UPDATE SKIP LOCKED`, backoff, `dead` after `max_attempts`), sweep loop ([ADR-0004](adr/0004-postgres-jobs-table.md))
- [ ] SCRUM-44 GitHub App service: JWT → installation token (cached), `httpx` + `tenacity`; **dispatch job** with `return_run_details`, storing run id and URL
- [ ] SCRUM-45 `POST /github/webhooks`: **HMAC-SHA256 validation with constant-time compare** before parsing, delivery-ID idempotency, run matching (repo, workflow, `run-name`)
- [ ] SCRUM-37 Release registration: `POST /releases/ci` (OIDC verification against JWKS, claim binding to repository id, workflow and SHA) and manual `POST /releases`; unique `(application_id, version)`
- [ ] SCRUM-42 `deployment_service` with the **state machine** (`ALLOWED_TRANSITIONS`, `transition()` that writes events and audit entries and enqueues follow-up jobs); `current_deployment_id` set on entering Verifying
- [ ] SCRUM-46 Auto-deploy on release (dev policy) and `POST /deployments` for staging; Verifying → Succeeded is immediate until verification lands in S4
- [ ] SCRUM-47 Reconcile sweep: read stuck runs from the API; `run_not_found` after `DISPATCH_TIMEOUT_SECONDS`
- [ ] SCRUM-43 GitHub integration connect and disconnect (installation callback, store `installation_id`)

**Frontend**
- [ ] SCRUM-48 Releases list and release details (version, SHA, digest, source, workflow link, deployments)
- [ ] SCRUM-49 Deployment list (recent, per environment) and deployment details with **state timeline**; poll active deployments
- [ ] SCRUM-50 Settings → GitHub integration page

**Tests**
- [ ] SCRUM-51 Unit: every allowed transition plus every forbidden pair
- [ ] SCRUM-53 Integration: webhook with a valid signature, an invalid signature, a duplicate delivery and an out-of-order event; OIDC token valid, expired, wrong audience and wrong repository; dispatch timeout → retried → exhausted → Failed; reconcile → `run_not_found`; a second active deployment refused by the index (409)
- [ ] SCRUM-52 GitHub API mocked with `respx`, OIDC with a local JWKS; no real GitHub calls in CI

**Definition of done:** a push to TaskFlow registers a release with SHA and digest, dev deploys automatically, requesting staging dispatches `deploy.yml`, and both statuses show up live.

---

### Sprint 3: Approval engine (Mon 28 Dec – Fri 8 Jan) → `v0.3.0` · Epic SCRUM-14
**Goal:** a production deployment **cannot** proceed without the required approval.

**Backend**
- [ ] SCRUM-54 Migration: `approval_decisions` (`UNIQUE (deployment_id, reviewer_id)`); workspace setting `block_self_approval`; environment policy validated by a Pydantic model (`requires_approval`, `min_approvals`, `approval_ttl_hours`, `require_comment`, `promote_from_environment_id`, `rollback_requires_approval`) and editable by Admins
- [ ] SCRUM-55 `approval_service`:
  - [ ] preconditions: release has a digest, a **Succeeded deployment in the `promote_from` environment**, requester role
  - [ ] request → Awaiting approval with `policy_snapshot`, `approval_expires_at` and `base_deployment_id`
  - [ ] decide: reviewer role, request unexpired and **not stale**, one decision per reviewer, self-approval rule, required comment
  - [ ] **one transaction:** record decision → (if `min_approvals` reached) transition to Queued → insert dispatch job
  - [ ] rejection → Rejected, no dispatch
- [ ] SCRUM-56 Expiry sweep → Expired
- [ ] SCRUM-57 `Idempotency-Key` on `POST /deployments`; `POST /deployments/{id}/cancel` (Awaiting approval and Queued only)
- [ ] SCRUM-58 Audit events: requested, approved, rejected, cancelled, expired, dispatched, finished

**TaskFlow**
- [ ] SCRUM-59 GitHub `production` environment protection for `deploy.yml` (deployment-branch rule, required reviewers if the plan allows) as a second layer

**Frontend**
- [ ] SCRUM-60 "Request deployment" with a confirmation dialog for production, showing promotion evidence
- [ ] SCRUM-61 **Approvals inbox:** pending list, release evidence (commit, digest, promotion result), approve and reject with comment
- [ ] SCRUM-62 Environment policy form (Admin)
- [ ] SCRUM-63 Approver identity and time on deployment details; audit log view

**Tests**
- [ ] SCRUM-64 Developer cannot approve; Reviewer from another workspace gets 404; self-approval blocked when enabled
- [ ] SCRUM-65 Expired and stale requests refused; a second decision by the same reviewer refused; approving while another deployment is active returns 409; `min_approvals = 2` needs two reviewers
- [ ] SCRUM-66 Same `Idempotency-Key` returns the same deployment; cancel after dispatch returns 409

**Definition of done:** as a Developer, request production → blocked until a Reviewer approves → the workflow is dispatched and the full audit trail is visible.

---

### Sprint 4: Health and rollback (Mon 11 – Fri 22 Jan) → `v0.4.0` · Epic SCRUM-15
**Goal:** a failed or unhealthy release can be replaced by an earlier known-good artifact.

**Worker**
- [ ] SCRUM-67 **SSRF guard** for health URLs (scheme allowlist, private-address block unless `HEALTH_CHECK_ALLOW_PRIVATE`, no redirects), checked on save and before every request
- [ ] SCRUM-68 Migration `health_checks` + scheduled checks via `environments.next_check_at`; write `health_checks` rows; update `health_status` and `consecutive_failures`
- [ ] SCRUM-69 Verification job: `verify_successes` passes within `verify_timeout_seconds` → **Succeeded**; `failure_threshold` consecutive failures or the timeout → **Unhealthy**
- [ ] SCRUM-70 Retention sweep (scheduled checks 14 days, `done` jobs 7 days)

**Backend**
- [ ] SCRUM-71 `rollback_service`: candidates (releases that **succeeded in this environment**, with a digest, not current), permission, eligibility, `rollback_requires_approval`, new deployment `operation_type=rollback` with `rollback_of_deployment_id` and `reason`, dispatched through the same `deploy.yml`; **never changes the original failed deployment**
- [ ] SCRUM-72 `POST /environments/{id}/health/check-now` (enqueue)

**TaskFlow**
- [ ] SCRUM-73 A "bad" release that is ready to go: `/health` returns 503

**Frontend**
- [ ] SCRUM-74 Environment details: health badge, check history (table or sparkline), current release, **version comparison across environments**; keeps **deployment status** and **environment health** visually distinct
- [ ] SCRUM-75 Rollback dialog: current vs. target version, reason field, explicit confirmation
- [ ] SCRUM-76 Deployment details: health checks tab; links between failed and rollback deployments

**Tests**
- [ ] SCRUM-77 Threshold logic (a single transient failure doesn't flip state); verification timeout; SSRF-blocked URL; rollback to an ineligible target rejected; rollback workflow failure; concurrent rollback returns 409; retention keeps verification checks

**Definition of done:** deploy the bad release to production → it ends Unhealthy and the environment turns unhealthy → roll back to the earlier digest → health is restored. History shows both deployments.

---

### Sprint 5: AI assistant (Mon 25 Jan – Fri 5 Feb) → `v0.5.0` · Epic SCRUM-16
**Goal:** a failed deployment shows a useful AI explanation without controlling any operations.

**Backend and worker**
- [ ] SCRUM-78 `AIService` interface plus one provider adapter (configured through `AI_PROVIDER`, `AI_MODEL`)
- [ ] SCRUM-79 **Log sanitizer:** redact tokens, keys, passwords, connection strings, emails and private keys; cap the size; pick relevant excerpts (failed step and its surrounding lines)
- [ ] SCRUM-80 Fetch failed job logs through the GitHub API (installation token, worker only)
- [ ] SCRUM-81 Prompt that treats logs as **untrusted data** (delimited, with instructions not to follow embedded text)
- [ ] SCRUM-82 Pydantic schema for the structured response; reject and store "unavailable" on invalid output
- [ ] SCRUM-83 Migration: `ai_failure_reports` (`status`, `model_provider`, `model_id`, `analysis_version`, evidence)
- [ ] SCRUM-84 `analyze_deployment_failure`, `summarize_pipeline_logs`, `generate_release_notes`
- [ ] SCRUM-85 `compare_deployment_failures` (**stretch**, cut list #1)
- [ ] SCRUM-86 Runs as `ai_analysis` / `ai_release_notes` jobs, auto-enqueued on Failed or Unhealthy; a deployment never waits on AI
- [ ] SCRUM-87 Authorization: users see analysis only for deployments in their workspace

**Frontend**
- [ ] SCRUM-88 AI analysis panel on failed or unhealthy deployments: summary, category, severity, probable cause (labeled **"AI-generated hypothesis"**), evidence excerpts, recommendations
- [ ] SCRUM-89 "Generate release notes" on release details
- [ ] SCRUM-90 States for unavailable, in progress and retry

**Tests**
- [ ] SCRUM-91 Sanitizer unit tests (secrets never leave the system); schema validation for good and bad payloads
- [ ] SCRUM-92 Provider timeout → deployment flow unaffected; prompt-injection fixture text doesn't change the output schema

**Definition of done:** the unhealthy TaskFlow deployment from S4 shows a structured, sensible explanation. With AI disabled, everything else still works.

---

### Sprint 6: DevOps delivery and polish (Mon 8 – Fri 19 Feb 2027) → `v1.0.0` · Epic SCRUM-17
**Goal:** the platform is deployed and the end-to-end demo can be repeated.

**DevOps**
- [ ] SCRUM-93 Multi-stage production Dockerfiles (backend, worker, frontend `output: standalone`), non-root users
- [ ] SCRUM-94 Production `docker-compose.yml`: proxy (Caddy, automatic TLS, `/` → frontend and `/api` → backend on **one origin**), frontend, backend, worker, db (named volume, not exposed publicly)
- [ ] SCRUM-96 `release.yml`: build → **Trivy (fail on HIGH/CRITICAL)** → push to GHCR → SSH deploy (`compose pull`, `alembic upgrade head`, `up -d`) → smoke test `/healthz`
- [ ] SCRUM-95 Production GitHub App registration and secrets on the VPS (`chmod 600` env file)
- [ ] SCRUM-97 `infra/scripts/backup.sh` (nightly `pg_dump`, retention, off-host copy) and `restore.sh`. **Run one restore test.**
- [ ] SCRUM-98 Optional: Prometheus `/metrics` and a Grafana dashboard

**Product polish**
- [ ] SCRUM-99 Dashboard: summary cards, env × app matrix, recent activity, pending approvals, failed deployments, dead jobs, success rate over a date range
- [ ] SCRUM-100 Deployment history filters (app, env, status, actor, date)
- [ ] SCRUM-101 Consistent status vocabulary and colors; empty, loading, error and permission-denied states everywhere
- [ ] SCRUM-102 UTC storage and local-time rendering checked

**Quality**
- [ ] SCRUM-103 Playwright E2E: login → request → approve → status updates → rollback UI
- [ ] SCRUM-104 Failure-path test sweep (GitHub timeout, lost webhook, duplicate webhook, rejected approval, unhealthy endpoint, rollback failure)
- [ ] SCRUM-105 Coverage report; Trivy report (secrets removed)

**Documentation and portfolio**
- [ ] SCRUM-106 README: architecture diagram, features, local setup, demo credentials (non-production)
- [ ] SCRUM-107 ER diagram, API docs link, TaskFlow workflow docs
- [ ] SCRUM-108 Screenshots and a 3–5 minute walkthrough video (approvals, failure, AI, rollback)
- [ ] SCRUM-109 Rehearse the [demo script](DEVELOPMENT_LIFECYCLE.md#172-demo-script--10-minutes) twice on the live instance

**Definition of done:** all [MVP acceptance criteria](#7-mvp-acceptance-checklist) are checked, and the live instance runs the full demo.

---

## 5. Work tracking

### Board
Jira project **`SCRUM`** is the only work tracker (one board sprint plus one Epic per sprint, one Task per checklist item, everything assigned to the owner; see [`.claude/rules/jira-workflow.md`](../.claude/rules/jira-workflow.md)). Board columns: **To Do → In Progress → In Review → Done**. GitHub is used for code, PRs and Actions runs only. A ticket moves to *In Progress* only when it meets the [Definition of Ready](DEVELOPMENT_LIFECYCLE.md#143-definition-of-ready-dor), and to *Done* only when it meets the [Definition of Done](DEVELOPMENT_LIFECYCLE.md#144-definition-of-done-dod).

### How the work flows
1. **All sprints are planned once, up front.** Every sprint's Epic, its Tasks (one per checkbox below) and its board sprint are created in Jira in a single approved pass. Each key is written next to its checkbox.
2. **Sprints run one at a time.** Only the current board sprint is active; the rest wait in the *future* state.
3. **Every day, Claude plans the day.** In the first session of each new date, Claude picks about a day's worth of unblocked Tasks from the active sprint, labels them `today` in Jira (JQL `project = SCRUM AND labels = today`) and rewrites the "Today" block below.
4. **Each Task starts in plan mode.** The developer opens a Task in plan mode; Claude writes the plan, and the Task moves to *In Progress* once the plan is approved.
5. **Git per Task:** one branch and one PR per Task. Commit after each working step, push at the end of every session (with a draft PR from the first push), and squash-merge once CI is green and the reviews pass. Full rhythm in [`git-workflow.md`](../.claude/rules/git-workflow.md#daily-git-rhythm).
6. **Done is automatic.** Claude moves a Task to *Done* (and ticks its checkbox) as soon as it passes `/dod-check` and its PR is merged. When the sprint's last Task is Done, Claude closes the Epic and the board sprint, starts the next sprint, and drafts the retro.

### Today
<!-- Claude rewrites this block in the first session of each day (jira-workflow.md §4). -->
- **Date:** Tue 24 Nov 2026
- **Today's Tasks:** SCRUM-6 Repos: monorepo layout + taskflow repo (0.5d) · SCRUM-11 ADR-0001 and ADR-0002 (0.25d; drafted 23 Nov, needs final review)
- **Carried over:** SCRUM-6 (In Progress since 23 Nov)
- **Blocked:** SCRUM-7, SCRUM-8, SCRUM-10 (wait on SCRUM-6); SCRUM-9 (waits on SCRUM-8)
- **Schedule:** Sprint 0 was extended to Wed 25 Nov. 2.25d of work is left for 2 days: tight but on track, if SCRUM-6 lands today so SCRUM-7, -8 and -10 can start. Sprint 1 starts Thu 26 Nov.

### Labels
| Group | Labels |
|---|---|
| Area | `area:api` `area:web` `area:worker` `area:db` `area:github` `area:ai` `area:infra` `area:docs` |
| Type | `type:feature` `type:bug` `type:chore` `type:test` `type:spike` |
| Sprint | `sprint:0` … `sprint:6` |
| Priority | `p0` (MVP-critical) · `p1` (MVP) · `p2` (stretch / cut first) |

### Solo cadence
| When | What | Time |
|---|---|---|
| Once, before Sprint 1 | Up-front planning: review and approve every sprint's Tasks, then Claude creates them in Jira | 1–2 h |
| Daily (first session) | Claude picks today's Tasks (`today` label) and updates the "Today" block; you confirm or swap | 5 min |
| Per Task | Start it in plan mode, approve the plan, build; Claude marks it Done when `/dod-check` passes | — |
| Mid-sprint (Wed, week 2) | Scope check: on track? If not, apply the cut list early | 15 min |
| Sprint end | Claude closes the sprint when its last Task is Done; you demo to yourself (record it), tag `v0.N.0`, review the retro draft | 1 h |

---

## 6. Buffer, risks and cut list

### Buffer
About 1.5 days per sprint (~15%). Unused buffer goes to tests and docs, **not** to new features.

### Top delivery risks
| Risk | Early signal | Response |
|---|---|---|
| GitHub App and webhook setup takes longer than planned | S2 day 4 with no release registered | Release registration (OIDC) doesn't depend on webhooks; until webhooks work, the reconcile sweep reads run status from the API |
| S2 is the heaviest sprint (worker, GitHub App, OIDC, webhooks, state machine) | S2 day 5 with no run dispatched | Move manual `POST /releases` and the GitHub integration settings page to S3; keep the dispatch → webhook → timeline path |
| Deploy target for TaskFlow is unclear | S2 day 2 | Use the same VPS with separate compose projects per environment (`taskflow-dev/staging/prod`) |
| Holiday weeks (end of S2, S3) | Before 14 Dec (S2 start) | Move dates; don't compress approval-engine work |
| AI output quality is poor | S5 day 5 | Narrow the input to the failed step's excerpt; add few-shot examples; keep the schema strict |
| VPS and TLS problems | S6 day 3 | Fall back to the provider's default domain; Caddy handles certificates |

### Cut list (apply in this order if the schedule slips)
1. `compare_deployment_failures()`: historical AI comparison
2. Prometheus and Grafana monitoring
3. Dashboard success-rate chart (keep the cards and tables)
4. Minimum-reviewer-count policy (keep single approval and the self-approval rule)
5. AI release notes (keep failure analysis)
6. Rollback approval policy (keep manual rollback with confirmation and reason)
7. Manual release registration (keep OIDC registration from CI)

**Never cut:** real GitHub Actions integration, digest-based deployment, backend RBAC and workspace isolation, the approval gate, the single-active-deployment constraint, health verification, manual rollback, the audit trail, webhook signature validation, OIDC release verification, the reconcile and expiry sweeps, the SSRF guard, backups.

---

## 7. MVP acceptance checklist

- [ ] **Application setup:** an admin can connect a GitHub repository and configure three environments.
- [ ] **Release registration:** a successful CI workflow creates a release record with commit SHA and image digest.
- [ ] **Staging:** a release can be deployed to staging through GitHub Actions, and its status appears in ReleaseGuard.
- [ ] **Production gate:** a developer cannot trigger production deployment until the required approval is recorded.
- [ ] **Auditability:** the system records who requested, approved, rejected and executed each deployment.
- [ ] **Health:** the system records HTTP health checks and marks the environment unhealthy after the failure threshold.
- [ ] **Rollback:** an authorized user can select an earlier successful artifact and trigger a new rollback deployment.
- [ ] **AI:** a failure detail page shows a structured explanation based on sanitized failure evidence.
- [ ] **Security:** workspace data is isolated, role checks run in the backend, and webhook signatures are validated.
- [ ] **Delivery:** ReleaseGuard runs through Docker Compose on a reachable environment, with a documented setup and backup procedure.

| Criterion | Delivered in |
|---|---|
| Application setup | S1 (+ GitHub connect in S2) |
| Release registration, Staging | S2 |
| Production gate, Auditability | S3 |
| Health, Rollback | S4 |
| AI | S5 |
| Security | S1–S3 (verified in S6) |
| Delivery | S6 |
