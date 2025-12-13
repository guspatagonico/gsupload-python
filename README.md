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

Create a configuration file in one of the following locations (searched in this order):

1. **`.gsupload.json` in current directory or any parent directory** - The script walks up from your current working directory until it finds `.gsupload.json` (similar to how git finds `.git`). The filename starts with a dot (".") to keep it hidden in project directories.
2. `~/.gsupload/gsupload.json` - User-specific global configuration (no dot prefix)
3. `~/.config/gsupload/gsupload.json` - XDG config directory (no dot prefix)

**Example:** If you have `/projects/myapp/.gsupload.json` and run the command from `/projects/myapp/src/components/`, the script will find and use the `.gsupload.json` from the project root.

This allows you to:
- Keep one `.gsupload.json` at your project root (hidden by default)
- Run the upload command from any subdirectory within your project
- Have different configurations for different projects

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
