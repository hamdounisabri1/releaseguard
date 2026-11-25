# infra/

Docker Compose, the reverse proxy and operations scripts for running ReleaseGuard itself, plus the GitHub repository settings.

| Path | Contents | Ticket |
|---|---|---|
| [`github/`](github/) | Repo settings as code: `protect-main` ruleset, rebase-merge only, labels | SCRUM-7 (Sprint 0) |
| `docker-compose.yml` | Local development stack: db, backend, worker, frontend | SCRUM-32 (Sprint 1) |
| [`reverse-proxy/`](reverse-proxy/README.md) | Caddy: one origin, `/` → frontend, `/api` → backend, automatic TLS | SCRUM-94 (Sprint 6) |
| [`scripts/`](scripts/README.md) | Backup, restore and deploy scripts | SCRUM-97 (Sprint 6) |

## GitHub repository settings

`github/setup-repo.sh <owner/repo>` applies the same settings to `releaseguard` and `taskflow`. It is idempotent; re-run it after changing [`ruleset-main.json`](github/ruleset-main.json) or the label list. It needs `gh` logged in as a repo admin.

```bash
infra/github/setup-repo.sh hamdounisabri1/releaseguard
infra/github/setup-repo.sh hamdounisabri1/taskflow
```

- **Ruleset `protect-main`** (default branch): PR required, rebase-merge only, no force-push, no deletion, linear history, **no bypass actors** (admins included). 0 required approvals, because a solo developer can't approve their own PR.
- **Merge settings:** rebase-merge only, so `main` keeps every commit of the branch (each one needs a Conventional Commit message with the Jira key); head branches are deleted on merge.
- **Labels:** the set in [PROJECT_PLAN.md §5](../docs/PROJECT_PLAN.md#labels) (`area:*`, `type:*`, `sprint:0`…`sprint:6`, `p0|p1|p2`); GitHub's default labels are removed.
- **Required status checks:** none yet. Add a `required_status_checks` rule to `ruleset-main.json` in Sprint 1, once CI exists, and re-run the script.
- **Emergency:** a direct push to `main` is rejected (GH013). If one is really needed, set the ruleset to *Disabled* in Settings → Rules → Rulesets, push, and re-run the script to restore it.

Rules: [infra.md](../.claude/rules/infra.md) · [security.md](../.claude/rules/security.md)
