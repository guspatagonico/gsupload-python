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
from typing import List, Dict, Any

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


def expand_files(
    patterns: List[str], excludes: List[str], local_basepath: Path
) -> List[Path]:
    files = []
    for pattern in patterns:
        # Check if it's a glob pattern or direct file
        # If shell expanded it, it's a file path. If quoted, it's a glob pattern.
        # We can just use glob.glob on it.
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
            path = Path(m)
            if is_excluded(path, excludes, local_basepath):
                continue

            if path.is_file():
                files.append(path)
            elif path.is_dir():
                # Recursively add all files in directory
                files.extend(walk_directory(path, excludes, local_basepath))
    return files


@click.command()
@click.argument("args", nargs=-1, required=True)
def main(args):
    """
    Upload files to a remote server based on configuration.

    Usage: gsupload.py {filename | directory_name | glob} {host alias}

    Example: gsupload.py *.css frontend
    """
    if len(args) < 2:
        click.echo(
            "Usage: gsupload.py {filename | directory_name | glob} {host alias}",
            err=True,
        )
        sys.exit(1)

    host_alias = args[-1]
    patterns = args[:-1]

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

    files_to_upload = expand_files(patterns, all_excludes, local_basepath)

    if not files_to_upload:
        click.echo("No files found to upload.")
        sys.exit(0)

    protocol = host_config.get("protocol", "ftp").lower()

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
