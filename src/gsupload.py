#!/usr/bin/env python3
import json
import os
import sys
import glob
import ftplib
import click
import paramiko
import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional

DEFAULT_MAX_DEPTH = 20


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
    configs_to_merge = []

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
        except json.JSONDecodeError as e:
            click.echo(f"Warning: Failed to parse '{config_path}': {e}", err=True)

    if not configs_to_merge:
        searched_paths = global_locations + [Path.cwd() / ".gsupload.json"]
        click.echo(
            f"Error: Configuration file not found. Checked: {', '.join(str(p) for p in searched_paths)}",
            err=True,
        )
        sys.exit(1)

    # Merge all configs
    merged_config = {}
    all_global_excludes = []

    for config_path, config in configs_to_merge:
        # Collect global_excludes additively
        if "global_excludes" in config:
            all_global_excludes.extend(config["global_excludes"])

        # Merge bindings (deep merge - each binding can be overridden independently)
        if "bindings" in config:
            if "bindings" not in merged_config:
                merged_config["bindings"] = {}

            for binding_name, binding_config in config["bindings"].items():
                if binding_name in merged_config["bindings"]:
                    # Merge/override this binding
                    merged_config["bindings"][binding_name].update(binding_config)
                else:
                    # New binding
                    merged_config["bindings"][binding_name] = binding_config.copy()

        # Other top-level keys: simple override
        for key in config:
            if key not in ["global_excludes", "bindings"]:
                merged_config[key] = config[key]

    # Set the combined global_excludes
    if all_global_excludes:
        merged_config["global_excludes"] = all_global_excludes

    return merged_config


def get_host_config(config: Dict[str, Any], alias: str) -> Dict[str, Any]:
    bindings = config.get("bindings", {})
    if alias not in bindings:
        click.echo(f"Error: Host alias '{alias}' not found in configuration.", err=True)
        sys.exit(1)
    return bindings[alias]


def auto_detect_binding(config: Dict[str, Any]) -> Optional[str]:
    """
    Auto-detect binding by comparing current working directory with local_basepath.

    Returns the binding alias if found, None otherwise.
    Prioritizes the most specific match (deepest path).
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
            matches.append((alias, local_basepath))
        except ValueError:
            # cwd is not within this basepath
            continue

    if not matches:
        return None

    # Return the most specific match (longest/deepest path)
    matches.sort(key=lambda x: len(str(x[1])), reverse=True)
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

    Args:
        ftp: Active FTP connection
        remote_basepath: Remote root directory to start listing from
        timeout: Socket timeout in seconds (default: 60)
        progress_bar: Optional click progressbar to update as files are found

    Returns:
        Set of relative file paths from remote_basepath
    """
    remote_files = set()
    remote_base = remote_basepath.rstrip("/")

    # Set socket timeout
    if ftp.sock:
        ftp.sock.settimeout(timeout)

    def list_directory(path: str):
        try:
            # Try using MLSD for better metadata (if supported)
            entries = []
            try:
                for name, facts in ftp.mlsd(path):
                    if name in (".", ".."):
                        continue
                    entries.append((name, facts.get("type") == "dir"))
            except (ftplib.error_perm, AttributeError):
                # MLSD not supported, fall back to NLST + checking each
                try:
                    names = ftp.nlst(path)
                    for full_path in names:
                        name = os.path.basename(full_path)
                        if name in (".", ".."):
                            continue
                        # Try to detect if it's a directory
                        is_dir = False
                        try:
                            current = ftp.pwd()
                            ftp.cwd(full_path)
                            ftp.cwd(current)
                            is_dir = True
                        except ftplib.error_perm:
                            is_dir = False
                        entries.append((name, is_dir))
                except ftplib.error_perm:
                    return

            for name, is_dir in entries:
                full_path = f"{path}/{name}".replace("//", "/")

                if is_dir:
                    list_directory(full_path)
                else:
                    # Calculate relative path from remote_basepath
                    if full_path.startswith(remote_base + "/"):
                        rel_path = full_path[len(remote_base) + 1 :]
                    elif full_path == remote_base:
                        rel_path = ""
                    else:
                        rel_path = full_path

                    if rel_path:
                        remote_files.add(rel_path)

        except Exception:
            pass  # Ignore permission errors or inaccessible directories

    list_directory(remote_base)
    return remote_files


