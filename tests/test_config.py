"""
Tests for gsupload.config module.
"""

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from gsupload.config import (
    auto_detect_binding,
    get_host_config,
    load_config,
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_returns_dict(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test that load_config returns a dictionary."""
        config_path = temp_dir / ".gsupload.json"
        with open(config_path, "w") as f:
            json.dump(sample_config, f)

        with patch.object(Path, "cwd", return_value=temp_dir):
            config = load_config()

        assert isinstance(config, dict)
        assert "bindings" in config

    def test_load_config_merges_global_excludes(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test that global_excludes are properly loaded."""
        config_path = temp_dir / ".gsupload.json"
        with open(config_path, "w") as f:
            json.dump(sample_config, f)

        with patch.object(Path, "cwd", return_value=temp_dir):
            config = load_config()

        assert "global_excludes" in config
        assert "*.pyc" in config["global_excludes"]


class TestGetHostConfig:
    """Tests for get_host_config function."""

    def test_get_existing_binding(self, sample_config: Dict[str, Any]) -> None:
        """Test retrieving an existing binding."""
        host_config = get_host_config(sample_config, "test-ftp")

        assert host_config["protocol"] == "ftp"
        assert host_config["hostname"] == "ftp.example.com"

    def test_get_nonexistent_binding_exits(self, sample_config: Dict[str, Any]) -> None:
        """Test that getting a nonexistent binding exits."""
        with pytest.raises(SystemExit):
            get_host_config(sample_config, "nonexistent")


class TestAutoDetectBinding:
    """Tests for auto_detect_binding function."""

    def test_auto_detect_returns_matching_binding(
        self, temp_dir: Path, sample_config: Dict[str, Any]
    ) -> None:
        """Test auto-detection of binding by cwd."""
        # Update config with temp_dir as local_basepath
        sample_config["bindings"]["test-ftp"]["local_basepath"] = str(temp_dir)

        with patch.object(Path, "cwd", return_value=temp_dir):
            binding = auto_detect_binding(sample_config)

        assert binding == "test-ftp"

    def test_auto_detect_returns_none_when_no_match(
        self, sample_config: Dict[str, Any]
    ) -> None:
        """Test auto-detection returns None when no binding matches."""
        with patch.object(Path, "cwd", return_value=Path("/nonexistent/path")):
            binding = auto_detect_binding(sample_config)

        assert binding is None

    def test_auto_detect_empty_bindings(self) -> None:
        """Test auto-detection with empty bindings."""
        config: Dict[str, Any] = {"bindings": {}}
        binding = auto_detect_binding(config)
        assert binding is None
