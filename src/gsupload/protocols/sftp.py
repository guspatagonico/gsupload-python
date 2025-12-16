"""
SFTP protocol implementation for gsupload.

Handles SFTP file listing and upload operations.
"""

import os
import stat
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue
from threading import Lock
from typing import Any, Dict, List, Set, Tuple

import click
import paramiko

from gsupload.utils import calculate_remote_path


def list_remote_sftp(
    sftp: paramiko.SFTPClient,
    remote_basepath: str,
    timeout: int = 60,
    progress_bar: Any = None,
    max_workers: int = 3,
) -> Set[str]:
    """
    Recursively list all files on SFTP server starting from remote_basepath.

    Uses iterative approach with single connection for SFTP compatibility.

    Args:
        sftp: Active SFTP connection.
        remote_basepath: Remote root directory to start listing from.
        timeout: Keepalive interval in seconds (default: 60).
        progress_bar: Optional click progressbar to update as files are found.
        max_workers: Number of parallel scanning workers (default: 3, unused).

    Returns:
        Set of relative file paths from remote_basepath.
    """
    remote_files: Set[str] = set()
    remote_base = remote_basepath.rstrip("/")
    dirs_scanned = 0
    files_found = 0
    files_lock = Lock()
    dirs_queue: Queue = Queue()
    dirs_queue.put(remote_base)

    def scan_directory(
        path: str, worker_sftp: paramiko.SFTPClient
    ) -> Tuple[List[str], List[str]]:
        """Scan a single directory and return (files, subdirs)."""
        found_files: List[str] = []
        found_dirs: List[str] = []

        try:
            # Try listdir_attr first (provides file attributes)
            entries: List[Tuple[str, int | None]] = []
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

    # Get SSH connection info
    channel = sftp.get_channel()
    if not channel:
        # Fallback to single-threaded if no channel available
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
            while not dirs_queue.empty():
                path = dirs_queue.get()

                dirs_scanned += 1
                if dirs_scanned % 3 == 0:
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


def upload_sftp(
    host_config: Dict[str, Any],
    files: List[Path],
    local_basepath: Path,
) -> None:
    """
    Upload files via SFTP with parallel connections.

    Args:
        host_config: Host configuration with connection details.
        files: List of local file paths to upload.
        local_basepath: Local base directory.
    """
    hostname = host_config["hostname"]
    port = host_config.get("port", 22)
    username = host_config["username"]
    password = host_config.get("password")
    key_filename = host_config.get("key_filename")
    remote_basepath = host_config["remote_basepath"]
    max_workers = host_config.get("max_workers", 5)

    # Sort files by depth (external first) then alphabetically
    def sort_key(f: Path) -> Tuple[int, str]:
        try:
            rel_path = f.relative_to(local_basepath)
            depth = len(rel_path.parts) - 1
            return (depth, str(rel_path).lower())
        except ValueError:
            return (999, str(f).lower())

    sorted_files = sorted(files, key=sort_key)

    # Cache for created directories (shared across threads)
    created_dirs: Set[str] = set()
    dir_lock = Lock()

    # Progress tracking
    completed = 0
    completed_lock = Lock()
    total_files = len([f for f in sorted_files if not f.is_dir()])

    def upload_single_file(local_file: Path) -> Tuple[bool, str, str]:
        """Upload a single file. Returns (success, local_path, message)."""
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

            sftp_conn = ssh.open_sftp()

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
                                sftp_conn.stat(current_path)
                                created_dirs.add(current_path)
                            except Exception:
                                try:
                                    sftp_conn.mkdir(current_path)
                                    created_dirs.add(current_path)
                                except Exception:
                                    pass  # Directory might exist

            # Upload the file
            sftp_conn.put(str(local_file), remote_path)

            sftp_conn.close()
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
