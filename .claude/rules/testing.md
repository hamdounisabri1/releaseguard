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
| Integration | pytest + real Postgres | Repositories, transactions, approval → outbox → dispatch, webhook handling |
| API | pytest + `httpx.AsyncClient` | Every router: **allowed, denied and cross-workspace** cases |
| E2E | Playwright | The demo journey: login → request → approve → status update → rollback |
| Frontend unit | Vitest + Testing Library | Status badges, formatters, hooks |

Targets: 100% of state-machine transitions and permission rules; ≥ 80% of the services package.

## Required failure-path tests
Each needs at least one test: GitHub API timeout (retry, then consistent state) · invalid webhook signature · duplicate webhook delivery · out-of-order webhook event · rejected approval · expired or stale approval · self-approval blocked · concurrent production request returns 409 · unhealthy endpoint and threshold logic (one transient failure doesn't flip state) · rollback to an ineligible target · rollback workflow failure · AI provider unavailable (the deployment flow is unaffected) · prompt-injection fixture doesn't change the output schema.

## Conventions
- Each test runs inside a transaction that is rolled back. Build data with factories (`factory_boy` or plain builders), not shared fixtures that change state.
- **Never call real GitHub or AI APIs in tests or CI.** Mock GitHub with `respx` and use recorded fixtures. Use a fake `AIService` provider.
- Use real Postgres (CI service container), not SQLite. Advisory locks, `SKIP LOCKED` and constraints must actually run.
- Name tests after the behavior: `test_reviewer_from_other_workspace_cannot_approve`.
- To check UI behavior in a real browser during development, use the `webapp-testing` skill.
