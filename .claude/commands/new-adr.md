---
description: Create the next Architecture Decision Record in docs/adr/
argument-hint: <short decision title>
---

Create a new ADR for: $ARGUMENTS

1. List `docs/adr/` and pick the next number `NNNN` (4 digits, starting at `0001`). Create the folder if missing.
2. Write `docs/adr/NNNN-<kebab-case-title>.md`:

```markdown
# NNNN. <Title>

- **Status:** Proposed
- **Date:** <today, YYYY-MM-DD>
- **Jira:** <SCRUM-n or "none">

## Context
<The forces at play and the problem. Link guide sections, e.g. docs/DEVELOPMENT_LIFECYCLE.md §5.1.>

## Decision
<What we decided, stated actively.>

## Alternatives considered
<Each option and why it lost, one line each.>

## Consequences
<What gets easier, what gets harder, follow-up work.>
```

3. Fill the sections from the conversation and the docs; mark anything uncertain with `TODO`.
4. If the decision changes the big picture, update the Architecture section of `CLAUDE.md` in the same change.
5. Show the file to the user. Don't commit.
