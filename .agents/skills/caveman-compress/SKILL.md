---
name: caveman-compress
description: >
  Compress natural language memory files (CLAUDE.md, todos, preferences) into caveman format
  to save input tokens. Preserves all technical substance, code, URLs, and structure.
  Trigger on "/caveman:compress <filepath>" or "compress memory file".
disable-model-invocation: true
---

## When to Use
- User asks to compress a memory/context file.
- User invokes `/caveman:compress <filepath>`.

## Repository Evidence Basis
- This skill ships with local scripts in `scripts/` under this skill directory.

## Clarification Gate
- If the file path is missing or ambiguous, ask for an absolute path.
- If the file type is not prose, stop and explain why.

## Purpose
- Reduce token usage by compressing prose while preserving technical content.

## Scope
Included:
- `.md`, `.txt`, or extensionless prose files.
Excluded:
- Source code, configs, lockfiles, and any non-prose formats.
- Files ending in `.original.md`.

## Inputs
- Absolute file path to compress.

## Step-by-step Execution
1) Verify the file exists and is a supported prose type.
2) From this skill directory, run:
   `python -m scripts <absolute_filepath>`
3) Confirm the tool created a backup at `<file>.original.md`.
4) Return a short summary of what changed.

## Output Contract
- Report the original file path and backup path.
- Provide a brief compression summary (line count change or high-level).

## Verification Commands
- None beyond the tool output; validate backup existence when possible.

## Evidence Format
- One paragraph summary plus a list of file paths touched.

## Safety / DONTs
- Do not modify non-prose files.
- Do not run if the file is already a `.original.md` backup.
- Do not change code blocks or inline code.

## Gotchas
- Mixed prose/code files must keep code blocks untouched.
- Always keep markdown headings and list structure intact.

## Compression Rules
### Remove
- Articles: a, an, the
- Filler: just, really, basically, actually, simply, essentially, generally
- Pleasantries: "sure", "certainly", "of course", "happy to", "I'd recommend"
- Hedging: "it might be worth", "you could consider", "it would be good to"
- Redundant phrasing: "in order to" → "to", "make sure to" → "ensure", "the reason is because" → "because"
- Connective fluff: "however", "furthermore", "additionally", "in addition"

### Preserve EXACTLY (never modify)
- Code blocks (fenced ``` and indented)
- Inline code (`backtick content`)
- URLs and links (full URLs, markdown links)
- File paths
- Commands
- Technical terms and proper nouns
- Dates, version numbers, numeric values
- Environment variables

### Preserve Structure
- Markdown headings (exact heading text)
- Bullet hierarchy and numbered lists
- Tables
- Frontmatter/YAML headers

### Compress
- Use short synonyms: "big" not "extensive", "fix" not "implement a solution for"
- Fragments OK: "Run tests before commit"
- Drop "you should", "make sure to", "remember to"
- Merge redundant bullets that say the same thing differently

CRITICAL RULE:
Anything inside ``` ... ``` must be copied EXACTLY.
Inline code must be preserved EXACTLY.
