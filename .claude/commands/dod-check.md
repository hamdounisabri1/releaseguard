---
description: Check the current change against the Definition of Done
---

Check the current change against the Definition of Done in `.claude/rules/git-workflow.md`.

1. Collect the change: `git diff main...HEAD`, `git diff --staged` and `git diff`. Note the Jira key from the branch name if present.
2. Go through each DoD item and mark it ✅ met, ❌ not met, or ➖ not applicable, with one line of evidence (file:line, test name, or what's missing):
   - Acceptance criteria incl. permission-denied and failure paths
   - Backend permission check plus workspace scoping (cross-workspace → 404)
   - Tests added or updated (name them); run the relevant tests if the tooling exists
   - Alembic migration included, reversible, tested on a fresh DB (if models changed)
   - UI empty / loading / error / permission-denied states (if UI changed)
   - Audit entries for state-changing actions
   - Docs in sync: walk the "Keep the docs in sync" table in `CLAUDE.md` and list each doc that should have changed but didn't
   - Bug fix: regression test, and a lesson only if `maintenance.md` §3 says so
   - New skills, plugins or MCP servers: committed and documented
3. If the diff touches deployments, approvals, webhooks, sessions, RBAC or tokens, recommend `/security-review` and the `release-safety-reviewer` agent.
4. End with **Ready / Not ready** and a short to-do list. Don't edit files or commit.
