#!/usr/bin/env python3
"""
gsupload - Sync files and folders to remote FTP/SFTP servers

Author: Gustavo Adrián Salvini
Email: gsalvini@ecimtech.com
GitHub: https://github.com/guspatagonico

License: MIT License
Copyright (c) 2025 Gustavo Adrián Salvini

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import json
import os
import sys
import glob
import ftplib
import socket
import click
import paramiko
import fnmatch
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

__version__ = "1.0.0a0"
DEFAULT_MAX_DEPTH = 20

# Suppress paramiko's verbose error messages
logging.getLogger("paramiko").setLevel(logging.CRITICAL)


def display_comment(comment: str, prefix: str = "💬"):
    """Display a comment with appropriate styling."""
    if comment:
        click.echo(click.style(f"{prefix} {comment}", fg="cyan"))


def load_config_with_sources() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load and merge configuration files with source tracking.

    Returns:
        Tuple of (merged_config, source_map) where source_map tracks which file
        contributed each piece of configuration
    """
    configs_to_merge = []
    source_map = {
        "global_excludes": {},
        "bindings": {},
        "config_files": [],
    }

    # First, try to load global config as base
    global_locations = [
        Path.home() / ".gsupload" / "gsupload.json",
        Path.home() / ".config" / "gsupload" / "gsupload.json",
    ]

    for loc in global_locations:
        if loc.exists():
            try:
                with open(loc, "r") as f:
                    configs_to_merge.append((loc, json.load(f)))
                    source_map["config_files"].append(str(loc))
                    break
            except json.JSONDecodeError as e:
                click.echo(f"Warning: Failed to parse '{loc}': {e}", err=True)

    # Collect all .gsupload.json files from root down to cwd
    project_configs = []
    current_dir = Path.cwd()

    while True:
        candidate = current_dir / ".gsupload.json"
        if candidate.exists():
            project_configs.append(candidate)

        # Move to parent directory
        parent = current_dir.parent
        if parent == current_dir:
            # Reached filesystem root
            break
        current_dir = parent

    # Reverse to process from root to cwd (shallowest to deepest)
    project_configs.reverse()

    # Load project configs
    for config_path in project_configs:
        try:
            with open(config_path, "r") as f:
                configs_to_merge.append((config_path, json.load(f)))
                source_map["config_files"].append(str(config_path))
        except json.JSONDecodeError as e:
            click.echo(f"Warning: Failed to parse '{config_path}': {e}", err=True)

    if not configs_to_merge:
        searched_paths = global_locations + [Path.cwd() / ".gsupload.json"]
        click.echo(
            f"Error: Configuration file not found. Checked: {', '.join(str(p) for p in searched_paths)}",
            err=True,
        )
        sys.exit(1)

    # Merge all configs with source tracking
    merged_config = {}
    all_global_excludes = []

    for config_path, config in configs_to_merge:
        config_path_str = str(config_path)

        # Track global_excludes with source
        if "global_excludes" in config:
            for pattern in config["global_excludes"]:
                if pattern not in source_map["global_excludes"]:
                    source_map["global_excludes"][pattern] = []
                source_map["global_excludes"][pattern].append(config_path_str)
            all_global_excludes.extend(config["global_excludes"])

        # Merge bindings with source tracking
        if "bindings" in config:
            if "bindings" not in merged_config:
                merged_config["bindings"] = {}

            for binding_name, binding_config in config["bindings"].items():
                # Track binding source
                if binding_name not in source_map["bindings"]:
                    source_map["bindings"][binding_name] = {
                        "defined_in": [],
                        "properties": {},
                    }

                source_map["bindings"][binding_name]["defined_in"].append(
                    config_path_str
                )

                # Resolve local_basepath relative to config file location
                if "local_basepath" in binding_config:
                    local_basepath_str = binding_config["local_basepath"]
                    local_basepath_path = Path(local_basepath_str).expanduser()

                    if not local_basepath_path.is_absolute():
                        local_basepath_path = (
                            config_path.parent / local_basepath_path
                        ).resolve()
                    else:
                        local_basepath_path = local_basepath_path.resolve()

                    binding_config = binding_config.copy()
                    binding_config["local_basepath"] = str(local_basepath_path)
                elif binding_name not in merged_config["bindings"]:
                    binding_config = binding_config.copy()
                    binding_config["local_basepath"] = str(config_path.parent.resolve())

                # Track each property's source
                for prop_key, prop_value in binding_config.items():
                    if (
                        prop_key
                        not in source_map["bindings"][binding_name]["properties"]
                    ):
                        source_map["bindings"][binding_name]["properties"][
                            prop_key
                        ] = []
                    source_map["bindings"][binding_name]["properties"][prop_key].append(
                        config_path_str
                    )

                if binding_name in merged_config["bindings"]:
                    merged_config["bindings"][binding_name].update(binding_config)
                else:
                    merged_config["bindings"][binding_name] = binding_config

        # Other top-level keys: simple override
        for key in config:
            if key not in ["global_excludes", "bindings"]:
                merged_config[key] = config[key]

    # Set the combined global_excludes
    if all_global_excludes:
        merged_config["global_excludes"] = all_global_excludes

    return merged_config, source_map


def load_config() -> Dict[str, Any]:
    """
    Load and merge configuration files with inheritance.

    Search order and merging:
    1. Load global config from ~/.gsupload/gsupload.json or ~/.config/gsupload/gsupload.json (base)
    2. Walk up from cwd collecting all .gsupload.json files
    3. Merge configs from root to current directory (deeper configs override)

    Merging rules:
    - global_excludes: Additive (all patterns from all configs are combined)
    - bindings: Deeper configs can override or add new bindings (deep merge per binding)
    - Other top-level keys: Deeper configs override

    Returns:
        Dictionary containing merged host configurations
    """
    merged_config, _ = load_config_with_sources()
    return merged_config


def get_host_config(config: Dict[str, Any], alias: str) -> Dict[str, Any]:
    bindings = config.get("bindings", {})
    if alias not in bindings:
        click.echo(f"Error: Host alias '{alias}' not found in configuration.", err=True)
        sys.exit(1)
    return bindings[alias]


def display_config(merged_config: Dict[str, Any], source_map: Dict[str, Any]) -> None:
    """
    Display merged configuration with source annotations.

    Shows:
    1. List of config files in merge order
    2. Merged configuration as colored JSON
    3. Source annotations for each item

    Args:
        merged_config: The final merged configuration
        source_map: Dictionary tracking sources for each config item
    """
    # Display config files in merge order
    click.echo(
        click.style("\n📋 Configuration Files (merge order):", fg="cyan", bold=True)
    )
    for i, config_file in enumerate(source_map["config_files"], 1):
        click.echo(f"  {i}. {config_file}")

    # Display merged configuration with colors
    click.echo(click.style("\n🔀 Merged Configuration:", fg="cyan", bold=True))
    formatted_json = json.dumps(merged_config, indent=2)
    click.echo(click.style(formatted_json, fg="green"))

    # Display source annotations
    click.echo(click.style("\n📍 Source Annotations:", fg="cyan", bold=True))

    # Global excludes
    if source_map.get("global_excludes"):
        click.echo(click.style("\n  global_excludes:", fg="yellow", bold=True))
        for pattern, sources in source_map["global_excludes"].items():
            sources_str = ", ".join(str(s) for s in sources)
            click.echo(f"    • {click.style(pattern, fg='white')}")
            click.echo(f"      ↳ from: {click.style(sources_str, fg='blue')}")

    # Bindings
    if source_map.get("bindings"):
        click.echo(click.style("\n  bindings:", fg="yellow", bold=True))
        for binding_name, binding_info in source_map["bindings"].items():
            click.echo(f"    • {click.style(binding_name, fg='white', bold=True)}")

            # Show where binding was defined
            defined_in_str = ", ".join(str(s) for s in binding_info["defined_in"])
            click.echo(
                f"      ↳ defined in: {click.style(defined_in_str, fg='blue', dim=True)}"
            )

            # Show source for each property
            if binding_info.get("properties"):
                for prop, sources in binding_info["properties"].items():
                    sources_str = ", ".join(str(s) for s in sources)
                    click.echo(
                        f"        - {click.style(prop, fg='magenta')}: from {click.style(sources_str, fg='blue', dim=True)}"
                    )


