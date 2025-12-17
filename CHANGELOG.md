## 2.0.0 (2025-12-16)

### BREAKING CHANGE

- Entry point changed from `gsupload:main` to `gsupload.cli:main`
- Version location moved from `gsupload.py:__version__` to `gsupload/__init__.py:__version__`

### Refactor

- **architecture**: restructure from single-file monolith to modular package
  - Extract `config.py` - configuration loading, merging, validation
  - Extract `excludes.py` - file exclusion patterns and directory walking
  - Extract `utils.py` - shared utility functions
  - Extract `tree.py` - visual tree comparison display
  - Extract `protocols/ftp.py` - FTP protocol implementation
  - Extract `protocols/sftp.py` - SFTP protocol implementation
  - Extract `cli.py` - Click CLI commands and argument parsing

### Added

- **test**: add comprehensive test scaffold with pytest (46 tests)
  - `test_cli.py` - CLI integration tests
  - `test_config.py` - configuration tests
  - `test_excludes.py` - exclusion pattern tests
  - `test_protocols_ftp.py` - FTP protocol tests
  - `test_protocols_sftp.py` - SFTP protocol tests
  - `test_tree.py` - tree display tests
  - `test_utils.py` - utility function tests
- **docs**: add ARCHITECTURE.md with module diagrams and data flow
- **docs**: add installation/update/uninstall instructions to USER_MANUAL.md

### Changed

- **deps**: add pytest and pytest-cov as dev dependencies

## 1.0.1b2 (2025-12-15)

### Fix

- **git**: modify .gitignore
- **cli**: make --max-workers override config; update dev install docs

## 1.0.1b1 (2025-12-14)

### Feat

- **cli**: show max_workers count in upload progress messages

## 1.0.0b0 (2025-12-14)

## 1.0.0a0 (2025-12-14)

### BREAKING CHANGE

- Minor configuration and default behavior modifications.

### Feat

- **upload**: add performance optimizations and enhanced connection handling

## 0.5.0 (2025-12-13)

### Feat

- **cli**: add config inspection and ignore listing tools

## 0.4.0 (2025-12-13)

### Feat

- **config**: BREAKING CHANGE: Configuration behavior and CLI defaults have changed

## 0.3.0 (2025-12-13)

### Feat

- **cli**: refactor binding selection with -b flag and auto-detection

### Fix

- **sftp**: improve channel handling and add safety checks for remote directory listing

## 0.2.0 (2025-12-12)

### Feat

- **visual-check**: add tree comparison before upload
