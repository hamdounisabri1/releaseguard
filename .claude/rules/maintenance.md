# Maintenance rules: keep docs, tools and lessons current

These rules always apply. Their goal is that the repository on GitHub always shows the **real, current** state of the project: its rules, tools and lessons learned.

## 1. New skills, plugins and MCP servers are committed with the project
Follow the checklist in [docs/AI_TOOLING.md § Adding a new tool](../../docs/AI_TOOLING.md#adding-a-new-tool) **in the same change**: project-scoped install (`--copy` for skills, never `-g`), review third-party files, keep the license, check `git check-ignore` prints nothing, and update `AI_TOOLING.md`, the `CLAUDE.md` tooling table and the README list. Removing a tool removes it from all of them.

## 2. Keep the `.md` files current
Use the "Keep the docs in sync" table in `CLAUDE.md` to find the file, and update it **in the same change**. Beyond that table:
- A finished sprint task: tick its checkbox in `docs/PROJECT_PLAN.md` **in the Task's own PR, before merge** (`main` is protected, so a tick made after the merge has nowhere to go).
- A doc that contradicts the code: fix the doc (or the code). Never leave the two disagreeing.
- When ending a session that produced new knowledge, offer `/claude-md-management:revise-claude-md`.
- **Project knowledge lives in the repo, never in Claude's personal memory.** Every rule, convention, process decision or project fact goes into `CLAUDE.md`, `.claude/rules/` or `docs/`, so it is versioned and visible on GitHub. Personal memory is only for things that have nothing to do with this project.

## 3. Fixed bugs become regression tests, and sometimes rules
**Scope:** bugs found after a change reached `main`. Failures fixed while still working the same ticket don't count.

1. **Always add a regression test** that fails without the fix.
2. **Add a lesson only when the bug's *class* could recur elsewhere** and a test alone won't stop it. Use `/lesson`, which appends to `## Lessons learned` at the bottom of the matching rules file:
   ```markdown
   - **<Short rule, written as an instruction>.** Why: <root cause in one line>. (<YYYY-MM-DD>, <SCRUM-n or commit>)
   ```
   State the rule **generally** (the class of bug). If an existing rule already covers it, sharpen that rule instead.
3. Security bug: also run `/security-review` on the fix.
4. Mention a new lesson in the commit body (`Lesson: added to .claude/rules/<file>.md`).

**Cap:** at most 8 lessons per rules file. At sprint end, promote recurring lessons into the rule body and delete the rest, so always-loaded context doesn't grow without bound.
