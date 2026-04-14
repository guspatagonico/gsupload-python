---
description: Create a handoff file capturing current project state
agent: general
---

Create a handoff file in `_handoffs/` capturing only work from the current session.

File naming: `handoff-{YYYY-MM-DD}-{HH-mm}.md`

Sections:

## Completed

- Tasks completed in the current session only (checkboxes with [x])

## Decisions Made

- Key decisions from this session

## Files Modified

- Files modified in this session

## Pending

- Pending tasks (checkboxes with [ ])

## Blockers

- Any blockers

Use shell output:

- Git status: !`git status --short`
- Recent commits: !`git log --oneline -10`

Write the file and confirm the path.
