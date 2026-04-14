---
name: caveman-commit
description: >
  Ultra-compressed commit message generator. Cuts noise from commit messages while preserving
  intent and reasoning. Conventional Commits format. Subject ≤50 chars, body only when "why"
  isn't obvious. Use when user says "write a commit", "commit message", "generate commit",
  "/commit", or invokes /caveman-commit. Auto-triggers when staging changes.
disable-model-invocation: false
---

## When to Use
- User asks for a commit message or says “/commit” or “/caveman-commit”.
- Agent is about to create a commit and needs a message.

## Repository Evidence Basis
- Conventional Commits enforced via commitizen (see `pyproject.toml`).

## Clarification Gate
- Ask only if the change intent is unclear (e.g., bug fix vs feature).
- If scope or “why” is missing, request a one-line summary and reason.

## Purpose
- Generate a terse Conventional Commit message with emphasis on “why”.

## Scope
Included:
- Commit message text only.
Excluded:
- Running git commands, staging, committing, or amending.

## Inputs
- Change summary (what changed and why).
- Optional scope, issue refs, or breaking-change note.

## Step-by-step Execution
1) Determine commit type and optional scope.
2) Draft subject in imperative mood, ≤50 chars when possible.
3) Add body only when “why” is non-obvious, breaking, security, or migration related.
4) Append issue references if provided.

## Output Contract
- Output a single commit message in a fenced code block.
- No extra commentary before or after the block.

## Verification Commands
- None. Validate format and length manually.

## Evidence Format
- One code block containing the final commit message.

## Safety / DONTs
- Do not claim to run git commands.
- Do not include secrets or credentials.
- Do not add AI attribution.

## Gotchas
- Use `!` in the type for breaking changes (`feat!:`).
- If commitizen is active, non-Conventional messages will be rejected.

Write commit messages terse and exact. Conventional Commits format. No fluff. Why over what.

## Rules

**Subject line:**
- `<type>(<scope>): <imperative summary>` — `<scope>` optional
- Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`, `ci`, `style`, `revert`
- Imperative mood: "add", "fix", "remove" — not "added", "adds", "adding"
- ≤50 chars when possible, hard cap 72
- No trailing period
- Match project convention for capitalization after the colon

**Body (only if needed):**
- Skip entirely when subject is self-explanatory
- Add body only for: non-obvious *why*, breaking changes, migration notes, linked issues
- Wrap at 72 chars
- Bullets `-` not `*`
- Reference issues/PRs at end: `Closes #42`, `Refs #17`

**What NEVER goes in:**
- "This commit does X", "I", "we", "now", "currently" — the diff says what
- "As requested by..." — use Co-authored-by trailer
- "Generated with Claude Code" or any AI attribution
- Emoji (unless project convention requires)
- Restating the file name when scope already says it

## Examples

Diff: new endpoint for user profile with body explaining the why
- ❌ "feat: add a new endpoint to get user profile information from the database"
- ✅
  ```
  feat(api): add GET /users/:id/profile

  Mobile client needs profile data without the full user payload
  to reduce LTE bandwidth on cold-launch screens.

  Closes #128
  ```

Diff: breaking API change
- ✅
  ```
  feat(api)!: rename /v1/orders to /v1/checkout

  BREAKING CHANGE: clients on /v1/orders must migrate to /v1/checkout
  before 2026-06-01. Old route returns 410 after that date.
  ```

## Auto-Clarity

Always include body for: breaking changes, security fixes, data migrations, anything reverting a prior commit. Never compress these into subject-only — future debuggers need the context.

## Boundaries

Only generates the commit message. Does not run `git commit`, does not stage files, does not amend. Output the message as a code block ready to paste. "stop caveman-commit" or "normal mode": revert to verbose commit style.
