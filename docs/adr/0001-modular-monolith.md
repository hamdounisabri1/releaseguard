# 0001. Modular monolith: one API, one worker, one database

- **Status:** Accepted
- **Date:** 2026-11-23
- **Jira:** SCRUM-11

## Context
ReleaseGuard is built by one developer in 12 weeks and runs on one VPS ([guide §5.1](../DEVELOPMENT_LIFECYCLE.md#51-style-modular-monolith)). Its core rules (approval gate, state machine, tenancy) must be enforced consistently and tested together. Load is small: a few apps × 3 environments, tens of deployments a day ([ARCHITECTURE_REVIEW.md §2](../ARCHITECTURE_REVIEW.md#2-requirements-and-constraints)).

## Decision
Build one Next.js frontend, one FastAPI backend, one PostgreSQL database and one worker process that **shares the backend code** (own entrypoint and container). Backend layering is route → service → repository → DB. The **API process never makes outbound network calls** (GitHub, LLM, health checks); it writes state plus jobs in one transaction, and the worker does all outbound I/O.

**No Redis, message broker or separate scheduler in v1.** Background work, retries and periodic sweeps all run from one Postgres `jobs` table ([ADR-0004](0004-postgres-jobs-table.md)).

## Alternatives considered

| Option | Complexity | Cost | Fit |
|---|---|---|---|
| **Modular monolith + worker** (chosen) | Low | One VPS | Business rules in one codebase, one transaction model |
| Microservices (approvals, deployments, health, AI) | High | More containers, a broker | Distributed transactions around the approval gate; far too much for one person |
| Monolith + Redis queue (Celery/ARQ) | Medium | Redis to run and back up | Enqueue isn't transactional with the state change; see [ADR-0004](0004-postgres-jobs-table.md) |
| Monolith with no worker (everything in request handlers) | Lowest | Lowest | Network calls inside requests and transactions; no retries; health checks need a scheduler anyway |

## Consequences
- Easier: one test suite exercises the full approval → dispatch path; one migration history; one deploy.
- Easier: "no network call inside a DB transaction" becomes a structural rule (API never calls out).
- Harder: worker and API must agree on job payload schemas (shared Pydantic models in the same package).
- Harder: one Postgres is a single point of failure; acceptable for one VPS with backups and restore tests ([guide §14.12](../DEVELOPMENT_LIFECYCLE.md#1412-operations-runbooks)).
- Revisit: split out a service only for a real scaling or ownership need.
