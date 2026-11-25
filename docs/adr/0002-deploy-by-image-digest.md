# 0002. Deploy by image digest

- **Status:** Accepted
- **Date:** 2026-11-23
- **Jira:** SCRUM-11

## Context
A release must mean exactly one artifact. Tags such as `v1.8.5` or `latest` are mutable labels in GHCR, so "approved v1.8.5" could later point to a different image ([guide §4.3](../DEVELOPMENT_LIFECYCLE.md#43-release-and-version-management), [§18](../DEVELOPMENT_LIFECYCLE.md#18-risks-and-mitigations)). Rollback must restore the exact bytes that were healthy before ([§11](../DEVELOPMENT_LIFECYCLE.md#11-rollback-design)).

## Decision
`releases.image_digest` (`sha256:…`, CHECK-constrained format) is the artifact identity. It is set at registration and never changes. Every dispatch passes `image_digest`; `deploy.yml` pulls `ghcr.io/<owner>/taskflow@sha256:…` and fails if the pulled digest differs. Docker itself refuses content that doesn't hash to the requested digest; the explicit check also catches a malformed or missing digest input. **On a mismatch nothing is deployed:** the run fails before the deploy step, the `workflow_run` webhook moves the deployment to Failed (`run_failed`), and the environment's current deployment is unchanged. Rollback redeploys an earlier release's digest; it never rebuilds old source.

## Alternatives considered

| Option | Complexity | Safety | Notes |
|---|---|---|---|
| **Digest everywhere** (chosen) | Low | High | Content-addressed; can't be repointed |
| Immutable tags (registry policy) | Low | Medium | Depends on registry settings that can be changed; GHCR has no enforced immutability |
| Rebuild from commit SHA | High | Low | Non-reproducible builds; slow during an incident |

## Consequences
- Easier: "what is running" is a fact; rollback is just "deploy an older digest".
- Easier: the approval binds to bytes, not to a name.
- Harder: old images must stay in GHCR. Don't enable retention that deletes digests referenced by a release with a succeeded deployment.
- Follow-up: the UI shows version + short digest together everywhere.
