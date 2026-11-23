# 0004. One Postgres jobs table as outbox, retry queue and scheduler

- **Status:** Accepted
- **Date:** 2026-11-23
- **Jira:** none (architecture review, findings 2, 9, 13)

## Context
The original design used three mechanisms for asynchronous work: an outbox row for dispatch, a Postgres job table for worker jobs, and APScheduler for periodic tasks (docs/DEVELOPMENT_LIFECYCLE.md §6.2 before this review). The plan dispatched staging deployments in Sprint 2 but introduced the worker only in Sprint 4. Periodic work was also missing owners: approval expiry, recovery of lost webhooks, and health-check retention.

## Decision
- **One table, `jobs`:** `id, workspace_id, kind, payload jsonb, status (pending|running|done|dead), run_after, attempts, max_attempts, locked_until, last_error, dedupe_key UNIQUE, created_at`.
- **Enqueue = insert in the caller's transaction** (this is the outbox). Approve → `queued` → dispatch job commit together or not at all.
- **Worker = one async loop:** claim due jobs with `SELECT … FOR UPDATE SKIP LOCKED`, set `locked_until`, run, then mark done or reschedule with exponential backoff (`tenacity`-style delays). After `max_attempts` the job is `dead` and its handler's failure hook runs (for dispatch: `queued → failed`, `error_code = dispatch_failed`).
- **Sweeps** run on fixed intervals inside the same loop and are idempotent:
  - `expire_approvals` (every 60 s): `awaiting_approval` past `approval_expires_at` → `expired`.
  - `reconcile_runs` (every 60 s): deployments in `deploying` with no update for 5 min → read the run from GitHub by id. If it has no run after `DISPATCH_TIMEOUT_SECONDS`, → `failed` (`run_not_found`).
  - `health_checks_due` (every 5 s): environments with `next_check_at <= now()` → check, then set the next time.
  - `retention` (daily): delete scheduled `health_checks` older than 14 days (keep verification checks) and `done` jobs older than 7 days.
- No APScheduler, no Redis.

## Alternatives considered

| Option | Complexity | Infra | Why not |
|---|---|---|---|
| **Jobs table + sweeps** (chosen) | Low | None | — |
| Outbox + job table + APScheduler | Medium | None | Three mechanisms; APScheduler 3→4 API churn; schedules live outside the DB |
| ARQ/Celery + Redis | Medium | Redis | Enqueue isn't transactional with the state change; extra service to run and back up |

## Consequences
- Easier: everything async is visible in one table (debugging, retries, the dashboard).
- Easier: the worker skeleton lands in Sprint 2 with dispatch; health checks and AI add new `kind`s later.
- Harder: ~1–2 s polling latency (fine for humans watching a deploy).
- Revisit: add `LISTEN/NOTIFY` for instant wake-up if latency matters; move to a broker only past ~50 jobs/s.
