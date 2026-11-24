<!--
PR title = Conventional Commit with the Jira key; it becomes the squash commit on main.
  feat(api): SCRUM-12 block self-approval when policy enabled
Scopes: api · web · worker · db · github · ai · infra · docs
-->

**Jira:** SCRUM-<!-- n -->

## What & why
<!-- What changed and why. Link the ADR or guide section if a decision is involved. -->

## How to test
<!-- Commands and steps a reviewer can run, including at least one failure path. -->

## Checklist
<!-- Tick what applies; strike through (~~item~~) what doesn't, with a reason if unclear. -->
- [ ] Tests cover the happy path **and** failure paths (permission denied, invalid input, conflicts)
- [ ] Backend permission check + workspace scoping (another workspace → 404)
- [ ] No secrets, tokens or cookies in code, logs, fixtures or the frontend bundle
- [ ] Alembic migration reversible and tested on a fresh database (if any)
- [ ] State-changing actions write audit entries
- [ ] UI has empty, loading, error and permission-denied states (if UI)
- [ ] Docs in sync: `CLAUDE.md`, `.claude/rules/`, guide, `.env.example`
- [ ] Task's checkbox in `docs/PROJECT_PLAN.md` ticked **in this PR** (and moved to "Done today")
- [ ] Bug fix: regression test that fails without the fix (+ lesson if the class can recur)
- [ ] Deployment, approval, webhook, session or token code: `/security-review` + `release-safety-reviewer` run
- [ ] Screenshots (if UI)
