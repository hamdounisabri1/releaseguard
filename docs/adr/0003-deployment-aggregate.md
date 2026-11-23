# 0003. The deployment is the aggregate: states, approvals and rollbacks live on it

- **Status:** Accepted
- **Date:** 2026-11-23
- **Jira:** none (architecture review, [ARCHITECTURE_REVIEW.md](../ARCHITECTURE_REVIEW.md) findings 1–6, 10, 14)

## Context
The original model (docs/DEVELOPMENT_LIFECYCLE.md §7–§8 before this review) had:
- an `approval_requests` table whose `status` duplicated the deployment's `AwaitingApproval`;
- a `rollback_events` table that repeated `release_id`, `requested_by` and the source deployment;
- a `Pending` state nobody could observe and an `Approved` state that read oddly for auto-deployed environments;
- no exit when dispatch fails permanently, and no timeout for `Deploying`;
- concurrency enforced by `pg_advisory_xact_lock` **plus** a hand-written in-flight check on each code path;
- no column for "what is running in this environment";
- `workspace_id` only on top-level tables.

## Decision
1. **States:** `awaiting_approval`, `queued`, `deploying`, `verifying` (active) and `succeeded`, `failed`, `unhealthy`, `rejected`, `expired`, `cancelled` (terminal). A deployment is created in `awaiting_approval` or `queued`, decided by the environment policy in the same transaction.

   | From | To |
   |---|---|
   | `awaiting_approval` | `queued`, `rejected`, `expired`, `cancelled` |
   | `queued` | `deploying`, `failed` (dispatch exhausted), `cancelled` |
   | `deploying` | `verifying`, `failed` (run failed or never appeared) |
   | `verifying` | `succeeded`, `unhealthy` |

2. **Single active deployment per environment** is a database rule: `CREATE UNIQUE INDEX … ON deployments (environment_id) WHERE status IN ('queued','deploying','verifying')`. A violation maps to **409**. Several requests may wait in `awaiting_approval`; only one can execute. No advisory lock.
3. **Approvals:** `approval_decisions(workspace_id, deployment_id, reviewer_id, decision, comment, decided_at)`, `UNIQUE (deployment_id, reviewer_id)`. The deployment stores `policy_snapshot` (policy frozen at request time), `approval_expires_at` and `base_deployment_id` (the environment's current deployment at request time). A decision is refused as **stale** if `base_deployment_id` no longer equals `environments.current_deployment_id`. Approve = one transaction: insert decision → if `min_approvals` reached, transition to `queued` → insert dispatch job.
4. **Rollback:** a new deployment with `operation_type = 'rollback'`, `rollback_of_deployment_id` and a required `reason`. The original is never changed.
5. **Environment state:** `environments.current_deployment_id` is set when a deployment **enters `verifying`** (the artifact is live from then on, even if it later proves unhealthy). `health_status`, `consecutive_failures`, `last_checked_at`, `next_check_at` live on the environment.
6. **Environment policy** (`environments.policy` JSONB, validated by Pydantic): `auto_deploy_on_release`, `requires_approval`, `min_approvals`, `approval_ttl_hours`, `require_comment`, `promote_from_environment_id`, `rollback_requires_approval`.
7. **Tenancy:** every tenant table carries `workspace_id`, with composite FKs (`(application_id, workspace_id)` → `applications(id, workspace_id)`) so no row can point across workspaces.
8. **Only `deployment_service.transition()`** changes `status`. It checks `ALLOWED_TRANSITIONS`, writes a `deployment_events` row and an audit entry, and runs in the caller's transaction. `deployment_events` and `audit_logs` are append-only (trigger).

## Alternatives considered

| Option | Complexity | Integrity | Why not |
|---|---|---|---|
| **Deployment aggregate + partial unique index** (chosen) | Low | Enforced by Postgres | — |
| Keep `approval_requests` / `rollback_events` | Medium | Two sources of truth | Extra tables, joins and sync code for no extra information |
| Advisory lock + in-flight check | Medium | Convention only | One forgotten path = concurrent production deploy |
| Separate "deploy queue" table | High | Good | Queueing behind a running deploy isn't a v1 need |

## Consequences
- Easier: the approvals inbox is `deployments WHERE status = 'awaiting_approval'`; no status sync.
- Easier: concurrency can't be bypassed by a new code path; tests assert the 409 from the DB constraint.
- Harder: to cancel a running deploy, cancel the run in GitHub; the webhook then fails the deployment.
- Harder: re-requesting after rejection means a new deployment (already the rule for terminal states).
- Follow-up: unit-test every row of the transition table and the stale/expired/self-approval paths.
