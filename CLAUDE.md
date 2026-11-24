# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ReleaseGuard is a **deployment approval and rollback manager** for small teams. It is **not** a CI/CD engine. GitHub Actions builds and deploys. ReleaseGuard decides whether a release may proceed, records every decision, dispatches approved workflows, verifies health over HTTP and coordinates rollback to an earlier image **digest**.

- **Status:** pre-code. The docs and the monorepo layout (README placeholders in `backend/`, `frontend/`, `worker/`, `infra/`) exist; no app code yet. **Current sprint: 0, Setup (22–25 Nov 2026, extended), Epic SCRUM-5 (Tasks SCRUM-6…11), started 23 Nov; Sprint 1 starts Thu 26 Nov. All sprints are planned in Jira (Epics SCRUM-12…17, Tasks SCRUM-18…109); MVP Fri 19 Feb 2027.** Claude updates this line when a sprint closes and the next one starts. Work follows [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md); check the sprint's checklist and Definition of Done before starting work.
- **Source of truth:** [docs/DEVELOPMENT_LIFECYCLE.md](docs/DEVELOPMENT_LIFECYCLE.md) covers architecture, data model, state machine, API, security and process. The original spec is [docs/ReleaseGuard_Project_Specification.pdf](docs/ReleaseGuard_Project_Specification.pdf).
- **Two repositories:** `releaseguard` (this repo, the platform) and `taskflow` ([hamdounisabri1/taskflow](https://github.com/hamdounisabri1/taskflow), a separate, small, public sample app with two workflows: `ci.yml`, which registers each release through GitHub OIDC, and `deploy.yml`, which ReleaseGuard dispatches for every environment and for rollback). The demo depends on both.
- **Team:** one full-stack developer. Prefer vertical slices that can be demoed at the end of each sprint over horizontal layers.
- **Work tracking:** Jira project **`SCRUM`** is the only tracker (through the `jira` MCP server, or REST via the `JIRA_*` env vars as a fallback). **All sprints are planned in Jira up front** (every Epic, Task and board sprint, from the plan's checklists, after one approval), then worked **one sprint at a time**. **Daily:** in the first session of each new day, Claude picks today's Tasks from the active sprint, labels them `today` in Jira and updates the "Today" block in the plan before other work. **Tasks:** the user starts each Task in plan mode; Claude marks it Done automatically once `/dod-check` passes and the user has squash-merged its PR (**the user always merges PRs by hand; Claude never merges**) (Git rhythm: commit per green step, push at session end, one PR per Task; see `git-workflow.md`), and closes the sprint (and starts the next) automatically when its last Task is Done. Put the key in branches, commits and PR titles (`feat/SCRUM-12-approval-gate`). Read [jira-workflow.md](.claude/rules/jira-workflow.md) at the day's first session, when starting or finishing a ticket, at sprint end, or when filing a bug. `/sprint-status` shows the board.

## Commands

> These are **planned** (from lifecycle guide §14.6 and §14.10). Verify them, and fix this section, once Sprint 0/1 scaffolding exists.

```bash
# Local stack
docker compose -f infra/docker-compose.yml up -d db          # Postgres only
docker compose -f infra/docker-compose.yml up --build        # everything

# Backend (Python 3.12+, uv). Run from backend/; `uv run` uses the project venv.
cd backend && uv sync
uv run alembic upgrade head && uv run python -m app.scripts.seed   # migrate + seed (1 workspace, 4 users, TaskFlow)
uv run uvicorn app.main:app --reload                               # http://localhost:8000/docs
uv run python -m app.worker                                        # worker: job loop + sweeps (second terminal)
uv run pytest                                                      # all tests (needs Postgres)
uv run pytest tests/path/test_file.py::test_name                   # single test
uv run ruff check . && uv run ruff format --check . && uv run mypy app   # lint + types
uv run alembic upgrade head && uv run alembic check                # migration gate (on an empty DB)

# Frontend (Node LTS, pnpm: not installed yet, `corepack enable` or `npm i -g pnpm`)
cd frontend && pnpm install && pnpm dev                       # http://localhost:3000
pnpm eslint . && pnpm tsc --noEmit && pnpm build

# GitHub repo settings (ruleset protect-main, squash-only, labels); idempotent, needs gh as repo admin
infra/github/setup-repo.sh hamdounisabri1/releaseguard
infra/github/setup-repo.sh hamdounisabri1/taskflow
```

**Windows dev machine:** both PowerShell 7 and Git Bash work; use the syntax of the shell you're in. If `python` opens the Microsoft Store stub, use `py -3`. `jq` isn't installed; parse JSON with Python.

CI gates that block a merge: Ruff, mypy, ESLint, `tsc`, pytest, Vitest/Playwright, Trivy (`--severity HIGH,CRITICAL --exit-code 1`), gitleaks, Alembic check.

## Architecture (big picture)

A **modular monolith**: one Next.js app, one FastAPI backend, one PostgreSQL database, and one worker process that shares the backend code. There's no Redis or message broker in v1. The design was reviewed on 23 Nov 2026: see [docs/ARCHITECTURE_REVIEW.md](docs/ARCHITECTURE_REVIEW.md) and ADRs [0001–0007](docs/adr/).

- **Layering:** route (thin, Pydantic in and out) → **service** (permissions, rules, transitions, transactions) → repository (data access only) → DB. **The API process never calls GitHub, the LLM or health URLs.** It writes state plus a job in one transaction; the worker does all outbound I/O.
- **Deployment status is a state machine** owned by `deployment_service` alone: `ALLOWED_TRANSITIONS` plus `transition()`, which writes a `deployment_events` row and an audit entry and enqueues the follow-up job. No other code sets `status`. States: `awaiting_approval`, `queued`, `deploying`, `verifying` (active), then `succeeded`, `failed`, `unhealthy`, `rejected`, `expired`, `cancelled` (terminal). Every non-terminal state has an owner and a timeout (guide §8).
- **Release ≠ deployment.** A release is an immutable build, identified by its **image digest**. A deployment is one attempt to put a release into one environment. Approval decisions, the frozen policy and the rollback link (`rollback_of_deployment_id`) live **on the deployment**. A rollback is a **new** deployment (`operation_type=rollback`). History is never rewritten; `audit_logs` and `deployment_events` are append-only.
- **One active deployment per environment**, enforced by a partial unique index on `deployments(environment_id)` for `queued/deploying/verifying` (violation → 409). No advisory locks.
- **Approval gate:** inserting the decision, moving to `queued` and inserting the dispatch job happen in **one transaction**. Requests are refused when expired, stale (the environment changed since the request) or self-approved under `block_self_approval`.
- **GitHub integration:** a GitHub App (Actions RW, Contents R, Metadata R; `workflow_run` events only). The worker dispatches `deploy.yml` with exactly `release_id`, `image_digest`, `environment`, `deployment_id` and `return_run_details`, then stores the run id. Webhook events are matched by repo, workflow and `run-name: deploy-<deployment_id>`. A reconcile sweep recovers lost webhooks. CI registers releases at `POST /releases/ci` with a **GitHub OIDC token** bound to the repository id, workflow and SHA.
- **Worker:** one async loop over a Postgres `jobs` table (`FOR UPDATE SKIP LOCKED`), which is also the outbox, plus sweeps for approval expiry, run reconciliation, due health checks and retention. No APScheduler.
- **AI** is isolated behind `AIService`, runs only as worker jobs, and is **read-only**. It never approves, dispatches or rolls back. A deployment never waits on AI.
- **Tenancy:** every tenant table has `workspace_id` (with composite FKs), and every query is scoped to the caller's workspace (404 for another workspace; see `security.md`).
- **Browser security:** one origin through Caddy (`/` and `/api`), server-side sessions, `SameSite=Lax`, and an Origin check on unsafe methods. Health URLs go through an SSRF guard.

## Rules folder: `.claude/rules/`

Detailed rules live in their own files so this file stays short. Files with a `paths:` frontmatter load **only** when a matching file is read. The rest always load.

**Before creating files in an area that has no matching file yet** (for example scaffolding `backend/` or `frontend/` for the first time), Read the matching rules file explicitly, because path-scoped rules can't load for files that don't exist yet.

| File | Covers | Loads |
|---|---|---|
| [maintenance.md](.claude/rules/maintenance.md) | Committing new tools, keeping `.md` files current, regression tests and lessons | Always |
| [security.md](.claude/rules/security.md) | Auth, RBAC, secrets, webhooks, deployment safety | Always |
| [git-workflow.md](.claude/rules/git-workflow.md) | Branches, commits, PRs, Definition of Done, ADRs | Always |
| [jira-workflow.md](.claude/rules/jira-workflow.md) | Claude as project manager: up-front sprint planning, daily plan, tickets, auto-Done, bugs, sprint end | `docs/PROJECT_PLAN.md`, `docs/retros/**`, or read explicitly |
| [backend.md](.claude/rules/backend.md) | FastAPI layering, services, transactions, state machine, API conventions, worker | `backend/**`, `worker/**` |
| [database.md](.claude/rules/database.md) | SQLAlchemy models, Alembic migrations, constraints | models, repositories, migrations |
| [frontend.md](.claude/rules/frontend.md) | Next.js, data fetching, UI states, status vocabulary | `frontend/**` |
| [testing.md](.claude/rules/testing.md) | Test layers, fixtures, mocking, required failure paths | test and spec files, Playwright |
| [github-actions.md](.claude/rules/github-actions.md) | Workflows, dispatch contract, GitHub App | `.github/**`, backend `services/github*`, `api/v1/github*` |
| [infra.md](.claude/rules/infra.md) | Docker, Compose, Caddy, VPS deploy, backups | `infra/**`, Dockerfiles, compose files |
| [ai.md](.claude/rules/ai.md) | `AIService`, log sanitizing, prompt-injection safety, output schema | `services/ai*`, `schemas/ai*`, AI worker jobs |

## Automation in `.claude/`

| What | Does |
|---|---|
| Hook `hooks/pre_bash.py` (PreToolUse, Bash/PowerShell) | Blocks commands that read `.env`, `*.pem` or `*.key`; runs gitleaks on `git commit` once gitleaks is installed |
| Hook `hooks/post_edit.py` (PostToolUse, Edit/Write) | Runs `ruff format` + `ruff check --fix` on backend Python and `eslint --fix` on frontend TS/JS once that tooling exists; reports leftover errors |
| `settings.json` permissions | Denies reading secret files and deleting repos or files via the GitHub MCP; denies merging PRs (`gh pr merge`, MCP merge: the user merges by hand); asks before `git push` or pushing files via MCP |
| Agent `release-safety-reviewer` | Checks a diff against the state-machine, approval, webhook, tenancy and dispatch invariants |
| `/sprint-status` · `/new-adr` · `/lesson` · `/dod-check` | Board summary · next ADR from template · record a lesson · walk the Definition of Done |

## Skills, plugins and MCP servers: use them when they fit

The project-scoped tooling is listed in [docs/AI_TOOLING.md](docs/AI_TOOLING.md). Reach for it whenever it applies instead of working from memory:

| When you are… | Use |
|---|---|
| Designing or changing any UI (pages, components, colors, typography, accessibility) | `ui-ux-pro-max` skill |
| Checking that a UI change works in a real browser, taking screenshots, writing Playwright checks | `webapp-testing` skill (on Windows, see the note in `frontend.md`) |
| Designing tables, constraints, indexes or Alembic migrations | `postgresql-table-design` skill |
| Using Postgres-specific features or tuning queries (JSONB, locks, `SKIP LOCKED`, indexes) | `postgresql-optimization` skill |
| FastAPI dependencies, error handling and async patterns (**not** auth or folder layout: auth is server-side sessions per `security.md`, layout per `backend.md`) | `fastapi-templates` skill |
| Writing complex TypeScript types (generics, unions, mapped types) | `typescript-advanced-types` skill |
| Writing or reviewing any `.github/workflows/*.yml` | `github-actions-hardening` skill |
| Writing or changing a Dockerfile | `multi-stage-dockerfile` skill |
| Reading, creating or updating Jira tickets | `jira` MCP server (`mcp-atlassian`, tools `jira_*`); the `jira-integration` skill is background reference only |
| Planning all sprints up front: turning the `PROJECT_PLAN.md` checklists into Jira Tasks | `/to-tickets` skill (Jira configuration in `jira-workflow.md` §3) |
| Designing a new component, API, data model or service boundary, or weighing options for a technical decision | `system-design` and `architecture` skills (they inform; `DEVELOPMENT_LIFECYCLE.md` stays the source of truth). Record the decision with `/new-adr` |
| Writing code against a library API (Next.js, FastAPI, SQLAlchemy, Alembic, Pydantic, TanStack Query, shadcn/ui, GitHub REST) | `context7` (look up current docs) |
| Working with PRs, repos or Actions runs | `github` plugin / `gh` CLI |
| Committing, pushing, opening a PR | `commit-commands` (`/commit`, `/commit-push-pr`) |
| Reviewing a change before merging | `/code-review`, `/security-review` and the `release-safety-reviewer` agent (always for auth, RBAC, webhook, approval or token code), then `/dod-check` |
| Writing AI provider code against Claude | built-in `claude-api` skill (see `ai.md`) |
| Updating this file or the rules after a session | `claude-md-management` |

## Keep the docs in sync: mandatory

Every change that adds or alters project knowledge updates the matching doc **in the same change**. Don't defer it.

| When you add or change… | Also update |
|---|---|
| A rule or convention | The matching file in `.claude/rules/` (create one if none fits) **and** the rules table above |
| A plugin, skill, MCP server, hook, agent or command | [docs/AI_TOOLING.md](docs/AI_TOOLING.md), the tables above, the README "Built with Claude Code" list, and `skills-lock.json` / `.claude/settings.json` / `.mcp.json` |
| A command, script or tool in the dev loop | The **Commands** section above |
| An application environment variable | `.env.example` and guide §14.6 |
| An architectural decision | A new ADR via `/new-adr`; update the Architecture section above if the big picture changes |
| Scope, dates or sprint tasks | [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) (tick a Task's checkbox in its own PR, before merge) and the "Current sprint" line above |
| The data model, API, state machine or security model | The matching section of [docs/DEVELOPMENT_LIFECYCLE.md](docs/DEVELOPMENT_LIFECYCLE.md) |

When something here turns out to be wrong (for example a planned command), fix it rather than working around it. Details, and the rules for regression tests and lessons, are in [maintenance.md](.claude/rules/maintenance.md).
