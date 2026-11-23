# Git and workflow rules

## Branches and commits
- Trunk-based. `main` is always deployable and protected (PR plus green CI).
- Short-lived branches: `feat/<scope>-<desc>`, `fix/…`, `chore/…`, `docs/…`, `test/…`. Merge within 1–3 days. Include the Jira key (project `SCRUM`) when a ticket exists: `feat/SCRUM-12-approval-gate`.
- Conventional Commits with a scope: `api`, `web`, `worker`, `db`, `github`, `ai`, `infra` or `docs`. Example: `feat(api): block self-approval when policy enabled`. Reference the Jira issue in the commit body or PR title (`SCRUM-12`) so Jira links it.
- Squash-merge. SemVer tags at the end of each sprint: `v0.1.0` … `v0.5.0`, then `v1.0.0` for the MVP.
- Commit or push only when the user asks. Use `/commit` or `/commit-push-pr` (commit-commands plugin).

## Issues (Definition of Ready)
Issues are Jira tickets in project `SCRUM` (see `jira-workflow.md`). A ticket is Ready when it has a goal, acceptance criteria **including failure paths**, area labels (`area:api|web|worker|db|github|ai|infra|docs`), no blocking dependencies, and a size of **≤ 2 days**. Labels: `type:*`, `sprint:N`, `p0|p1|p2`.

## Definition of Done
- [ ] Acceptance criteria met, including permission-denied and failure paths
- [ ] Backend permission check plus workspace scoping verified
- [ ] Tests added or updated, CI green (lint, types, tests, Trivy)
- [ ] Alembic migration included, reversible, tested on a fresh database
- [ ] UI has empty, loading, error and permission-denied states (where relevant)
- [ ] State-changing actions write audit entries
- [ ] Docs, OpenAPI descriptions, `.env.example`, `CLAUDE.md` and `.claude/rules/` updated (see "Keep the docs in sync" in CLAUDE.md)
- [ ] Bug fixes: a regression test, plus a lesson under `## Lessons learned` in the matching rules file (see `maintenance.md`)
- [ ] New skills or plugins: committed and documented (see `maintenance.md`)
- [ ] From Sprint 6 onward: deployed and checked on the VPS

## Pull requests
- Use the PR template (`.github/pull_request_template.md`): Jira key · What and why · How to test · Checklist (tests, permissions, no secrets, reversible migration, audit events, screenshots).
- Review before merging with `/code-review`, and `/security-review` for sensitive areas. For deployment, approval, webhook or token code also run the `release-safety-reviewer` agent. Use `/dod-check` to walk the Definition of Done against the diff.

## Decisions and scope
- Record significant technical decisions as ADRs: `docs/adr/NNNN-title.md` (context, decision, consequences).
- Don't add out-of-scope v1 features (Kubernetes, other CI providers, canary or blue-green, automatic rollback, a policy language). If the schedule slips, apply the **cut list** in `docs/PROJECT_PLAN.md` §6 in order. Never cut the items on its "never cut" list.
