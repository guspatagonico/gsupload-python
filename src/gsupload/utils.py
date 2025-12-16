"""
Utility functions for gsupload.

Contains helper functions for path calculations, file expansion, and display.
"""

import glob
import os
import sys
from pathlib import Path
from typing import List

import click

from gsupload.excludes import is_excluded, walk_directory


def display_comment(comment: str, prefix: str = "💬") -> None:
    """
    Display a comment with appropriate styling.

    Args:
        comment: Comment text to display.
        prefix: Emoji prefix for the comment.
    """
    if comment:
        click.echo(click.style(f"{prefix} {comment}", fg="cyan"))


def calculate_remote_path(
    local_path: Path, local_basepath: Path, remote_basepath: str
) -> str:
    """
    Calculate remote path from local path and base paths.

    Args:
        local_path: Local file path.
        local_basepath: Local base directory.
        remote_basepath: Remote base directory.

    Returns:
        Remote path string.

    Raises:
        SystemExit: If local_path is not within local_basepath.
    """
    try:
        relative_path = local_path.absolute().relative_to(local_basepath.absolute())
    except ValueError:
        click.echo(
            f"Error: File '{local_path}' is not within local basepath '{local_basepath}'.",
            err=True,
        )
        sys.exit(1)

    # Ensure remote_basepath doesn't end with slash unless it's root
    remote_base = remote_basepath.rstrip("/")
    rel_path_str = str(relative_path).replace(os.sep, "/")
    return f"{remote_base}/{rel_path_str}"


def expand_patterns(
    patterns: List[str],
    excludes: List[str],
    local_basepath: Path,
    recursive: bool = False,
) -> List[Path]:
    """
    Expand glob patterns to a list of files.

    Args:
        patterns: List of file patterns or paths.
        excludes: List of exclude patterns.
        local_basepath: Base directory for relative path calculation.
        recursive: If True, search recursively for patterns without path separators.

    Returns:
        List of resolved file paths.
    """
    files: List[Path] = []
    seen: set = set()

    for pattern in patterns:
        matched: List[str] = []

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
