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
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict

CONFIG_LOCATIONS = [
    Path("hosts.json"),
    Path.home() / ".gsupload" / "hosts.json",
    Path.home() / ".config" / "gsupload" / "hosts.json",
]


def load_config() -> Dict[str, Any]:
    config_file = None
    for loc in CONFIG_LOCATIONS:
        if loc.exists():
            config_file = loc
            break

    if not config_file:
        click.echo(
            f"Error: Configuration file not found. Checked: {', '.join(str(p) for p in CONFIG_LOCATIONS)}",
            err=True,
        )
        sys.exit(1)

    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        click.echo(f"Error: Failed to parse '{config_file}': {e}", err=True)
        sys.exit(1)


def get_host_config(config: Dict[str, Any], alias: str) -> Dict[str, Any]:
    if alias not in config:
        click.echo(f"Error: Host alias '{alias}' not found in configuration.", err=True)
        sys.exit(1)
    return config[alias]


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
    ftp: ftplib.FTP, remote_basepath: str, timeout: int = 60
) -> Set[str]:
    """
    Recursively list all files on FTP server starting from remote_basepath.

    Args:
        ftp: Active FTP connection
        remote_basepath: Remote root directory to start listing from
        timeout: Socket timeout in seconds (default: 60)

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
    sftp: paramiko.SFTPClient, remote_basepath: str, timeout: int = 60
) -> Set[str]:
    """
    Recursively list all files on SFTP server starting from remote_basepath.

    Args:
        sftp: Active SFTP connection
        remote_basepath: Remote root directory to start listing from
        timeout: Keepalive interval in seconds (default: 60)

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

    try:
        ftp = ftplib.FTP()
        ftp.connect(hostname, port)
        ftp.login(username, password)

        for local_file in files:
            if local_file.is_dir():
                continue  # Directories are handled by walking or creating, but here we expect a list of files

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
                    click.echo(f"Uploading {local_file} to {remote_path}...")
                    ftp.storbinary(f"STOR {remote_path}", f)
            except Exception as e:
                click.echo(f"Failed to upload {local_file}: {e}", err=True)

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

        for local_file in files:
            if local_file.is_dir():
                continue

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
                click.echo(f"Uploading {local_file} to {remote_path}...")
                sftp.put(str(local_file), remote_path)
            except Exception as e:
                click.echo(f"Failed to upload {local_file}: {e}", err=True)

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
    ignore_file = directory / ".gsuploadignore"

    local_excludes = load_ignore_file(ignore_file)
    adjusted_local_excludes = []

    # Adjust local excludes to be relative to local_basepath
    if local_excludes:
        try:
            rel_dir = directory.relative_to(local_basepath)
        except ValueError:
            rel_dir = Path(".")

        for p in local_excludes:
            if "/" in p.rstrip("/"):
                # It has path components. Anchor it to the current directory.
                # If p starts with /, it's anchored to current dir.
                # If p doesn't start with /, it's also anchored to current dir because it has slashes.
                # e.g. "foo/bar" in src/.gsuploadignore means "src/foo/bar".

                clean_p = p
                if clean_p.startswith("/"):
                    clean_p = clean_p[1:]

                # Construct new pattern: /rel_dir/clean_p
                # We use forward slashes for patterns
                rel_dir_str = str(rel_dir).replace(os.sep, "/")
                if rel_dir_str == ".":
                    new_p = "/" + clean_p
                else:
                    new_p = "/" + rel_dir_str + "/" + clean_p

                adjusted_local_excludes.append(new_p)
            else:
                # No slash (e.g. "*.tmp"). Applies to names anywhere inside.
                # Keep as is.
                adjusted_local_excludes.append(p)

    current_excludes = excludes + adjusted_local_excludes

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
    max_depth: int = 8,
    summary_only: bool = False,
) -> Tuple[int, int, int]:
    """
    Display tree comparison of local vs remote files before upload.

    Args:
        host_config: Host configuration with connection details
        local_files: List of local Path objects to upload
        local_basepath: Local root directory
        protocol: 'ftp' or 'sftp'
        max_depth: Maximum tree depth to display (default: 8)
        summary_only: If True, show only statistics without tree (default: False)

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
    click.echo(f"\n🔍 Connecting to {hostname}...")
    remote_files = set()

    try:
        if protocol == "ftp":
            ftp = ftplib.FTP()
            ftp.connect(hostname, port, timeout=60)
            ftp.login(username, password or "")

            click.echo("📡 Listing remote files...")
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

            click.echo("📡 Listing remote files...")
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
    remote_only_files = remote_files - local_rel_paths

    # Build tree structure
    if not summary_only:
        tree_data = defaultdict(list)

        for path in sorted(new_files):
            depth = path.count("/")
            tree_data[depth].append((path, "[NEW]"))

        for path in sorted(overwrite_files):
            depth = path.count("/")
            tree_data[depth].append((path, "[OVERWRITE]"))

        for path in sorted(remote_only_files):
            depth = path.count("/")
            tree_data[depth].append((path, "[REMOTE ONLY]"))

        # Display tree
        click.echo(f"\n📂 File Comparison Tree (max depth: {max_depth}):\n")
        click.echo(f"Local:  {local_basepath}")
        click.echo(f"Remote: {remote_basepath}\n")

        displayed_count = 0
        depth_exceeded_count = 0

        for depth in sorted(tree_data.keys()):
            if depth > max_depth:
                depth_exceeded_count += len(tree_data[depth])
                continue

            for path, status in tree_data[depth]:
                # Build tree formatting
                parts = path.split("/")
                indent = ""

                for i in range(len(parts) - 1):
                    indent += "│   "

                if len(parts) > 1:
                    connector = "├── "
                else:
                    connector = ""

                # Color status markers
                if status == "[NEW]":
                    colored_status = click.style(status, fg="green", bold=True)
                elif status == "[OVERWRITE]":
                    colored_status = click.style(status, fg="yellow", bold=True)
                else:  # REMOTE ONLY
                    colored_status = click.style(status, fg="blue", dim=True)

                click.echo(f"{indent}{connector}{parts[-1]} {colored_status}")
                displayed_count += 1

        if depth_exceeded_count > 0:
            click.echo(
                f"\n... ({depth_exceeded_count} more files beyond depth {max_depth})"
            )

    # Display summary
    click.echo(f"\n{'=' * 60}")
    click.echo(f"📊 Summary:")
    click.echo(f"{'=' * 60}")
    click.echo(f"  {click.style('New files:', fg='green')}        {len(new_files)}")
    click.echo(
        f"  {click.style('Files to overwrite:', fg='yellow')} {len(overwrite_files)}"
    )
    click.echo(
        f"  {click.style('Remote only:', fg='blue')}       {len(remote_only_files)}"
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


@click.command()
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
    help="Display tree comparison of local vs remote files before uploading",
)
@click.option(
    "--max-depth",
    default=8,
    type=int,
    help="Maximum tree depth to display in visual check (default: 8)",
)
@click.option(
    "-ts",
    "--tree-summary",
    is_flag=True,
    help="Show summary statistics only, skip tree display in visual check",
)
@click.argument("patterns", nargs=-1, required=True)
@click.argument("host_alias")
def main(recursive, visual_check, max_depth, tree_summary, patterns, host_alias):
    """
    Upload files and directories to a remote FTP/SFTP server.

    Uploads files matching PATTERNS to the remote server configured under HOST_ALIAS.
    The remote path is calculated relative to the local_basepath and remote_basepath
    defined in your hosts.json configuration file.

    \b
    PATTERNS can be:
      - Specific filenames: index.html style.css
      - Glob patterns: *.css *.js
      - Directories: src/assets (uploads all files in directory)

    \b
    Examples:
      gsupload *.css frontend                    # Upload CSS files in current directory
      gsupload -r *.css frontend                 # Upload CSS files recursively in all subdirectories
      gsupload -vc *.css frontend                # Visual check before uploading CSS files
      gsupload -vc -r *.js backend               # Visual check for recursive JS file upload
      gsupload -vc --max-depth 5 -r *.html admin # Visual check with custom tree depth
      gsupload -vc -ts *.css frontend            # Show summary only, no tree display
      gsupload src/assets frontend               # Upload all files in src/assets directory
      gsupload index.html app.js backend         # Upload specific files to backend host

    \b
    Configuration:
      The script looks for hosts.json in:
        - ./hosts.json
        - ~/.gsupload/hosts.json
        - ~/.config/gsupload/hosts.json
    """
    config = load_config()
    host_config = get_host_config(config, host_alias)

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

    protocol = host_config.get("protocol", "ftp").lower()

    # Visual check before upload
    if visual_check:
        new_count, overwrite_count, remote_only_count = display_visual_comparison(
            host_config,
            files_to_upload,
            local_basepath,
            protocol,
            max_depth,
            tree_summary,
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


if __name__ == "__main__":
    main()