def list_ignored_files(
    local_basepath: Path, excludes: List[str], recursive: bool = True
) -> None:
    """
    List all files and directories that are being ignored by exclude patterns.

    Args:
        local_basepath: Base directory to scan from
        excludes: List of exclude patterns to apply
        recursive: If True, scan subdirectories recursively
    """
    click.echo(click.style("\n🚫 Ignored Files and Directories:", fg="cyan", bold=True))
    click.echo(f"Scanning from: {local_basepath}")
    click.echo(f"Mode: {'Recursive' if recursive else 'Current directory only'}\n")

    if not excludes:
        click.echo(click.style("No exclude patterns configured.", dim=True))
        return

    # Display active exclude patterns
    click.echo(click.style("Active exclude patterns:", fg="yellow"))
    for pattern in excludes:
        click.echo(f"  • {click.style(pattern, fg='white')}")
    click.echo()

    ignored_items = []
    scanned_count = 0

    def scan_directory(directory: Path, depth: int = 0):
        nonlocal scanned_count

        try:
            entries = sorted(directory.iterdir())
        except (OSError, PermissionError):
            return

        for entry in entries:
            scanned_count += 1

            # Check if this item is excluded
            if is_excluded(entry, excludes, local_basepath):
                try:
                    rel_path = entry.relative_to(local_basepath)
                    item_type = "📁" if entry.is_dir() else "📄"
                    ignored_items.append((str(rel_path), item_type, depth))
                except ValueError:
                    pass
                continue  # Don't descend into excluded directories

            # If not excluded and it's a directory, scan it recursively
            if recursive and entry.is_dir():
                scan_directory(entry, depth + 1)

    scan_directory(local_basepath)

    # Display ignored items
    if ignored_items:
        click.echo(
            click.style(
                f"Found {len(ignored_items)} ignored items:", fg="red", bold=True
            )
        )
        click.echo()

        for rel_path, item_type, depth in ignored_items:
            indent = "  " * depth
            click.echo(f"{indent}{item_type} {click.style(rel_path, fg='bright_red')}")
    else:
        click.echo(click.style("No ignored files or directories found.", fg="green"))

    click.echo(f"\n{click.style('Total items scanned:', fg='cyan')} {scanned_count}")


def auto_detect_binding(config: Dict[str, Any]) -> Optional[str]:
    """
    Auto-detect binding by comparing current working directory with local_basepath.

    Returns the binding alias if found, None otherwise.
    Prioritizes the most specific match (deepest path).
    If multiple bindings point to the same local_basepath, prompts user to choose.
    """
    bindings = config.get("bindings", {})
    if not bindings:
        return None

    cwd = Path.cwd().resolve()

    # Find all bindings where cwd is within or equals local_basepath
    matches = []
    for alias, binding_config in bindings.items():
        local_basepath_str = binding_config.get("local_basepath", "")
        if not local_basepath_str:
            continue

        # Expand ~ and resolve to absolute path
        local_basepath = Path(local_basepath_str).expanduser().resolve()

        try:
            # Check if cwd is within this binding's basepath
            cwd.relative_to(local_basepath)
            matches.append((alias, local_basepath, binding_config))
        except ValueError:
            # cwd is not within this basepath
            continue

    if not matches:
        return None

    # Return the most specific match (longest/deepest path)
    matches.sort(key=lambda x: len(str(x[1])), reverse=True)

    # Check if multiple bindings point to the exact same local_basepath
    best_match_path = matches[0][1]
    same_path_bindings = [
        (alias, cfg) for alias, path, cfg in matches if path == best_match_path
    ]

    if len(same_path_bindings) > 1:
        # Multiple bindings for the same path - let user choose
        click.echo(
            click.style(
                f"\n⚠️  WARNING: Multiple bindings detected for path: {best_match_path}",
                fg="yellow",
                bold=True,
            )
        )
        click.echo(
            click.style(
                "This could indicate a configuration issue. Please select the binding to use:\n",
                fg="yellow",
            )
        )

        # Display options
        for idx, (alias, cfg) in enumerate(same_path_bindings, start=1):
            protocol = cfg.get("protocol", "ftp").upper()
            hostname = cfg.get("hostname", "N/A")
            comment = cfg.get("comments", "")

            click.echo(
                f"  {click.style(str(idx), fg='cyan', bold=True)}. {click.style(alias, fg='green', bold=True)} - {protocol} to {hostname}"
            )
            if comment:
                click.echo(f"     {click.style(comment, fg='cyan', dim=True)}")

        click.echo(f"  {click.style('0', fg='red', bold=True)}. Cancel and exit")

        # Get user choice
        while True:
            try:
                choice = click.prompt(
                    "\nSelect binding",
                    type=int,
                    default=1,
                    show_default=True,
                )

                if choice == 0:
                    click.echo("Operation cancelled.")
                    sys.exit(0)
                elif 1 <= choice <= len(same_path_bindings):
                    selected_alias = same_path_bindings[choice - 1][0]
                    click.echo(
                        click.style(
                            f"✓ Selected binding: {selected_alias}",
                            fg="green",
                        )
                    )
                    return selected_alias
                else:
                    click.echo(
                        click.style(
                            f"Invalid choice. Please enter 0-{len(same_path_bindings)}",
                            fg="red",
                        ),
                        err=True,
                    )
            except (ValueError, click.Abort):
                click.echo("\nOperation cancelled.")
                sys.exit(0)

    return matches[0][0]


def calculate_remote_path(
    local_path: Path, local_basepath: Path, remote_basepath: str
) -> str:
    try:
        relative_path = local_path.absolute().relative_to(local_basepath.absolute())
    except ValueError:
        click.echo(
            f"Error: File '{local_path}' is not within local basepath '{local_basepath}'.",
            err=True,
        )
        sys.exit(1)

    # Ensure remote_basepath doesn't end with slash unless it's root, and join with forward slashes
    remote_base = remote_basepath.rstrip("/")
    rel_path_str = str(relative_path).replace(os.sep, "/")
    return f"{remote_base}/{rel_path_str}"


