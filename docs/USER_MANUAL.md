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
# Clone repository (HTTPS)
git clone https://github.com/guspatagonico/gsupload-python.git
# or SSH (with password-protected key)
git clone git@github.com:guspatagonico/gsupload-python.git

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
      "max_workers": 5,
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
- `password` (optional): For SFTP, serves dual purpose:
  - SSH password authentication (when `key_filename` is omitted)
  - Passphrase to decrypt encrypted private key (when `key_filename` is provided)
  - For FTP: Login password
- `key_filename` (optional): Path to SSH private key (SFTP only)
  - Can be encrypted (requires `password` as passphrase) or unencrypted
  - If both `password` and `key_filename` are omitted, SSH agent authentication is used
- `local_basepath` (optional): Local root directory. Can be:
  - Absolute path: `/full/path/to/directory`
  - Relative path: `.`, `./dist`, `../sibling` (resolves from config file location)
  - Omitted: Defaults to directory containing config file
- `remote_basepath` (required): Remote root directory
- `max_workers` (optional): Number of parallel upload workers (default: 5)
  - **SFTP**: Parallel uploads work reliably with SSH multiplexing
  - **FTP**: Some servers limit concurrent connections per IP or may reject parallel uploads
    - Start with 1-2 workers for FTP and increase if server allows
    - If you experience connection errors or rejections, reduce to 1 (sequential)
  - Higher values increase upload speed but use more resources
  - Recommended: 5-10 for SFTP, 1-3 for FTP
  - Can be overridden with `--max-workers` CLI flag
- `excludes` (optional): Binding-specific exclude patterns
- `comments` (optional): Description displayed during operations

**Root Fields:**

- `global_excludes` (optional): Exclude patterns applied to all bindings
- `comments` (optional): Root-level description

### SFTP Authentication Methods

`gsupload` supports four authentication methods for SFTP connections:

#### 1. SSH Agent (Recommended)

Uses keys managed by your SSH agent (most secure, no credentials in config):

```json
{
  "protocol": "sftp",
  "hostname": "example.com",
  "username": "user"
  // No password or key_filename
}
```

**Requirements:**
- SSH agent running: `ssh-add -l` to verify
- Key added to agent: `ssh-add ~/.ssh/id_rsa`

**Advantages:**
- ✅ No credentials stored in config files
- ✅ Works with password-protected keys without storing passphrase
- ✅ Ideal for team environments and version control

#### 2. Password Authentication

Uses password for SSH authentication:

```json
{
  "protocol": "sftp",
  "hostname": "example.com",
  "username": "user",
  "password": "your-ssh-password"
}
```

**Use when:**
- Server requires password authentication
- SSH keys are not available

**Security note:** Store passwords in global config outside version control

#### 3. Unencrypted SSH Key

Uses private key file without passphrase:

```json
{
  "protocol": "sftp",
  "hostname": "example.com",
  "username": "user",
  "key_filename": "~/.ssh/id_rsa"
}
```

**Use when:**
- Automated deployments (CI/CD)
- Non-interactive scripts

**Security note:** Unencrypted keys should have restricted permissions (`chmod 600`)

#### 4. Encrypted SSH Key with Passphrase

Uses password-protected private key:

```json
{
  "protocol": "sftp",
  "hostname": "example.com",
  "username": "user",
  "key_filename": "~/.ssh/id_rsa_encrypted",
  "password": "key-passphrase"
}
```

**How it works:**
- The `password` field is used to decrypt the private key
- After decryption, the key authenticates with the server
- Most secure option when SSH agent is not available

**Use when:**
- Keys must be encrypted for security policy
- SSH agent cannot be used
- Personal deployments with encrypted keys

**Important:** When `key_filename` is provided, `password` is interpreted as the key passphrase, NOT the SSH login password.

#### Authentication Priority

If multiple methods are configured, authentication attempts in this order:

1. `key_filename` (if provided)
2. SSH agent (if no `password` or `key_filename`)
3. `password` (if provided without `key_filename`)
4. SSH keys in default locations (`~/.ssh/id_rsa`, etc.)

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

