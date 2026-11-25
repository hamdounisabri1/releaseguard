# backend/

FastAPI API and the shared code for the worker (Python 3.12, managed with `uv`).

## Run it

```bash
cd backend
uv sync                                   # creates .venv (uv downloads Python 3.12 if needed)
uv run uvicorn app.main:app --reload      # http://localhost:8000/docs
uv run alembic upgrade head               # migrate DATABASE_URL
uv run pytest                             # tests (Postgres at TEST_DATABASE_URL)
uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
```

Settings come from environment variables, falling back to the repository-root `.env` (copy `.env.example`). `SITE_ORIGIN` and `DATABASE_URL` are required: without a valid value the app refuses to start. `ENV` defaults to `production` (fails closed: https only, `CORS_ORIGINS` ignored), so local development sets `ENV=local`. Variables: [guide §14.6](../docs/DEVELOPMENT_LIFECYCLE.md#146-local-development-environment).

## What exists (SCRUM-18, SCRUM-19)

| Module | Does |
|---|---|
| `app/main.py` | `create_app(settings)` factory; `app` is built at import, so bad settings fail fast |
| `app/core/config.py` | `Settings` (pydantic-settings): `ENV`, `SITE_ORIGIN`, `CORS_ORIGINS`, `LOG_LEVEL` |
| `app/core/errors.py` | `AppError` (+ `NotFoundError`, `ForbiddenError`, `ConflictError`, `UnauthorizedError`) and the handlers that render every error as `{"error": {"code", "message", "details"}}` |
| `app/core/security.py` | `OriginCheckMiddleware`: `POST/PUT/PATCH/DELETE` need an `Origin` (or `Referer`) equal to `SITE_ORIGIN` (plus `CORS_ORIGINS` when `ENV=local`), else 403 `csrf_origin_mismatch`. Only `POST /api/v1/github/webhooks` and `POST /api/v1/releases/ci` are exempt ([ADR-0007](../docs/adr/0007-server-side-sessions-and-csrf.md)) |
| `app/core/permissions.py` | `Role`, `Capability` and the role matrix from [guide §3.1](../docs/DEVELOPMENT_LIFECYCLE.md#31-permission-matrix) |
| `app/api/v1/router.py` | `api_router` (`/api/v1`); each area adds its own module and is included there |
| `app/schemas/errors.py` | `ErrorResponse` for OpenAPI |
| `app/core/logging.py`, `app/core/request_id.py` | structlog JSON logging with redaction; `RequestIdMiddleware` (`X-Request-ID` in and out, one access line per request) |
| `app/api/health.py` | `GET /healthz` (liveness) and `GET /readyz` (`SELECT 1`; 503 `not_ready` when the database is unreachable), at the root for container health checks |
| `app/services/audit.py` | `record_audit(db, actor, action, target, details)`: one `audit_logs` row in the caller's transaction, with redacted details and the request id |
| `app/api/v1/auth.py`, `app/services/auth_service.py` | `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`; argon2id (`app/core/passwords.py`), server-side sessions (SHA-256 of the cookie token, 12 h idle, 7 days absolute, rotated on login); `CurrentPrincipal` dependency |
| `app/db/` | `Base` with the constraint naming convention and `check_in()` (CHECK from an enum); engine and session factory (sync SQLAlchemy 2.0 + psycopg 3) |
| `app/models/` | `users`, `workspaces`, `workspace_members`, `sessions`, `applications`, `environments`, `audit_logs`; enums mirrored by CHECK constraints; composite FKs keep children in their workspace |
| `migrations/` | Alembic. `0001` also creates `forbid_history_mutation()` and the `audit_logs` append-only triggers (UPDATE, DELETE, TRUNCATE) |

Tests build their own app with `tests/conftest.py::build_app(**settings)`, which also mounts test-only routes. Database tests use the `db` fixture (a session in a transaction that is rolled back; services' `commit()` becomes a savepoint) and `db_client` (requests share that session); build data with `tests/factories.py`.

## Layout as it grows

Per [guide §5.6](../docs/DEVELOPMENT_LIFECYCLE.md#56-repository-layout); each folder arrives with its first real code:

```text
app/
  main.py
  core/          config.py, security.py, permissions.py, errors.py
  api/v1/        thin routers
  db/            Base, naming convention, engine
  models/        SQLAlchemy 2.0 models
  schemas/       Pydantic request/response models, job payloads, policy
  services/      business rules, transitions, transactions, audit
  repositories/  data access only, always workspace-scoped
  worker/        job runner, job handlers, sweeps (run by ../worker)
migrations/      Alembic
tests/
pyproject.toml + uv.lock
```

Rules: [backend.md](../.claude/rules/backend.md) · [database.md](../.claude/rules/database.md) · [testing.md](../.claude/rules/testing.md) · [security.md](../.claude/rules/security.md)