def list_remote_ftp(
    ftp: ftplib.FTP, remote_basepath: str, timeout: int = 60, progress_bar=None
) -> Set[str]:
    """
    Recursively list all files on FTP server starting from remote_basepath.
    Uses parallel connections for faster directory scanning.

    Args:
        ftp: Active FTP connection
        remote_basepath: Remote root directory to start listing from
        timeout: Socket timeout in seconds (default: 60)
        progress_bar: Optional click progressbar to update as files are found

    Returns:
        Set of relative file paths from remote_basepath
    """
    from queue import Queue

    remote_files = set()
    remote_base = remote_basepath.rstrip("/")
    dirs_scanned = 0
    files_found = 0
    files_lock = Lock()
    dirs_queue = Queue()
    dirs_queue.put(remote_base)

    # Get FTP credentials from initial connection
    # We need to extract these to create new connections
    ftp_host = ftp.host
    ftp_port = ftp.port or 21

    def scan_directory(path: str, conn: ftplib.FTP) -> tuple:
        """Scan a single directory and return (files, subdirs)"""
        found_files = []
        found_dirs = []

        try:
            # Try using MLSD for better metadata (if supported)
            entries = []
            try:
                for name, facts in conn.mlsd(path):
                    if name in (".", ".."):
                        continue
                    entries.append((name, facts.get("type") == "dir"))
            except (ftplib.error_perm, AttributeError):
                # MLSD not supported, fall back to NLST + checking each
                try:
                    names = conn.nlst(path)
                    for full_path in names:
                        name = os.path.basename(full_path)
                        if name in (".", ".."):
                            continue
                        # Try to detect if it's a directory
                        is_dir = False
                        try:
                            current = conn.pwd()
                            conn.cwd(full_path)
                            conn.cwd(current)
                            is_dir = True
                        except ftplib.error_perm:
                            is_dir = False
                        entries.append((name, is_dir))
                except ftplib.error_perm:
                    return (found_files, found_dirs)

            for name, is_dir in entries:
                full_path = f"{path}/{name}".replace("//", "/")

                if is_dir:
                    found_dirs.append(full_path)
                else:
                    # Calculate relative path from remote_basepath
                    if full_path.startswith(remote_base + "/"):
                        rel_path = full_path[len(remote_base) + 1 :]
                    elif full_path == remote_base:
                        rel_path = ""
                    else:
                        rel_path = full_path

                    if rel_path:
                        found_files.append(rel_path)

        except Exception:
            pass  # Ignore permission errors or inaccessible directories

        return (found_files, found_dirs)

    # Note: FTP doesn't support true parallel connections well due to protocol limitations
    # But we can still optimize by using iterative BFS approach
    while not dirs_queue.empty():
        path = dirs_queue.get()

        dirs_scanned += 1
        if dirs_scanned % 5 == 0:
            click.echo(
                f"\r🔍 Scanning... {dirs_scanned} dirs, {files_found} files found",
                nl=False,
            )

        found_files, found_dirs = scan_directory(path, ftp)

        remote_files.update(found_files)
        files_found += len(found_files)

        for d in found_dirs:
            dirs_queue.put(d)

    # Clear the progress line and show final count
    click.echo(
        f"\r✅ Found {files_found} files in {dirs_scanned} directories" + " " * 20
    )

    return remote_files


def list_remote_sftp(
    sftp: paramiko.SFTPClient,
    remote_basepath: str,
    timeout: int = 60,
    progress_bar=None,
    max_workers: int = 3,
) -> Set[str]:
    """
    Recursively list all files on SFTP server starting from remote_basepath.
    Uses parallel connections for faster directory scanning.

    Args:
        sftp: Active SFTP connection
        remote_basepath: Remote root directory to start listing from
        timeout: Keepalive interval in seconds (default: 60)
        progress_bar: Optional click progressbar to update as files are found
        max_workers: Number of parallel scanning workers (default: 3)

    Returns:
        Set of relative file paths from remote_basepath
    """
    from queue import Queue

    remote_files = set()
    remote_base = remote_basepath.rstrip("/")
    dirs_scanned = 0
    files_found = 0
    files_lock = Lock()
    dirs_queue = Queue()
    dirs_queue.put(remote_base)

    def scan_directory(path: str, worker_sftp: paramiko.SFTPClient) -> tuple:
        """Scan a single directory and return (files, subdirs)"""
        found_files = []
        found_dirs = []

        try:
            # Try listdir_attr first (provides file attributes)
            entries = []
            use_attr = False
            try:
                attr_entries = worker_sftp.listdir_attr(path)
                entries = [(e.filename, e.st_mode) for e in attr_entries]
                use_attr = True
            except Exception:
                # Fallback to simple listdir if listdir_attr not supported
                try:
                    simple_entries = worker_sftp.listdir(path)
                    entries = [(name, None) for name in simple_entries]
                except Exception:
                    return (found_files, found_dirs)

            for filename, st_mode in entries:
                if filename in (".", ".."):
                    continue

                full_path = f"{path}/{filename}".replace("//", "/")

                # Check if it's a directory
                is_dir = False
                if use_attr and st_mode is not None:
                    import stat

                    is_dir = stat.S_ISDIR(st_mode)
                else:
                    # Try to list it as a directory to determine type
                    try:
                        worker_sftp.listdir(full_path)
                        is_dir = True
                    except Exception:
                        is_dir = False

                if is_dir:
                    found_dirs.append(full_path)
                else:
                    # Calculate relative path from remote_basepath
                    if full_path.startswith(remote_base + "/"):
                        rel_path = full_path[len(remote_base) + 1 :]
                    elif full_path == remote_base:
                        rel_path = ""
                    else:
                        rel_path = full_path

                    if rel_path:
                        found_files.append(rel_path)

        except Exception:
            pass  # Ignore all errors

        return (found_files, found_dirs)

    def worker_scan(worker_sftp: paramiko.SFTPClient):
        """Worker function to scan directories from queue"""
        nonlocal dirs_scanned, files_found

        while True:
            try:
                path = dirs_queue.get_nowait()
            except:
                break

            with files_lock:
                dirs_scanned += 1
                if dirs_scanned % 5 == 0:
                    click.echo(
                        f"\r🔍 Scanning... {dirs_scanned} dirs, {files_found} files found",
                        nl=False,
                    )

            found_files, found_dirs = scan_directory(path, worker_sftp)

            with files_lock:
                remote_files.update(found_files)
                files_found += len(found_files)

            for d in found_dirs:
                dirs_queue.put(d)

    # Get SSH connection info to create worker connections
    channel = sftp.get_channel()
    if not channel:
        # Fallback to single-threaded if no channel available
        dirs_queue_list = []
        while not dirs_queue.empty():
            path = dirs_queue.get()
            dirs_scanned += 1
            if dirs_scanned % 5 == 0:
                click.echo(
                    f"\r🔍 Scanning... {dirs_scanned} dirs, {files_found} files found",
                    nl=False,
                )
            found_files, found_dirs = scan_directory(path, sftp)
            remote_files.update(found_files)
            files_found += len(found_files)
            for d in found_dirs:
                dirs_queue.put(d)
    else:
        transport = channel.get_transport()
        if transport:
            # Use iterative approach with single connection for better SFTP compatibility
            # Many SFTP servers don't handle multiple simultaneous connections well
            while not dirs_queue.empty():
                path = dirs_queue.get()

                dirs_scanned += 1
                if dirs_scanned % 3 == 0:  # More frequent updates for SFTP
                    click.echo(
                        f"\r🔍 Scanning... {dirs_scanned} dirs, {files_found} files found",
                        nl=False,
                    )

                found_files, found_dirs = scan_directory(path, sftp)
                remote_files.update(found_files)
                files_found += len(found_files)

                for d in found_dirs:
                    dirs_queue.put(d)

    # Clear the progress line and show final count
    click.echo(
        f"\r✅ Found {files_found} files in {dirs_scanned} directories" + " " * 20
    )

    return remote_files


