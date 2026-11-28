# infra/

Docker Compose, the reverse proxy and operations scripts for running ReleaseGuard itself, plus the GitHub repository settings.

| Path | Contents | Ticket |
|---|---|---|
| [`github/`](github/) | Repo settings as code: `protect-main` ruleset, rebase-merge only, labels | SCRUM-7 (Sprint 0) |
| [`docker-compose.yml`](docker-compose.yml) | Local development stack: db (Postgres 17), backend, worker, frontend | SCRUM-32 (Sprint 1), worker SCRUM-41 |
| [`postgres/init/`](postgres/init/) | First-start SQL for the local db: creates `releaseguard_test` | SCRUM-32 (Sprint 1) |
| [`reverse-proxy/`](reverse-proxy/README.md) | Caddy: one origin, `/` → frontend, `/api` → backend, automatic TLS | SCRUM-94 (Sprint 6) |
| [`scripts/`](scripts/README.md) | Backup, restore and deploy scripts | SCRUM-97 (Sprint 6) |

## Local development stack

`docker compose -f infra/docker-compose.yml up -d db` starts Postgres only (run the apps on the host); `up -d --wait` starts db, backend and frontend with hot reload. Settings come from the repo-root `.env` (`env_file`); it must set `POSTGRES_PASSWORD` (see `.env.example`).

- **No secrets in the file.** The backend container builds `DATABASE_URL` at start for host `db` without a password and passes `POSTGRES_PASSWORD` as libpq's `PGPASSWORD`, because Compose's own `${...}` interpolation reads `infra/.env` or the shell, never the repo-root `.env`.
- **Localhost only.** Every published port binds to `127.0.0.1` (`DB_PORT`, `BACKEND_PORT`, `FRONTEND_PORT` change the host side; set them in the shell or `infra/.env`).
- **Volumes:** `db-data` (Postgres), `backend-venv` and `uv-cache` (Linux venv, kept apart from a host `.venv`), `frontend-node-modules`, `frontend-next` and `pnpm-store` (kept out of the bind-mounted `frontend/`). `down -v` resets them all, including the database.
- The backend runs `alembic upgrade head` and the idempotent seed on every start. `DATABASE_URL` exists only in its start command's shell, so restart the service (`docker compose -f infra/docker-compose.yml restart backend`) rather than running those through `exec`.
- The production stack (Caddy, built images pinned by digest, worker) is SCRUM-93/94.

## GitHub repository settings

`github/setup-repo.sh <owner/repo>` applies the same settings to `releaseguard` and `taskflow`. It is idempotent; re-run it after changing [`ruleset-main.json`](github/ruleset-main.json) or the label list. It needs `gh` logged in as a repo admin.

```bash
infra/github/setup-repo.sh hamdounisabri1/releaseguard
infra/github/setup-repo.sh hamdounisabri1/taskflow
```

- **Ruleset `protect-main`** (default branch): PR required, rebase-merge only, no force-push, no deletion, linear history, **no bypass actors** (admins included). 0 required approvals, because a solo developer can't approve their own PR.
- **Merge settings:** rebase-merge only, so `main` keeps every commit of the branch (each one needs a Conventional Commit message with the Jira key); head branches are deleted on merge.
- **Labels:** the set in [PROJECT_PLAN.md §5](../docs/PROJECT_PLAN.md#labels) (`area:*`, `type:*`, `sprint:0`…`sprint:6`, `p0|p1|p2`); GitHub's default labels are removed.
- **Required status checks** (releaseguard only, SCRUM-33): a second ruleset, `ci-required`, from [`ruleset-ci-releaseguard.json`](github/ruleset-ci-releaseguard.json). It requires the four `ci.yml` jobs (`backend`, `frontend`, `api-types`, `gitleaks`), bound to the GitHub Actions app (`integration_id` 15368) so no other app can post a passing status under those names. The script applies `ruleset-ci-<repo-name>.json` only when that file exists, so taskflow gets its own list once its CI exists. Renaming a CI job means updating this file and re-running the script; otherwise every PR waits forever for a check that never reports.
- **Emergency:** a direct push to `main` is rejected (GH013). If one is really needed, set the ruleset to *Disabled* in Settings → Rules → Rulesets, push, and re-run the script to restore it.

Rules: [infra.md](../.claude/rules/infra.md) · [security.md](../.claude/rules/security.md)
