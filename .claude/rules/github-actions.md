---
paths:
  - ".github/**"
  - "backend/app/services/github*"
  - "backend/app/services/github/**"
  - "backend/app/api/v1/github*"
---

# GitHub Actions and GitHub App rules

## ReleaseGuard's own workflows (`.github/workflows/`)
- `ci.yml` (all PRs): Ruff, mypy, pytest with a Postgres service, ESLint, `tsc`, `next build`, gitleaks, Alembic check.
- `release.yml` (main or tags): build images → **Trivy, fail on HIGH/CRITICAL** → push to GHCR → SSH deploy (`compose pull`, `alembic upgrade head`, `up -d`) → smoke test `/healthz`.
- `nightly.yml` (optional): full Playwright E2E plus a backup restore test.
- Pin third-party actions to a full commit SHA. Set the minimal `permissions:` per job. Secrets come only from GitHub encrypted secrets.

## TaskFlow workflows (separate `taskflow` repo)
| File | Trigger | Rule |
|---|---|---|
| `ci.yml` | push / PR | lint, test, Trivy, build, push to GHCR, capture the **digest**, then send a signed callback to ReleaseGuard |
| `staging-deploy.yml` | `workflow_dispatch` | Deploy the given digest to staging |
| `production-deploy.yml` | `workflow_dispatch` **only** | Check the digest matches the release; the GitHub `production` environment protection is a second layer |
| `rollback.yml` | `workflow_dispatch` | Redeploy the given earlier digest; never rebuild old source |

- Dispatch inputs are exactly `release_id`, `image_digest`, `environment` and `deployment_id`. Accept no free-form commands.
- Every dispatched workflow sets `run-name: deploy-${{ inputs.deployment_id }}`. ReleaseGuard matches `workflow_run` events on that name.
- Pull images by digest: `ghcr.io/<owner>/taskflow@sha256:…`.

## GitHub App (backend side)
- Use a separate development App (webhooks through a smee.io or cloudflared tunnel) and a production App.
- Events: `workflow_run` and `workflow_job`. Handle them idempotently by delivery ID. Out-of-order events must not move a deployment backwards (rely on the state machine plus run IDs).
- Look up the current REST API (`workflow_dispatch`, runs, job logs) with **context7** or the GitHub docs before coding against it.