def upload_ftp(
    host_config: Dict[str, Any],
    files: List[Path],
    local_basepath: Path,
    use_pasv: bool = True,
):
    hostname = host_config["hostname"]
    port = host_config.get("port", 21)
    username = host_config["username"]
    password = host_config["password"]
    remote_basepath = host_config["remote_basepath"]
    max_workers = host_config.get(
        "max_workers", 5
    )  # Parallel uploads (FTP servers may limit connections)

    # Sort files by depth (external first) then alphabetically
    def sort_key(f: Path):
        try:
            rel_path = f.relative_to(local_basepath)
            depth = len(rel_path.parts) - 1
            return (depth, str(rel_path).lower())
        except ValueError:
            return (999, str(f).lower())

    sorted_files = sorted(files, key=sort_key)

    # Cache for created directories (shared across threads)
    created_dirs = set()
    dir_lock = Lock()

    # Progress tracking
    completed = 0
    completed_lock = Lock()
    total_files = len([f for f in sorted_files if not f.is_dir()])

    def upload_single_file(local_file: Path) -> Tuple[bool, str, str]:
        """Upload a single file. Returns (success, local_path, message)"""
        if local_file.is_dir():
            return (True, str(local_file), "skipped (directory)")

        try:
            # Each thread needs its own FTP connection
            ftp = ftplib.FTP()
            ftp.connect(hostname, port, timeout=60)
            ftp.login(username, password)
            ftp.set_pasv(use_pasv)  # Enable passive mode (default) or active mode

            remote_path = calculate_remote_path(
                local_file, local_basepath, remote_basepath
            )
            remote_dir = os.path.dirname(remote_path)

            # Ensure remote directory exists (with caching)
            with dir_lock:
                if remote_dir not in created_dirs:
                    path_parts = remote_dir.split("/")
                    current_path = ""
                    for part in path_parts:
                        if not part:
                            continue
                        current_path += "/" + part
                        if current_path not in created_dirs:
                            try:
                                ftp.cwd(current_path)
                                created_dirs.add(current_path)
                            except ftplib.error_perm:
                                try:
                                    ftp.mkd(current_path)
                                    created_dirs.add(current_path)
                                except ftplib.error_perm:
                                    pass  # Directory might exist

            # Upload the file
            with open(local_file, "rb") as f:
                ftp.storbinary(f"STOR {remote_path}", f)

            ftp.quit()
            return (True, str(local_file), remote_path)

        except Exception as e:
            return (False, str(local_file), str(e))

    click.echo(f"Uploading with parallel connections (max: {max_workers})...")

    # Upload files in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(upload_single_file, f): f for f in sorted_files
        }

        for future in as_completed(future_to_file):
            success, local_path, message = future.result()

            with completed_lock:
                completed += 1
                click.echo(f"[{completed}/{total_files}] ", nl=False)

            if success:
                click.echo(f"✅ {local_path} → {message}")
            else:
                click.echo(f"❌ {local_path} ({message})", err=True)


def upload_sftp(host_config: Dict[str, Any], files: List[Path], local_basepath: Path):
    hostname = host_config["hostname"]
    port = host_config.get("port", 22)
    username = host_config["username"]
    password = host_config.get("password")
    key_filename = host_config.get("key_filename")
    remote_basepath = host_config["remote_basepath"]
    max_workers = host_config.get("max_workers", 5)  # Parallel uploads

    # Sort files by depth (external first) then alphabetically
    def sort_key(f: Path):
        try:
            rel_path = f.relative_to(local_basepath)
            depth = len(rel_path.parts) - 1
            return (depth, str(rel_path).lower())
        except ValueError:
            return (999, str(f).lower())

    sorted_files = sorted(files, key=sort_key)

    # Cache for created directories (shared across threads)
    created_dirs = set()
    dir_lock = Lock()

    # Progress tracking
    completed = 0
    completed_lock = Lock()
    total_files = len([f for f in sorted_files if not f.is_dir()])

    def upload_single_file(local_file: Path) -> Tuple[bool, str, str]:
        """Upload a single file. Returns (success, local_path, message)"""
        if local_file.is_dir():
            return (True, str(local_file), "skipped (directory)")

        try:
            # Each thread needs its own SSH/SFTP connection
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Enable SSH compression for faster uploads
            if key_filename:
                ssh.connect(
                    hostname,
                    port,
                    username,
                    key_filename=key_filename,
                    password=password,  # Used as passphrase for encrypted keys
                    timeout=60,
                    compress=True,
                )
            else:
                ssh.connect(
                    hostname, port, username, password, timeout=60, compress=True
                )

            sftp = ssh.open_sftp()

            remote_path = calculate_remote_path(
                local_file, local_basepath, remote_basepath
            )
            remote_dir = os.path.dirname(remote_path)

            # Ensure remote directory exists (with caching)
            with dir_lock:
                if remote_dir not in created_dirs:
                    path_parts = remote_dir.split("/")
                    current_path = ""
                    for part in path_parts:
                        if not part:
                            continue
                        current_path += "/" + part
                        if current_path not in created_dirs:
                            try:
                                sftp.stat(current_path)
                                created_dirs.add(current_path)
                            except Exception:
                                try:
                                    sftp.mkdir(current_path)
                                    created_dirs.add(current_path)
                                except Exception:
                                    pass  # Directory might exist

            # Upload the file
            sftp.put(str(local_file), remote_path)

            sftp.close()
            ssh.close()
            return (True, str(local_file), remote_path)

        except Exception as e:
            return (False, str(local_file), str(e))

    click.echo("✅ SFTP connection established")
    click.echo(
        f"Uploading with compression + parallel connections (max: {max_workers})..."
    )

    # Upload files in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(upload_single_file, f): f for f in sorted_files
        }

        for future in as_completed(future_to_file):
            success, local_path, message = future.result()

            with completed_lock:
                completed += 1
                click.echo(f"[{completed}/{total_files}] ", nl=False)

            if success:
                click.echo(f"✅ {local_path} → {message}")
            else:
                click.echo(f"❌ {local_path} ({message})", err=True)


