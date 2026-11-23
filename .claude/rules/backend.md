---
paths:
  - "backend/**"
  - "worker/**"
---

# Backend rules (FastAPI, Python 3.12+)

## Layout and layering
- `app/core` (config via `pydantic-settings`, security, permissions) · `app/api/v1` (routers) · `app/schemas` (Pydantic) · `app/services` · `app/repositories` · `app/models` · `app/worker`.
- **Routes are thin:** validate with Pydantic, call **one** service function, return a response schema. No SQL and no business rules in routes.
- **Services own the rules:** permission checks, state transitions, transactions, GitHub and AI calls, audit entries.
- **Repositories only do data access.** Every query takes `workspace_id` (or joins to it). Repositories never commit: the **service layer owns the transaction boundary**.
- Use the Pydantic v2 and SQLAlchemy 2.0 APIs. Check current docs with context7 rather than relying on memory.
- The `fastapi-templates` skill is fine for dependencies, error handling and async patterns, but **not** for auth or layout: it teaches JWT/OAuth2 and an `endpoints/` folder. Auth here is server-side sessions (`security.md`) and the layout is the one above.

## Deployment state machine
- Only `deployment_service.transition(deployment, to_status, actor, source)` changes `deployments.status`. It checks `ALLOWED_TRANSITIONS`, writes a `deployment_events` row and an audit entry, and runs inside the caller's transaction.
- An invalid transition raises a domain error, which maps to **409**.
- Terminal states (Succeeded, Rejected, Failed, Unhealthy, Cancelled, Expired) never change. A retry or rollback creates a **new** deployment.
- Production can't reach Deploying without a recorded approval.

## Approvals and dispatch
- Approve = one transaction: insert decision → transition to Approved → insert an outbox job. The worker dispatches the workflow from the outbox with `tenacity` backoff and stores `workflow_run_id` and URL.
- Preconditions for a production request: the release exists, has a digest, and has a **Succeeded staging deployment** of the same release.
- Take `pg_advisory_xact_lock(hash(environment_id))` and check for in-flight deployments. A conflict returns 409.
- `POST /deployments` honors the `Idempotency-Key` header.

## API conventions
- Prefix `/api/v1`, JSON only, paginated lists.
- Error shape: `{"error": {"code", "message", "details"}}`. Use 403 for a role failure, 404 for another workspace's resource, 409 for an invalid state or lock conflict, 422 for validation.
- `/healthz` (liveness) and `/readyz` (DB reachable) are public.
- Every state-changing service calls `record_audit(actor, action, target, details)`.

## Integrations
- Make external HTTP calls with `httpx` (explicit timeouts) wrapped in `tenacity` bounded retries. Never call GitHub or AI inside a request that holds a DB transaction open.
- GitHub App: sign the JWT with `PyJWT`, exchange it for an installation token, and cache the token until shortly before expiry.

## Worker
- Same codebase, its own entrypoint. APScheduler plus a Postgres job table claimed with `SELECT … FOR UPDATE SKIP LOCKED`.
- Jobs are idempotent and retryable, and log start, finish, retry and failure.
- Health: an environment turns Unhealthy only after `failure_threshold` **consecutive** failures. Link each failure to the deployment that last changed the environment.

## Logging
- `structlog` JSON with `request_id`, `workspace_id`, `user_id`, `deployment_id` and `workflow_run_id` where known. Middleware propagates `X-Request-ID`.
- Store timestamps as UTC (`timestamptz`).
