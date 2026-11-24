# Git and workflow rules

## Branches and commits
- Trunk-based. `main` is always deployable and protected (PR plus green CI).
- Short-lived branches: `feat/<scope>-<desc>`, `fix/…`, `chore/…`, `docs/…`, `test/…`. One Task = one branch = one PR, merged within 1–2 days (Tasks are ≤ 2 days); merge daily when possible. Include the Jira key (project `SCRUM`) when a ticket exists: `feat/SCRUM-12-approval-gate`.
- Conventional Commits with a scope: `api`, `web`, `worker`, `db`, `github`, `ai`, `infra` or `docs`. Example: `feat(api): block self-approval when policy enabled`. Reference the Jira issue in the commit body or PR title (`SCRUM-12`) so Jira links it.
- Squash-merge. SemVer tags at the end of each sprint: `v0.1.0` … `v0.5.0`, then `v1.0.0` for the MVP.
- Commit or push only when the user asks. Use `/commit` or `/commit-push-pr` (commit-commands plugin).

## Daily Git rhythm
| When | Git action |
|---|---|
| Start of day | `git pull` on `main`, rebase any open Task branch onto it |
| Task starts (after its plan is approved) | Create the Task branch from the up-to-date `main` |
| Each working step | Commit: one small step that works, with its tests passing (roughly 3–8 commits a day; no more than 1–2 hours of work per commit) |
| End of session | Push the branch, even if unfinished (backup + CI); open a **draft PR** on the first push |
| Task done | CI green → `/code-review` (plus the safety reviews where needed) → `/dod-check` → **the user squash-merges** → Jira Done |
| Sprint done | Tag `v0.N.0` on `main` and push the tag |

- Never commit directly to `main`.
- **The user merges every PR, by hand, in GitHub. Claude never merges** (`gh pr merge` and the MCP merge tool are denied in `.claude/settings.json`). Claude says when a PR is ready to merge; once `gh pr view <n> --json state` shows `MERGED`, it marks the Task Done, deletes the local branch and pulls `main`.
- After merging, delete the branch and pull `main`.
- Claude reminds the user at each of these points (commit after a green step, push at session end) and runs the command once the user says so.
- **Commit on demand:** the user can ask for a commit (or a push) at any time, not only at these points. Claude does it right away: it reviews `git diff --staged` for secrets, writes a Conventional Commit message with the Jira key, and commits on the current Task branch. If the current branch is `main`, it creates the Task branch first, because nothing is committed directly to `main`.

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
