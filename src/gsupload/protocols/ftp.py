"""
FTP protocol implementation for gsupload.

Handles FTP file listing and upload operations.
"""

import ftplib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue
from threading import Lock
from typing import Any, Dict, List, Set, Tuple

import click

from gsupload.utils import calculate_remote_path


def list_remote_ftp(
    ftp: ftplib.FTP,
    remote_basepath: str,
    timeout: int = 60,
    progress_bar: Any = None,
) -> Set[str]:
    """
    Recursively list all files on FTP server starting from remote_basepath.

    Uses iterative BFS approach for directory scanning.

    Args:
        ftp: Active FTP connection.
        remote_basepath: Remote root directory to start listing from.
        timeout: Socket timeout in seconds (default: 60).
        progress_bar: Optional click progressbar to update as files are found.

    Returns:
        Set of relative file paths from remote_basepath.
    """
    remote_files: Set[str] = set()
    remote_base = remote_basepath.rstrip("/")
    dirs_scanned = 0
    files_found = 0
    dirs_queue: Queue = Queue()
    dirs_queue.put(remote_base)

    def scan_directory(path: str, conn: ftplib.FTP) -> Tuple[List[str], List[str]]:
        """Scan a single directory and return (files, subdirs)."""
        found_files: List[str] = []
        found_dirs: List[str] = []

        try:
            # Try using MLSD for better metadata (if supported)
            entries: List[Tuple[str, bool]] = []
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


def upload_ftp(
    host_config: Dict[str, Any],
    files: List[Path],
    local_basepath: Path,
    use_pasv: bool = True,
) -> None:
    """
    Upload files via FTP with parallel connections.

    Args:
        host_config: Host configuration with connection details.
        files: List of local file paths to upload.
        local_basepath: Local base directory.
        use_pasv: Use passive mode (default: True).
    """
    hostname = host_config["hostname"]
    port = host_config.get("port", 21)
    username = host_config["username"]
    password = host_config["password"]
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
            # Each thread needs its own FTP connection
            ftp = ftplib.FTP()
            ftp.connect(hostname, port, timeout=60)
            ftp.login(username, password)
            ftp.set_pasv(use_pasv)

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
