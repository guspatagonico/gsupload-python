---
description: Prepare a release for gsupload
argument-hint: "[version]"
mode: manual
---

# Release Workflow

## Goal
- Prepare a new release version for the `gsupload` package with tests and changelog updates.

## Preconditions
- Clean working tree (`git status` shows no pending changes).
- Python 3.9+ and `uv` available.
- Dev dependencies installed (`uv pip install -e ".[dev]"`).
- Commitizen (`cz`) available in PATH.

## Ordered Steps
1) Confirm working tree is clean and on the intended branch.
2) Run tests: `pytest` (or `python -m pytest`).
3) If tests pass, bump the version with Commitizen: `cz bump`.
4) Review `pyproject.toml`, `src/gsupload/__init__.py`, and `CHANGELOG.md` for expected updates.
5) Create the release commit using Conventional Commits (commit-msg hook enforces this).

## Failure Handling
- If tests fail, stop and report failures; do not bump version.
- If `cz bump` fails, stop and report; do not attempt to force changes.
- If required tools are missing, stop and ask for installation preference.

## Verification and Evidence
- Test output shows all tests passing.
- `git diff` shows version updates and changelog entries only.
- `cz version` (or `pyproject.toml` version) matches the intended release.

## Safety Gates
- Do not publish to package indexes or push tags unless explicitly requested.
- Do not force-push or rewrite history.
