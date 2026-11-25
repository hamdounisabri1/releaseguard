# Git and workflow rules

## Branches and commits
- Trunk-based. `main` is always deployable and protected (PR plus green CI).
- Short-lived branches: `feat/<scope>-<desc>`, `fix/…`, `chore/…`, `docs/…`, `test/…`. One Task = one branch = one PR, merged within 1–2 days (Tasks are ≤ 2 days); merge daily when possible. Include the Jira key (project `SCRUM`) when a ticket exists: `feat/SCRUM-12-approval-gate`.
- **Bulk completion = one PR.** When the user asks to complete Tasks in bulk ("bulk complete", or names more than one Task to finish together), all of them go on **one branch and one PR**: branch `<type>/SCRUM-<first>-<last>-<desc>` (for example `chore/SCRUM-9-10-dev-tooling`), PR title listing every key (`chore(infra): SCRUM-9, SCRUM-10 webhook tunnel and pre-commit`), one commit per Task inside it (each with its own key) so the history stays readable, every Task's checkbox ticked in that same PR, and every Task marked Done once it merges. A single Task named on its own stays on its own PR.
- **Don't stack Task PRs.** Branch every Task from an up-to-date `main`, never from another unmerged Task branch. Squash-merging the lower PR rewrites its commits, so every PR stacked on it then conflicts. If a stack already exists, after each merge run `git rebase --onto origin/main <old-tip-of-merged-branch> <next-branch>` and force-push it with `--force-with-lease`.
- Conventional Commits with a scope: `api`, `web`, `worker`, `db`, `github`, `ai`, `infra` or `docs`. Example: `feat(api): block self-approval when policy enabled`. Reference the Jira issue in the commit body or PR title (`SCRUM-12`) so Jira links it.
- Squash-merge. SemVer tags at the end of each sprint: `v0.1.0` … `v0.5.0`, then `v1.0.0` for the MVP.
- **Finishing a Task ships it without asking** (user preference, 25 Nov 2026): when a Task, or a bulk set of Tasks, is complete (code, tests and docs green, plan checkbox ticked), Claude commits, pushes the branch and opens a ready-for-review PR right away, without waiting for the user. It still never merges. Mid-Task commits after each green step are fine too. Other pushes (unfinished work, tags) still wait for the user. Use `/commit` or `/commit-push-pr` (commit-commands plugin) or plain `git`/`gh`.

## Daily Git rhythm
| When | Git action |
|---|---|
| Start of day | `git pull` on `main`, rebase any open Task branch onto it. The daily "Today" block edit stays uncommitted until the day's first Task branch is created, then goes in as that branch's first commit |
| Task starts (after its plan is approved) | Create the Task branch from the up-to-date `main` |
| Each working step | Commit: one small step that works, with its tests passing (roughly 3–8 commits a day; no more than 1–2 hours of work per commit) |
| End of session | Push the branch, even if unfinished (backup + CI); open a **draft PR** on the first push |
| Task done | CI green → **tick the Task's checkbox in `PROJECT_PLAN.md` (and move it to "Done today") on the Task branch** → `/code-review` (plus the safety reviews where needed) → `/dod-check` → **the user squash-merges** → Jira Done |
| Sprint done | Tag `v0.N.0` on `main` and push the tag |

- Never commit directly to `main`. **`main` is protected on both repos** by the ruleset `protect-main` (PR required, squash only, no bypass, admins included; see `infra/README.md`), so a direct push fails with GH013.
- **Leave no edit behind on `main`.** Every file change goes through a branch and a PR, including process edits: the Task's own plan checkbox (ticked in its PR, before merge), the daily "Today" block (rides on the day's first Task branch), and sprint-close edits (retro, "Current sprint" line, leftover ticks) in a `docs/sprint-<N>-close` PR. Anything that would only happen after a merge must be done before it, inside the PR.
- **The user merges every PR, by hand, in GitHub. Claude never merges** (`gh pr merge` and the MCP merge tool are denied in `.claude/settings.json`). Claude says when a PR is ready to merge; once `gh pr view <n> --json state` shows `MERGED`, it marks the Task Done, deletes the local branch and pulls `main`.
- After merging, delete the branch and pull `main`.
- Claude commits after each green step and, when the Task is complete, pushes and opens the PR on its own (see above). For an unfinished branch at session end, it reminds the user and pushes once they say so.
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
