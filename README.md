# gsupload-python

A Python script to sync files and folders to a remote FTP/SFTP server based on a configuration file.

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
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
python src/gsupload.py {filename | directory_name | glob} {host alias}
```

### Examples

Upload all CSS files to the `frontend` host:
```bash
python src/gsupload.py *.css frontend
```

Upload a specific directory:
```bash
python src/gsupload.py src/assets frontend
```

Upload multiple specific files:
```bash
python src/gsupload.py index.html style.css frontend
```

The script calculates the remote path relative to `local_basepath` defined in the configuration.
