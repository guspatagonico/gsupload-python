# gsupload Architecture

This document describes the modular architecture of `gsupload` after the refactor from a single-file monolith to a well-organized package structure.

---

## Table of Contents

1. [Overview](#overview)
2. [Package Structure](#package-structure)
3. [Module Dependency Graph](#module-dependency-graph)
4. [Module Responsibilities](#module-responsibilities)
5. [Data Flow](#data-flow)
6. [Entry Points](#entry-points)
7. [Testing Structure](#testing-structure)

---

## Overview

The `gsupload` tool was restructured from a single 1,712-line monolithic file into a modular package with clear separation of concerns. This improves:

- **Maintainability** - Each module has a single responsibility
- **Testability** - Modules can be tested in isolation
- **Readability** - Smaller files are easier to navigate
- **Extensibility** - Adding new protocols or features is straightforward

---

## Package Structure

```
src/
└── gsupload/
    ├── __init__.py          # Package root, version, public API exports
    ├── cli.py               # Click CLI commands and argument parsing
    ├── config.py            # Configuration loading, merging, validation
    ├── excludes.py          # File exclusion patterns and directory walking
    ├── utils.py             # Shared utility functions
    ├── tree.py              # Visual tree comparison display
    └── protocols/
        ├── __init__.py      # Protocol exports (list_remote, upload)
        ├── ftp.py           # FTP protocol implementation
        └── sftp.py          # SFTP protocol implementation

tests/
├── conftest.py              # Shared pytest fixtures
├── test_cli.py              # CLI integration tests
├── test_config.py           # Configuration tests
├── test_excludes.py         # Exclusion pattern tests
├── test_protocols_ftp.py    # FTP protocol tests
├── test_protocols_sftp.py   # SFTP protocol tests
├── test_tree.py             # Tree display tests
└── test_utils.py            # Utility function tests
```

### File Size Distribution

| Module              | Lines | Responsibility                |
| ------------------- | ----- | ----------------------------- |
| `cli.py`            | ~550  | Main entry point, CLI parsing |
| `config.py`         | ~350  | Configuration management      |
| `excludes.py`       | ~250  | File exclusion logic          |
| `protocols/sftp.py` | ~220  | SFTP operations               |
| `protocols/ftp.py`  | ~180  | FTP operations                |
| `tree.py`           | ~180  | Visual comparison             |
| `utils.py`          | ~80   | Shared utilities              |
| `__init__.py`       | ~40   | Package metadata              |

---

## Module Dependency Graph

```
                           ┌─────────────────┐
                           │     cli.py      │
                           │  (entry point)  │
                           └────────┬────────┘
                                    │
            ┌───────────────┬───────┼───────┬───────────────┐
            │               │       │       │               │
            ▼               ▼       ▼       ▼               ▼
    ┌───────────┐   ┌───────────┐ ┌─────┐ ┌──────────┐ ┌─────────┐
    │ config.py │   │excludes.py│ │tree │ │protocols/│ │ utils.py│
    └─────┬─────┘   └─────┬─────┘ │.py  │ │__init__.py│ └────┬────┘
          │               │       └──┬──┘ └────┬─────┘      │
          │               │          │         │            │
          │               │          │    ┌────┴────┐       │
          │               │          │    │         │       │
          │               │          │    ▼         ▼       │
          │               │          │ ┌──────┐ ┌───────┐   │
          │               │          │ │ftp.py│ │sftp.py│   │
          │               │          │ └──────┘ └───────┘   │
          │               │          │                      │
          └───────────────┴──────────┴──────────────────────┘
                                    │
                                    ▼
                           ┌─────────────────┐
                           │   __init__.py   │
                           │ (version, API)  │
                           └─────────────────┘
```

### Import Relationships

```
gsupload/
├── __init__.py
│   └── exports: __version__, DEFAULT_MAX_DEPTH
│
├── cli.py
│   └── imports from: config, excludes, tree, protocols, utils, __init__
│
├── config.py
│   └── imports from: (standard library only)
│
├── excludes.py
│   └── imports from: (standard library only)
│
├── utils.py
│   └── imports from: (standard library only)
│
├── tree.py
│   └── imports from: protocols, excludes, __init__
│
└── protocols/
    ├── __init__.py
    │   └── re-exports from: ftp, sftp
    ├── ftp.py
    │   └── imports from: utils
    └── sftp.py
        └── imports from: utils
```

---

## Module Responsibilities

### `__init__.py` - Package Root

```
┌─────────────────────────────────────────┐
│              __init__.py                │
├─────────────────────────────────────────┤
│ • Package version (__version__)         │
│ • Default constants (DEFAULT_MAX_DEPTH) │
│ • Public API exports                    │
└─────────────────────────────────────────┘
```

**Exports:**
- `__version__` - Semantic version string
- `DEFAULT_MAX_DEPTH` - Default tree display depth

---

### `cli.py` - Command Line Interface

```
┌─────────────────────────────────────────┐
│                 cli.py                  │
├─────────────────────────────────────────┤
│ • Click command definitions             │
│ • Argument/option parsing               │
│ • Main workflow orchestration           │
│ • User interaction (prompts, output)    │
│ • Upload coordination                   │
└─────────────────────────────────────────┘
        │
        ├── main()           → Entry point
        └── version_callback() → --version handler
```

**Key Functions:**
- `main()` - Primary Click command with all CLI options
- `version_callback()` - Handles `--version` flag

---

### `config.py` - Configuration Management

```
┌─────────────────────────────────────────┐
│               config.py                 │
├─────────────────────────────────────────┤
│ • JSON config file discovery            │
│ • Hierarchical config merging           │
│ • Binding resolution & validation       │
│ • Path resolution (relative → absolute) │
│ • Source tracking for debugging         │
└─────────────────────────────────────────┘
        │
        ├── load_config_with_sources() → Load + track origins
        ├── load_config()              → Simple merged config
        ├── get_host_config()          → Resolve specific binding
        ├── show_config()              → Display merged config
        └── auto_detect_binding()      → Match CWD to binding
```

**Configuration Merge Flow:**

```
┌──────────────────┐
│ ~/.gsupload/     │ ◄─── Global (lowest priority)
│ gsupload.json    │
└────────┬─────────┘
         │ merge
         ▼
┌──────────────────┐
│ /project/        │ ◄─── Project root
│ .gsupload.json   │
└────────┬─────────┘
         │ merge
         ▼
┌──────────────────┐
│ /project/dist/   │ ◄─── Subdirectory (highest priority)
│ .gsupload.json   │
└────────┬─────────┘
         │
         ▼
   Final Merged Config
```

---

### `excludes.py` - File Exclusion System

```
┌─────────────────────────────────────────┐
│              excludes.py                │
├─────────────────────────────────────────┤
│ • .gsupload_ignore file parsing         │
│ • Gitignore-style pattern matching      │
│ • Directory tree walking with filtering │
│ • Exclusion debugging (--show-ignored)  │
└─────────────────────────────────────────┘
        │
        ├── load_ignore_file()       → Parse single ignore file
        ├── collect_ignore_patterns() → Gather all patterns
        ├── is_excluded()            → Check if path matches
        ├── walk_directory()         → Filtered os.walk
        └── show_ignored_files()     → Debug exclusions
```

**Pattern Sources:**

```
┌─────────────────────────────────────────┐
│           Exclusion Sources             │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │ global_     │  │ binding.excludes │  │
│  │ excludes    │  │ (per-binding)    │  │
│  └──────┬──────┘  └────────┬─────────┘  │
│         │                  │            │
│         └────────┬─────────┘            │
│                  │                      │
│         ┌────────▼────────┐             │
│         │ .gsupload_ignore│             │
│         │ files (walked)  │             │
│         └────────┬────────┘             │
│                  │                      │
│         ┌────────▼────────┐             │
│         │ Combined Pattern│             │
│         │      Set        │             │
│         └─────────────────┘             │
│                                         │
└─────────────────────────────────────────┘
```

---

### `utils.py` - Shared Utilities

```
┌─────────────────────────────────────────┐
│                utils.py                 │
├─────────────────────────────────────────┤
│ • Comment display formatting            │
│ • Remote path calculation               │
│ • Glob pattern expansion                │
└─────────────────────────────────────────┘
        │
        ├── display_comment()         → Format config comments
        ├── calculate_remote_path()   → Local → remote mapping
        └── expand_patterns()         → Glob pattern resolution
```

---

### `tree.py` - Visual Tree Comparison

```
┌─────────────────────────────────────────┐
│                tree.py                  │
├─────────────────────────────────────────┤
│ • Remote file listing                   │
│ • Local/remote diff calculation         │
│ • Tree structure rendering              │
│ • Upload summary statistics             │
└─────────────────────────────────────────┘
        │
        ├── display_tree_comparison()    → Main comparison entry
        ├── _display_scan_time()         → Performance output
        ├── _connect_sftp_with_retry()   → Connection handling
        ├── _display_tree()              → Recursive tree render
        └── _display_summary()           → Stats summary
```

**Tree Output Modes:**

```
┌─────────────────────────────────────────┐
│           Visual Check Modes            │
├─────────────────────────────────────────┤
│                                         │
│  -vcc (default)    -vc           -f     │
│  ┌──────────┐  ┌──────────┐  ┌───────┐  │
│  │ Complete │  │ Changes  │  │ None  │  │
│  │   Tree   │  │   Only   │  │(skip) │  │
│  └──────────┘  └──────────┘  └───────┘  │
│                                         │
│  Shows:        Shows:        Shows:     │
│  • NEW         • NEW         (nothing)  │
│  • OVERWRITE   • OVERWRITE              │
│  • REMOTE ONLY                          │
│                                         │
└─────────────────────────────────────────┘
```

---

### `protocols/` - Protocol Implementations

```
protocols/
├── __init__.py    ← Re-exports for clean imports
├── ftp.py         ← FTP implementation
└── sftp.py        ← SFTP implementation
```

#### `protocols/ftp.py`

```
┌─────────────────────────────────────────┐
│            protocols/ftp.py             │
├─────────────────────────────────────────┤
│ • FTP connection management             │
│ • Passive/Active mode handling          │
│ • Directory listing (recursive)         │
│ • File upload with retries              │
└─────────────────────────────────────────┘
        │
        ├── list_remote_ftp()  → Recursive directory listing
        └── upload_ftp()       → Single file upload
```

#### `protocols/sftp.py`

```
┌─────────────────────────────────────────┐
│           protocols/sftp.py             │
├─────────────────────────────────────────┤
│ • SSH/SFTP connection management        │
│ • Multiple auth methods support         │
│ • SSH compression enabled               │
│ • Parallel upload support               │
│ • Connection retry with backoff         │
└─────────────────────────────────────────┘
        │
        ├── list_remote_sftp() → Recursive directory listing
        └── upload_sftp()      → Single file upload
```

**Authentication Flow (SFTP):**

```
┌─────────────────────────────────────────────┐
│         SFTP Authentication Flow            │
├─────────────────────────────────────────────┤
│                                             │
│  Start                                      │
│    │                                        │
│    ▼                                        │
│  ┌─────────────────┐                        │
│  │ key_filename    │──Yes──► Use key file   │
│  │ provided?       │         (decrypt with  │
│  └────────┬────────┘          password if   │
│           │ No                provided)     │
│           ▼                                 │
│  ┌─────────────────┐                        │
│  │ password only   │──Yes──► Password auth  │
│  │ provided?       │                        │
│  └────────┬────────┘                        │
│           │ No                              │
│           ▼                                 │
│  ┌─────────────────┐                        │
│  │ Try SSH Agent   │──Success──► Connected  │
│  └────────┬────────┘                        │
│           │ Fail                            │
│           ▼                                 │
│  ┌─────────────────┐                        │
│  │ Try default     │──Success──► Connected  │
│  │ ~/.ssh/id_*     │                        │
│  └────────┬────────┘                        │
│           │ Fail                            │
│           ▼                                 │
│       Auth Error                            │
│                                             │
└─────────────────────────────────────────────┘
```

---

## Data Flow

### Upload Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                     Upload Workflow                             │
└─────────────────────────────────────────────────────────────────┘

User Input                    CLI Processing                Output
─────────                     ──────────────                ──────

gsupload "*.css"
       │
       ▼
┌──────────────┐
│  cli.main()  │
└──────┬───────┘
       │
       ├──────────────────────────────────────────────────────────┐
       │                                                          │
       ▼                                                          │
┌──────────────┐    ┌─────────────────┐                           │
│load_config() │───►│ Merged config   │                           │
└──────────────┘    │ + source info   │                           │
                    └────────┬────────┘                           │
                             │                                    │
       ┌─────────────────────┘                                    │
       │                                                          │
       ▼                                                          │
┌──────────────────┐    ┌─────────────────┐                       │
│auto_detect_      │───►│ Selected        │                       │
│binding()         │    │ binding config  │                       │
└──────────────────┘    └────────┬────────┘                       │
                                 │                                │
       ┌─────────────────────────┘                                │
       │                                                          │
       ▼                                                          │
┌──────────────────┐    ┌─────────────────┐                       │
│expand_patterns() │───►│ List of local   │                       │
│walk_directory()  │    │ files to upload │                       │
└──────────────────┘    └────────┬────────┘                       │
                                 │                                │
       ┌─────────────────────────┘                                │
       │                                                          │
       ▼                                                          │
┌──────────────────┐    ┌─────────────────┐    ┌───────────────┐  │
│display_tree_     │───►│ Tree comparison │───►│ User confirms │  │
│comparison()      │    │ + summary       │    │ (y/n prompt)  │  │
└──────────────────┘    └─────────────────┘    └───────┬───────┘  │
                                                       │          │
       ┌───────────────────────────────────────────────┘          │
       │                                                          │
       ▼                                                          │
┌──────────────────┐                                              │
│ ThreadPoolExec   │                                              │
│ (max_workers)    │                                              │
└────────┬─────────┘                                              │
         │                                                        │
    ┌────┴────┐                                                   │
    │         │                                                   │
    ▼         ▼                                                   │
┌───────┐ ┌────────┐    ┌─────────────────┐    ┌───────────────┐  │
│upload │ │upload  │───►│ Upload results  │───►│ ✅ Success    │  │
│_sftp()│ │_ftp()  │    │ (success/fail)  │    │ ❌ Errors     │──┘
└───────┘ └────────┘    └─────────────────┘    └───────────────┘
```

---

## Entry Points

### Package Entry Point

Defined in `pyproject.toml`:

```toml
[project.scripts]
gsupload = "gsupload.cli:main"
```

### Import Entry Points

```python
# CLI usage (primary)
from gsupload.cli import main

# Library usage
from gsupload import __version__, DEFAULT_MAX_DEPTH
from gsupload.config import load_config, get_host_config
from gsupload.excludes import is_excluded, walk_directory
from gsupload.protocols import list_remote_sftp, upload_sftp
from gsupload.protocols import list_remote_ftp, upload_ftp
```

---

## Testing Structure

```
tests/
├── conftest.py              ← Shared fixtures
│   ├── tmp_dir fixture
│   ├── sample_config fixture
│   └── mock_sftp fixture
│
├── test_cli.py              ← CLI integration
│   ├── test_version_flag
│   ├── test_help_flag
│   └── test_show_config
│
├── test_config.py           ← Configuration
│   ├── test_load_config
│   ├── test_config_merging
│   ├── test_get_host_config
│   └── test_auto_detect_binding
│
├── test_excludes.py         ← Exclusion patterns
│   ├── test_is_excluded
│   ├── test_load_ignore_file
│   └── test_walk_directory
│
├── test_protocols_ftp.py    ← FTP protocol
│   ├── test_list_remote_ftp
│   └── test_upload_ftp
│
├── test_protocols_sftp.py   ← SFTP protocol
│   ├── test_list_remote_sftp
│   └── test_upload_sftp
│
├── test_tree.py             ← Tree display
│   └── test_display_tree_comparison
│
└── test_utils.py            ← Utilities
    ├── test_calculate_remote_path
    ├── test_expand_patterns
    └── test_display_comment
```

### Test Coverage Goals

| Module           | Coverage Target      |
| ---------------- | -------------------- |
| `config.py`      | 90%+                 |
| `excludes.py`    | 85%+                 |
| `utils.py`       | 95%+                 |
| `protocols/*.py` | 80%+ (mocked I/O)    |
| `tree.py`        | 75%+ (visual output) |
| `cli.py`         | 70%+ (integration)   |

---

## Migration Notes

### From Monolith to Modular

The refactor followed these principles:

1. **Extract by responsibility** - Each module handles one concern
2. **Minimize coupling** - Modules depend on interfaces, not implementations
3. **Preserve public API** - CLI interface unchanged
4. **Functional style** - No unnecessary classes, prefer pure functions

### Breaking Changes

- Entry point changed: `gsupload:main` → `gsupload.cli:main`
- Version location: `gsupload.py:__version__` → `gsupload/__init__.py:__version__`

### Backwards Compatibility

- All CLI options remain unchanged
- Configuration file format unchanged
- `.gsupload_ignore` format unchanged
