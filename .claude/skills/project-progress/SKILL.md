---
name: project-progress
description: Full ReleaseGuard project progress report, the way a project manager reports to stakeholders - RAG status, earned value (SPI), burn-up, milestones, features delivered vs planned, tech stack, folder and codebase state, environments, quality gates, docs and decisions, risks and next steps. Use when the user asks for project progress, a status report, "where are we", a full report or a stakeholder update (not just the current sprint; /sprint-status covers that).
argument-hint: "[short | page]"
---

# Project progress report

A whole-project report, not a sprint board. It answers: **are we on track, what works today, what is it built with, where does it run, what's left and what could stop us.**

Arguments: none → the full report in the terminal. `short` → only section 1 (executive summary). `page` → the full report, then also publish it as a private artifact page with a burn-up chart (see "Page mode").

## 1. Gather facts (two calls, in parallel)

```bash
py -3 .claude/skills/project-progress/scripts/collect.py          # JSON: plan, schedule maths, code, envs, docs, git, PRs, CI
py -3 .claude/scripts/jira.py brief --open --short                # live Jira status of the active sprint's open Tasks
```

- The collector is read-only and stdlib-only. It reads tracked files only, prints `.env.example` variable **names** only, and never reads `.env` or key files. Add `--no-network` if `gh` is unavailable, and `--today YYYY-MM-DD` to report as of another day.
- If `jira.py` fails, try the `jira` MCP server (`jira_search`, `project = SCRUM AND statusCategory != Done`). If that fails too, say so in one line and use the plan's checkboxes.
- For the feature and environment sections, read `docs/DEVELOPMENT_LIFECYCLE.md` only where the JSON isn't enough (deploy environments dev/staging/prod, the VPS target). Don't re-read the whole guide.

**Never invent** ticket keys, numbers, dates or versions. Every figure comes from the JSON, Jira or a file you read. If something is unknown, write "unknown" and where it would come from.

## 2. How the numbers work (explain them only if asked)

- **Earned value (EV):** estimated hours of ticked Tasks in `PROJECT_PLAN.md`. **Planned value (PV):** hours the daily timetable scheduled on days *before* today (a start-of-day view). **SPI = EV / PV.** Above 1 means ahead of plan.
- **Buffer:** remaining working days (today included) × 10 h, minus the remaining estimated hours.
- **RAG:** 🟢 green when SPI ≥ 0.95 and the buffer is ≥ 0. 🟡 amber when SPI ≥ 0.85 and remaining capacity covers at least 95% of the remaining work. 🔴 red otherwise. **Override it one level worse**, and say why, when an item on the plan's "never cut" list is at risk, a sprint is still open after its day, or CI on `main` is red.
- **Milestone forecast:** a milestone is ✅ when its sprint is closed. Otherwise its forecast is the planned time, shifted by the sprint's remaining hours versus the hours left in that day. Say "on time", "early" or "late by ~N h".
- **Scope change:** Tasks above the up-front range SCRUM-18…109 (for example SCRUM-110) were added after planning. List them with their hours.

## 3. Report template

Write for a stakeholder who knows the project's goal but not the code. Use short sections, tables over prose, and no filler. Put the as-of date and time in the title line.

```
# ReleaseGuard progress, <Day DD Mon YYYY HH:MM>

## 1. Executive summary
<RAG emoji + word> · <percent>% done (<EV> of <total> h, <done>/<total> Tasks) · SPI <x> · buffer <±h> · next milestone <Mx name, planned, forecast>
2–4 bullets: the headline, the biggest win since the last report, the top risk with its trigger, any decision needed from the user.

## 2. Schedule
Table per sprint: sprint · dates · Tasks done/total · hours done/total · state (✅ closed / 🔵 active / ⏳ waiting) · tag.
A text burn-up: one line per day from the timetable with planned cumulative hours vs earned so far (EV only for past days and today).
Required pace: <h/day> for the remaining <n> days, against 10 h/day available.

## 3. Milestones
Table: M# · what it proves · planned · forecast · status.

## 4. Features
Group by Epic (one row per sprint theme). Columns: feature · status (✅ delivered / 🔵 in progress / ⏳ planned / ✂️ cut) · evidence.
Evidence = endpoints, pages or Task keys that prove it. Then the MVP acceptance checklist (§7 of the plan) as x/10 with each item's state.

## 5. Tech stack
Table: layer (backend, data, frontend, worker, infra/runtime, CI/CD, security tooling, AI) · technology and version · status (in use / planned in S<n>).
Versions from the JSON (pyproject, package.json, .python-version, pnpm pin); planned items from CLAUDE.md "Architecture" and the plan.

## 6. Codebase and folders
Table from `structure`: folder · state (active / placeholder / missing) · files · lines · what lives there.
Then: API routes (count + grouped list), database tables and migrations, services, frontend pages and component counts, test files and test function count.

## 7. Environments
- **Development:** local stack (compose file present or not, which services), `.env.example` variables (names only, grouped: app, database, frontend, GitHub, AI…).
- **CI:** workflows and their jobs, latest `main` run (status, link), pre-commit hooks, branch protection.
- **Deploy targets for TaskFlow:** dev / staging / prod and their policies (auto-deploy, promote, approval).
- **Production (ReleaseGuard itself):** VPS, Caddy, TLS, backups. State what exists versus what's planned for S6.

## 8. Quality and security
Tests (backend and frontend), CI gates, security controls delivered so far (CSRF Origin check, sessions, RBAC, workspace scoping, append-only audit…) versus still to come (webhook HMAC, OIDC, SSRF guard, Trivy). Open bugs (`type:bug` Tasks), if any.

## 9. Docs and decisions
ADRs (number and title), retros, main docs, the Claude Code tooling count (rules, skills, commands, agents).

## 10. Risks, issues and scope
Table: risk · early signal · triggered? (✅ no / ⚠️ watch / 🔴 yes) · response. Cut list: items applied so far (normally none). Scope changes since planning.

## 11. Next
Today's Tasks (Jira `today` label and the plan's Today block), what's next in the following sprint, and blockers. Repository activity: commits on main per day, merged PRs, open PRs, tags.
```

`short` mode: only section 1, at most 6 lines.

## 4. Page mode (`page`)

After the terminal report, publish the same content as a private artifact page. Follow the Artifact tool's rules: run its `quickstart` with intent `other`, load the skills it asks for (`artifact-design`, and `dataviz` for the burn-up chart, which shows planned vs earned cumulative hours per day, with total scope as a line). Write the HTML to the session scratchpad, never into the repo. Then give the link. Republishing later from the same file path keeps the same URL.

## 5. Rules

- Read-only. Don't create, edit or transition Jira tickets, and don't edit the plan. If the report reveals drift (a Done Task with an unticked box, or the reverse), report it and suggest the fix.
- The "Today" block in `PROJECT_PLAN.md` may be an uncommitted edit on `main` (`git-workflow.md`). That's expected, not drift.
- Don't paste the JSON. Summarize it.
- If the collector breaks because the plan's format changed, fix `scripts/collect.py` and its tests (`uv run --no-project --with pytest pytest .claude/skills/project-progress/scripts`) in a PR, rather than working around it.
