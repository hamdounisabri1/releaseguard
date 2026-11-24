# infra/

Docker Compose, the reverse proxy and operations scripts for running ReleaseGuard itself.

> **Placeholder.** No files yet.

| Path | Contents | Ticket |
|---|---|---|
| `docker-compose.yml` | Local development stack: db, backend, worker, frontend | SCRUM-32 (Sprint 1) |
| [`reverse-proxy/`](reverse-proxy/README.md) | Caddy: one origin, `/` → frontend, `/api` → backend, automatic TLS | SCRUM-94 (Sprint 6) |
| [`scripts/`](scripts/README.md) | Backup, restore and deploy scripts | SCRUM-97 (Sprint 6) |

Rules: [infra.md](../.claude/rules/infra.md) · [security.md](../.claude/rules/security.md)
