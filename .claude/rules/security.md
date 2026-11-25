# Security rules

ReleaseGuard has authority over production releases. These rules apply to all code.

## Authorization
- Enforce permissions in the **backend** (FastAPI dependency plus the service layer). Hiding a button in the UI is not authorization.
- Every query is filtered by the caller's `workspace_id`. Resources in another workspace return **404** (never confirm they exist). Use **403** for a role failure inside the caller's own workspace.
- **How:** routes declare `Depends(require_capability(Capability.X))` (or `require_role(...)`, both in `app/api/deps.py`, derived from the one matrix in `app/core/permissions.py`); services repeat the check with `app.services.authz.ensure_can` and turn a scoped miss into 404 with `found()`. Every public function in a tenant repository takes `(db, workspace_id, …)`; `tests/test_scoping.py` fails otherwise. Only `app/repositories/identity.py` (login and session lookups) is exempt.
- Role matrix (guide §3.1): only **Admin** manages members, the GitHub integration and environment and approval policy. **Admin/Reviewer** approve. **Admin/Developer** request deployments and rollbacks. **Viewer** is read-only.
- Self-approval is blocked when the workspace setting `block_self_approval` is on. A reviewer can't decide twice on the same request. Stale or expired requests can't be decided.

## Authentication and sessions
- Hash passwords with argon2id. Sessions are server-side in Postgres (the `rg_session` cookie holds a random 256-bit token; the table stores only its SHA-256, so no `SESSION_SECRET` is needed; idle 12 h, absolute 7 days, rotated on login), sent as an `HttpOnly`, `Secure`, `SameSite=Lax` cookie. No JWT in `localStorage` (ADR-0007). Code: `app/services/auth_service.py`.
- Login failures (unknown email, wrong password, disabled user, no active membership) all return the **same** 401 `invalid_credentials`, and an unknown email still pays for one argon2 verification. An expired session returns 401 `session_expired` and its row is deleted. Protected routes take `CurrentPrincipal` from `app/api/deps.py`.
- **CSRF:** the browser uses one origin (Caddy serves `/` and `/api`). Every unsafe method (`POST/PUT/PATCH/DELETE`) must carry an `Origin` (or `Referer`) equal to `SITE_ORIGIN`, otherwise 403. Only `POST /github/webhooks` (HMAC) and `POST /releases/ci` (OIDC) are exempt, because they don't use cookies.
- Session secrets, GitHub App private key, webhook secret and AI key are **backend/worker only**. Never prefix them `NEXT_PUBLIC_*`. The only public variable is `NEXT_PUBLIC_API_BASE_URL`.

## GitHub and webhooks
- Validate `X-Hub-Signature-256` with HMAC-SHA256 and `hmac.compare_digest` **before** parsing the body. Reject a missing or invalid signature with 401.
- De-duplicate by `X-GitHub-Delivery` (`webhook_deliveries.delivery_id` unique). A duplicate returns 200 and does nothing.
- Use short-lived installation tokens, cached and refreshed before they expire. Never use personal access tokens in app code.
- Request only the GitHub App permissions the workflows need: Actions RW, Contents R, Metadata R. Subscribe to `workflow_run` only.
- **CI release registration** uses GitHub Actions OIDC, not a shared secret. Verify the JWT signature against GitHub's JWKS plus `iss`, `aud` (`GITHUB_OIDC_AUDIENCE`) and `exp`, then require `repository_id` = the application's repository id, `workflow_ref` = its CI workflow on the default branch or a tag, and `sha` = the body's commit SHA. Any mismatch → 401/403 and nothing is written (ADR-0006).

## Deployment safety
- Never run shell commands to deploy. The backend only sends `workflow_dispatch` with the fixed inputs `release_id`, `image_digest`, `environment` and `deployment_id`. User input and AI output must never become commands, repositories, refs or targets.
- Deploy by **digest** (`sha256:…`), never by a mutable tag. Workflows check that the digest matches the approved release.
- Check that each incoming workflow run matches the deployment's expected repo, workflow and `run-name`.
- At most one active deployment per environment: rely on the partial unique index, never on application-level checks alone.
- **SSRF guard for health URLs:** `http`/`https` only; resolve the host and refuse private, loopback, link-local and multicast addresses (unless `HEALTH_CHECK_ALLOW_PRIVATE=true`, local dev only); no redirects; cap the response size; validate on save **and** before every request.
- `audit_logs` and `deployment_events` are append-only (DB trigger). Never write code that updates or deletes them.

## Data handling
- Logs never contain secrets, tokens, cookies or full webhook payloads. Redact before logging.
- Database errors: the engine uses `hide_parameters=True`, and the 500 handler logs a `DBAPIError` as its driver class, SQLSTATE and stack frames only, **never its message** (Postgres echoes row values there, e.g. a unique violation's `DETAIL: Key (token_hash)=…`).
- `repository_id` binds CI OIDC tokens to an application (ADR-0006): changing `repository_owner`/`repository_name` must restate `repository_id` (422 `repository_id_required` otherwise).
- Anything sent to the AI provider goes through the sanitizer first (see `ai.md`).
- Commit no secrets: use `.env` (git-ignored), GitHub encrypted secrets, and a `chmod 600` env file on the VPS. Secret scanning: **`pre-commit` runs gitleaks on the staged changes of every commit** (`.pre-commit-config.yaml`; run `pre-commit install` once per clone) and blocks on findings. The `.claude/hooks/pre_bash.py` hook also runs it on Claude's `git commit` when a `gitleaks` binary is on `PATH`. Never bypass a finding with `--no-verify`: remove the secret, and rotate it if it was ever pushed. Still review `git diff --staged` before committing.
- Never read `.env`, `*.pem` or `*.key` files (they are denied in `.claude/settings.json` and blocked in the Bash hook). Edit `.env.example` instead.

## Review
- Run `/security-review` on any change that touches auth, RBAC, sessions, webhooks, approvals, GitHub tokens or the AI sanitizer.
