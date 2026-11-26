---
paths:
  - "backend/tests/**"
  - "frontend/**/*.test.ts"
  - "frontend/**/*.test.tsx"
  - "frontend/**/*.spec.ts"
  - "frontend/**/*.spec.tsx"
  - "frontend/e2e/**"
  - "**/playwright.config.*"
  - "**/conftest.py"
---

# Testing rules

## Layers (guide §14.9)
| Layer | Tool | Must cover |
|---|---|---|
| Unit | pytest | **Every** allowed state transition plus representative forbidden ones; every permission rule; policies; log sanitizer; AI response schema |
| Integration | pytest + real Postgres | Repositories, constraints (single active deployment, append-only triggers), approval → job → dispatch, job runner and sweeps, webhook handling, OIDC verification with a local JWKS |
| API | pytest + `httpx.AsyncClient` | Every router: **allowed, denied and cross-workspace** cases; a state-changing request with a foreign `Origin` returns 403 |
| E2E | Playwright | The demo journey: login → request → approve → status update → rollback |
| Frontend unit | Vitest + Testing Library | Status badges, formatters, hooks |

Targets: 100% of state-machine transitions and permission rules; ≥ 80% of the services package.

## Required failure-path tests
Each needs at least one test: GitHub dispatch timeout (retried, then consistent state) · dispatch retries exhausted → `failed` (`dispatch_failed`) · run never appears → `failed` (`run_not_found`) · lost webhook recovered by the reconcile sweep · invalid webhook signature · duplicate webhook delivery · out-of-order webhook event · invalid, expired or wrong-repository OIDC token · rejected approval · expired approval · stale approval (environment changed) · second decision by the same reviewer · self-approval blocked · a second active deployment in one environment returns 409 (from the index) · `Idempotency-Key` replay returns the same deployment · `UPDATE`/`DELETE` on `audit_logs` refused · unhealthy endpoint and threshold logic (one transient failure doesn't flip state) · verification timeout · SSRF-blocked health URL · rollback to an ineligible target · rollback workflow failure · AI provider unavailable (the deployment flow is unaffected) · prompt-injection fixture doesn't change the output schema.

## Route-wide security sweeps (`backend/tests/test_security.py`)
- The sweeps read every `/api/v1` route from the app's OpenAPI document (FastAPI 0.165 keeps included routers lazy, so `app.routes` doesn't list them) and check each one: a foreign `Origin` → 403 on every write, no session → 401 everywhere, a Viewer → 403 on every write, another workspace's id → 404 on every route with a path parameter, and **no audit row or changed data** in each case.
- A new route is covered automatically. Its write body goes in `BODIES`, a new path parameter needs a resource in `_ids()`, and a deliberate exception (a public route, a cookie-less HMAC/OIDC endpoint) goes in `PUBLIC` or `CSRF_EXEMPT` with a reason. Never add `include_in_schema=False` to a real route: it would drop out of the sweep.

## Conventions
- Each test runs inside a transaction that is rolled back. Build data with factories (`factory_boy` or plain builders), not shared fixtures that change state.
- **Never call real GitHub or AI APIs in tests or CI.** Mock GitHub with `respx` and use recorded fixtures. Use a fake `AIService` provider.
- Use real Postgres (CI service container), not SQLite. Partial unique indexes, triggers, `SKIP LOCKED` and constraints must actually run.
- Test the worker by calling the job runner and sweeps directly (one iteration at a time) with a frozen clock; don't sleep in tests.
- Name tests after the behavior: `test_reviewer_from_other_workspace_cannot_approve`.
- To check UI behavior in a real browser during development, use the `webapp-testing` skill.
