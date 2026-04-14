---
description: Stage all changes, commit with conventional message, and push to main branch
agent: build
---

Stage all changes, commit with a conventional commits message, and push to the main branch.

Workflow:

1. Check current branch is main (abort if not)
2. Show git status for context
3. Show recent commits for message style reference
4. Stage all changes: `git add -A`
5. Create commit with conventional format (feat:, fix:, docs:, refactor:, chore:)
6. Push to remote main: `git push`

If there are no changes to commit, skip the commit and push.

If the push fails (e.g., remote has new changes), report the error to the user.
