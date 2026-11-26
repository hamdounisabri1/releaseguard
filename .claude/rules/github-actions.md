---
paths:
  - ".github/**"
  - "backend/app/services/github*"
  - "backend/app/services/github/**"
  - "backend/app/api/v1/github*"
---

# GitHub Actions and GitHub App rules

## ReleaseGuard's own workflows (`.github/workflows/`)
- `ci.yml` (all PRs and pushes to `main`; SCRUM-33): jobs `backend` (Ruff, mypy, Alembic up/down/up + check, pytest with a Postgres service), `frontend` (ESLint, `tsc`, Prettier, Vitest, `next build`), `api-types` (generated `frontend/types/api.ts` matches the backend) and `gitleaks` (full history, checksum-verified binary). The job names are the required checks in `infra/github/ruleset-ci-releaseguard.json`: rename one only together with that file, then re-run `setup-repo.sh`.
- Triggers: `pull_request` and `push` only. Never `pull_request_target` or `workflow_run` for anything that runs repository code.
- Top-level `permissions: {}`; each job grants itself only what it needs (`contents: read` for CI). `actions/checkout` always with `persist-credentials: false`.
- Pin every action (first-party too) to a full commit SHA with the version in a trailing comment, choosing a release at least two weeks old. Pin tool versions (`UV_VERSION`, `GITLEAKS_VERSION`) in the workflow `env:`; download binaries only with checksum verification.
- No `${{ }}` expressions inside `run:` scripts: pass values through `env:` and use `"$VAR"`. Lint workflows with `uvx --from actionlint-py actionlint`.
- `release.yml` (main or tags): build images → **Trivy, fail on HIGH/CRITICAL** → push to GHCR → SSH deploy (`compose pull`, `alembic upgrade head`, `up -d`) → smoke test `/healthz`.
- `nightly.yml` (optional): full Playwright E2E plus a backup restore test.
- Pin third-party actions to a full commit SHA. Set the minimal `permissions:` per job. Secrets come only from GitHub encrypted secrets.

## TaskFlow workflows (separate `taskflow` repo)
| File | Trigger | Rule |
|---|---|---|
| `ci.yml` | push / PR | lint, test, Trivy, build, push to GHCR, capture the **digest**; on the default branch or a tag, register the release at `POST /api/v1/releases/ci` with an **OIDC token** (`permissions: id-token: write`, audience = `GITHUB_OIDC_AUDIENCE`). No shared secret |
| `deploy.yml` | `workflow_dispatch` **only** | Deploy one digest to one environment. Used for **every** environment and for rollback (ADR-0005). Never rebuilds source |

- `deploy.yml` inputs are exactly `release_id`, `image_digest`, `environment` (`type: choice`: `development`, `staging`, `production`) and `deployment_id`. Accept no free-form commands. Validate `image_digest` against `^sha256:[0-9a-f]{64}$` before use, and pass inputs through `env:`, never interpolated into `run:` scripts.
- `run-name: deploy-${{ inputs.deployment_id }}`. The job sets `environment: ${{ inputs.environment }}`, so GitHub environment protection (required reviewers, deployment-branch rule) and environment-scoped secrets apply to production as a second layer.
- Pull images by digest (`ghcr.io/<owner>/taskflow@sha256:…`) and fail if the pulled digest differs.
- There are no `staging-deploy.yml`, `production-deploy.yml` or `rollback.yml` files; don't add them.

## GitHub App (backend side)
- Use a separate development App (webhooks through a smee.io or cloudflared tunnel) and a production App.
- Local webhooks come through a **smee.io** channel ([GITHUB_APP_SETUP.md § Run the webhook tunnel](../../docs/GITHUB_APP_SETUP.md#run-the-webhook-tunnel)). smee re-serializes the JSON body, so a delivery containing `\uXXXX` or `\/` escapes or big numbers fails the HMAC check locally. Confirm through a cloudflared tunnel before debugging the endpoint, and never relax the signature check to suit a tunnel.
- Permissions: Actions read/write, Contents read, Metadata read. Nothing else.
- Events: `workflow_run` only. Handle them idempotently by delivery ID. Accept an event only if its repository id, workflow path and `run-name` match the deployment. Out-of-order events must not move a deployment backwards (the state machine rejects them; log and ignore).
- Only the **worker** calls GitHub. Dispatch with `return_run_details: true` and store the returned run id and URL; the reconcile sweep reads runs by id when a webhook is missing.
- Look up the current REST API (`workflow_dispatch`, runs, job logs) with **context7** or the GitHub docs before coding against it.
