"""
Configuration loading and merging for gsupload.

Handles hierarchical configuration from global and project-level files.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click


def load_config_with_sources() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load and merge configuration files with source tracking.

    Returns:
        Tuple of (merged_config, source_map) where source_map tracks which file
        contributed each piece of configuration.
    """
    configs_to_merge: List[Tuple[Path, Dict[str, Any]]] = []
    source_map: Dict[str, Any] = {
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
    project_configs: List[Path] = []
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
    merged_config: Dict[str, Any] = {}
    all_global_excludes: List[str] = []

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
        Dictionary containing merged host configurations.
    """
    merged_config, _ = load_config_with_sources()
    return merged_config


def get_host_config(config: Dict[str, Any], alias: str) -> Dict[str, Any]:
    """
    Get host binding configuration by alias.

    Args:
        config: Merged configuration dictionary.
        alias: Binding alias name.

    Returns:
        Binding configuration dictionary.

    Raises:
        SystemExit: If alias not found in configuration.
    """
    bindings = config.get("bindings", {})
    if alias not in bindings:
        click.echo(f"Error: Host alias '{alias}' not found in configuration.", err=True)
        sys.exit(1)
    return bindings[alias]


def show_config(merged_config: Dict[str, Any], source_map: Dict[str, Any]) -> None:
    """
    Display merged configuration with source annotations.

    Shows:
    1. List of config files in merge order
    2. Merged configuration as colored JSON
    3. Source annotations for each item

    Args:
        merged_config: The final merged configuration.
        source_map: Dictionary tracking sources for each config item.
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


def auto_detect_binding(config: Dict[str, Any]) -> Optional[str]:
    """
    Auto-detect binding by comparing current working directory with local_basepath.

    Returns the binding alias if found, None otherwise.
    Prioritizes the most specific match (deepest path).
    If multiple bindings point to the same local_basepath, prompts user to choose.

    Args:
        config: Merged configuration dictionary.

    Returns:
        Binding alias string or None if not detected.
    """
    bindings = config.get("bindings", {})
    if not bindings:
        return None

    cwd = Path.cwd().resolve()

    # Find all bindings where cwd is within or equals local_basepath
    matches: List[Tuple[str, Path, Dict[str, Any]]] = []
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
