# backend/

FastAPI API and the shared code for the worker (Python 3.12+, managed with `uv`).

> **Placeholder.** No code yet. Sprint 1 fills this in: SCRUM-18 (app skeleton) and SCRUM-19 (models + first Alembic migration).

Planned layout ([guide §5.6](../docs/DEVELOPMENT_LIFECYCLE.md#56-repository-layout)):

```text
app/
  main.py
  core/          config.py (pydantic-settings), security.py, permissions.py
  api/v1/        thin routers
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
