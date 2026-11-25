# ReleaseGuard

**Deployment approval and rollback manager** for small teams.
Next.js · FastAPI · PostgreSQL · Docker · GitHub Actions · AI-assisted failure analysis

ReleaseGuard is not a CI/CD engine. GitHub Actions builds and deploys. ReleaseGuard decides whether a release may proceed, records every approval, triggers the approved workflows, verifies health and coordinates rollback to a known-good image digest.

> 🚧 **Status: pre-code.** The design, plan and tooling are in place. The monorepo layout exists as placeholders; application code starts in Sprint 1. Target MVP `v1.0.0`: 2 Dec 2026 (compressed from 19 Feb 2027 on 25 Nov).

## How it works

1. A CI workflow in the sample app (**TaskFlow**) builds an image and registers a **release**, identified by its image digest. The call is authenticated with a GitHub OIDC token, so no shared secret is involved.
2. ReleaseGuard deploys the release to **dev** and **staging** by dispatching one GitHub Actions workflow, `deploy.yml`, and tracks the run.
3. A production deployment needs an **approval** from a reviewer. The decision, the state change and the queued dispatch are recorded in one transaction, and only one deployment per environment can run at a time.
4. After a deploy, ReleaseGuard runs **HTTP health checks**. If the deployment turns out unhealthy, an authorized user starts a **rollback**: a new deployment of an earlier successful digest through the same workflow. History is never rewritten.
5. For failed deployments, an optional **AI assistant** explains the failure from sanitized logs. It is read-only and never approves, deploys or rolls back.

## Roadmap

| Sprint | Dates | Goal | Release |
|---|---|---|---|
| 0 Setup | 22–24 Nov 2026 | Repos, GitHub App, tooling, ADRs | none |
| 1 Foundation | 26 – 27 Nov | Auth, RBAC, applications and environments, CI | `v0.1.0` |
| 2 Releases and tracking | 28 Nov | GitHub integration, OIDC releases, worker, webhooks, dev and staging deployments | `v0.2.0` |
| 3 Approval engine | 29 Nov | Approval gate, production dispatch, concurrency | `v0.3.0` |
| 4 Health and rollback | 30 Nov | Verification, health checks, rollback | `v0.4.0` |
| 5 AI assistant | 1 Dec | Sanitized failure analysis | `v0.5.0` |
| 6 Delivery and polish | 2 Dec 2026 | Production Docker setup, E2E tests, demo | `v1.0.0` |

The full checklist is in the [project plan](docs/PROJECT_PLAN.md). Work is tracked in the Jira project `SCRUM`.

## Documentation

| Doc | Contents |
|---|---|
| [Development lifecycle guide](docs/DEVELOPMENT_LIFECYCLE.md) | Architecture, stack, data model, state machine, API, security, process |
| [Project plan](docs/PROJECT_PLAN.md) | 6 sprints, milestones, cut list, MVP acceptance checklist |
| [Architecture review](docs/ARCHITECTURE_REVIEW.md) + [ADRs](docs/adr/) | Design review of 23 Nov 2026 and the decisions it produced |
| [Project specification (PDF)](docs/ReleaseGuard_Project_Specification.pdf) | The original spec |
| [GitHub App setup](docs/GITHUB_APP_SETUP.md) | Registering the development and production GitHub Apps, verifying them, rotating keys |
| [AI tooling](docs/AI_TOOLING.md) | Claude Code plugins, skills and MCP servers used here, and how to set them up |
| [CLAUDE.md](CLAUDE.md) + [.claude/rules/](.claude/rules/) | Project instructions and rules for Claude Code (security, backend, frontend, database, testing, CI, infra, AI) |
| [Pull request template](.github/pull_request_template.md) | What every PR must cover |

## Repository layout

```text
backend/        FastAPI API + shared worker code
frontend/       Next.js web UI (App Router, shadcn/ui)
worker/         Worker entrypoint and container (Sprint 2)
infra/          Docker Compose, Caddy reverse proxy, backup/restore scripts
.claude/        Claude Code config: rules, skills, hooks, agents, commands
.github/        PR template (workflows arrive in Sprint 1)
docs/           Lifecycle guide, project plan, architecture review, ADRs, AI tooling, spec
CLAUDE.md       Instructions for Claude Code
.env.example    Environment variables (filled in as they are introduced)
.mcp.json       Project MCP servers (Jira)
```

`backend/` (skeleton, SCRUM-18) and `frontend/` (app shell, SCRUM-26) hold code; `worker/` and `infra/` hold README placeholders that describe their planned layout ([guide §5.6](docs/DEVELOPMENT_LIFECYCLE.md#56-repository-layout)). The sample app **TaskFlow** lives in a separate repository: [hamdounisabri1/taskflow](https://github.com/hamdounisabri1/taskflow).

## Getting started

The backend skeleton and the frontend shell run locally (commands in [CLAUDE.md](CLAUDE.md#commands)). To work on the project with Claude Code, follow [Setup after cloning](docs/AI_TOOLING.md#setup-after-cloning): it covers the prerequisites, plugins, and the GitHub and Jira tokens (kept in your OS environment, never in the repo). Commands still marked `(planned)` there are verified as their Tasks land.

## Built with Claude Code

This project uses [Claude Code](https://claude.com/claude-code) with project-scoped tooling:

- **Plugins:** `github`, `context7`, `security-guidance`, `commit-commands`, `claude-md-management`
- **MCP servers:** `jira` (`mcp-atlassian`, Jira project `SCRUM`)
- **Skills:** `ui-ux-pro-max`, `webapp-testing`, `postgresql-table-design`, `postgresql-optimization`, `fastapi-templates`, `typescript-advanced-types`, `github-actions-hardening`, `multi-stage-dockerfile`, `jira-integration`, `to-tickets`, `system-design`, `architecture`
- **Hooks:** secret-file guard + gitleaks on commit, auto-format/lint after edits
- **Agents and commands:** `release-safety-reviewer`, `/sprint-status`, `/new-adr`, `/lesson`, `/dod-check`

See [docs/AI_TOOLING.md](docs/AI_TOOLING.md) for what each one does and how to set them up after cloning.
