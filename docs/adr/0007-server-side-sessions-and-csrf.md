# 0007. Server-side sessions, same-origin API and CSRF defense

- **Status:** Accepted
- **Date:** 2026-11-23
- **Jira:** none (architecture review, finding 11)

## Context
The guide chose server-side sessions in Postgres with an `HttpOnly`, `Secure`, `SameSite` cookie (docs/DEVELOPMENT_LIFECYCLE.md §6.2, `security.md`) but said nothing about CSRF, which every cookie-authenticated API must handle. The frontend and API were also drawn as separate origins, which brings CORS configuration and cross-site cookie problems.

## Decision
- **Sessions:** random 256-bit session id; the cookie holds only the id; the `sessions` table stores a hash of it, `user_id`, `workspace_id`, `expires_at`, `last_seen_at`. Idle timeout 12 h, absolute 7 days, rotated on login, deleted on logout.
- **Same origin:** Caddy serves the frontend at `/` and proxies `/api` to the backend. The browser only ever talks to one origin. `CORS_ORIGINS` is used only in local development.
- **CSRF:** cookie `SameSite=Lax`, `Secure`, `HttpOnly`; plus a middleware that, for every unsafe method (`POST/PUT/PATCH/DELETE`), requires the `Origin` (or, if missing, `Referer`) to match the configured site origin, and rejects with 403 otherwise. `POST /github/webhooks` and `POST /releases/ci` are exempt because they don't use cookies (HMAC and OIDC auth respectively).
- Passwords: argon2id.

## Alternatives considered

| Option | Complexity | Risk |
|---|---|---|
| **Sessions + same origin + Origin check** (chosen) | Low | Low |
| JWT in `localStorage` | Low | Token theft through XSS; no server-side revocation |
| Double-submit CSRF token | Medium | Fine, but redundant with `SameSite` + Origin check for a same-origin app |

## Consequences
- Easier: no CORS in production; logout and member removal revoke sessions immediately.
- Harder: local dev runs frontend and API on different ports, so the Origin check must allow `CORS_ORIGINS` in `ENV=local`.
- Follow-up: API tests for a missing or foreign `Origin` on a state-changing request.
