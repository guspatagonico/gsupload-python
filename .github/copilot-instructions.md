# Copilot Instructions

## Project Context
- **Description**: Python project (gsupload-python)
- **Architecture**: Modular, with a focus on maintainability and readability

## Code Style & Conventions
- **Python Version**: 3.9.6
- **Formatting**: Follow PEP 8. Use `ruff` if configured.
- **Type Hinting**: Use standard Python type hints for all function signatures.
- **Docstrings**: Use Google style docstrings.

## Development Workflow
- **Dependency Management**: uv (use `uv pip install` for packages, `uv run python` for scripts)
- **Testing**: pytest
- **Linting**: ruff
- **Important**: Always use `uv` commands instead of `pip3` or `python3` directly

## Key Files & Directories
- `src/`: Source code
- `tests/`: Test suite
- `.github/workflows/`: CI/CD configurations

## Commit Messages
- **Convention**: Follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/)
- **Format**: `<type>[optional scope]: <description>`
- **Types**: 
  - `feat`: New feature (MINOR bump)
  - `fix`: Bug fix (PATCH bump)
  - `docs`: Documentation changes
  - `refactor`: Code refactoring
  - `perf`: Performance improvements (PATCH bump)
  - `test`: Test additions/changes
  - `build`: Build system changes
  - `ci`: CI/CD changes
  - `chore`: Maintenance tasks
- **Scopes**: `ftp`, `sftp`, `cli`, `config`, `visual-check`, `excludes`, `tree`
- **Breaking Changes**: Add `!` after type/scope or use `BREAKING CHANGE:` in footer (MAJOR bump)
- **Examples**:
  - `feat(visual-check): add tree comparison before upload`
  - `fix(sftp): handle connection timeout gracefully`
  - `docs: update README with visual check examples`
  - `feat!: change config file format to YAML`
- When asked about commits, help format messages following this specification
