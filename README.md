# gsupload-python

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

Create a `hosts.json` file in one of the following locations:
- Current directory (`./hosts.json`)
- `~/.gsupload/hosts.json`
- `~/.config/gsupload/hosts.json`

### Example `hosts.json`

```json
{
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
```

**Note:** `key_filename` is optional for SFTP if you use password authentication.

### Excludes

You can exclude files from being uploaded in three ways:

1.  **Global Excludes**: Add a `global_excludes` list to the top level of `hosts.json`.
2.  **Host Excludes**: Add an `excludes` list to a specific host configuration in `hosts.json`.
3.  **Folder Excludes**: Create a `.gsuploadignore` file in any directory.

**Supported Patterns:**
- `*.log`: Matches any file ending in `.log` in any directory.
- `node_modules`: Matches any file or folder named `node_modules` in any directory.
- `/dist`: Matches `dist` folder only at the root (relative to `local_basepath` or `.gsuploadignore` location).
- `src/*.tmp`: Matches `.tmp` files directly inside `src`.
- `src/**/*.tmp`: Matches `.tmp` files recursively inside `src`.

**Example `hosts.json` with excludes:**

```json
{
    "global_excludes": [
        ".DS_Store",
        "*.log",
        ".git"
    ],
    "frontend": {
        ...
        "excludes": [
            "node_modules",
            "secrets.js"
        ]
    }
}
```

**Example `.gsuploadignore`:**

```
# Ignore all temporary files
*.tmp
# Ignore specific config
local_config.php
```

## Usage

```bash
gsupload [OPTIONS] PATTERNS... HOST_ALIAS
```

**Options:**
- `-r, --recursive` - Search for files recursively in subdirectories when using glob patterns

**Arguments:**
- `PATTERNS` - One or more file patterns, filenames, or directories to upload
- `HOST_ALIAS` - The host configuration name from hosts.json

### Examples

Upload all CSS files in the current directory only:
```bash
gsupload *.css frontend
```

Upload all CSS files recursively (including subdirectories):
```bash
gsupload -r *.css frontend
```

Upload a specific directory (always recursive for directories):
```bash
gsupload src/assets frontend
```

Upload multiple specific files:
```bash
gsupload index.html style.css app.js frontend
```

Upload with a specific pattern in a subdirectory:
```bash
gsupload src/**/*.js backend
```

**Note:** If you installed locally without `uv tool`, use `python src/gsupload.py` instead of `gsupload`.

The script calculates the remote path relative to `local_basepath` defined in the configuration.
