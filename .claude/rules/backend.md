---
paths:
  - "backend/**"
  - "worker/**"
---

# Backend rules (FastAPI, Python 3.12+)

## Layout and layering
- `app/core` (config via `pydantic-settings`, security, permissions) · `app/api/v1` (routers) · `app/schemas` (Pydantic) · `app/services` · `app/repositories` · `app/models` · `app/worker`.
- **Routes are thin:** validate with Pydantic, call **one** service function, return a response schema. No SQL and no business rules in routes.
- **Services own the rules:** permission checks, state transitions, transactions, job enqueueing, audit entries.
- **The API process never makes outbound network calls** (GitHub, LLM, health URLs). It writes state plus a `jobs` row in one transaction; the worker does the I/O (ADR-0001).
- **Repositories only do data access.** Every query takes `workspace_id` (or joins to it). Repositories never commit: the **service layer owns the transaction boundary**.
- **Database access is synchronous** SQLAlchemy 2.0 + psycopg 3 (async psycopg can't run on Windows' default event loop; sync keeps Alembic and test rollback simple). Routes and dependencies that touch the DB are plain `def` (FastAPI runs them in its threadpool); take the session with `DbSession` from `app/api/deps.py`. Worker code calls DB functions through `asyncio.to_thread`.
- Use the Pydantic v2 and SQLAlchemy 2.0 APIs. Check current docs with context7 rather than relying on memory.
- The `fastapi-templates` skill is fine for dependencies, error handling and async patterns, but **not** for auth or layout: it teaches JWT/OAuth2 and an `endpoints/` folder. Auth here is server-side sessions (`security.md`) and the layout is the one above.

## Deployment state machine (guide §8, ADR-0003)
- Only `deployment_service.transition(deployment, to_status, actor, source, details)` changes `deployments.status`. It checks `ALLOWED_TRANSITIONS`, sets timestamps, writes a `deployment_events` row and an audit entry, enqueues the follow-up job, and runs inside the caller's transaction.
- `ALLOWED_TRANSITIONS`: `awaiting_approval → queued | rejected | expired | cancelled` · `queued → deploying | failed | cancelled` · `deploying → verifying | failed` · `verifying → succeeded | unhealthy`. Nothing else.
- A deployment is **created** in `awaiting_approval` or `queued`, decided by the environment policy in the same transaction. There is no `pending` state.
- Follow-up jobs from `transition()`: `queued` → dispatch job; `verifying` → verification job and `environments.current_deployment_id = deployment.id`; `failed`/`unhealthy` → AI analysis job (if AI is enabled).
- An invalid transition raises a domain error, which maps to **409**. Terminal states never change. A retry or rollback creates a **new** deployment.
- Cancel is allowed only in `awaiting_approval` and `queued`.

## Approvals, concurrency and dispatch
- Request preconditions: the release has a digest and a **Succeeded deployment in the policy's `promote_from` environment**; the requester has the role. Store `policy_snapshot`, `approval_expires_at` and `base_deployment_id` on the deployment.
- Decide = one transaction: insert into `approval_decisions` → if `min_approvals` approvals are reached, transition to `queued` (which inserts the dispatch job). Refuse when expired, **stale** (`base_deployment_id ≠ environments.current_deployment_id`), already decided by this reviewer, or self-approved under `block_self_approval`.
- **Concurrency is a database rule:** the partial unique index on `deployments(environment_id)` for active statuses. Map its `IntegrityError` to 409 (`environment_busy`). Don't add locks or in-flight checks around it.
- `POST /deployments` honors the `Idempotency-Key` header (unique per workspace on `deployments.idempotency_key`; a replay returns the original deployment).
- The dispatch job calls the GitHub dispatch API with `return_run_details`, stores `workflow_run_id` and URL, and moves `queued → deploying`. After `max_attempts` its failure hook moves `queued → failed` (`dispatch_failed`).

