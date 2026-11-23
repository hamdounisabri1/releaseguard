# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

ReleaseGuard is a **deployment approval and rollback manager** for small teams. It is **not** a CI/CD engine. GitHub Actions builds and deploys. ReleaseGuard decides whether a release may proceed, records every decision, dispatches approved workflows, verifies health over HTTP and coordinates rollback to an earlier image **digest**.

- **Status:** pre-code. Only the docs exist so far. **Current sprint: 0, Setup (22–23 Nov 2026), Epic SCRUM-5 (Tasks SCRUM-6…11), started 23 Nov; Sprint 1 starts 24 Nov.** Claude updates this line when a sprint closes and the next one starts. Work follows [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md); check the sprint's checklist and Definition of Done before starting work.
- **Source of truth:** [docs/DEVELOPMENT_LIFECYCLE.md](docs/DEVELOPMENT_LIFECYCLE.md) covers architecture, data model, state machine, API, security and process. The original spec is [docs/ReleaseGuard_Project_Specification.pdf](docs/ReleaseGuard_Project_Specification.pdf).
- **Two repositories:** `releaseguard` (this repo, the platform) and `taskflow` (a separate, small sample app whose `ci.yml`, `staging-deploy.yml`, `production-deploy.yml` and `rollback.yml` workflows ReleaseGuard triggers and monitors). The demo depends on both.
- **Team:** one full-stack developer. Prefer vertical slices that can be demoed at the end of each sprint over horizontal layers.
- **Work tracking:** Jira project **`SCRUM`** is the only tracker (through the `jira` MCP server, or REST via the `JIRA_*` env vars as a fallback). **All sprints are planned in Jira up front** (every Epic, Task and board sprint, from the plan's checklists, after one approval), then worked **one sprint at a time**. **Daily:** in the first session of each new day, Claude picks today's Tasks from the active sprint, labels them `today` in Jira and updates the "Today" block in the plan before other work. **Tasks:** the user starts each Task in plan mode; Claude marks it Done automatically once `/dod-check` passes and its PR is squash-merged (Git rhythm: commit per green step, push at session end, one PR per Task; see `git-workflow.md`), and closes the sprint (and starts the next) automatically when its last Task is Done. Put the key in branches, commits and PR titles (`feat/SCRUM-12-approval-gate`). Read [jira-workflow.md](.claude/rules/jira-workflow.md) at the day's first session, when starting or finishing a ticket, at sprint end, or when filing a bug. `/sprint-status` shows the board.

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
uv run pytest                                                      # all tests (needs Postgres)
uv run pytest tests/path/test_file.py::test_name                   # single test
uv run ruff check . && uv run ruff format --check . && uv run mypy app   # lint + types
uv run alembic upgrade head && uv run alembic check                # migration gate (on an empty DB)

# Frontend (Node LTS, pnpm: not installed yet, `corepack enable` or `npm i -g pnpm`)
cd frontend && pnpm install && pnpm dev                       # http://localhost:3000
pnpm eslint . && pnpm tsc --noEmit && pnpm build
```

**Windows dev machine:** both PowerShell 7 and Git Bash work; use the syntax of the shell you're in. If `python` opens the Microsoft Store stub, use `py -3`. `jq` isn't installed; parse JSON with Python.

CI gates that block a merge: Ruff, mypy, ESLint, `tsc`, pytest, Vitest/Playwright, Trivy (`--severity HIGH,CRITICAL --exit-code 1`), gitleaks, Alembic check.

## Architecture (big picture)

A **modular monolith**: one Next.js app, one FastAPI backend, one PostgreSQL database, and one worker process that shares the backend code. There's no Redis or message broker in v1.

- **Layering:** route (thin, Pydantic in and out) → **service** (permissions, rules, transitions, transactions, integration calls) → repository (data access only) → DB.
- **Deployment status is a state machine** owned by `deployment_service` alone: `ALLOWED_TRANSITIONS` plus `transition()`, which writes a `deployment_events` row and an audit entry. No other code sets `status`. The states are in guide §8.
- **Release ≠ deployment.** A release is an immutable build, identified by its **image digest**. A deployment is one attempt to put a release into one environment. A rollback is a **new** deployment (`operation_type=rollback`) linked to the failed one. History is never rewritten.
- **Approval gate:** recording the decision, the transition to Approved and the outbox row that dispatches the workflow all happen in **one transaction**. The worker dispatches from the outbox with retries. A per-environment `pg_advisory_xact_lock` blocks concurrent deployments (409).
- **GitHub integration:** through a GitHub App (JWT → installation token). ReleaseGuard sends `workflow_dispatch` with inputs `release_id`, `image_digest`, `environment` and `deployment_id`. Each run is matched back by `run-name: deploy-<deployment_id>`. Status comes back through `workflow_run` webhooks (details in `security.md`).
- **Worker:** APScheduler plus a Postgres job table (`FOR UPDATE SKIP LOCKED`). It runs health checks, post-deploy verification, dispatch retries and AI jobs.
- **AI** is isolated behind `AIService`, runs only as async worker jobs, and is **read-only**. It never approves, dispatches or rolls back. A deployment never waits on AI.
- **Tenancy:** every query is scoped to the caller's workspace (404 for another workspace; see `security.md`).

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
| `settings.json` permissions | Denies reading secret files and deleting repos or files via the GitHub MCP; asks before `git push`, merging PRs or pushing files via MCP |
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
| Scope, dates or sprint tasks | [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) (tick checkboxes as items land) and the "Current sprint" line above |
| The data model, API, state machine or security model | The matching section of [docs/DEVELOPMENT_LIFECYCLE.md](docs/DEVELOPMENT_LIFECYCLE.md) |

When something here turns out to be wrong (for example a planned command), fix it rather than working around it. Details, and the rules for regression tests and lessons, are in [maintenance.md](.claude/rules/maintenance.md).