def load_ignore_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            return [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    except Exception:
        return []


def collect_ignore_files(directory: Path, local_basepath: Path) -> List[str]:
    """
    Collect all .gsupload_ignore files from directory up to local_basepath.
    Returns combined exclude patterns with additive behavior.

    Args:
        directory: Starting directory
        local_basepath: Root directory (stops walking up here)

    Returns:
        List of exclude patterns from all .gsupload_ignore files found
    """
    all_excludes = []
    current = directory

    # Walk up from directory to local_basepath, collecting ignore files
    while True:
        ignore_file = current / ".gsupload_ignore"
        if ignore_file.exists():
            local_excludes = load_ignore_file(ignore_file)

            # Adjust patterns to be relative to local_basepath
            adjusted_excludes = []
            try:
                rel_dir = current.relative_to(local_basepath)
            except ValueError:
                rel_dir = Path(".")

            for p in local_excludes:
                if "/" in p.rstrip("/"):
                    # Pattern has path components - anchor it to current directory
                    clean_p = p
                    if clean_p.startswith("/"):
                        clean_p = clean_p[1:]

                    # Construct pattern relative to local_basepath
                    rel_dir_str = str(rel_dir).replace(os.sep, "/")
                    if rel_dir_str == ".":
                        new_p = "/" + clean_p
                    else:
                        new_p = "/" + rel_dir_str + "/" + clean_p

                    adjusted_excludes.append(new_p)
                else:
                    # Simple name pattern - applies anywhere
                    adjusted_excludes.append(p)

            all_excludes.extend(adjusted_excludes)

        # Stop if we've reached local_basepath or filesystem root
        try:
            if current.resolve() == local_basepath.resolve():
                break
        except (ValueError, OSError):
            break

        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        current = parent

    return all_excludes


def is_excluded(path: Path, excludes: List[str], local_basepath: Path) -> bool:
    try:
        rel_path = path.relative_to(local_basepath)
    except ValueError:
        return False

    name = path.name

    # Create a "rooted" path for matching to ensure anchors work correctly
    # e.g. "src/foo" becomes "/src/foo"
    # This allows us to use Path.match with patterns that look like absolute paths
    # to simulate anchored matching.
    rooted_rel_path = Path("/") / rel_path

    for pattern in excludes:
        p = pattern
        must_be_dir = False
        if p.endswith("/"):
            p = p[:-1]
            must_be_dir = True

        if must_be_dir and not path.is_dir():
            continue

        # Check if it's a simple filename match (no slash in pattern)
        # Note: We check original pattern for slash, excluding the trailing slash we just removed
        if "/" not in p:
            # Simple name match (e.g. "*.log", "node_modules")
            # Matches against the file/dir name anywhere
            if fnmatch.fnmatch(name, p):
                return True
        else:
            # Pattern involves paths (e.g. "src/*.tmp", "/build", "foo/bar")

            # If pattern starts with /, it's anchored to local_basepath
            # If it doesn't, it's technically a relative path match, but in .gitignore
            # "foo/bar" matches "foo/bar" and "src/foo/bar".
            # However, for simplicity and common usage in this script context:
            # We will treat "foo/bar" as relative to the ignore file location (handled in walk_directory)
            # or relative to root if global/host config.

            # To support "recursive" matching with globs like "**", we use Path.match.
            # Path.match matches from the right.
            # To enforce anchoring (if pattern starts with /), we use the rooted path.

            match_pattern = p
            if match_pattern.startswith("/"):
                # Pattern is anchored.
                # We match against rooted_rel_path.
                # Ensure pattern starts with / (it does).
                if rooted_rel_path.match(match_pattern):
                    return True
            else:
                # Pattern is not anchored (e.g. "src/foo").
                # But wait, if we adjusted patterns in walk_directory, they might be relative to root now.
                # If we have "src/foo" in global config, it usually means "src/foo" at root.
                # So we should treat it as anchored?
                # In .gitignore, "foo/bar" matches "foo/bar" in the directory of .gitignore.
                # If .gitignore is at root, it matches /foo/bar.
                # So effectively, patterns with slashes are anchored to the base.

                # So we treat "src/foo" as "/src/foo".
                match_pattern = "/" + match_pattern
                if rooted_rel_path.match(match_pattern):
                    return True

                # What about "**/*.js"?
                # "/src/**/*.js"
                # rooted_rel_path: "/src/app/test.js"
                # Match? Yes.

    return False


def walk_directory(
    directory: Path, excludes: List[str], local_basepath: Path
) -> List[Path]:
    files = []

    # Collect all .gsupload_ignore files from this directory up to local_basepath
    ignore_excludes = collect_ignore_files(directory, local_basepath)

    # Combine with passed excludes
    current_excludes = excludes + ignore_excludes

    try:
        entries = list(directory.iterdir())
    except OSError:
        return []

    for entry in entries:
        if is_excluded(entry, current_excludes, local_basepath):
            continue

        if entry.is_file():
            files.append(entry)
        elif entry.is_dir():
            files.extend(walk_directory(entry, current_excludes, local_basepath))

    return files


def display_visual_comparison(
    host_config: Dict[str, Any],
    local_files: List[Path],
    local_basepath: Path,
    protocol: str,
    binding_alias: str,
    max_depth: int = DEFAULT_MAX_DEPTH,
    summary_only: bool = False,
    complete_tree: bool = False,
) -> Tuple[int, int, int]:
    """
    Display tree comparison of local vs remote files before upload.

    Args:
        host_config: Host configuration with connection details
        local_files: List of local Path objects to upload
        local_basepath: Local root directory
        protocol: 'ftp' or 'sftp'
        binding_alias: Binding configuration alias name
        max_depth: Maximum tree depth to display (default: DEFAULT_MAX_DEPTH)
        summary_only: If True, show only statistics without tree (default: False)
        complete_tree: If True, show all files including remote-only (default: False)

    Returns:
        Tuple of (new_files_count, overwrite_count, remote_only_count)
    """
    hostname = host_config["hostname"]
    port = host_config.get("port", 21 if protocol == "ftp" else 22)
    username = host_config["username"]
    password = host_config.get("password")
    remote_basepath = host_config["remote_basepath"]

    # Calculate local file relative paths
    local_rel_paths = set()
    for local_file in local_files:
        try:
            rel_path = local_file.relative_to(local_basepath)
            local_rel_paths.add(str(rel_path).replace(os.sep, "/"))
        except ValueError:
            continue

    # Connect and list remote files
    click.echo(f"🔍 Connecting to {hostname}...")
    click.echo(f"📌 Binding in use: {binding_alias}")

    # Display binding comment if present
    if "comments" in host_config:
        display_comment(host_config["comments"], prefix="📝")

    remote_files = set()

    try:
        if protocol == "ftp":
            ftp = ftplib.FTP()
            ftp.connect(hostname, port, timeout=60)
            ftp.login(username, password or "")
            ftp.set_pasv(True)  # Use passive mode by default

            scan_start = time.time()
            remote_files = list_remote_ftp(ftp, remote_basepath, timeout=60)
            scan_elapsed = time.time() - scan_start

            # Display scan time
            days = int(scan_elapsed // 86400)
            hours = int((scan_elapsed % 86400) // 3600)
            minutes = int((scan_elapsed % 3600) // 60)
            seconds = scan_elapsed % 60

            time_parts = []
            if days > 0:
                time_parts.append(f"{days}d")
            if hours > 0 or days > 0:
                time_parts.append(f"{hours}h")
            if minutes > 0 or hours > 0 or days > 0:
                time_parts.append(f"{minutes}m")
            time_parts.append(f"{seconds:.2f}s")

            click.echo(f"⏱️  Scan completed in {' '.join(time_parts)}")

            ftp.quit()

        elif protocol == "sftp":
            key_filename = host_config.get("key_filename")

            # Use SSHClient for better compatibility and automatic host key handling
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                # Retry connection with multiple strategies for problematic servers
                max_retries = 4
                retry_count = 0
                connection_successful = False

                while retry_count < max_retries and not connection_successful:
                    try:
                        # Progressive timeout and connection strategy
                        if retry_count == 0:
                            # First attempt: standard settings with longer timeout
                            timeout_value = 120
                            use_compression = True
                            gss_auth = False  # Disable to avoid GSS-API import errors
                            gss_kex = False
                            # Enable SSH agent if no password/key provided
                            allow_agent = not password and not key_filename
                            # Look for keys unless using password-only auth
                            look_for_keys = not password or key_filename
                            auth_method = (
                                "agent"
                                if allow_agent
                                else ("key" if key_filename else "password")
                            )
                            click.echo(
                                f"📡 Attempting connection with standard settings... (auth: {auth_method})"
                            )
                        elif retry_count == 1:
                            # Second attempt: disable compression (can cause issues)
                            timeout_value = 150
                            use_compression = False
                            gss_auth = False
                            gss_kex = False
                            allow_agent = not password and not key_filename
                            look_for_keys = not password or key_filename
                            click.echo("⏳ Retry 1/3: Disabling compression...")
                        elif retry_count == 2:
                            # Third attempt: disable GSS-API auth (can cause delays)
                            timeout_value = 180
                            use_compression = False
                            gss_auth = False
                            gss_kex = False
                            allow_agent = not password and not key_filename
                            look_for_keys = False
                            click.echo(
                                "⏳ Retry 2/3: Disabling GSS auth and key scanning..."
                            )
                        else:
                            # Final attempt: maximum timeout, all optimizations
                            timeout_value = 240
                            use_compression = False
                            gss_auth = False
                            gss_kex = False
                            allow_agent = not password and not key_filename
                            look_for_keys = False
                            click.echo("⏳ Retry 3/3: Maximum timeout (240s)...")

                        if key_filename:
                            ssh.connect(
                                hostname,
                                port=port,
                                username=username,
                                key_filename=key_filename,
                                password=password,  # Used as passphrase for encrypted keys
                                timeout=timeout_value,
                                banner_timeout=timeout_value,
                                auth_timeout=timeout_value,
                                compress=use_compression,
                                gss_auth=gss_auth,
                                gss_kex=gss_kex,
                                look_for_keys=bool(look_for_keys),
                                allow_agent=bool(allow_agent),
                            )
                        else:
                            ssh.connect(
                                hostname,
                                port=port,
                                username=username,
                                password=password,
                                timeout=timeout_value,
                                banner_timeout=timeout_value,
                                auth_timeout=timeout_value,
                                compress=use_compression,
                                gss_auth=gss_auth,
                                gss_kex=gss_kex,
                                look_for_keys=bool(look_for_keys),
                                allow_agent=bool(allow_agent),
                            )

                        connection_successful = True
                        click.echo("✅ SFTP connection established")

                    except (
                        paramiko.SSHException,
                        socket.timeout,
                        socket.error,
                        ImportError,  # Handle GSS-API import errors
                    ) as conn_error:
                        retry_count += 1
                        if retry_count < max_retries:
                            click.echo(
                                click.style(
                                    f"⚠️  Connection attempt {retry_count} failed: {conn_error}",
                                    fg="yellow",
                                )
                            )
                            time.sleep(3)  # Wait before retry
                        else:
                            # Final attempt failed
                            click.echo(
                                click.style(
                                    f"❌ All {max_retries} connection attempts failed.",
                                    fg="red",
                                    bold=True,
                                )
                            )
                            click.echo(
                                click.style(
                                    "💡 Tip: This server may have connection rate limiting or firewall issues.",
                                    fg="cyan",
                                )
                            )
                            raise

                # Open SFTP session
                sftp = ssh.open_sftp()

                click.echo("🔍 Listing remote files...")
                scan_start = time.time()
                remote_files = list_remote_sftp(sftp, remote_basepath, timeout=60)
                scan_elapsed = time.time() - scan_start

                # Display scan time
                days = int(scan_elapsed // 86400)
                hours = int((scan_elapsed % 86400) // 3600)
                minutes = int((scan_elapsed % 3600) // 60)
                seconds = scan_elapsed % 60

                time_parts = []
                if days > 0:
                    time_parts.append(f"{days}d")
                if hours > 0 or days > 0:
                    time_parts.append(f"{hours}h")
                if minutes > 0 or hours > 0 or days > 0:
                    time_parts.append(f"{minutes}m")
                time_parts.append(f"{seconds:.2f}s")

                click.echo(f"⏱️  Scan completed in {' '.join(time_parts)}")

                sftp.close()
                ssh.close()

            except Exception as ssh_error:
                if ssh:
                    ssh.close()
                raise

    except Exception as e:
        click.echo(
            f"\n⚠️  Warning: Failed to list remote files: {type(e).__name__}: {e}",
            err=True,
        )
        import traceback

        click.echo(f"Traceback:\n{traceback.format_exc()}", err=True)
        if not click.confirm("Proceed with upload without comparison?", default=False):
            sys.exit(0)
        return (len(local_files), 0, 0)

    # Categorize files
    new_files = local_rel_paths - remote_files
    overwrite_files = local_rel_paths & remote_files

    # Only calculate remote-only files if complete tree is requested (saves time)
    remote_only_files = set()
    if complete_tree:
        remote_only_files = remote_files - local_rel_paths

    # Build tree structure
    if not summary_only:
        # Build a proper tree structure with directories
        tree_structure = {}

        def add_to_tree(path: str, status: str):
            parts = path.split("/")
            current = tree_structure

            # Build directory structure
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {"__type__": "dir", "__children__": {}}
                current = current[part]["__children__"]

            # Add file with status
            filename = parts[-1]
            current[filename] = {"__type__": "file", "__status__": status}

        # Add all files to tree
        for path in new_files:
            add_to_tree(path, "[NEW]")
        for path in overwrite_files:
            add_to_tree(path, "[OVERWRITE]")

        # Only add remote-only files if complete tree is requested
        if complete_tree:
            for path in remote_only_files:
                add_to_tree(path, "[REMOTE ONLY]")

        # Display tree
        tree_mode = "Complete" if complete_tree else "Changes Only"
        click.echo(
            f"\n📂 File Comparison Tree - {tree_mode} (max depth: {max_depth}):\n"
        )
        click.echo(f"Local:  {local_basepath}")
        click.echo(f"Remote: {remote_basepath}\n")

        if not complete_tree:
            click.echo(
                click.style(
                    "... (remote-only files not shown, use -vcc or --visual-check-complete to see all)\n",
                    dim=True,
                )
            )

        displayed_count = 0
        depth_exceeded_count = 0

        def display_tree(node: dict, prefix: str = "", depth: int = 0):
            nonlocal displayed_count, depth_exceeded_count

            if depth > max_depth:
                # Count all items in this subtree
                def count_items(n):
                    count = 0
                    for key, value in n.items():
                        if value.get("__type__") == "file":
                            count += 1
                        elif value.get("__type__") == "dir":
                            count += count_items(value.get("__children__", {}))
                    return count

                depth_exceeded_count += count_items(node)
                return

            items = sorted(node.items())
            # Separate directories and files, directories first
            dirs = [(k, v) for k, v in items if v.get("__type__") == "dir"]
            files = [(k, v) for k, v in items if v.get("__type__") == "file"]
            all_items = dirs + files

            for idx, (name, value) in enumerate(all_items):
                is_last = idx == len(all_items) - 1
                connector = "└── " if is_last else "├── "

                if value.get("__type__") == "dir":
                    click.echo(f"{prefix}{connector}{name}/")
                    displayed_count += 1

                    # Prepare prefix for children
                    extension = "    " if is_last else "│   "
                    display_tree(
                        value.get("__children__", {}), prefix + extension, depth + 1
                    )

                elif value.get("__type__") == "file":
                    status = value.get("__status__", "")

                    # Color status markers
                    if status == "[NEW]":
                        colored_status = click.style(status, fg="green", bold=True)
                    elif status == "[OVERWRITE]":
                        colored_status = click.style(status, fg="yellow", bold=True)
                    else:  # REMOTE ONLY
                        colored_status = click.style(status, fg="blue", dim=True)

                    click.echo(f"{prefix}{connector}{name} {colored_status}")
                    displayed_count += 1

        display_tree(tree_structure)

        if depth_exceeded_count > 0:
            click.echo(
                f"\n... ({depth_exceeded_count} more files beyond depth {max_depth})"
            )

    # Display summary
    click.echo(f"\n{'=' * 60}")
    click.echo("📊 Summary:")
    click.echo(f"{'=' * 60}")
    click.echo(f"  {click.style('New files:         ', fg='green')} {len(new_files)}")
    click.echo(
        f"  {click.style('Files to overwrite:', fg='yellow')} {len(overwrite_files)}"
    )

    # Calculate remote-only count efficiently (without creating the full set)
    remote_only_count = len(remote_files) - len(overwrite_files)
    if complete_tree:
        click.echo(
            f"  {click.style('Remote only:       ', fg='blue')} {len(remote_only_files)}"
        )
    else:
        click.echo(
            f"  {click.style('Remote only:       ', fg='blue')} {remote_only_count}"
        )
    click.echo(f"{'=' * 60}\n")

    return (len(new_files), len(overwrite_files), len(remote_only_files))


def expand_files(
    patterns: List[str],
    excludes: List[str],
    local_basepath: Path,
    recursive: bool = False,
) -> List[Path]:
    files = []
    seen = set()

    for pattern in patterns:
        matched = []

        # If recursive flag is set and pattern has no path separator, search recursively from cwd
        if recursive and "/" not in pattern and "\\" not in pattern:
            cwd = Path.cwd()
            try:
                # Use rglob for recursive matching
                matched = [str(p) for p in cwd.rglob(pattern) if p.is_file()]
            except Exception:
                matched = []

        if not matched:
            # Fall back to standard glob
            matched = glob.glob(pattern, recursive=True)

        if not matched:
            # Maybe it's a file that doesn't exist yet? Or just a typo.
            # Or maybe it's a directory.
            if os.path.exists(pattern):
                matched = [pattern]
            else:
                click.echo(f"Warning: No files found for pattern '{pattern}'", err=True)
                continue

        for m in matched:
            path = Path(m).resolve()

            # Skip if already processed (deduplication)
            if path in seen:
                continue

            # Filter: only include files within local_basepath
            try:
                path.relative_to(local_basepath.resolve())
            except ValueError:
                # File is outside local_basepath, skip it
                continue

            if is_excluded(path, excludes, local_basepath):
                continue

            if path.is_file():
                files.append(path)
                seen.add(path)
            elif path.is_dir():
                # Recursively add all files in directory
                dir_files = walk_directory(path, excludes, local_basepath)
                for f in dir_files:
                    if f not in seen:
                        files.append(f)
                        seen.add(f)

    return files


def version_callback(ctx, param, value):
    """Callback to display version and exit."""
    if value and not ctx.resilient_parsing:
        click.echo(f"gsupload version {__version__}")
        ctx.exit()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--version",
    "-v",
    is_flag=True,
    callback=version_callback,
    expose_value=False,
    is_eager=True,
    help="Show version and exit.",
)
@click.option(
    "-r/-nr",
    "--recursive/--no-recursive",
    default=True,
    help="Search for files recursively in subdirectories when using glob patterns [default: enabled]",
)
@click.option(
    "-vc",
    "--visual-check",
    is_flag=True,
    help="Display tree comparison showing only changes (new/overwritten files, excludes remote-only)",
)
@click.option(
    "-vcc/-nvcc",
    "--visual-check-complete/--no-visual-check-complete",
    default=True,
    help="Display complete tree comparison including remote-only files [default: enabled]",
)
@click.option(
    "--max-depth",
    default=DEFAULT_MAX_DEPTH,
    type=int,
    help=f"Maximum tree depth to display in visual check (default: {DEFAULT_MAX_DEPTH})",
)
@click.option(
    "-ts",
    "--tree-summary",
    is_flag=True,
    help="Show summary statistics only, skip tree display in visual check",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Force upload without confirmation or remote file check (fastest mode)",
)
@click.option(
    "-b",
    "--binding",
    "binding_alias",
    default=None,
    help="Binding alias from configuration. If omitted, auto-detects from current directory.",
)
@click.option(
    "--show-config",
    is_flag=True,
    help="Display the merged configuration with source file annotations and exit.",
)
@click.option(
    "--show-ignored",
    is_flag=True,
    help="List all files and directories that are being ignored by exclude patterns and exit.",
)
@click.option(
    "--max-workers",
    default=None,
    type=int,
    help="Number of parallel upload workers for faster transfers (overrides config; default: binding max_workers or 5)",
)
@click.option(
    "--ftp-active",
    is_flag=True,
    help="Use FTP active mode instead of passive mode (PASV). Passive mode is recommended for most networks.",
)
@click.argument("patterns", nargs=-1, required=False)
def main(
    recursive,
    visual_check,
    visual_check_complete,
    max_depth,
    tree_summary,
    force,
    binding_alias,
    show_config,
    show_ignored,
    max_workers,
    ftp_active,
    patterns,
):
    """
    Upload files and directories to a remote FTP/SFTP server.

    Uploads files matching PATTERNS to the remote server.
    Use -b/--binding to specify the binding, or let it auto-detect from your current directory.
    The remote path is calculated relative to the local_basepath and remote_basepath
    defined in your .gsupload.json configuration file.

    \b
    PATTERNS can be:
      - Specific filenames: index.html style.css
      - Glob patterns: "*.css" "*.js" (MUST be quoted to prevent shell expansion)
      - Directories: src/assets (uploads all files in directory)

    \b
    IMPORTANT: Always quote glob patterns!
      Shell expansion happens BEFORE gsupload runs. Without quotes, your shell
      expands *.css to file1.css file2.css, and gsupload never sees the pattern.

    \b
    Examples:
      gsupload "*.css"                                  # Auto-detect binding (quotes required!)
      gsupload -b=frontend "*.css"                      # Upload CSS files using 'frontend' binding
      gsupload --binding=frontend "*.css"               # Same as above (long form)
      gsupload -r -b=frontend "*.css"                   # Upload CSS files recursively
      gsupload -f -b=frontend "*.css"                   # Force upload without confirmation (fastest)
      gsupload -vc -b=frontend "*.css"                  # Visual check (changes only) before upload
      gsupload -vcc -b=frontend "*.css"                 # Visual check with complete tree
      gsupload -vc -r -b=backend "*.js"                 # Visual check for recursive JS file upload
      gsupload -vc --max-depth=5 -r -b=admin "*.html"   # Visual check with custom tree depth
      gsupload -vc -ts -b=frontend "*.css"              # Show summary only, no tree display
      gsupload -b=frontend src/assets                   # Upload all files in src/assets directory
      gsupload -b=backend index.html app.js             # Upload specific files to backend host

    \b
    Configuration:
      The script looks for configuration file in this order:
        1. Looks for .gsupload.json in the current directory and parent directories (walks up until found). Filename starts with dot (".") on purpose.
        2. ~/.gsupload/gsupload.json (no dot file, on purpose)
        3. ~/.config/gsupload/gsupload.json (no dot file, on purpose)

    \b
    Created by Gustavo Adrián Salvini - @guspatagonico - https://gustavosalvini.com.ar
    Licensed under the MIT License - free to use, modify, and distribute.

    """
    click.echo()

    # Show help if no arguments provided
    if not patterns and not show_config and not show_ignored:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()

    # Handle --show-config flag
    if show_config:
        merged_config, source_map = load_config_with_sources()
        display_config(merged_config, source_map)
        sys.exit(0)

    config = load_config()

    # Handle --show-ignored flag
    if show_ignored:
        # Auto-detect or use provided binding
        if binding_alias is None:
            binding_alias = auto_detect_binding(config)
            if binding_alias is None:
                click.echo(
                    "Error: Could not auto-detect binding. Please specify binding with -b or --binding.",
                    err=True,
                )
                click.echo("\nAvailable bindings:", err=True)
                bindings = config.get("bindings", {})
                for alias, binding_config in bindings.items():
                    click.echo(
                        f"  - {alias}: {binding_config.get('local_basepath')}",
                        err=True,
                    )
                sys.exit(1)
            click.echo(f"🔍 Auto-detected binding: {binding_alias}")

        # Display root-level comment if present
        if "comments" in config:
            display_comment(config["comments"])

        host_config = get_host_config(config, binding_alias)

        # Display binding comment if present
        if "comments" in host_config:
            display_comment(host_config["comments"], prefix="📝")

        local_basepath = Path(host_config["local_basepath"])

        if not local_basepath.exists():
            click.echo(
                f"Error: Local basepath '{local_basepath}' does not exist.", err=True
            )
            sys.exit(1)

        global_excludes = config.get("global_excludes", [])
        host_excludes = host_config.get("excludes", [])
        all_excludes = global_excludes + host_excludes

        # Display excludes comments if present
        if "global_excludes_comments" in config:
            display_comment(config["global_excludes_comments"], prefix="🚫")
        if "excludes_comments" in host_config:
            display_comment(host_config["excludes_comments"], prefix="🚫")

        list_ignored_files(local_basepath, all_excludes, recursive)
        sys.exit(0)

    # Auto-detect binding if not provided
    if binding_alias is None:
        binding_alias = auto_detect_binding(config)
        if binding_alias is None:
            click.echo(
                "Error: Could not auto-detect binding. Please specify binding with -b or --binding.",
                err=True,
            )
            click.echo(
                "\nAvailable bindings:",
                err=True,
            )
            bindings = config.get("bindings", {})
            for alias, binding_config in bindings.items():
                click.echo(
                    f"  - {alias}: {binding_config.get('local_basepath')}", err=True
                )
            sys.exit(1)
        click.echo(f"🔍 Auto-detected binding: {binding_alias}")

    # Display root-level comment if present
    if "comments" in config:
        display_comment(config["comments"])

    # Require patterns for upload operation
    if not patterns:
        click.echo(
            "Error: No file patterns specified. Please provide file patterns to upload.",
            err=True,
        )
        click.echo("Examples:", err=True)
        click.echo("  gsupload '*.css'", err=True)
        click.echo("  gsupload 'src/**/*.js'", err=True)
        click.echo("  gsupload index.html style.css", err=True)
        sys.exit(1)

    host_config = get_host_config(config, binding_alias)

    # Display binding comment if present
    if "comments" in host_config:
        display_comment(host_config["comments"], prefix="📝")

    # Resolve max_workers with precedence:
    # 1) explicit --max-workers (CLI)
    # 2) binding config max_workers
    # 3) fallback default (5)
    if max_workers is not None:
        host_config["max_workers"] = max_workers
    else:
        host_config["max_workers"] = host_config.get("max_workers", 5)

    local_basepath = Path(host_config["local_basepath"])
    if not local_basepath.exists():
        click.echo(
            f"Error: Local basepath '{local_basepath}' does not exist.", err=True
        )
        sys.exit(1)

    global_excludes = config.get("global_excludes", [])
    host_excludes = host_config.get("excludes", [])
    all_excludes = global_excludes + host_excludes

    # Display excludes comments if present
    if "global_excludes_comments" in config:
        display_comment(config["global_excludes_comments"], prefix="🚫")
    if "excludes_comments" in host_config:
        display_comment(host_config["excludes_comments"], prefix="🚫")

    files_to_upload = expand_files(patterns, all_excludes, local_basepath, recursive)

    if not files_to_upload:
        click.echo("No files found to upload.")
        sys.exit(0)

    # Sort files by depth (external first) then alphabetically for consistent ordering
    def sort_key(f: Path):
        try:
            rel_path = f.relative_to(local_basepath)
            depth = len(rel_path.parts) - 1
            return (depth, str(rel_path).lower())
        except ValueError:
            return (999, str(f).lower())

    files_to_upload = sorted(files_to_upload, key=sort_key)

    protocol = host_config.get("protocol", "ftp").lower()

    # Visual check before upload (skip if force mode enabled)
    # -vc explicitly sets complete_tree=False (changes only)
    # -vcc sets complete_tree=True (includes remote-only files)
    # Default is -vcc behavior
    if not force and (visual_check or visual_check_complete):
        # If -vc is explicitly set, show changes only (disable complete tree)
        show_complete_tree = visual_check_complete and not visual_check

        new_count, overwrite_count, remote_only_count = display_visual_comparison(
            host_config,
            files_to_upload,
            local_basepath,
            protocol,
            binding_alias,
            max_depth,
            tree_summary,
            complete_tree=show_complete_tree,
        )

        if not click.confirm("\n⚠️  Proceed with upload?", default=False):
            click.echo("Upload cancelled.")
            sys.exit(0)

        click.echo("")

    # Start timer
    start_time = time.time()

    if protocol == "ftp":
        upload_ftp(
            host_config, files_to_upload, local_basepath, use_pasv=not ftp_active
        )
    elif protocol == "sftp":
        upload_sftp(host_config, files_to_upload, local_basepath)
    else:
        click.echo(
            f"Error: Unsupported protocol '{protocol}'. Use 'ftp' or 'sftp'.", err=True
        )
        sys.exit(1)

    # Calculate elapsed time
    elapsed = time.time() - start_time
    days = int(elapsed // 86400)
    hours = int((elapsed % 86400) // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = elapsed % 60

    # Format time output
    time_parts = []
    if days > 0:
        time_parts.append(f"{days}d")
    if hours > 0 or days > 0:
        time_parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        time_parts.append(f"{minutes}m")
    time_parts.append(f"{seconds:.2f}s")

    click.echo()
    click.echo(f"⏱️  Upload completed in {' '.join(time_parts)}")


if __name__ == "__main__":
    main()
