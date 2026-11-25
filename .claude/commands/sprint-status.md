---
description: Summarize the current sprint from Jira SCRUM and docs/PROJECT_PLAN.md
---

Give a sprint status report for ReleaseGuard.

1. Read `.claude/rules/jira-workflow.md` and the "Current sprint" line in `CLAUDE.md`.
2. From `docs/PROJECT_PLAN.md`, list the current sprint's checklist (ticked vs open).
3. Query Jira with one call: `py -3 .claude/scripts/jira.py brief --open --short` (open Tasks in the active sprint, with status, plan estimate, labels and blockers). If the script fails, use the `jira` MCP server (`jira_search`, `project = SCRUM AND statusCategory != Done ORDER BY rank`); if that fails too, say so in one line (suggest `/mcp`) and continue with the plan only. Never invent ticket keys.
4. Report in at most 8 lines: today's picks (`labels = today`, and the "Today" block in plan §5), In Progress, next in To Do, blocked items, plan items without a ticket, and whether the sprint is on track for its end date (if behind, mention the cut list in plan §6).

Don't create, edit or transition tickets in this command.

$ARGUMENTS
