# gsupload-python

[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits&logoColor=white)](https://conventionalcommits.org)
[![Commitizen friendly](https://img.shields.io/badge/commitizen-friendly-brightgreen.svg)](http://commitizen.github.io/cz-cli/)

A Python script to sync files and folders to a remote FTP/SFTP server based on a configuration file.

## Installation

### Option 1: Install as a global tool (recommended)

Install `gsupload` globally using `uv` so it's available from anywhere in your PATH:

```bash
# Install the tool
uv tool install --editable /path/to/gsupload-python

# Update your shell configuration to add the tool directory to PATH
uv tool update-shell

# Restart your shell or source your profile, then use directly:
gsupload --help
```

After installation, you can run `gsupload` from any directory without activating a virtual environment.

### Option 2: Local development setup

For development or if you prefer not to install globally:

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    uv pip install -r requirements.txt
    ```
3.  Run with:
    ```bash
    python src/gsupload.py [OPTIONS] PATTERNS... HOST_ALIAS
    ```

## Configuration

Configuration files are **merged with inheritance** - you can have global settings and project-specific overrides.

### Configuration Discovery and Merging

The tool searches for and merges multiple configuration files to provide maximum flexibility:

1. **Global config** (optional base): `~/.gsupload/gsupload.json` or `~/.config/gsupload/gsupload.json`
2. **Project configs** (layered): All `.gsupload.json` files found walking up from current directory to filesystem root

**Discovery Process:**
1. Checks if global config exists (if yes, loads as base layer)
2. Walks up from your current directory collecting all `.gsupload.json` files
3. Sorts configs from root → current directory (shallowest to deepest)
4. Merges them layer by layer, with deeper configs overriding

**Merging Rules:**

| Configuration Key    | Merge Strategy           | Behavior                                                                                                                |
| -------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `global_excludes`    | **Additive**             | All patterns from all configs are combined into one list                                                                |
| `bindings`           | **Per-binding Override** | Each binding can be added or overridden independently. Properties within a binding are merged (deeper values override). |
| Other top-level keys | **Simple Override**      | Deeper config value replaces shallower value completely                                                                 |

### Detailed Merging Examples

#### Example 1: Simple Inheritance with Global Excludes

**File structure:**
```
~/.gsupload/gsupload.json
/projects/myapp/.gsupload.json
```

**Global config** (`~/.gsupload/gsupload.json`):
```json
{
  "global_excludes": [".DS_Store", "*.log"],
  "bindings": {
    "shared-staging": {
      "protocol": "ftp",
      "hostname": "staging.example.com",
      "username": "deploy",
      "password": "secret",
      "local_basepath": "/projects",
      "remote_basepath": "/www"
    }
  }
}
```

**Project config** (`/projects/myapp/.gsupload.json`):
```json
{
  "global_excludes": [".git", "node_modules", "__pycache__"],
  "bindings": {
    "frontend": {
      "protocol": "sftp",
      "hostname": "app.example.com",
      "username": "frontend-user",
      "password": "pass123",
      "local_basepath": "/projects/myapp/frontend",
      "remote_basepath": "/var/www/html"
    }
  }
}
```

**Resulting merged config when running from `/projects/myapp/`:**
```json
{
  "global_excludes": [
    ".DS_Store",
    "*.log",
    ".git",
    "node_modules",
    "__pycache__"
  ],
  "bindings": {
    "shared-staging": {
      "protocol": "ftp",
      "hostname": "staging.example.com",
      "username": "deploy",
      "password": "secret",
      "local_basepath": "/projects",
      "remote_basepath": "/www"
    },
    "frontend": {
      "protocol": "sftp",
      "hostname": "app.example.com",
      "username": "frontend-user",
      "password": "pass123",
      "local_basepath": "/projects/myapp/frontend",
      "remote_basepath": "/var/www/html"
    }
  }
}
```

**Key takeaways:**
- ✅ `global_excludes` combined from both files (5 total patterns)
- ✅ Both bindings available: `shared-staging` from global, `frontend` from project

---

#### Example 2: Binding Override in Subdirectory

**File structure:**
```
/projects/myapp/.gsupload.json
/projects/myapp/dist_production/.gsupload.json
```

**Project root config** (`/projects/myapp/.gsupload.json`):
```json
{
  "global_excludes": ["*.log", ".git"],
  "bindings": {
    "frontend": {
      "protocol": "sftp",
      "hostname": "dev.example.com",
      "port": 22,
      "username": "devuser",
      "password": "devpass",
      "local_basepath": "/projects/myapp/frontend",
      "remote_basepath": "/var/www/dev"
    }
  }
}
```

**Subdirectory config** (`/projects/myapp/dist_production/.gsupload.json`):
```json
{
  "global_excludes": ["*.map"],
  "bindings": {
    "frontend": {
      "hostname": "prod.example.com",
      "username": "produser",
      "password": "prodpass",
      "remote_basepath": "/var/www/production"
    }
  }
}
```

**Resulting merged config when running from `/projects/myapp/dist_production/`:**
```json
{
  "global_excludes": ["*.log", ".git", "*.map"],
  "bindings": {
    "frontend": {
      "protocol": "sftp",
      "port": 22,
      "hostname": "prod.example.com",
      "username": "produser",
      "password": "prodpass",
      "local_basepath": "/projects/myapp/frontend",
      "remote_basepath": "/var/www/production"
    }
  }
}
```

**Key takeaways:**
- ✅ `global_excludes` includes patterns from both levels (3 total)
- ✅ `frontend` binding merged: `protocol` and `port` inherited from parent
- ✅ `hostname`, `username`, `password`, `remote_basepath` overridden by subdirectory config
- ✅ `local_basepath` inherited from parent (not overridden)

---

#### Example 3: Multiple Bindings at Different Levels

**File structure:**
```
~/.gsupload/gsupload.json
/projects/webapp/.gsupload.json
/projects/webapp/admin/.gsupload.json
```

**Global config** (`~/.gsupload/gsupload.json`):
```json
{
  "global_excludes": [".DS_Store", "Thumbs.db"],
  "bindings": {
    "global-backup": {
      "protocol": "ftp",
      "hostname": "backup.example.com",
      "username": "backup",
      "password": "backup123",
      "local_basepath": "/projects",
      "remote_basepath": "/backups"
    }
  }
}
```

**Project root config** (`/projects/webapp/.gsupload.json`):
```json
{
  "global_excludes": ["node_modules", ".env"],
  "bindings": {
    "frontend": {
      "protocol": "sftp",
      "hostname": "web.example.com",
      "username": "frontend",
      "password": "front123",
      "local_basepath": "/projects/webapp/public",
      "remote_basepath": "/var/www/public"
    },
    "backend": {
      "protocol": "sftp",
      "hostname": "api.example.com",
      "username": "backend",
      "password": "back456",
      "local_basepath": "/projects/webapp/api",
      "remote_basepath": "/var/www/api"
    }
  }
}
```

**Admin subdirectory config** (`/projects/webapp/admin/.gsupload.json`):
```json
{
  "global_excludes": ["*.cache"],
  "bindings": {
    "admin-panel": {
      "protocol": "sftp",
      "hostname": "admin.example.com",
      "username": "admin",
      "password": "admin789",
      "local_basepath": "/projects/webapp/admin",
      "remote_basepath": "/var/admin"
    },
    "backend": {
      "hostname": "admin-api.example.com",
      "remote_basepath": "/var/www/admin-api"
    }
  }
}
```

**Resulting merged config when running from `/projects/webapp/admin/`:**
```json
{
  "global_excludes": [
    ".DS_Store",
    "Thumbs.db",
    "node_modules",
    ".env",
    "*.cache"
  ],
  "bindings": {
    "global-backup": {
      "protocol": "ftp",
      "hostname": "backup.example.com",
      "username": "backup",
      "password": "backup123",
      "local_basepath": "/projects",
      "remote_basepath": "/backups"
    },
    "frontend": {
      "protocol": "sftp",
      "hostname": "web.example.com",
      "username": "frontend",
      "password": "front123",
      "local_basepath": "/projects/webapp/public",
      "remote_basepath": "/var/www/public"
    },
    "backend": {
      "protocol": "sftp",
      "hostname": "admin-api.example.com",
      "username": "backend",
      "password": "back456",
      "local_basepath": "/projects/webapp/api",
      "remote_basepath": "/var/www/admin-api"
    },
    "admin-panel": {
      "protocol": "sftp",
      "hostname": "admin.example.com",
      "username": "admin",
      "password": "admin789",
      "local_basepath": "/projects/webapp/admin",
      "remote_basepath": "/var/admin"
    }
  }
}
```

**Key takeaways:**
- ✅ All 5 exclude patterns combined from 3 config files
- ✅ 4 bindings available: `global-backup` from global, `frontend` from project, `backend` merged, `admin-panel` new
- ✅ `backend` binding partially overridden: `hostname` and `remote_basepath` changed, other properties inherited
- ✅ Can use any of these bindings: `gsupload -b=global-backup`, `-b=frontend`, `-b=backend`, `-b=admin-panel`

---

### Use Cases for Layered Configurations

**Use Case 1: Development vs Production**
```
/project/.gsupload.json          # Dev settings with dev.example.com
/project/dist/.gsupload.json     # Production overrides with prod.example.com
```
Run from `/project/` for dev uploads, from `/project/dist/` for production.

**Use Case 2: Multi-environment Monorepo**
```
/monorepo/.gsupload.json                    # Shared excludes and common bindings
/monorepo/frontend/.gsupload.json           # Frontend-specific binding
/monorepo/backend/.gsupload.json            # Backend-specific binding
/monorepo/admin/.gsupload.json              # Admin-specific binding
```
Each directory has its own binding, all share global excludes.

**Use Case 3: Team-wide Defaults**
```
~/.gsupload/gsupload.json                   # Your personal global settings
/projects/team-app/.gsupload.json           # Team's shared project config (versioned in git)
```
Personal settings in home directory, project settings shared with team via version control.

---

### Configuration Priority Summary

When running from `/projects/myapp/subfolder/deep/`:

1. **First loaded (lowest priority):** `~/.gsupload/gsupload.json` or `~/.config/gsupload/gsupload.json`
2. `/projects/.gsupload.json` (if exists)
3. `/projects/myapp/.gsupload.json` (if exists)
4. `/projects/myapp/subfolder/.gsupload.json` (if exists)
5. `/projects/myapp/subfolder/deep/.gsupload.json` (if exists)
6. **Last merged (highest priority):** Closest to cwd

Each level can:
- ✅ Add new patterns to `global_excludes`
- ✅ Add new bindings
- ✅ Override properties of existing bindings
- ✅ Replace other top-level settings completely

### Example configuration file

```json
{
    "bindings": {
        "frontend": {
            "protocol": "sftp",
            "hostname": "example.com",
            "port": 22,
            "username": "user",
            "password": "password",
            "key_filename": "/path/to/private/key", 
            "local_basepath": "/Users/gustavo/dev/project",
            "remote_basepath": "/var/www/html"
        },
        "admin": {
            "protocol": "ftp",
            "hostname": "ftp.example.com",
            "port": 21,
            "username": "admin",
            "password": "secretpassword",
            "local_basepath": "/Users/gustavo/dev/project/admin",
            "remote_basepath": "/public_html/admin"
        }
    }
}
```

**Note:** `key_filename` is optional for SFTP if you use password authentication.

### Excludes

You can exclude files from being uploaded in three ways:

1.  **Global Excludes**: Add a `global_excludes` list to the top level of your configuration file.
2.  **Host Excludes**: Add an `excludes` list to a specific host configuration.
3.  **Folder Excludes**: Create a `.gsupload_ignore` file in any directory. The script walks up from the current directory to the project root, collecting all `.gsupload_ignore` files found along the way. Exclude patterns are **additive** - all ignore files in parent directories are also applied.

**Supported Patterns:**
- `*.log`: Matches any file ending in `.log` in any directory.
- `node_modules`: Matches any file or folder named `node_modules` in any directory.
- `/dist`: Matches `dist` folder only at the root (relative to `local_basepath` or `.gsupload_ignore` location).
- `src/*.tmp`: Matches `.tmp` files directly inside `src`.
- `src/**/*.tmp`: Matches `.tmp` files recursively inside `src`.

**Example configuration with excludes:**

```json
{
    "global_excludes": [
        ".DS_Store",
        "*.log",
        ".git"
    ],
    "bindings": {
        "frontend": {
            ...
            "excludes": [
                "node_modules",
                "secrets.js"
            ]
        }
    }
}
```

**Example `.gsupload_ignore`:**

```
# Ignore all temporary files
*.tmp
# Ignore specific config
local_config.php
```

## Usage

```bash
gsupload [OPTIONS] PATTERNS...
```

**Options:**
- `-r, --recursive` - Search for files recursively in subdirectories when using glob patterns
- `-vc, --visual-check` - Display tree comparison of local vs remote files before uploading
- `-vcc, --visual-check-complete` - Display complete tree comparison including remote-only files
- `--max-depth` - Maximum tree depth to display in visual check (default: 20)
- `-ts, --tree-summary` - Show summary statistics only, skip tree display in visual check
- `-f, --force` - Force upload without confirmation or remote file check (fastest mode)
- `-b, --binding` - Binding alias from configuration. If omitted, auto-detects from current directory

**Arguments:**
- `PATTERNS` - One or more file patterns, filenames, or directories to upload

**⚠️ IMPORTANT: Always Quote Glob Patterns!**

When using glob patterns (like `*.txt`, `*.css`, or `src/**/*.js`), you **MUST** quote them to prevent shell expansion. Without quotes, your shell will expand the pattern before `gsupload` sees it, which will cause unexpected behavior or errors.

```bash
# ✅ CORRECT - Pattern is quoted, gsupload handles the glob
gsupload -r "*.txt"
gsupload -b=frontend "*.css"
gsupload -b=backend "src/**/*.js"

# ❌ WRONG - Shell expands the pattern before gsupload sees it
gsupload -r *.txt       # Shell expands to: gsupload -r file1.txt file2.txt ...
gsupload -r src/**/*.js # May fail or behave unexpectedly
```

**Why this matters:** Without quotes, if you have `file1.txt` and `file2.txt` in your current directory and run `gsupload -r *.txt`, your shell will expand this to `gsupload -r file1.txt file2.txt`, which only uploads those two files instead of recursively finding all `.txt` files as intended.

### Examples

Upload all CSS files in the current directory (auto-detect binding):
```bash
gsupload "*.css"
```

Upload all CSS files using a specific binding:
```bash
gsupload -b=frontend "*.css"
# or
gsupload --binding=frontend "*.css"
```

Auto-detect binding from current directory:
```bash
gsupload "*.css"
```

Upload all CSS files recursively (including subdirectories):
```bash
gsupload -r -b=frontend "*.css"
```

Preview changes before uploading with visual tree comparison:
```bash
gsupload -vc -b=frontend "*.css"
```

Visual check with recursive search and custom tree depth:
```bash
gsupload -vc --max-depth=5 -r -b=backend "*.js"
```

Show summary statistics only (no tree display):
```bash
gsupload -vc -ts -b=frontend "*.html"
```

Upload a specific directory (always recursive for directories):
```bash
gsupload -b=frontend src/assets
```

Upload multiple specific files:
```bash
gsupload -b=frontend index.html style.css app.js
```

Upload with a specific pattern in a subdirectory:
```bash
gsupload -b=backend "src/**/*.js"
```

**Note:** If you installed locally without `uv tool`, use `python src/gsupload.py` instead of `gsupload`.

The script calculates the remote path relative to `local_basepath` defined in the configuration.
