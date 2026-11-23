# Security rules

ReleaseGuard has authority over production releases. These rules apply to all code.

## Authorization
- Enforce permissions in the **backend** (FastAPI dependency plus the service layer). Hiding a button in the UI is not authorization.
- Every query is filtered by the caller's `workspace_id`. Resources in another workspace return **404** (never confirm they exist). Use **403** for a role failure inside the caller's own workspace.
- Role matrix (guide §3.1): only **Admin** manages members, the GitHub integration and environment and approval policy. **Admin/Reviewer** approve. **Admin/Developer** request deployments and rollbacks. **Viewer** is read-only.
- Self-approval is blocked when the workspace setting `block_self_approval` is on. A reviewer can't decide twice on the same request. Stale or expired requests can't be decided.

## Authentication and sessions
- Hash passwords with argon2. Sessions are server-side in Postgres, sent as an `HttpOnly`, `Secure`, `SameSite` cookie. No JWT in `localStorage`.
- Session secrets, GitHub App private key, webhook secret and AI key are **backend/worker only**. Never prefix them `NEXT_PUBLIC_*`. The only public variable is `NEXT_PUBLIC_API_BASE_URL`.

## GitHub and webhooks
- Validate `X-Hub-Signature-256` with HMAC-SHA256 and `hmac.compare_digest` **before** parsing the body. Reject a missing or invalid signature with 401.
- De-duplicate by `X-GitHub-Delivery` (`webhook_deliveries.delivery_id` unique). A duplicate returns 200 and does nothing.
- Use short-lived installation tokens, cached and refreshed before they expire. Never use personal access tokens in app code.
- Request only the GitHub App permissions the workflows need (Actions RW, Contents R, Metadata R, Deployments RW).

## Deployment safety
- Never run shell commands to deploy. The backend only sends `workflow_dispatch` with the fixed inputs `release_id`, `image_digest`, `environment` and `deployment_id`. User input and AI output must never become commands, repositories, refs or targets.
- Deploy by **digest** (`sha256:…`), never by a mutable tag. Workflows check that the digest matches the approved release.
- Check that each incoming workflow run matches the deployment's expected repo, workflow and `run-name`.

## Data handling
- Logs never contain secrets, tokens, cookies or full webhook payloads. Redact before logging.
- Anything sent to the AI provider goes through the sanitizer first (see `ai.md`).
- Commit no secrets: use `.env` (git-ignored), GitHub encrypted secrets, and a `chmod 600` env file on the VPS. Secret scanning: the `.claude/hooks/pre_bash.py` hook runs gitleaks on `git commit` **once gitleaks is installed** (it isn't yet; `pre-commit` with gitleaks is a Sprint 0 task). Until then, review `git diff --staged` for secrets before every commit.
- Never read `.env`, `*.pem` or `*.key` files (they are denied in `.claude/settings.json` and blocked in the Bash hook). Edit `.env.example` instead.

## Review
- Run `/security-review` on any change that touches auth, RBAC, sessions, webhooks, approvals, GitHub tokens or the AI sanitizer.
