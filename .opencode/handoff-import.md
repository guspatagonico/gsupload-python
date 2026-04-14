---
description: Import the last handoff file into current conversation
agent: general
---

Import the last handoff file from `_handoffs/` into the current conversation.

1. Use glob to find all `handoff-*.md` files
2. Parse filenames to extract datetime (format: `handoff-YYYY-MM-DD-{HH-mm}.md`)
3. Sort by datetime descending to get the most recent file
4. Read and display its contents, then merge its sections into the current conversation:
   - Summarize completed tasks
   - Note key decisions
   - Identify pending tasks and blockers
