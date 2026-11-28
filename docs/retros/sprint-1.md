# Sprint 1 retro: Foundation

- **Dates:** planned Thu 26 – Fri 27 Nov 2026; work ran Thu 26 – Fri 27 Nov, all Tasks Done by Sat 28 Nov morning
- **Epic:** SCRUM-12 · **Tasks:** SCRUM-18 … SCRUM-34 plus SCRUM-110 (18 of 18 Done, 110 added during SCRUM-20)
- **Tag:** `v0.1.0` (offered after the close PR merges)
- **Demo:** sign in, create TaskFlow, configure its three environments; runs locally with `docker compose -f infra/docker-compose.yml up -d --wait`. Recording not yet made.

## Goal and result

**Goal:** a user can sign in, create an application and configure its three environments.
**Result:** met. Definition of done: sign-in, application and environments work; a Viewer cannot edit; another workspace's data cannot be reached (tests in SCRUM-34); CI green.

| Task | What landed | PR |
|---|---|---|
| SCRUM-18 | Backend skeleton: config, error shape, Origin-check CSRF, role matrix | #10 |
| SCRUM-19 to 25 | Models and first migration, argon2 sessions, RBAC, audit helper, application and environment CRUD, health and logging, seed script | #14 |
| SCRUM-26 | Next.js App Router, Tailwind, shadcn/ui shell | #12 |
| SCRUM-27, 29, 33, 34 | API client and generated types, shared UI states, CI workflow, route-wide security sweeps | #17 |
| SCRUM-28 | Login page, auth guard, sign-out, dashboard placeholder | #20 |
| SCRUM-30, 31 | Applications list and details, environment settings form | #22 |
| SCRUM-110, 32 | Login throttling per (email, IP) and per IP; local docker-compose (db, backend, frontend) | #19 |
| (tooling) | `/project-progress` skill; rebase-merge switch; block pushing or opening a PR from an already-merged branch | #18, #16, #23 |

## What went well

- Vertical slices: each day ended with something a user could click through (login, then applications, then environment settings).
- The security sweeps (SCRUM-34) ran against every route, so cross-workspace and CSRF checks cover new endpoints automatically.
- Login throttling was found while working SCRUM-20 and filed as its own Task (SCRUM-110) instead of being squeezed into it.

## What didn't

- Two Tasks shipped in one bulk PR (SCRUM-30 and SCRUM-31), so review had to look at a larger diff. Keep bulk sets to related Tasks.
- A stale local branch was pushed after its rebase-merge and reopened as a duplicate PR (#21). The guard in `pre_bash.py` now blocks it; the lesson is in `git-workflow.md`.
- The README still said "pre-code" after Sprint 1 landed. The close step did not cover the README, so `jira-workflow.md` §7 and the docs-sync table in `CLAUDE.md` now list it.

## Findings to carry forward

- Sprint 2 is the first sprint with the worker and the GitHub App. The App's dev channel and webhook secret are needed before SCRUM-45 can be tested end to end ([GITHUB_APP_SETUP.md](../GITHUB_APP_SETUP.md)).
- Sprint 2 has no buffer (see the timetable in [PROJECT_PLAN.md](../PROJECT_PLAN.md#daily-timetable)). Risk triggers are at 11:00 and 17:15.

## Open items

- None blocking. The `v0.1.0` tag waits for the close PR to merge.

## Lessons

No bugs reached `main` as a regression in Sprint 1, so no new lessons were added in this retro. The stale-branch lesson was added earlier in `git-workflow.md`.
