"""
Tree comparison display for gsupload.

Displays visual diff between local and remote files before upload.
"""

import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import click
import paramiko

from gsupload import DEFAULT_MAX_DEPTH
from gsupload.utils import display_comment


def display_tree_comparison(
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
        host_config: Host configuration with connection details.
        local_files: List of local Path objects to upload.
        local_basepath: Local root directory.
        protocol: 'ftp' or 'sftp'.
        binding_alias: Binding configuration alias name.
        max_depth: Maximum tree depth to display (default: DEFAULT_MAX_DEPTH).
        summary_only: If True, show only statistics without tree (default: False).
        complete_tree: If True, show all files including remote-only (default: False).

    Returns:
        Tuple of (new_files_count, overwrite_count, remote_only_count).
    """
    from gsupload.protocols.ftp import list_remote_ftp
    from gsupload.protocols.sftp import list_remote_sftp

    hostname = host_config["hostname"]
    port = host_config.get("port", 21 if protocol == "ftp" else 22)
    username = host_config["username"]
    password = host_config.get("password")
    remote_basepath = host_config["remote_basepath"]

    # Calculate local file relative paths
    local_rel_paths: Set[str] = set()
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

    remote_files: Set[str] = set()

    try:
        if protocol == "ftp":
            import ftplib

            ftp = ftplib.FTP()
            ftp.connect(hostname, port, timeout=60)
            ftp.login(username, password or "")
            ftp.set_pasv(True)  # Use passive mode by default

            scan_start = time.time()
            remote_files = list_remote_ftp(ftp, remote_basepath, timeout=60)
            scan_elapsed = time.time() - scan_start

            # Display scan time
            _display_scan_time(scan_elapsed)

            ftp.quit()

        elif protocol == "sftp":
            key_filename = host_config.get("key_filename")

            # Use SSHClient for better compatibility and automatic host key handling
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                # Retry connection with multiple strategies for problematic servers
                _connect_sftp_with_retry(
                    ssh, hostname, port, username, password, key_filename
                )

                # Open SFTP session
                sftp = ssh.open_sftp()

                click.echo("🔍 Listing remote files...")
                scan_start = time.time()
                remote_files = list_remote_sftp(sftp, remote_basepath, timeout=60)
                scan_elapsed = time.time() - scan_start

                # Display scan time
                _display_scan_time(scan_elapsed)

                sftp.close()
                ssh.close()

            except Exception:
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
    remote_only_files: Set[str] = set()
    if complete_tree:
        remote_only_files = remote_files - local_rel_paths

    # Build tree structure
    if not summary_only:
        _display_tree(
            new_files,
            overwrite_files,
            remote_only_files,
            local_basepath,
            remote_basepath,
            max_depth,
            complete_tree,
        )

    # Display summary
    _display_summary(
        new_files, overwrite_files, remote_files, remote_only_files, complete_tree
    )

    return (len(new_files), len(overwrite_files), len(remote_only_files))


def _display_scan_time(elapsed: float) -> None:
    """Display formatted scan time."""
    days = int(elapsed // 86400)
    hours = int((elapsed % 86400) // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = elapsed % 60

    time_parts = []
    if days > 0:
        time_parts.append(f"{days}d")
    if hours > 0 or days > 0:
        time_parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        time_parts.append(f"{minutes}m")
    time_parts.append(f"{seconds:.2f}s")

    click.echo(f"⏱️  Scan completed in {' '.join(time_parts)}")


def _connect_sftp_with_retry(
    ssh: paramiko.SSHClient,
    hostname: str,
    port: int,
    username: str,
    password: str | None,
    key_filename: str | None,
) -> None:
    """Connect to SFTP with retry strategies for problematic servers."""
    max_retries = 4
    retry_count = 0
    connection_successful = False

    while retry_count < max_retries and not connection_successful:
        try:
            # Progressive timeout and connection strategy
            if retry_count == 0:
                timeout_value = 120
                use_compression = True
                gss_auth = False
                gss_kex = False
                allow_agent = not password and not key_filename
                look_for_keys = not password or key_filename
                auth_method = (
                    "agent" if allow_agent else ("key" if key_filename else "password")
                )
                click.echo(
                    f"📡 Attempting connection with standard settings... (auth: {auth_method})"
                )
            elif retry_count == 1:
                timeout_value = 150
                use_compression = False
                gss_auth = False
                gss_kex = False
                allow_agent = not password and not key_filename
                look_for_keys = not password or key_filename
                click.echo("⏳ Retry 1/3: Disabling compression...")
            elif retry_count == 2:
                timeout_value = 180
                use_compression = False
                gss_auth = False
                gss_kex = False
                allow_agent = not password and not key_filename
                look_for_keys = False
                click.echo("⏳ Retry 2/3: Disabling GSS auth and key scanning...")
            else:
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
            ImportError,
        ) as conn_error:
            retry_count += 1
            if retry_count < max_retries:
                click.echo(
                    click.style(
                        f"⚠️  Connection attempt {retry_count} failed: {conn_error}",
                        fg="yellow",
                    )
                )
                time.sleep(3)
            else:
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


def _display_tree(
    new_files: Set[str],
    overwrite_files: Set[str],
    remote_only_files: Set[str],
    local_basepath: Path,
    remote_basepath: str,
    max_depth: int,
    complete_tree: bool,
) -> None:
    """Build and display tree structure."""
    tree_structure: Dict[str, Any] = {}

    def add_to_tree(path: str, status: str) -> None:
        parts = path.split("/")
        current = tree_structure

        # Build directory structure
        for part in parts[:-1]:
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
    click.echo(f"\n📂 File Comparison Tree - {tree_mode} (max depth: {max_depth}):\n")
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

    def display_node(node: dict, prefix: str = "", depth: int = 0) -> None:
        nonlocal displayed_count, depth_exceeded_count

        if depth > max_depth:

            def count_items(n: dict) -> int:
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
        dirs = [(k, v) for k, v in items if v.get("__type__") == "dir"]
        files = [(k, v) for k, v in items if v.get("__type__") == "file"]
        all_items = dirs + files

        for idx, (name, value) in enumerate(all_items):
            is_last = idx == len(all_items) - 1
            connector = "└── " if is_last else "├── "

            if value.get("__type__") == "dir":
                click.echo(f"{prefix}{connector}{name}/")
                displayed_count += 1

                extension = "    " if is_last else "│   "
                display_node(
                    value.get("__children__", {}), prefix + extension, depth + 1
                )

            elif value.get("__type__") == "file":
                status = value.get("__status__", "")

                if status == "[NEW]":
                    colored_status = click.style(status, fg="green", bold=True)
                elif status == "[OVERWRITE]":
                    colored_status = click.style(status, fg="yellow", bold=True)
                else:
                    colored_status = click.style(status, fg="blue", dim=True)

                click.echo(f"{prefix}{connector}{name} {colored_status}")
                displayed_count += 1

    display_node(tree_structure)

    if depth_exceeded_count > 0:
        click.echo(
            f"\n... ({depth_exceeded_count} more files beyond depth {max_depth})"
        )


def _display_summary(
    new_files: Set[str],
    overwrite_files: Set[str],
    remote_files: Set[str],
    remote_only_files: Set[str],
    complete_tree: bool,
) -> None:
    """Display summary statistics."""
    click.echo(f"\n{'=' * 60}")
    click.echo("📊 Summary:")
    click.echo(f"{'=' * 60}")
    click.echo(f"  {click.style('New files:         ', fg='green')} {len(new_files)}")
    click.echo(
        f"  {click.style('Files to overwrite:', fg='yellow')} {len(overwrite_files)}"
    )

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
