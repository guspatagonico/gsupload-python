---
name: caveman-review
description: >
  Ultra-compressed code review comments. One-line findings with location, problem, fix.
  Trigger on "review this PR", "code review", "review the diff", or "/caveman-review".
disable-model-invocation: false
---

## When to Use
- User asks for PR/code review or invokes `/caveman-review`.

## Repository Evidence Basis
- Repo uses Conventional Commits and pytest; review comments should be terse and actionable.

## Clarification Gate
- Ask only if the diff or files to review are unclear.

## Purpose
- Produce concise, actionable review comments.

## Scope
Included:
- Review notes only.
Excluded:
- Applying fixes, approving, or requesting changes.

## Inputs
- Diff or file paths with line numbers.

## Step-by-step Execution
1) Scan the diff for correctness, safety, and behavior regressions.
2) Emit one line per finding with location, problem, and fix.
3) If a security issue is found, write a full explanation first, then resume terse mode.

## Output Contract
- One line per finding using `L<line>:` or `<file>:L<line>:` format.

## Verification Commands
- None.

## Evidence Format
- Plain text lines with the agreed format.

## Safety / DONTs
- Do not claim to have run tests or linters.
- Do not approve or request changes on behalf of the user.

## Gotchas
- Security findings require full context, not a one-liner.

Write code review comments terse and actionable. One line per finding. Location, problem, fix. No throat-clearing.

## Rules

**Format:** `L<line>: <problem>. <fix>.` — or `<file>:L<line>: ...` when reviewing multi-file diffs.

**Severity prefix (optional, when mixed):**
- `🔴 bug:` — broken behavior, will cause incident
- `🟡 risk:` — works but fragile (race, missing null check, swallowed error)
- `🔵 nit:` — style, naming, micro-optim. Author can ignore
- `❓ q:` — genuine question, not a suggestion

**Drop:**
- "I noticed that...", "It seems like...", "You might want to consider..."
- "This is just a suggestion but..." — use `nit:` instead
- "Great work!", "Looks good overall but..." — say it once at the top, not per comment
- Restating what the line does — the reviewer can read the diff
- Hedging ("perhaps", "maybe", "I think") — if unsure use `q:`

**Keep:**
- Exact line numbers
- Exact symbol/function/variable names in backticks
- Concrete fix, not "consider refactoring this"
- The *why* if the fix isn't obvious from the problem statement

## Examples

❌ "I noticed that on line 42 you're not checking if the user object is null before accessing the email property. This could potentially cause a crash if the user is not found in the database. You might want to add a null check here."

✅ `L42: 🔴 bug: user can be null after .find(). Add guard before .email.`

❌ "It looks like this function is doing a lot of things and might benefit from being broken up into smaller functions for readability."

✅ `L88-140: 🔵 nit: 50-line fn does 4 things. Extract validate/normalize/persist.`

❌ "Have you considered what happens if the API returns a 429? I think we should probably handle that case."

✅ `L23: 🟡 risk: no retry on 429. Wrap in withBackoff(3).`

## Auto-Clarity

Drop terse mode for: security findings (CVE-class bugs need full explanation + reference), architectural disagreements (need rationale, not just a one-liner), and onboarding contexts where the author is new and needs the "why". In those cases write a normal paragraph, then resume terse for the rest.

## Boundaries

Reviews only — does not write the code fix, does not approve/request-changes, does not run linters. Output the comment(s) ready to paste into the PR. "stop caveman-review" or "normal mode": revert to verbose review style.