def list_remote_sftp(
    sftp: paramiko.SFTPClient,
    remote_basepath: str,
    timeout: int = 60,
    progress_bar=None,
) -> Set[str]:
    """
    Recursively list all files on SFTP server starting from remote_basepath.

    Args:
        sftp: Active SFTP connection
        remote_basepath: Remote root directory to start listing from
        timeout: Keepalive interval in seconds (default: 60)
        progress_bar: Optional click progressbar to update as files are found

    Returns:
        Set of relative file paths from remote_basepath
    """
    remote_files = set()
    remote_base = remote_basepath.rstrip("/")

    # Set keepalive to prevent timeout
    channel = sftp.get_channel()
    if channel:
        transport = channel.get_transport()
        if transport:
            transport.set_keepalive(30)

    def list_directory(path: str):
        try:
            entries = sftp.listdir_attr(path)

            for entry in entries:
                if entry.filename in (".", ".."):
                    continue

                full_path = f"{path}/{entry.filename}".replace("//", "/")

                # Check if it's a directory using stat
                try:
                    import stat

                    if entry.st_mode is not None and stat.S_ISDIR(entry.st_mode):
                        list_directory(full_path)
                    else:
                        # Calculate relative path from remote_basepath
                        if full_path.startswith(remote_base + "/"):
                            rel_path = full_path[len(remote_base) + 1 :]
                        elif full_path == remote_base:
                            rel_path = ""
                        else:
                            rel_path = full_path

                        if rel_path:
                            remote_files.add(rel_path)
                except Exception:
                    pass  # Treat as file if stat fails

        except Exception:
            pass  # Ignore permission errors or inaccessible directories

    list_directory(remote_base)
    return remote_files


def upload_ftp(host_config: Dict[str, Any], files: List[Path], local_basepath: Path):
    hostname = host_config["hostname"]
    port = host_config.get("port", 21)
    username = host_config["username"]
    password = host_config["password"]
    remote_basepath = host_config["remote_basepath"]

    # Sort files by depth (external first) then alphabetically
    def sort_key(f: Path):
        try:
            rel_path = f.relative_to(local_basepath)
            depth = len(rel_path.parts) - 1
            return (depth, str(rel_path).lower())
        except ValueError:
            return (999, str(f).lower())

    sorted_files = sorted(files, key=sort_key)

    try:
        ftp = ftplib.FTP()
        ftp.connect(hostname, port)
        ftp.login(username, password)

        click.echo("Uploading:")

        total_files = len(sorted_files)
        for idx, local_file in enumerate(sorted_files, start=1):
            if local_file.is_dir():
                continue  # Directories are handled by walking or creating, but here we expect a list of files

            click.echo(f"[{idx}/{total_files}]", nl=False)

            remote_path = calculate_remote_path(
                local_file, local_basepath, remote_basepath
            )
            remote_dir = os.path.dirname(remote_path)

            # Ensure remote directory exists
            path_parts = remote_dir.split("/")
            current_path = ""
            for part in path_parts:
                if not part:
                    continue
                current_path += "/" + part
                try:
                    ftp.cwd(current_path)
                except ftplib.error_perm:
                    try:
                        ftp.mkd(current_path)
                    except ftplib.error_perm:
                        pass  # Directory might exist or permission denied

            try:
                with open(local_file, "rb") as f:
                    ftp.storbinary(f"STOR {remote_path}", f)
                click.echo(f" ✅ {local_file} → {remote_path}")
            except Exception as e:
                click.echo(f" ❌ {local_file} → {remote_path} ({e})", err=True)

        ftp.quit()
    except Exception as e:
        click.echo(f"FTP Error: {e}", err=True)
        sys.exit(1)