## API conventions
- Prefix `/api/v1`, JSON only, paginated lists: `page` (from 1) and `page_size` (≤ 100) in, `Page[T]` (`app/schemas/common.py`: `items`, `total`, `page`, `page_size`) out.
- Request bodies use `extra="forbid"`, so unknown fields (or ones not editable yet) are a 422. PATCH bodies change only the fields sent (`model_dump(exclude_unset=True)`); audit entries record `{"changes": {field: {"from", "to"}}}` and are skipped when nothing changed.
- Map a unique-constraint `IntegrityError` to a named 409 by catching it around a `db.begin_nested()` savepoint and matching the constraint name; re-raise anything else.
- Error shape: `{"error": {"code", "message", "details"}}`. Use 403 for a role failure, 404 for another workspace's resource, 409 for an invalid state or lock conflict, 422 for validation.
- A 422 returns each error's `msg` as is, so **custom Pydantic validators never put the submitted value in their message** (`raise ValueError("must be a bare origin")`, not `f"{value} is invalid"`): it may be a password or token.
- `/healthz` (liveness) and `/readyz` (DB reachable) are public.
- Every state-changing service calls `record_audit(db, actor, action, target, details)` (`app/services/audit.py`) **before** it commits, so the row shares the change's transaction. `actor` is `Actor.user(workspace_id, user_id)` or `Actor.system(workspace_id)`; `action` is `<area>.<verb>` (`application.created`); `target` is `AuditTarget(type, id)`. Details are redacted like log fields; record what changed (field names, old/new values), never secrets.

## Integrations
- Make external HTTP calls with `httpx` (explicit timeouts) wrapped in `tenacity` bounded retries. Never call GitHub or AI inside a request that holds a DB transaction open.
- GitHub App: sign the JWT with `PyJWT`, exchange it for an installation token, and cache the token until shortly before expiry. Only worker code calls GitHub.
- CI release registration (`POST /releases/ci`): verify the OIDC JWT with `PyJWKClient` (cached JWKS), check `iss`, `aud`, `exp`, then bind `repository_id`, `workflow_ref` and `sha` to the application (ADR-0006).

## Worker (ADR-0004)
- Same codebase, its own entrypoint (`python -m app.worker`). One async loop: claim due rows from `jobs` with `SELECT … FOR UPDATE SKIP LOCKED`, set `locked_until`, run the handler for its `kind`, then mark `done` or reschedule with exponential backoff; `dead` after `max_attempts`. No APScheduler.
- Jobs are idempotent (`dedupe_key`), carry `workspace_id`, and log start, finish, retry and failure. Payloads are Pydantic models shared with the API (`app/schemas/jobs.py`). Enqueue with `app.services.jobs.enqueue` inside the state change's transaction (it never commits).
- **Code:** `app/worker/runner.py` (`Worker`, `JobSpec(handler, on_dead)`, `Sweep`), handlers registered in `app/worker/registry.py`, claim queries in `app/repositories/job_queue.py` (the one unscoped tenant repository besides `identity`). A worker claims **only registered kinds**, so a kind without a handler waits in `pending`. A crashed attempt is re-run once its lease (`locked_until`) passes; on the last attempt it goes `dead` (`LeaseExpired`). Writes after the claim are conditional on the attempt number, so a stale attempt can't overwrite a newer one.
- `last_error` and log lines keep the exception **class only** (`error_name`), never its message: it can carry a token or a URL with credentials.
- Sweeps in the same loop: `expire_approvals` (60 s), `reconcile_runs` (60 s; `run_not_found` after `DISPATCH_TIMEOUT_SECONDS`), `health_checks_due` (5 s, by `environments.next_check_at`), `retention` (daily).
- Never hold a DB transaction open across an HTTP call: read → commit → call → new transaction to write the result.
- Health: verification needs `verify_successes` consecutive passes within `verify_timeout_seconds`; `failure_threshold` consecutive failures or the timeout → `unhealthy`. Scheduled checks change only `environments.health_status`, and only after `failure_threshold` **consecutive** failures. Every health URL goes through the SSRF guard (`security.md`).

## Logging
- `structlog` JSON (`app/core/logging.py`) with `request_id`, `workspace_id`, `user_id`, `deployment_id` and `workflow_run_id` where known: bind them with `structlog.contextvars.bind_contextvars`, and get loggers with `app.core.logging.get_logger`. Stdlib loggers (uvicorn, SQLAlchemy) go through the same JSON formatter.
- `RequestIdMiddleware` (outermost) reuses a plain incoming `X-Request-ID` (`[A-Za-z0-9._-]{1,64}`) or makes one, echoes it on every response and writes one access line per request: method, path (**never the query string**), status, duration.
- Values under sensitive keys (`password`, `secret`, `token`, `cookie`, `authorization`, `api_key`, `private_key`, `credential`) are redacted by a processor, nested ones too. Still never log request bodies, headers or exception text that can carry a connection URL.
- Store timestamps as UTC (`timestamptz`).
