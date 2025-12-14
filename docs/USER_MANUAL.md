# gsupload User Manual

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [File Patterns & Exclusions](#file-patterns--exclusions)
6. [Usage Examples](#usage-examples)
7. [Advanced Features](#advanced-features)
8. [Troubleshooting](#troubleshooting)
9. [Performance Optimization](#performance-optimization)
10. [FAQ](#faq)

---

## Introduction

`gsupload` is a Python tool for syncing files and directories to remote FTP/SFTP servers using configuration-based aliases. It provides:

- **Configuration-based deployment** - Define multiple deployment targets in config files
- **Hierarchical configuration** - Global, project, and subdirectory configs with inheritance
- **Smart file exclusion** - Gitignore-style patterns with `.gsupload_ignore` files
- **Visual tree comparison** - See what will change before uploading
- **Parallel uploads** - Multi-threaded transfers with SSH compression
- **Auto-detection** - Automatically selects the right binding from your directory

### Key Features

✅ FTP and SFTP protocol support  
✅ Recursive file pattern matching  
✅ Layered configuration with inheritance  
✅ Visual diff before upload  
✅ Parallel uploads (5 workers by default)  
✅ SSH compression for SFTP  
✅ Binding auto-detection  
✅ Flexible exclude patterns  

---

## Installation

### Option 1: Global Tool Installation (Recommended)

Install globally with `uv` for system-wide access:

```bash
# Install the tool
uv tool install --editable /path/to/gsupload-python

# Update shell configuration
uv tool update-shell

# Restart shell, then use from anywhere
gsupload --help
```

After installation, `gsupload` is available from any directory without activating a virtual environment.

### Option 2: Local Development Setup

For development or testing:

```bash
# Clone repository
git clone <repository-url>
cd gsupload-python

# Install dependencies
uv pip install -r requirements.txt

# Run directly
python src/gsupload.py [OPTIONS] PATTERNS... HOST_ALIAS
```

### Requirements

- **Python**: 3.9+
- **Dependencies**: `click`, `paramiko` (installed automatically)

---

## Quick Start

### 1. Create Configuration File

Create `.gsupload.json` in your project root:

```json
{
  "global_excludes": [".DS_Store", "*.log", ".git"],
  "bindings": {
    "production": {
      "protocol": "sftp",
      "hostname": "example.com",
      "port": 22,
      "username": "deploy",
      "password": "your-password",
      "local_basepath": "/path/to/your/project",
      "remote_basepath": "/var/www/html"
    }
  }
}
```

### 2. Upload Files

```bash
# Upload all CSS files (with confirmation)
gsupload "*.css"

# Upload without confirmation (fast mode)
gsupload -f "*.css"

# Upload specific files
gsupload index.html style.css app.js
```

**Important**: Always quote glob patterns to prevent shell expansion.

---

## Configuration

### Configuration File Locations

The tool searches for configuration files in this order:

1. **Project configs** (walked up from current directory):
   - `.gsupload.json` files from current directory to filesystem root
2. **Global configs**:
   - `~/.gsupload/gsupload.json`
   - `~/.config/gsupload/gsupload.json`

### Configuration Merging

Configurations are **merged with inheritance** - deeper configs override shallower ones:

```
~/.gsupload/gsupload.json          # Global base (lowest priority)
/projects/.gsupload.json           # Project root
/projects/webapp/.gsupload.json    # Subdirectory (highest priority)
```

#### Merging Rules

| Key               | Strategy                 | Behavior                               |
| ----------------- | ------------------------ | -------------------------------------- |
| `global_excludes` | **Additive**             | All patterns combined from all configs |
| `bindings`        | **Per-binding Override** | Each binding independently merged      |
| Other keys        | **Simple Override**      | Deeper value replaces shallower value  |

### Configuration Schema

```json
{
  "comments": "Optional: Root-level description",
  "global_excludes": ["pattern1", "pattern2"],
  "global_excludes_comments": "Optional: Excludes description",
  "bindings": {
    "binding-alias": {
      "comments": "Optional: Binding description",
      "protocol": "sftp",
      "hostname": "example.com",
      "port": 22,
      "username": "user",
      "password": "password",
      "key_filename": "/path/to/key",
      "local_basepath": "/local/path",
      "remote_basepath": "/remote/path",
      "excludes": ["pattern1", "pattern2"],
      "excludes_comments": "Optional: Binding excludes description"
    }
  }
}
```

#### Field Descriptions

**Binding Fields:**

- `protocol` (required): `"ftp"` or `"sftp"`
- `hostname` (required): Server hostname or IP
- `port` (optional): Port number (default: 21 for FTP, 22 for SFTP)
- `username` (required): Login username
- `password` (optional): Login password (can use `key_filename` for SFTP instead)
- `key_filename` (optional): Path to SSH private key (SFTP only)
- `local_basepath` (optional): Local root directory. Can be:
  - Absolute path: `/full/path/to/directory`
  - Relative path: `.`, `./dist`, `../sibling` (resolves from config file location)
  - Omitted: Defaults to directory containing config file
- `remote_basepath` (required): Remote root directory
- `excludes` (optional): Binding-specific exclude patterns
- `comments` (optional): Description displayed during operations

**Root Fields:**

- `global_excludes` (optional): Exclude patterns applied to all bindings
- `comments` (optional): Root-level description

### Example: Multi-Environment Setup

**Project structure:**

```
/project/.gsupload.json           # Development config
/project/dist/.gsupload.json      # Production overrides
```

**Development config** (`/project/.gsupload.json`):

```json
{
  "global_excludes": ["*.log", ".git"],
  "bindings": {
    "app": {
      "protocol": "sftp",
      "hostname": "dev.example.com",
      "username": "devuser",
      "password": "devpass",
      "local_basepath": ".",
      "remote_basepath": "/var/www/dev"
    }
  }
}
```

**Production config** (`/project/dist/.gsupload.json`):

```json
{
  "global_excludes": ["*.map"],
  "bindings": {
    "app": {
      "hostname": "prod.example.com",
      "username": "produser",
      "password": "prodpass",
      "remote_basepath": "/var/www/production"
    }
  }
}
```

**Merged config when running from `/project/dist/`:**

- `global_excludes`: `["*.log", ".git", "*.map"]` (combined)
- `app` binding:
  - `hostname`: `prod.example.com` (overridden)
  - `protocol`, `port`: Inherited from parent
  - `username`, `password`: Overridden
  - `remote_basepath`: Overridden

### Inspecting Configuration

View merged configuration with source annotations:

```bash
gsupload --show-config
```

**Output:**

```
📋 Configuration Files (merge order):
  1. /Users/user/.gsupload/gsupload.json
  2. /projects/webapp/.gsupload.json

🔀 Merged Configuration:
{
  "global_excludes": ["*.log", ".git"],
  "bindings": { ... }
}

📍 Source Annotations:

  global_excludes:
    • *.log
      ↳ from: /projects/webapp/.gsupload.json
    ...
```

---

## File Patterns & Exclusions

### Glob Patterns

`gsupload` supports standard glob patterns:

| Pattern       | Matches                        |
| ------------- | ------------------------------ |
| `*.css`       | All CSS files                  |
| `*.{js,jsx}`  | JS and JSX files               |
| `src/**/*.js` | JS files recursively in `src/` |
| `index.html`  | Specific file                  |

**Critical**: Always quote patterns to prevent shell expansion:

```bash
# ✅ Correct
gsupload "*.css"

# ❌ Wrong - shell expands before gsupload sees it
gsupload *.css
```

### Exclusion Methods

Files can be excluded three ways (all are additive):

#### 1. Global Excludes

In configuration file:

```json
{
  "global_excludes": [
    ".DS_Store",
    "*.log",
    ".git",
    "node_modules"
  ]
}
```

#### 2. Binding-Specific Excludes

```json
{
  "bindings": {
    "frontend": {
      ...
      "excludes": [
        "*.tmp",
        "secrets.js"
      ]
    }
  }
}
```

#### 3. `.gsupload_ignore` Files

Create `.gsupload_ignore` in any directory:

```
# Ignore patterns
*.tmp
*.cache
local_config.php
```

**Discovery**: The tool walks up from current directory to `local_basepath`, collecting all `.gsupload_ignore` files (additive).

### Pattern Syntax

Patterns follow gitignore-style syntax:

| Pattern        | Behavior                                    |
| -------------- | ------------------------------------------- |
| `*.log`        | Matches `.log` files anywhere               |
| `node_modules` | Matches `node_modules` file/folder anywhere |
| `/dist`        | Matches `dist` only at root                 |
| `src/*.tmp`    | Matches `.tmp` files directly in `src`      |
| `src/**/*.tmp` | Matches `.tmp` files recursively in `src`   |
| `build/`       | Matches only directories named `build`      |

### Debugging Exclusions

List ignored files:

```bash
# List all ignored files (recursive)
gsupload --show-ignored

# Current directory only
gsupload --show-ignored -nr

# For specific binding
gsupload --show-ignored -b=frontend
```

**Output:**

```
🚫 Ignored Files and Directories:
Scanning from: /projects/webapp
Mode: Recursive

Active exclude patterns:
  • .DS_Store
  • node_modules
  • *.log

Found 6 ignored items:

📄 .DS_Store
📁 node_modules
📄 test.log
```

---

## Usage Examples

### Basic Upload

```bash
# Auto-detect binding, recursive search, show complete tree
gsupload "*.css"

# Specify binding explicitly
gsupload -b=frontend "*.js"

# Upload specific files
gsupload index.html style.css app.js
```

### Recursive Patterns

```bash
# Recursively find all CSS files (default)
gsupload "*.css"

# Recursively find all JS files in src/
gsupload "src/**/*.js"

# Disable recursive search (current directory only)
gsupload -nr "*.css"
```

### Visual Checks

```bash
# Default: Show complete tree including remote-only files
gsupload "*.css"

# Show only files that will change (faster)
gsupload -vc "*.css"

# Force mode: No confirmation, no tree (fastest)
gsupload -f "*.css"

# Disable visual check completely
gsupload -nvcc "*.css"

# Custom tree depth
gsupload --max-depth=10 "*.css"

# Summary only (no tree display)
gsupload -vc -ts "*.css"
```

### Multiple Files & Directories

```bash
# Upload all files in directory
gsupload src/assets

# Upload multiple directories
gsupload dist/ public/

# Mix patterns and specific files
gsupload "*.html" app.js style.css
```

### Binding Selection

```bash
# Auto-detect from current directory
gsupload "*.css"

# Explicit binding
gsupload -b=frontend "*.css"
gsupload --binding=production "*.js"

# List available bindings
gsupload --show-config
```

### Performance Tuning

```bash
# Default: 5 parallel workers
gsupload "*.css"

# More workers (faster, higher resource usage)
gsupload --max-workers=10 "*.css"

# Single worker (sequential, for debugging)
gsupload --max-workers=1 "*.css"
```

### FTP Mode Selection

```bash
# Default: Passive mode (recommended)
gsupload "*.css"

# Active mode (for restrictive firewalls)
gsupload --ftp-active "*.css"
```

### Workflow Examples

**Deploy frontend assets:**

```bash
cd /project/frontend
gsupload -f "dist/**/*.{js,css,html}"
```

**Update specific page:**

```bash
cd /project/pages
gsupload about.html about.css
```

**Sync entire directory:**

```bash
cd /project
gsupload public/
```

**Production deployment with verification:**

```bash
cd /project/dist
gsupload -vcc "**/*"  # Review changes
# Confirm, then upload
```

---

## Advanced Features

### Auto-Detection

If no binding specified with `-b`, `gsupload` automatically selects binding by matching current directory with `local_basepath`:

```bash
cd /projects/webapp/frontend
gsupload "*.css"  # Auto-detects "frontend" binding
```

**Conflict resolution**: If multiple bindings match, you'll be prompted to choose:

```
⚠️  WARNING: Multiple bindings detected for path: /projects/webapp

  1. frontend - SFTP to app.example.com
  2. staging - FTP to staging.example.com
  0. Cancel and exit

Select binding [1]:
```

### Configuration Comments

Add descriptive comments to configurations:

```json
{
  "comments": "Production deployment config for main website",
  "global_excludes_comments": "Exclude system and build artifacts",
  "bindings": {
    "frontend": {
      "comments": "Frontend assets to CDN",
      "excludes_comments": "Skip source maps in production",
      ...
    }
  }
}
```

Comments are displayed during operations:

```
💬 Production deployment config for main website
📝 Frontend assets to CDN
```

### Tree Comparison Modes

Three visual check modes:

#### Complete Tree (Default)

Shows all files including remote-only:

```bash
gsupload "*.css"  # or gsupload -vcc "*.css"
```

**Output:**

```
📂 File Comparison Tree - Complete (max depth: 20):

├── index.html [NEW]
├── style.css [OVERWRITE]
└── old.css [REMOTE ONLY]

Summary:
  New files:          1
  Files to overwrite: 1
  Remote only:        1
```

#### Changes Only

Shows only files that will be uploaded:

```bash
gsupload -vc "*.css"
```

**Output:**

```
📂 File Comparison Tree - Changes Only (max depth: 20):

├── index.html [NEW]
└── style.css [OVERWRITE]

... (remote-only files not shown)

Summary:
  New files:          1
  Files to overwrite: 1
  Remote only:        1
```

#### No Visual Check (Force Mode)

Skips tree and uploads immediately:

```bash
gsupload -f "*.css"
```

Fastest mode for CI/CD pipelines.

### Parallel Uploads

Default: 5 parallel workers with SSH compression (SFTP) or passive mode (FTP).

```bash
# Adjust worker count based on server capacity
gsupload --max-workers=10 "*.css"  # High-speed connection
gsupload --max-workers=3 "*.css"   # Slower connection
gsupload --max-workers=1 "*.css"   # Debugging
```

**Performance impact**: See [PERFORMANCE.md](../PERFORMANCE.md) for benchmarks.

### Inspection Tools

```bash
# View merged configuration
gsupload --show-config

# List ignored files
gsupload --show-ignored

# List ignored files for specific binding
gsupload --show-ignored -b=frontend

# List ignored in current directory only
gsupload --show-ignored -nr
```

---

## Troubleshooting

### Common Issues

#### "Configuration file not found"

**Problem**: No `.gsupload.json` found in directory tree or home directory.

**Solution**:

```bash
# Create config in project root
cd /path/to/project
nano .gsupload.json
```

Or create global config:

```bash
mkdir -p ~/.gsupload
nano ~/.gsupload/gsupload.json
```

#### "Could not auto-detect binding"

**Problem**: Current directory doesn't match any `local_basepath`.

**Solution**: Specify binding explicitly:

```bash
# List available bindings
gsupload --show-config

# Use specific binding
gsupload -b=frontend "*.css"
```

#### "No files found for pattern"

**Problem**: Pattern matches no files or files are excluded.

**Solutions**:

1. Check pattern syntax:
   ```bash
   # Ensure pattern is quoted
   gsupload "*.css"
   ```

2. Verify files exist:
   ```bash
   ls *.css
   ```

3. Check exclusions:
   ```bash
   gsupload --show-ignored
   ```

4. Enable recursive mode:
   ```bash
   gsupload -r "*.css"
   ```

#### "File is not within local basepath"

**Problem**: Trying to upload file outside `local_basepath`.

**Solution**: Ensure `local_basepath` encompasses target files:

```json
{
  "bindings": {
    "app": {
      "local_basepath": "/projects/webapp",  // Not /projects/webapp/dist
      ...
    }
  }
}
```

#### SFTP Connection Timeout

**Problem**: Connection hangs or times out.

**Solutions**:

1. **Increase timeout**: Tool retries with progressive timeouts (120s → 240s)
2. **Check firewall**: Ensure port 22 is open
3. **Test connection**:
   ```bash
   ssh user@hostname
   ```
4. **Use password instead of key**:
   ```json
   {
     "password": "your-password"  // Instead of key_filename
   }
   ```

#### FTP Passive Mode Issues

**Problem**: FTP connection fails with "Connection refused".

**Solution**: Try active mode:

```bash
gsupload --ftp-active "*.css"
```

**Note**: Most networks require passive mode. Active mode may fail behind NAT/firewalls.

### Debug Mode

For detailed error information:

```bash
# Run with Python directly to see full traceback
python src/gsupload.py "*.css"
```

### Logs & Errors

Error messages follow this format:

```
❌ /path/to/file.css (Connection timeout)
```

Successful uploads:

```
✅ /path/to/file.css → /var/www/html/file.css
```

---

## Performance Optimization

### Parallel Uploads

Default: 5 workers (optimal for most scenarios)

**Recommendations:**

- **Fast connection**: `--max-workers=10`
- **Slow connection**: `--max-workers=3`
- **Unstable connection**: `--max-workers=1`

### SSH Compression (SFTP)

Enabled automatically for SFTP connections. Reduces transfer time for text files by ~40-60%.

### Skip Visual Check

For CI/CD pipelines:

```bash
gsupload -f "*.css"  # Force mode (fastest)
```

Skips remote file listing and confirmation.

### Partial Tree Comparison

For faster checks:

```bash
gsupload -vc "*.css"  # Changes only (faster than complete tree)
```

### FTP Passive Mode

Passive mode (default) is faster and more reliable than active mode for most networks.

### Benchmarks

See [PERFORMANCE.md](../PERFORMANCE.md) for detailed benchmarks showing:

- **5x faster** with 5 workers vs sequential
- **60% reduction** in transfer time with SSH compression
- **20-30s saved** by skipping visual check in force mode

---

## FAQ

### General

**Q: What protocols are supported?**

A: FTP and SFTP. Configure with `"protocol": "ftp"` or `"protocol": "sftp"`.

**Q: Can I use SSH keys instead of passwords?**

A: Yes, for SFTP:

```json
{
  "protocol": "sftp",
  "key_filename": "/path/to/private_key"
}
```

**Q: How do I deploy to multiple environments?**

A: Create multiple bindings:

```json
{
  "bindings": {
    "dev": { "hostname": "dev.example.com", ... },
    "staging": { "hostname": "staging.example.com", ... },
    "production": { "hostname": "prod.example.com", ... }
  }
}
```

Then use:

```bash
gsupload -b=dev "*.css"
gsupload -b=production "*.css"
```

### Configuration

**Q: Can I use relative paths in `local_basepath`?**

A: Yes, relative to config file location:

```json
{
  "local_basepath": ".",      // Config file's directory
  "local_basepath": "./dist", // dist/ subdirectory
  "local_basepath": "../app"  // Parent's app/ sibling
}
```

**Q: How does configuration merging work?**

A: Configs are merged from global → project root → current directory:

- `global_excludes`: Additive (all patterns combined)
- `bindings`: Per-binding merge (deeper values override)
- Other keys: Simple override

See [Configuration Merging](#configuration-merging) for examples.

**Q: Can I override just one field in a binding?**

A: Yes, only specify fields to override:

```json
// Parent config
{
  "bindings": {
    "app": {
      "protocol": "sftp",
      "hostname": "dev.example.com",
      "username": "devuser"
    }
  }
}

// Child config (overrides only hostname)
{
  "bindings": {
    "app": {
      "hostname": "prod.example.com"
    }
  }
}
```

### Usage

**Q: Why must I quote glob patterns?**

A: Without quotes, your shell expands the pattern before `gsupload` sees it:

```bash
# Shell expands to: gsupload file1.css file2.css
gsupload *.css

# Correct: gsupload receives the pattern
gsupload "*.css"
```

**Q: How do I upload an entire directory?**

A: Specify the directory:

```bash
gsupload dist/
gsupload src/assets/
```

All files are recursively included (unless excluded).

**Q: Can I see what will change before uploading?**

A: Yes, visual check is enabled by default:

```bash
gsupload "*.css"  # Shows tree comparison and asks confirmation
```

Skip it with `-f` (force mode).

**Q: How do I disable recursive search?**

A: Use `-nr`:

```bash
gsupload -nr "*.css"  # Only current directory
```

**Q: What's the difference between `-vc` and `-vcc`?**

A:

- `-vcc` (default): Complete tree including remote-only files
- `-vc`: Changes only (new/overwrite), excludes remote-only files
- `-f`: No visual check (fastest)

### Exclusions

**Q: Do exclude patterns apply recursively?**

A: Yes, patterns like `node_modules` match anywhere in the tree.

**Q: How do I exclude only at the root?**

A: Prefix with `/`:

```json
{
  "global_excludes": [
    "/dist"  // Only dist/ at root
  ]
}
```

**Q: Are `.gsupload_ignore` files inherited?**

A: Yes, the tool walks up from current directory to `local_basepath`, combining all `.gsupload_ignore` files found.

**Q: How do I debug exclusions?**

A: Use `--show-ignored`:

```bash
gsupload --show-ignored
```

### Performance

**Q: How can I speed up uploads?**

A:

1. Increase workers: `--max-workers=10`
2. Skip visual check: `-f`
3. Use changes-only check: `-vc`
4. Use SFTP (has compression)

**Q: Why is remote scanning slow?**

A: Remote directory listing requires traversing the entire tree. Use:

- `-vc` (changes only, faster)
- `-f` (skip entirely)

**Q: Does parallel upload work for FTP?**

A: Yes, but less effective than SFTP due to FTP protocol limitations.

### Security

**Q: How do I avoid storing passwords in config?**

A:

1. Use SSH keys (SFTP):
   ```json
   {
     "key_filename": "~/.ssh/id_rsa"
   }
   ```

2. Use environment variables (requires manual editing):
   ```json
   {
     "password": "$ENV_VAR"
   }
   ```

   Then set `ENV_VAR` in your shell.

**Q: Are credentials sent securely?**

A:

- **SFTP**: Yes, all traffic is encrypted
- **FTP**: No, credentials and data sent in plaintext. Use SFTP for production.

**Q: Can I share configs with my team?**

A: Yes, but:

1. Use global config for credentials:
   ```
   ~/.gsupload/gsupload.json  # Personal credentials (not in git)
   ```

2. Project config for paths/settings:
   ```
   /project/.gsupload.json    # Paths and excludes (in git)
   ```

3. Override credentials in global config.

---

## Additional Resources

- **README**: [README.md](../README.md) - Quick reference
- **Performance Guide**: [PERFORMANCE.md](../PERFORMANCE.md) - Detailed benchmarks
- **Changelog**: [CHANGELOG.md](../CHANGELOG.md) - Version history
- **Example Config**: [gsupload.json.example](../gsupload.json.example) - Sample configuration

---

## Support

For issues, feature requests, or questions:

1. Check this manual and [README.md](../README.md)
2. Review [Troubleshooting](#troubleshooting) section
3. Open an issue in the repository

🥑
