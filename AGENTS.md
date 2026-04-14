# AGENTS

## Do
- Scan `README.md` and `docs/` before changing user-facing behavior.
- Keep version updates consistent with `pyproject.toml` and `src/gsupload/__init__.py`.
- Use `agentlint_get_guidelines` before editing any context artifact.
- Apply Agent Lint remediation directly when safe and requested.

## Don't
- Do not commit credentials or real hostnames in config examples.
- Do not bypass Conventional Commits (commit-msg hook enforces this).
- Do not duplicate large doc sections; reference doc paths instead.

## Repository Evidence Basis
- Python CLI package with entry point `gsupload` (see `pyproject.toml`).
- Dev tooling: `uv`, `pytest`, `commitizen` (commit-msg hook).
- Architecture and behavior documented in `docs/ARCHITECTURE.md` and `docs/USER_MANUAL.md`.

## Clarification Gate
- Ask only when intent is ambiguous after scanning docs and code.
- If a change affects upload behavior, confirm expected outcomes first.

## Quick Commands
- Install dev deps: `uv pip install -e ".[dev]"`
- Run CLI help: `gsupload --help`
- Run tests: `pytest`

## Repo Map
- `src/gsupload/cli.py`: CLI entry point and workflow orchestration.
- `src/gsupload/config.py`: config discovery, merge, validation.
- `src/gsupload/protocols/`: FTP/SFTP implementations.
- `tests/`: pytest coverage for CLI/config/protocols.
- `docs/`: architecture, user manual, performance guidance.

## Working Rules
- Preserve config merge behavior documented in `docs/USER_MANUAL.md`.
- Keep protocol changes isolated within `src/gsupload/protocols/`.
- Use Agent Lint: `agentlint_plan_workspace_autofix` for broad reviews, `agentlint_quick_check` for targeted changes.
- After context artifact changes, re-run the relevant Agent Lint check.

## When Stuck / Escalation
- Re-read `docs/ARCHITECTURE.md` and `docs/USER_MANUAL.md`.
- Ask the user for expected behavior deltas or reproduction steps.

## Verification Steps
- Run `pytest` for behavior changes.
- Confirm CLI help and key flows still match docs.

## Security Boundaries
- Treat `.gsupload.json` as sensitive; redact secrets.
- Do not run real FTP/SFTP uploads without explicit user request.
- Avoid destructive git operations or force pushes.

## PR / Change Checklist
- Tests pass (`pytest`).
- Docs updated if behavior or flags change.
- Version files in sync when bumping releases.
