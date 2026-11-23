# 0001. Modular monolith: one API, one worker, one database

- **Status:** Accepted
- **Date:** 2026-11-23
- **Jira:** SCRUM-11

## Context
ReleaseGuard is built by one developer in 12 weeks and runs on one VPS (docs/DEVELOPMENT_LIFECYCLE.md §5.1). Its core rules (approval gate, state machine, tenancy) must be enforced consistently and tested together. Load is small: a few apps × 3 environments, tens of deployments a day ([ARCHITECTURE_REVIEW.md §2](../ARCHITECTURE_REVIEW.md#2-requirements-and-constraints)).

## Decision
Build one Next.js frontend, one FastAPI backend, one PostgreSQL database and one worker process that **shares the backend code** (own entrypoint and container). Backend layering is route → service → repository → DB. The **API process never makes outbound network calls** (GitHub, LLM, health checks); it writes state plus jobs in one transaction, and the worker does all outbound I/O.

## Alternatives considered

| Option | Complexity | Cost | Fit |
|---|---|---|---|
| **Modular monolith + worker** (chosen) | Low | One VPS | Business rules in one codebase, one transaction model |
| Microservices (approvals, deployments, health, AI) | High | More containers, a broker | Distributed transactions around the approval gate; far too much for one person |
| Monolith with no worker (everything in request handlers) | Lowest | Lowest | Network calls inside requests and transactions; no retries; health checks need a scheduler anyway |

## Consequences
- Easier: one test suite exercises the full approval → dispatch path; one migration history; one deploy.
- Easier: "no network call inside a DB transaction" becomes a structural rule (API never calls out).
- Harder: worker and API must agree on job payload schemas (shared Pydantic models in the same package).
- Revisit: split out a service only for a real scaling or ownership need.
