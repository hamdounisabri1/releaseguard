# Sprint 0 retro: Setup

- **Dates:** planned Sun 22 – Wed 25 Nov 2026 (extended); work ran Mon 23 – Tue 24 Nov, closed Tue 24 Nov, a day early
- **Epic:** SCRUM-5 · **Tasks:** SCRUM-6 … SCRUM-11 (6 of 6 Done)
- **Tag:** none (the first tag, `v0.1.0`, closes Sprint 1)
- **Demo:** nothing to run yet; the outcome is the repo, tooling and docs below

## Goal and result
**Goal:** repos, GitHub App, webhook tunnel, pre-commit tooling and ADR-0001/0002 in place so Sprint 1 can start coding.
**Result:** met.

| Task | What landed | PR |
|---|---|---|
| SCRUM-6 | Monorepo layout (`backend/`, `frontend/`, `worker/`, `infra/`) and the public `taskflow` repo | #1 |
| SCRUM-8 | Development GitHub App registered to the contract (Actions RW, Contents R, Metadata R; `workflow_run` only; installed on `taskflow` only); `GITHUB_APP_SETUP.md` | #2 |
| SCRUM-7 | Ruleset `protect-main` on both repos (PR required, squash only, linear history, no bypass), PR template, labels, `infra/github/setup-repo.sh`; process rule "leave no edit behind on `main`" | #3, #4 |
| SCRUM-11 | ADR-0001 (modular monolith, no Redis/broker in v1) and ADR-0002 (deploy by digest, mismatch failure path), final review | #5 |
| SCRUM-9 | smee.io webhook tunnel, stand-in receiver `infra/scripts/webhook_echo.py`, runbook | #6 |
| SCRUM-10 | pre-commit (gitleaks, Ruff, ESLint, Prettier, basic checks; revs frozen to SHAs), `.editorconfig` | #7 |

## What went well
- All sprints were planned in Jira up front (Epics SCRUM-12…17, Tasks SCRUM-18…109), so daily planning is just picking from the active sprint.
- Testing the tunnel for real, instead of trusting the docs, found two things before they could cost debugging time in Sprint 2 (below).
- The secret gate works and is proven: a staged fake AWS key blocks the commit, and the full history scans clean.

## What didn't
- The sprint was extended once (planned to end Mon 23 Nov), because the architecture review on 23 Nov took priority. It still closed early.
- SCRUM-8's doc claimed smee "queues" deliveries; it doesn't. Docs written before a tool is exercised need a "verified on" note or a test.
- With `main` protected, every process edit (Today block, ticks) needs a PR, so the PRs had to be stacked (#5 → #6 → #7 → this one). Fine for docs; avoid deep stacks for code.
- SCRUM-9–11 were closed in Jira before their PRs merged (one-time exception at the owner's request). The normal rule (Done only after merge) applies from Sprint 1.

## Findings to carry forward
- **smee.io answers 200 even with no client connected.** GitHub shows a green delivery, but the event is lost. Recover with **Redeliver** (3-day window); the product's reconcile sweep covers it too.
- **smee re-serializes the JSON body.** Escaped (`\uXXXX`, `\/`), pretty or big-number payloads fail the HMAC check locally. SCRUM-45 has a note: confirm through cloudflared before debugging the endpoint, and never relax the check.
- Keep the Ruff rev in `.pre-commit-config.yaml` equal to the backend's pinned ruff once `backend/pyproject.toml` exists (SCRUM-18).

## Open items
- One real Redeliver from the dev App through the tunnel (needs the owner's channel URL and webhook secret): steps in [GITHUB_APP_SETUP.md § Verify a real delivery](../GITHUB_APP_SETUP.md#verify-a-real-delivery).
- pnpm isn't installed yet; needed for SCRUM-26 (`corepack enable` or `npm i -g pnpm`).

## Lessons
No bugs reached `main`, so no lessons were added and nothing needs pruning.
