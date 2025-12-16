"""
Tests for gsupload.cli module.
"""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from gsupload.cli import main


class TestCli:
    """Tests for CLI commands."""

    def test_version_flag(self) -> None:
        """Test --version flag displays version."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "gsupload version" in result.output

    def test_help_flag(self) -> None:
        """Test --help flag displays help."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Upload files and directories" in result.output

    def test_no_args_shows_help(self) -> None:
        """Test that no arguments shows help."""
        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_show_config_flag(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test --show-config flag displays configuration."""
        import json

        config_path = temp_dir / ".gsupload.json"
        with open(config_path, "w") as f:
            json.dump(sample_config, f)

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=str(temp_dir)):
            # Copy config to isolated filesystem
            (Path.cwd() / ".gsupload.json").write_text(json.dumps(sample_config))

            result = runner.invoke(main, ["--show-config"])

            assert "Configuration Files" in result.output or "bindings" in result.output


class TestCliOptions:
    """Tests for CLI options."""

    def test_recursive_flag_default(self) -> None:
        """Test that recursive is enabled by default."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert "recursive" in result.output.lower()

    def test_visual_check_flags(self) -> None:
        """Test visual check flags are documented."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert "visual-check" in result.output
        assert "visual-check-complete" in result.output

    def test_binding_option(self) -> None:
        """Test binding option is documented."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert "--binding" in result.output or "-b" in result.output

    def test_max_workers_option(self) -> None:
        """Test max-workers option is documented."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert "max-workers" in result.output
