# worker/

Entrypoint and container definition for the **worker process**. The worker shares the backend code: its job runner, job handlers and sweeps live in [`backend/app/worker/`](../backend/README.md), not here.

> **Placeholder** for the production Dockerfile (SCRUM-93/94). The entrypoint exists: `cd backend && uv run python -m app.worker` (SCRUM-41), and the local compose stack runs it as the `worker` service.

The worker is the only process that makes outbound calls (GitHub, the LLM provider, health URLs). It runs one async loop over the Postgres `jobs` table (`FOR UPDATE SKIP LOCKED`) plus interval sweeps; see [ADR-0004](../docs/adr/0004-postgres-jobs-table.md).

Rules: [backend.md](../.claude/rules/backend.md) · [infra.md](../.claude/rules/infra.md)