def upload_sftp(host_config: Dict[str, Any], files: List[Path], local_basepath: Path):
    hostname = host_config["hostname"]
    port = host_config.get("port", 22)
    username = host_config["username"]
    password = host_config.get("password")
    key_filename = host_config.get("key_filename")
    remote_basepath = host_config["remote_basepath"]

    # Sort files by depth (external first) then alphabetically
    def sort_key(f: Path):
        try:
            rel_path = f.relative_to(local_basepath)
            depth = len(rel_path.parts) - 1
            return (depth, str(rel_path).lower())
        except ValueError:
            return (999, str(f).lower())

    sorted_files = sorted(files, key=sort_key)

    try:
        transport = paramiko.Transport((hostname, port))
        if key_filename:
            key = paramiko.RSAKey.from_private_key_file(key_filename)
            transport.connect(username=username, pkey=key)
        else:
            transport.connect(username=username, password=password)

        sftp = paramiko.SFTPClient.from_transport(transport)
        if sftp is None:
            raise ConnectionError("Failed to initialize SFTP client.")

        click.echo("Uploading:")

        total_files = len(sorted_files)
        for idx, local_file in enumerate(sorted_files, start=1):
            if local_file.is_dir():
                continue

            click.echo(f"[{idx}/{total_files}]", nl=False)

            remote_path = calculate_remote_path(
                local_file, local_basepath, remote_basepath
            )
            remote_dir = os.path.dirname(remote_path)

            # Ensure remote directory exists
            path_parts = remote_dir.split("/")
            current_path = ""
            for part in path_parts:
                if not part:
                    continue
                current_path += "/" + part
                try:
                    sftp.stat(current_path)
                except FileNotFoundError:
                    try:
                        sftp.mkdir(current_path)
                    except OSError:
                        pass  # Directory might exist

            try:
                sftp.put(str(local_file), remote_path)
                click.echo(f" ✅ {local_file} → {remote_path}")
            except Exception as e:
                click.echo(f" ❌ {local_file} → {remote_path} ({e})", err=True)

        sftp.close()
        transport.close()
    except Exception as e:
        click.echo(f"SFTP Error: {e}", err=True)
        sys.exit(1)


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
    remote_files = set()

    try:
        if protocol == "ftp":
            ftp = ftplib.FTP()
            ftp.connect(hostname, port, timeout=60)
            ftp.login(username, password or "")

            remote_files = list_remote_ftp(ftp, remote_basepath, timeout=60)

            ftp.quit()

        elif protocol == "sftp":
            key_filename = host_config.get("key_filename")
            transport = paramiko.Transport((hostname, port))
            transport.banner_timeout = 60

            if key_filename:
                key = paramiko.RSAKey.from_private_key_file(key_filename)
                transport.connect(username=username, pkey=key)
            else:
                transport.connect(username=username, password=password)

            sftp = paramiko.SFTPClient.from_transport(transport)
            if sftp is None:
                raise ConnectionError("Failed to initialize SFTP client.")

            remote_files = list_remote_sftp(sftp, remote_basepath, timeout=60)

            sftp.close()
            transport.close()

    except Exception as e:
        click.echo(f"\n⚠️  Warning: Failed to list remote files: {e}", err=True)
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


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="Search for files recursively in subdirectories when using glob patterns without path separators (e.g., *.css)",
)
@click.option(
    "-vc",
    "--visual-check",
    is_flag=True,
    help="Display tree comparison of local vs remote files before uploading (shows changes only)",
)
@click.option(
    "-vcc",
    "--visual-check-complete",
    is_flag=True,
    help="Display complete tree comparison including remote-only files",
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
@click.argument("patterns", nargs=-1, required=True)
def main(
    recursive,
    visual_check,
    visual_check_complete,
    max_depth,
    tree_summary,
    force,
    binding_alias,
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
      - Glob patterns: *.css *.js
      - Directories: src/assets (uploads all files in directory)

    \b
    Examples:
      gsupload *.css                                    # Auto-detect binding from current directory
      gsupload -b=frontend *.css                        # Upload CSS files using 'frontend' binding
      gsupload --binding=frontend *.css                 # Same as above (long form)
      gsupload -r -b=frontend *.css                     # Upload CSS files recursively
      gsupload -f -b=frontend *.css                     # Force upload without confirmation (fastest)
      gsupload -vc -b=frontend *.css                    # Visual check (changes only) before upload
      gsupload -vcc -b=frontend *.css                   # Visual check with complete tree
      gsupload -vc -r -b=backend *.js                   # Visual check for recursive JS file upload
      gsupload -vc --max-depth=5 -r -b=admin *.html     # Visual check with custom tree depth
      gsupload -vc -ts -b=frontend *.css                # Show summary only, no tree display
      gsupload -b=frontend src/assets                   # Upload all files in src/assets directory
      gsupload -b=backend index.html app.js             # Upload specific files to backend host

    \b
    Configuration:
      The script looks for configuration file in this order:
        1. Looks for .gsupload.json in the current directory and parent directories (walks up until found). Filename starts with dot (".") on purpose.
        2. ~/.gsupload/gsupload.json (no dot file)
        3. ~/.config/gsupload/gsupload.json (no dot file)

    """
    click.echo()

    config = load_config()

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

    host_config = get_host_config(config, binding_alias)

    local_basepath = Path(host_config["local_basepath"])
    if not local_basepath.exists():
        click.echo(
            f"Error: Local basepath '{local_basepath}' does not exist.", err=True
        )
        sys.exit(1)

    global_excludes = config.get("global_excludes", [])
    host_excludes = host_config.get("excludes", [])
    all_excludes = global_excludes + host_excludes

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
    if not force and (visual_check or visual_check_complete):
        new_count, overwrite_count, remote_only_count = display_visual_comparison(
            host_config,
            files_to_upload,
            local_basepath,
            protocol,
            binding_alias,
            max_depth,
            tree_summary,
            complete_tree=visual_check_complete,
        )

        if not click.confirm("\n⚠️  Proceed with upload?", default=False):
            click.echo("Upload cancelled.")
            sys.exit(0)

        click.echo("")

    if protocol == "ftp":
        upload_ftp(host_config, files_to_upload, local_basepath)
    elif protocol == "sftp":
        upload_sftp(host_config, files_to_upload, local_basepath)
    else:
        click.echo(
            f"Error: Unsupported protocol '{protocol}'. Use 'ftp' or 'sftp'.", err=True
        )
        sys.exit(1)

    click.echo()


if __name__ == "__main__":
    main()
