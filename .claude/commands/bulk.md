---
description: Bulk mode - plan, build and ship several Tasks on one branch and one PR, with few calls
argument-hint: last N | rest | SCRUM-27 SCRUM-28 … | done
---

Bulk mode for ReleaseGuard. Same workflow as `jira-workflow.md` §5 and `git-workflow.md` ("Bulk completion = one PR"), done with as few tool calls and as little context as possible. Arguments: `$ARGUMENTS`.

Jira goes through `py -3 .claude/scripts/jira.py` (one call covers all the keys). Use the `jira` MCP server only if the script fails. **No Explore/Plan subagents. Never read `docs/PROJECT_PLAN.md` or `docs/DEVELOPMENT_LIFECYCLE.md` whole**: `grep -n` the headings first, then do a ranged Read.

## `done`: after the user has merged the PR
1. `gh pr view --json number,state,url,headRefName` on the bulk branch. If the state isn't `MERGED`, stop and say so.
2. `py -3 .claude/scripts/jira.py done <keys> --pr <url> --comment "<what changed, how tested>"` (one call; keys from the branch name and PR title).
3. `git switch main && git pull --ff-only && git branch -D <branch>`.
4. `py -3 .claude/scripts/jira.py sprint-close`. If it closes the sprint, do the sprint-close PR (`jira-workflow.md` §7).
5. Report in 3 lines or fewer.

## Plan phase (the user is in plan mode)
1. **Tasks:** `py -3 .claude/scripts/jira.py brief --last N` (or `--open` for `rest`, or the listed keys). This one call gives the status, plan estimate, labels, blockers and acceptance criteria. Drop Tasks already Done. If a blocker is outside the set and not Done, say so and propose the order or a smaller set.
2. **Context, ranged only:** the active sprint's section of `PROJECT_PLAN.md`, the rules files for the areas in the Tasks' `area:*` labels (`backend.md`, `frontend.md`, `database.md`, …), and only the lifecycle-guide sections the acceptance criteria cite. Glob/Grep the existing code that the Tasks extend; read only the files you'll change.
3. **One compact plan** (about 40 lines): a table `Task | files | tests (incl. failure paths) | docs`, the commit order (dependency order), the branch name `<type>/SCRUM-<first>-<last>-<desc>`, and which reviews apply. Then ExitPlanMode.

## Build phase (after approval)
1. `git switch main && git pull --ff-only && git switch -c <branch>`. If the "Today" block edit is uncommitted, it becomes the first commit.
2. `py -3 .claude/scripts/jira.py start <all keys> --comment "<≤5-line plan>"` (one call).
3. For each Task, in order:
   - implement it;
   - run **only the tests for the area it touched** (the post-edit hook already lints each edited file);
   - tick its checkbox in `PROJECT_PLAN.md` and add it to "Done today";
   - `git commit` with a Conventional Commit that carries its key.
   **No push and no draft PR between Tasks.** If the session must end mid-set, ask before pushing a backup.

## Finish phase (once for the whole set)
1. **Full local gate, once**, for the areas changed. Backend: `uv run ruff check . && uv run ruff format --check . && uv run mypy app tests && uv run pytest`. Frontend: `pnpm lint && pnpm typecheck && pnpm build`.
2. **One push** (`git push -u origin <branch>`, the user's single prompt) and **one PR** from `.github/pull_request_template.md`, titled with every key.
3. **One review of the combined diff:** `/code-review medium`. Add `/security-review` and the `release-safety-reviewer` agent only if the diff touches auth, RBAC, sessions, webhooks, approvals, GitHub tokens or the AI sanitizer. Fix the findings in one commit and push again.
4. **One `/dod-check`.** Then run `gh pr checks <n> --watch` in the background and don't poll it. When it finishes, tell the user the PR is ready to merge (Claude never merges). Tasks stay In Progress until `/bulk done`.
