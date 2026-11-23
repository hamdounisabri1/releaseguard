---
description: Record a lesson from a fixed bug in the matching .claude/rules file
argument-hint: <what went wrong and the fix>
---

Record a lesson learned for: $ARGUMENTS

Follow `.claude/rules/maintenance.md` §3:

1. Decide whether it qualifies: the bug reached `main`, **and** its class could recur elsewhere, **and** a regression test alone won't stop it. If not, say so and stop (a regression test is enough).
2. Pick the matching rules file (`backend.md`, `frontend.md`, `security.md`, `database.md`, `testing.md`, `github-actions.md`, `infra.md`, `ai.md`, `jira-workflow.md`).
3. If an existing rule already covers it, sharpen that rule instead of adding a line.
4. Otherwise append under `## Lessons learned` (create the section at the bottom if missing):
   `- **<Short rule, written as an instruction>.** Why: <root cause in one line>. (<YYYY-MM-DD>, <SCRUM-n or commit>)`
   State the rule generally (the class of bug), not the one-off symptom.
5. If the file now has more than 8 lessons, propose which to promote into the rule body or delete.
6. Remind the user to add `Lesson: added to .claude/rules/<file>.md` to the commit body. Don't commit.
