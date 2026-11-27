---
paths:
  - "infra/**"
  - "**/Dockerfile"
  - "**/Dockerfile.*"
  - "**/docker-compose*.yml"
  - "**/compose*.yml"
---

# Infrastructure rules (Docker, Compose, VPS)

## Images
- Multi-stage Dockerfiles for backend, worker and frontend (`output: "standalone"`). Run as a **non-root** user. Use a slim base pinned to a version.
- The backend runs `uvicorn … --no-proxy-headers`; production sets `TRUSTED_PROXIES` to Caddy's address or network (login throttling keys on the client IP, see `security.md`).
- No secrets in images or build args. Configuration comes from environment variables at runtime.
- Every image must pass Trivy with no HIGH/CRITICAL findings before it's pushed.

## Compose
- `infra/docker-compose.yml` for local development (db, backend, frontend, worker).
- Production Compose services: `proxy` (Caddy, automatic TLS) · `frontend` · `backend` · `worker` · `db`.
- Caddy serves **one origin**: `/` → frontend, `/api/*` → backend (including `/api/v1/github/webhooks` and `/api/v1/releases/ci`). No CORS in production (ADR-0007).
- The worker needs outbound access to GitHub, the LLM provider and the TaskFlow health URLs. It needs no published port.
- Postgres uses a **named volume** and is **never exposed publicly** (internal network only).
- Pin production images by digest in `.env` (`BACKEND_IMAGE=ghcr.io/…@sha256:…`), so rolling back ReleaseGuard itself means changing the digest and running `docker compose up -d`.
- Give services healthchecks. The backend depends on db being healthy.

## VPS deploy
- Deploy sequence: `docker compose pull` → `docker compose run --rm backend alembic upgrade head` → `docker compose up -d` → `curl -fsS https://<host>/api/v1/healthz`.
- The env file on the VPS is readable only by the deploy user (`chmod 600`).
- TaskFlow environments run as separate Compose projects (`taskflow-dev`, `taskflow-staging`, `taskflow-prod`) if they share the VPS.

## Backups
- `infra/scripts/backup.sh`: nightly `pg_dump` (compressed), keeping 7 daily and 4 weekly copies, plus an **off-host** copy.
- `infra/scripts/restore.sh`: restore into a scratch container, then `alembic current` and a row-count check.
- A backup only counts once a restore has been tested. Do one restore test before v1.0.0.
