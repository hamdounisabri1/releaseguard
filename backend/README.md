# backend/

FastAPI API and the shared code for the worker (Python 3.12, managed with `uv`).

## Run it

```bash
cd backend
uv sync                                   # creates .venv (uv downloads Python 3.12 if needed)
uv run uvicorn app.main:app --reload      # http://localhost:8000/docs
uv run pytest                             # tests
uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
```

Settings come from environment variables, falling back to the repository-root `.env` (copy `.env.example`). `SITE_ORIGIN` is required: without a valid value the app refuses to start. Variables: [guide §14.6](../docs/DEVELOPMENT_LIFECYCLE.md#146-local-development-environment).

## What exists (SCRUM-18)

| Module | Does |
|---|---|
| `app/main.py` | `create_app(settings)` factory; `app` is built at import, so bad settings fail fast |
| `app/core/config.py` | `Settings` (pydantic-settings): `ENV`, `SITE_ORIGIN`, `CORS_ORIGINS`, `LOG_LEVEL` |
| `app/core/errors.py` | `AppError` (+ `NotFoundError`, `ForbiddenError`, `ConflictError`, `UnauthorizedError`) and the handlers that render every error as `{"error": {"code", "message", "details"}}` |
| `app/core/security.py` | `OriginCheckMiddleware`: `POST/PUT/PATCH/DELETE` need an `Origin` (or `Referer`) equal to `SITE_ORIGIN` (plus `CORS_ORIGINS` when `ENV=local`), else 403 `csrf_origin_mismatch`. Only `POST /api/v1/github/webhooks` and `POST /api/v1/releases/ci` are exempt ([ADR-0007](../docs/adr/0007-server-side-sessions-and-csrf.md)) |
| `app/core/permissions.py` | `Role`, `Capability` and the role matrix from [guide §3.1](../docs/DEVELOPMENT_LIFECYCLE.md#31-permission-matrix) |
| `app/api/v1/router.py` | `api_router` (`/api/v1`); each area adds its own module and is included there |
| `app/schemas/errors.py` | `ErrorResponse` for OpenAPI |

Tests build their own app with `tests/conftest.py::build_app(**settings)`, which also mounts test-only routes.

## Layout as it grows

Per [guide §5.6](../docs/DEVELOPMENT_LIFECYCLE.md#56-repository-layout); each folder arrives with its first real code:

```text
app/
  main.py
  core/          config.py, security.py, permissions.py, errors.py
  api/v1/        thin routers
  models/        SQLAlchemy 2.0 models                       (SCRUM-19)
  schemas/       Pydantic request/response models, job payloads, policy
  services/      business rules, transitions, transactions, audit
  repositories/  data access only, always workspace-scoped
  worker/        job runner, job handlers, sweeps (run by ../worker)
migrations/      Alembic                                      (SCRUM-19)
tests/
pyproject.toml + uv.lock
```

Rules: [backend.md](../.claude/rules/backend.md) · [database.md](../.claude/rules/database.md) · [testing.md](../.claude/rules/testing.md) · [security.md](../.claude/rules/security.md)