**Critical: Always quote patterns to prevent shell expansion**

**Why quotes are necessary:**
- Shell expansion happens **before** your program runs
- By the time `gsupload` receives arguments, the shell has already expanded `*.css` to `file1.css file2.css`  
- Your program never sees the original pattern
- This is fundamental to how all shells (bash, zsh, fish) work

**This is standard practice across Unix tools:**
- `find . -name "*.txt"` - requires quotes
- `grep "pattern" *.log` - requires quotes for the pattern
- `git add "*.js"` - requires quotes  
- `rsync "*.css" remote:/path/` - requires quotes

The requirement to quote patterns is correct and matches industry standards.

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
# Use binding config or default (5 workers)
gsupload "*.css"

# Override with more workers (faster, higher resource usage)
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

**Protocol-Specific Considerations:**

- **SFTP**: Parallel uploads work reliably. SSH multiplexing handles concurrent connections efficiently.
- **FTP**: Parallel uploads are supported but may be limited by server configuration:
  - Some servers limit concurrent connections per IP address
  - Some servers may reject or throttle parallel uploads
  - **Recommendation**: Start with 1-2 workers for FTP, increase if no issues occur
  - If you get connection errors, reduce `max_workers` to 1

You can configure workers in two ways:

#### 1. Per-Binding Configuration (Recommended)

Set `max_workers` in binding config for consistent performance:

```json
{
  "bindings": {
    "production-sftp": {
      "protocol": "sftp",
      "hostname": "fast-server.com",
      "max_workers": 10,  // SFTP handles many parallel connections
      ...
    },
    "staging-sftp": {
      "protocol": "sftp",
      "hostname": "slow-server.com",
      "max_workers": 3,   // Lower-capacity server
      ...
    },
    "legacy-ftp": {
      "protocol": "ftp",
      "hostname": "ftp.example.com",
      "max_workers": 1,   // Conservative for FTP (increase if server allows)
      ...
    }
  }
}
```

**Advantages:**
- ✅ Different servers get optimal worker count automatically
- ✅ Team members share same performance settings
- ✅ No need to remember CLI flags

#### 2. CLI Override

Override binding config with CLI flag:

```bash
# Use binding config value (or default 5)
gsupload "*.css"

# Override with CLI flag
gsupload --max-workers=10 "*.css"  # High-speed connection
gsupload --max-workers=3 "*.css"   # Slower connection
gsupload --max-workers=1 "*.css"   # Debugging
```

**When to use CLI override:**
- Testing different worker counts
- Temporary performance adjustments
- Debugging connection issues

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

A: Yes, SFTP supports multiple authentication methods:

1. **SSH Agent** (recommended - no credentials in config):
   ```json
   {
     "protocol": "sftp",
     "username": "user"
     // Omit password and key_filename
   }
   ```

2. **Unencrypted Key**:
   ```json
   {
     "protocol": "sftp",
     "username": "user",
     "key_filename": "~/.ssh/id_rsa"
   }
   ```

3. **Encrypted Key** (requires passphrase):
   ```json
   {
     "protocol": "sftp",
     "username": "user",
     "key_filename": "~/.ssh/id_rsa_encrypted",
     "password": "key-passphrase"
   }
   ```

See [SFTP Authentication Methods](#sftp-authentication-methods) for details.

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

A: Use SSH agent authentication (most secure):

```json
{
  "protocol": "sftp",
  "username": "user"
  // No password or key_filename - uses SSH agent
}
```

**Setup:**
```bash
# Start SSH agent
eval "$(ssh-agent -s)"

# Add your key (enter passphrase once)
ssh-add ~/.ssh/id_rsa

# Verify key is loaded
ssh-add -l
```

**Advantages:**
- ✅ No credentials in config files
- ✅ Works with encrypted keys
- ✅ Passphrase entered once per session
- ✅ Safe to commit config to version control

**Alternative:** Use unencrypted keys (less secure):
```json
{
  "key_filename": "~/.ssh/id_rsa"
}
```

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