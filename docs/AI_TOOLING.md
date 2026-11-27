# AI Tooling: Claude Code Plugins, Skills, MCP Servers and Automation

ReleaseGuard is built with [Claude Code](https://claude.com/claude-code). This page lists the plugins, skills, MCP servers, hooks, agents and commands the project uses, what each one is for, and how to set them up after cloning.

Everything here is **project-scoped**. It is configured inside this repository and does not change your global Claude Code setup.

| What | Where it lives | Committed? |
|---|---|:-:|
| Project instructions for Claude | [`CLAUDE.md`](../CLAUDE.md) (short: overview, commands, architecture, index) | ✅ |
| Detailed rules | [`.claude/rules/`](../.claude/rules/). Three always load (`maintenance`, `security`, `git-workflow`); the rest (`jira-workflow`, `backend`, `database`, `frontend`, `testing`, `github-actions`, `infra`, `ai`) are path-scoped and load only for matching files | ✅ |
| Plugins, permissions and hooks | [`.claude/settings.json`](../.claude/settings.json) | ✅ |
| Hook scripts | [`.claude/hooks/`](../.claude/hooks/) | ✅ |
| Subagents | [`.claude/agents/`](../.claude/agents/) | ✅ |
| Slash commands | [`.claude/commands/`](../.claude/commands/) | ✅ |
| MCP servers (besides plugin ones) | [`.mcp.json`](../.mcp.json) | ✅ |
| Skills | [`.claude/skills/`](../.claude/skills/) | ✅ |
| Skill versions (source repo + commit + hash) | [`skills-lock.json`](../skills-lock.json) | ✅ |
| Personal overrides | `.claude/settings.local.json` | ❌ git-ignored |
| Tokens and secrets | Your OS user environment variables (GitHub and Jira tokens) | ❌ never |

---

## Plugins

All plugins come from the official marketplace, `claude-plugins-official`.

| Plugin | What it does | Used for in ReleaseGuard |
|---|---|---|
| **github** | GitHub MCP server: issues, pull requests, repositories, Actions | PRs, repos, checking GitHub Actions runs (TaskFlow workflows). Destructive tools are denied or need approval in `settings.json` |
| **context7** | Up-to-date, version-specific library documentation | Current docs for Next.js, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic |
| **security-guidance** | Works **passively**: flags security problems while code is written (injection, XSS, SSRF, hard-coded secrets and more). Nothing to invoke | Webhook signature checks, RBAC, approval logic, token handling |
| **commit-commands** | Commit, push and open-PR commands | Conventional Commits and the rebase-merge PR flow |
| **claude-md-management** | Audits and updates `CLAUDE.md` | Keeping project instructions current as the code grows |

## MCP servers (`.mcp.json`)

| Server | What it does | Used for in ReleaseGuard |
|---|---|---|
| **jira** | [`mcp-atlassian`](https://github.com/sooperset/mcp-atlassian) `0.21.0`, run locally with `uvx` (stdio). Credentials come from your environment through `${VAR}` expansion; none are in the file. Limited to project `SCRUM` via `JIRA_PROJECTS_FILTER` | Jira project `SCRUM`: creating issues, links and sprints (`jira_*` tools; see `jira-workflow.md`). Routine reads and transitions go through `.claude/scripts/jira.py` first; this server is the fallback |

## Skills

| Skill | Source | License | Used for in ReleaseGuard |
|---|---|---|---|
| **ui-ux-pro-max** | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | MIT | UI/UX guidance for every screen: styles, palettes, typography, accessibility, Next.js and shadcn/ui rules |
| **webapp-testing** | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/webapp-testing) | Apache-2.0 | Driving the running app with Playwright: verifying sprint demos, screenshots, E2E checks |
| **postgresql-table-design** | [wshobson/agents](https://github.com/wshobson/agents) | MIT | Designing the Postgres schema and Alembic migrations: data types, constraints, indexes |
| **postgresql-optimization** | [github/awesome-copilot](https://github.com/github/awesome-copilot) | MIT | Postgres-specific features and tuning: JSONB, indexes, the `FOR UPDATE SKIP LOCKED` jobs table, the partial unique index for one active deployment per environment |
| **fastapi-templates** | [wshobson/agents](https://github.com/wshobson/agents) | MIT | Async patterns, dependency injection and error handling. **Not** for auth (it teaches JWT; this project uses server-side sessions) or folder layout (see `backend.md`) |
| **typescript-advanced-types** | [wshobson/agents](https://github.com/wshobson/agents) | MIT | Type-safe API clients, status unions and generics in the Next.js frontend |
| **github-actions-hardening** | [github/awesome-copilot](https://github.com/github/awesome-copilot) | MIT | Security review of the `ci.yml` and deploy/rollback workflows: injection, token permissions, SHA pinning |
| **jira-integration** | [affaan-m/ECC](https://github.com/affaan-m/ECC) | MIT | Background reference for Jira concepts (JQL, transitions). Use the **jira** MCP server for actual calls (note: its setup example passes `JIRA_EMAIL`, but `mcp-atlassian` needs `JIRA_USERNAME`; `.mcp.json` maps it): the skill's REST examples need `jq` and use the retired `/rest/api/3/search` endpoint |
| **multi-stage-dockerfile** | [github/awesome-copilot](https://github.com/github/awesome-copilot) | MIT | Small, safe multi-stage Dockerfiles for the backend, worker and frontend images |
| **to-tickets** | [mattpocock/skills](https://github.com/mattpocock/skills/tree/main/skills/engineering/to-tickets) | MIT | `/to-tickets` (user-invoked only): in the one-time up-front planning pass, drafts every sprint's checklist as vertical-slice Jira Tasks with blocking links, then creates them under each sprint's Epic after approval. Its Jira configuration is in `jira-workflow.md` §3 |

| **system-design** | [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins/tree/main/engineering/skills/system-design) | Apache-2.0 | Framework for designing components, APIs, data models and service boundaries: requirements, high-level design, deep dive, trade-offs. Complements `DEVELOPMENT_LIFECYCLE.md`; it never overrides it |
| **architecture** | [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins/tree/main/engineering/skills/architecture) | Apache-2.0 | `/architecture`: weighs options and trade-offs for a technical decision. Record the outcome with `/new-adr` (project template), not with this skill's own ADR format |
| **project-progress** | First-party (this repo; not in `skills-lock.json`, which tracks third-party sources only) | Project's own | `/project-progress [short \| page]`: whole-project report as a project manager would give it. Covers RAG status, earned value (EV from ticked plan estimates, PV from the daily timetable, SPI), a burn-up, milestone forecast, features vs the MVP checklist, tech stack, folder and codebase state, environments, quality gates, ADRs, risks and next steps. `scripts/collect.py` (stdlib, read-only, reads tracked files only and `.env.example` names only) gathers the facts as JSON; `page` also publishes the report as a private artifact. Chosen over the skills.sh status-report skills (under 100 installs each, and none can read this plan or `jira.py`). Tests: `uv run --no-project --with pytest pytest .claude/skills/project-progress/scripts` |

Built-in skills the rules also reference (shipped with Claude Code, nothing to install): **`claude-api`** for AI provider code (`ai.md`).

> **Local changes to third-party skills** (reapply after `npx skills update`, which overwrites them):
> - `ui-ux-pro-max/SKILL.md`: script paths changed from `${CLAUDE_PLUGIN_ROOT}/.claude/skills/...` to `.claude/skills/...` so it works as a project skill.
> - `to-tickets/SKILL.md`: the "run `/setup-matt-pocock-skills`" line now points to `jira-workflow.md` §3 (Jira `SCRUM` configuration). `LICENSE` was added from upstream, because the installer copies only the skill folder.
>
> - `architecture/SKILL.md`: the `CONNECTORS.md` link (a file that doesn't exist in this repo) now points to `/new-adr` and the `jira` MCP server. `LICENSE` (Apache-2.0) was added to both `architecture` and `system-design` from upstream, because the installer copies only the skill folder.
>
> **Known issue, not patched:** `webapp-testing/scripts/with_server.py` leaves `node` running on Windows and can hang on full output pipes. Start the app yourself as a background task and run Playwright directly (see `frontend.md`).

## Hooks, agents and commands

| Item | Type | What it does |
|---|---|---|
| `.claude/hooks/pre_bash.py` | PreToolUse hook (Bash, PowerShell) | Blocks commands that read `.env`, `*.pem` or `*.key` (`.env.example` is allowed). On `git commit` runs `gitleaks` on staged changes **if a `gitleaks` binary is on `PATH`** and blocks on findings. The main secret gate is the pre-commit gitleaks hook, which needs no separate install |
| `.claude/hooks/post_edit.py` | PostToolUse hook (Edit, Write, MultiEdit) | Backend `*.py`: `uv run ruff format` + `ruff check --fix`. Frontend TS/JS: `eslint --fix` (eslint's JS entry run with `node`, so route-group paths like `app/(app)/…` work on Windows). Silent until `backend/pyproject.toml` or `frontend/node_modules` exists. Regression tests: `uv run --no-project --with pytest pytest .claude/hooks` |
| `release-safety-reviewer` | Subagent | Read-only review of a diff against the state-machine, approval, concurrency, tenancy, webhook, dispatch and secrets invariants |
| `/sprint-status` | Command | Current sprint summary from the plan and Jira |
| `/new-adr <title>` | Command | Creates the next `docs/adr/NNNN-*.md` from the template |
| `/lesson <bug>` | Command | Records a lesson in the matching rules file (only when `maintenance.md` §3 says so) |
| `/dod-check` | Command | Walks the Definition of Done against the current diff |
| `/bulk last N \| rest \| <keys> \| done` | Command | Bulk mode: runs several Tasks with one plan, one branch, a commit per Task, a single push and PR at the end, and one review and DoD pass on the combined diff. `done` marks them Done after the user merges |
| `.claude/scripts/jira.py` | Script (stdlib Python) | Primary Jira path: `brief`, `start`, `done`, `today` and `sprint-close` across many tickets per call, in compact output, with `--dry-run` on writes. Reads `JIRA_URL`, `JIRA_EMAIL` and `JIRA_API_TOKEN`; never prints them. Tests: `.claude/scripts/test_jira.py` |

Hooks run with `python`. On Windows, if `python` opens the Microsoft Store stub, install Python from python.org or change the hook command to `py -3` in your `.claude/settings.local.json`.

---

## Setup after cloning

### 1. Prerequisites
- [Claude Code](https://claude.com/claude-code)
- Python 3.12+ on `PATH` as `python` (hooks) and [uv](https://docs.astral.sh/uv/)
- [GitHub CLI](https://cli.github.com/): `winget install GitHub.cli` (Windows) or `brew install gh` (macOS)
- [pre-commit](https://pre-commit.com/): `uv tool install pre-commit`, then `pre-commit install` in the clone. It runs gitleaks, Ruff, ESLint and Prettier on every commit and downloads gitleaks itself
- Optional: a [gitleaks](https://github.com/gitleaks/gitleaks) binary on `PATH` (`winget install gitleaks` or `brew install gitleaks`) so the Claude commit hook also scans, and for ad hoc scans (`gitleaks git --redact .`)
- Playwright for `webapp-testing`, isolated from your global Python: `uv tool install playwright && playwright install chromium`

### 2. Plugins
Open the repository in Claude Code and accept the prompt to install the project's plugins. If no prompt appears, install them yourself:

```bash
claude plugin install github@claude-plugins-official --scope project
claude plugin install context7@claude-plugins-official --scope project
claude plugin install security-guidance@claude-plugins-official --scope project
claude plugin install commit-commands@claude-plugins-official --scope project
claude plugin install claude-md-management@claude-plugins-official --scope project
```

### 3. Skills
The skills are committed in `.claude/skills/`, so they load automatically. To reinstall them from source:

```bash
npx skills experimental_install
```

### 4. GitHub authentication
The `github` plugin reads a token from the `GITHUB_PERSONAL_ACCESS_TOKEN` environment variable. Use a **fine-grained personal access token**, not the `gh` CLI's broad OAuth token:

1. GitHub → Settings → Developer settings → Fine-grained tokens → **Generate new token**.
2. **Expiration:** 90 days or less. **Repository access:** only `releaseguard` and `taskflow`.
3. **Permissions:** Contents (read/write), Pull requests (read/write), Issues (read/write), Actions (read/write), Metadata (read). Nothing else.
4. Store it as a user environment variable (it is never printed or committed):

**Windows (PowerShell):**
```powershell
[Environment]::SetEnvironmentVariable("GITHUB_PERSONAL_ACCESS_TOKEN", (Read-Host -AsSecureString "Token" | ConvertFrom-SecureString -AsPlainText), "User")
```

**macOS / Linux:** add `export GITHUB_PERSONAL_ACCESS_TOKEN="…"` to a file only you can read (e.g. `~/.config/secrets.sh`, `chmod 600`) and source it from `~/.zshrc` or `~/.bashrc`.

Fully restart your editor or terminal afterwards. Set a reminder to rotate the token before it expires.

> **Never** put the token in `.env`, in a committed file, or in a chat message. If it leaks, delete it on GitHub immediately and create a new one.

### 5. Context7 and Jira authentication
In Claude Code run `/mcp` → choose **context7** → **Authenticate**, finish in the browser.

For Jira, create an API token at <https://id.atlassian.com/manage-profile/security/api-tokens> and store three **user environment variables** the same way as the GitHub token above: `JIRA_URL` (e.g. `https://yourorg.atlassian.net`), `JIRA_EMAIL` and `JIRA_API_TOKEN`. Restart your editor, open the repo and approve the project's **jira** server when prompted. `.mcp.json` passes them to `mcp-atlassian` (mapping `JIRA_EMAIL` to its `JIRA_USERNAME`); the REST fallback in `jira-workflow.md` uses the same variables.

> If `/mcp` shows **jira** connected but no `jira_*` tools appear, a variable is missing: `mcp-atlassian` starts without Jira credentials but exposes zero tools. Also remove any older user-level copy (`claude mcp remove jira -s user`) so only the project one runs.

### 6. Check everything
```bash
claude plugin list   # all five plugins: enabled
claude mcp list      # github, context7 and jira: Connected
```
In a session, `/memory` lists the loaded `CLAUDE.md` and rules, and `/hooks` lists the two hooks.

---

## Adding a new tool

Do all of this **in the same change** (`maintenance.md` §1 points here):

1. Install it with **project scope**:
   - Skills: `npx skills add <repo> --skill <name> -a claude-code --copy -y`. Use `--copy`, because symlinks point outside the repo and wouldn't be pushed. Never use `-g`.
   - Plugins: `claude plugin install <name>@<marketplace> --scope project`.
   - MCP servers: add them to `.mcp.json` and to `enabledMcpjsonServers` in `.claude/settings.json`. Prefer OAuth over tokens; never put a secret in `.mcp.json`.
2. **Review** a third-party skill's files before committing them (scripts, network calls, shell execution). Skills run with full agent permissions.
3. Keep the upstream **license file** inside the skill folder.
4. Check git tracks it: `git check-ignore -v .claude/skills/<name>/SKILL.md` must print nothing. The skill folder, `skills-lock.json`, `.claude/settings.json` and `.mcp.json` go in the same commit.
5. Add a row to the matching table above, to the tooling table in [`CLAUDE.md`](../CLAUDE.md), and to the README "Built with Claude Code" list.
6. Removing a tool means removing it from all of the above too.

## Adding a new rule

Put it in the matching file in [`.claude/rules/`](../.claude/rules/). If none fits, create a new file with a `paths:` frontmatter (so it loads only where it's relevant) and add it to the rules table in [`CLAUDE.md`](../CLAUDE.md). Keep `CLAUDE.md` itself short.
