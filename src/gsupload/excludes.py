"""
File exclusion pattern handling for gsupload.

Handles .gsupload_ignore files, pattern matching, and directory walking.
"""

import fnmatch
import os
from pathlib import Path
from typing import List

import click


def load_ignore_file(path: Path) -> List[str]:
    """
    Load exclude patterns from a .gsupload_ignore file.

    Args:
        path: Path to the ignore file.

    Returns:
        List of exclude patterns (empty if file doesn't exist or can't be read).
    """
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            return [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    except Exception:
        return []


def collect_ignore_patterns(directory: Path, local_basepath: Path) -> List[str]:
    """
    Collect all .gsupload_ignore files from directory up to local_basepath.

    Returns combined exclude patterns with additive behavior.

    Args:
        directory: Starting directory.
        local_basepath: Root directory (stops walking up here).

    Returns:
        List of exclude patterns from all .gsupload_ignore files found.
    """
    all_excludes: List[str] = []
    current = directory

    # Walk up from directory to local_basepath, collecting ignore files
    while True:
        ignore_file = current / ".gsupload_ignore"
        if ignore_file.exists():
            local_excludes = load_ignore_file(ignore_file)

            # Adjust patterns to be relative to local_basepath
            adjusted_excludes: List[str] = []
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
    """
    Check if a path matches any exclude pattern.

    Supports fnmatch and glob-style patterns.

    Args:
        path: Path to check.
        excludes: List of exclude patterns.
        local_basepath: Base directory for relative path calculation.

    Returns:
        True if path should be excluded, False otherwise.
    """
    try:
        rel_path = path.relative_to(local_basepath)
    except ValueError:
        return False

    name = path.name

    # Create a "rooted" path for matching to ensure anchors work correctly
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
        if "/" not in p:
            # Simple name match (e.g. "*.log", "node_modules")
            if fnmatch.fnmatch(name, p):
                return True
        else:
            # Pattern involves paths (e.g. "src/*.tmp", "/build", "foo/bar")
            match_pattern = p
            if match_pattern.startswith("/"):
                # Pattern is anchored - match against rooted_rel_path
                if rooted_rel_path.match(match_pattern):
                    return True
            else:
                # Pattern is not anchored - treat as anchored to base
                match_pattern = "/" + match_pattern
                if rooted_rel_path.match(match_pattern):
                    return True

    return False


def walk_directory(
    directory: Path, excludes: List[str], local_basepath: Path
) -> List[Path]:
    """
    Recursively walk a directory, applying exclude patterns.

    Args:
        directory: Directory to walk.
        excludes: List of exclude patterns.
        local_basepath: Base directory for relative path calculation.

    Returns:
        List of file paths that are not excluded.
    """
    files: List[Path] = []

    # Collect all .gsupload_ignore files from this directory up to local_basepath
    ignore_excludes = collect_ignore_patterns(directory, local_basepath)

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


def show_ignored_files(
    local_basepath: Path, excludes: List[str], recursive: bool = True
) -> None:
    """
    List all files and directories that are being ignored by exclude patterns.

    Args:
        local_basepath: Base directory to scan from.
        excludes: List of exclude patterns to apply.
        recursive: If True, scan subdirectories recursively.
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

    ignored_items: List[tuple] = []
    scanned_count = 0

    def scan_directory(directory: Path, depth: int = 0) -> None:
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
