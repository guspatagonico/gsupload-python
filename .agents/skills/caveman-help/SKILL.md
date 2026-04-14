---
name: caveman-help
description: >
  Quick-reference card for caveman modes and commands. Trigger on "/caveman-help",
  "caveman help", "what caveman commands", or "how do I use caveman".
disable-model-invocation: false
---

## When to Use
- User asks for caveman commands or help.
- User invokes `/caveman-help`.

## Repository Evidence Basis
- Caveman skills are installed under `.agents/skills/` in this repo.

## Clarification Gate
- None. This is a deterministic output.

## Purpose
- Display the caveman reference card in a single response.

## Scope
Included:
- One-shot help output only.
Excluded:
- Mode changes, file writes, or persistent state.

## Inputs
- None.

## Step-by-step Execution
1) Output the help card below.
2) Ensure the response uses caveman style (terse, no fluff).

## Output Contract
- Output the card only; no additional commentary.

## Verification Commands
- None.

## Evidence Format
- The card text exactly once.

## Safety / DONTs
- Do not change mode or persist state.
- Do not add external links beyond the reference link.

## Gotchas
- If the user wants to change mode, instruct them to use `/caveman ...`.

# Caveman Help

Display this reference card when invoked. One-shot — do NOT change mode, write flag files, or persist anything. Output in caveman style.

## Modes

| Mode | Trigger | What change |
|------|---------|-------------|
| **Lite** | `/caveman lite` | Drop filler. Keep sentence structure. |
| **Full** | `/caveman` | Drop articles, filler, pleasantries, hedging. Fragments OK. Default. |
| **Ultra** | `/caveman ultra` | Extreme compression. Bare fragments. Tables over prose. |
| **Wenyan-Lite** | `/caveman wenyan-lite` | Classical Chinese style, light compression. |
| **Wenyan-Full** | `/caveman wenyan` | Full 文言文. Maximum classical terseness. |
| **Wenyan-Ultra** | `/caveman wenyan-ultra` | Extreme. Ancient scholar on a budget. |

Mode stick until changed or session end.

## Skills

| Skill | Trigger | What it do |
|-------|---------|-----------|
| **caveman-commit** | `/caveman-commit` | Terse commit messages. Conventional Commits. ≤50 char subject. |
| **caveman-review** | `/caveman-review` | One-line PR comments: `L42: bug: user null. Add guard.` |
| **caveman-compress** | `/caveman:compress <file>` | Compress .md files to caveman prose. Saves ~46% input tokens. |
| **caveman-help** | `/caveman-help` | This card. |

## Deactivate

Say "stop caveman" or "normal mode". Resume anytime with `/caveman`.

## Configure Default Mode

Default mode = `full`. Change it:

**Environment variable** (highest priority):
```bash
export CAVEMAN_DEFAULT_MODE=ultra
```

**Config file** (`~/.config/caveman/config.json`):
```json
{ "defaultMode": "lite" }
```

Set "off" to disable auto-activation on session start. User can still activate manually with `/caveman`.

Resolution: env var > config file > `full`.

## More

Full docs: https://github.com/JuliusBrussee/caveman
