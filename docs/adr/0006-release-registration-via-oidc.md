# 0006. Register releases from CI with GitHub Actions OIDC

- **Status:** Accepted
- **Date:** 2026-11-23
- **Jira:** none (architecture review, finding 8)

## Context
TaskFlow's `ci.yml` must tell ReleaseGuard that a new image exists (version, commit SHA, image digest, run id). The original design called this a "signed callback" without saying which secret signs it or how ReleaseGuard knows the call came from the right repository and workflow (docs/DEVELOPMENT_LIFECYCLE.md §10.1 before this review). The plan also mentioned registering from `workflow_run` events, which would be a second, competing path.

## Decision
- `ci.yml` requests an OIDC token (`permissions: id-token: write`) with audience `GITHUB_OIDC_AUDIENCE` and calls **`POST /api/v1/releases/ci`** with `Authorization: Bearer <token>` and a JSON body (`version`, `commit_sha`, `branch`, `image_repository`, `image_tag`, `image_digest`, `workflow_run_id`).
- The backend verifies the JWT signature against GitHub's JWKS (`https://token.actions.githubusercontent.com/.well-known/jwks`, cached), `iss`, `aud`, `exp`, and then binds the claims to the application: `repository_id` equals the application's stored repository id, `workflow_ref` matches `<owner>/<repo>/.github/workflows/ci.yml@refs/heads/<default_branch>` (or a tag ref), and the body's `commit_sha` equals the `sha` claim.
- The release's `created_by` is the system actor; the OIDC `actor` and `run_id` go into the audit entry.
- Manual `POST /releases` (Admin/Developer, session auth) stays as a fallback with `source = 'manual'`. Promotion rules still apply to it.
- No release registration from webhooks.

## Alternatives considered

| Option | Complexity | Secret to manage | Identity binding |
|---|---|---|---|
| **OIDC** (chosen) | Medium (JWKS cache) | None | Strong: repo id + workflow + sha |
| HMAC with a shared secret in GitHub secrets | Low | Yes, per app | Weak: anyone with the secret can register any digest |
| Derive from `workflow_run` + API lookups | High | None | Good, but the digest isn't in the event; extra API calls and parsing |

## Consequences
- Easier: nothing to rotate; a leaked token is short-lived and tied to one run.
- Harder: tests need a local JWKS and signed fixture tokens (no real GitHub in CI).
- Note: repositories created after 15 Jul 2026 use an immutable `sub` format that includes ids. Bind on `repository_id`, not on `sub` string matching.
- Source: [GitHub OIDC token claims](https://docs.github.com/en/actions/reference/security/oidc).
