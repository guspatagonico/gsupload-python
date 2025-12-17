"""
CLI entry point for gsupload.

Provides the command-line interface using Click.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import click

from gsupload import __version__, DEFAULT_MAX_DEPTH
from gsupload.config import (
    auto_detect_binding,
    get_host_config,
    load_config,
    load_config_with_sources,
)

from gsupload.excludes import show_ignored_files
from gsupload.protocols.ftp import upload_ftp
from gsupload.protocols.sftp import upload_sftp
from gsupload.tree import display_tree_comparison
from gsupload.utils import display_comment, expand_patterns

# Suppress paramiko's verbose error messages
logging.getLogger("paramiko").setLevel(logging.CRITICAL)


def version_callback(ctx: click.Context, param: click.Parameter, value: bool) -> None:
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
    recursive: bool,
    visual_check: bool,
    visual_check_complete: bool,
    max_depth: int,
    tree_summary: bool,
    force: bool,
    binding_alias: Optional[str],
    show_config: bool,
    show_ignored: bool,
    max_workers: Optional[int],
    ftp_active: bool,
    patterns: Tuple[str, ...],
) -> None:
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
        from gsupload.config import show_config as display_config_fn

        merged_config, source_map = load_config_with_sources()
        display_config_fn(merged_config, source_map)
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

        show_ignored_files(local_basepath, all_excludes, recursive)
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

    files_to_upload = expand_patterns(
        list(patterns), all_excludes, local_basepath, recursive
    )

    if not files_to_upload:
        click.echo("No files found to upload.")
        sys.exit(0)

    # Sort files by depth (external first) then alphabetically for consistent ordering
    def sort_key(f: Path) -> Tuple[int, str]:
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
        # If -vc is explicitly set, show changes only (disable complete tree)
        show_complete_tree = visual_check_complete and not visual_check

        new_count, overwrite_count, remote_only_count = display_tree_comparison(
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
