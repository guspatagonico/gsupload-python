"""
Shared pytest fixtures for gsupload tests.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Sample configuration for testing."""
    return {
        "global_excludes": ["*.pyc", "__pycache__/", ".git/"],
        "bindings": {
            "test-ftp": {
                "protocol": "ftp",
                "hostname": "ftp.example.com",
                "port": 21,
                "username": "testuser",
                "password": "testpass",
                "local_basepath": "/tmp/local",
                "remote_basepath": "/var/www/html",
                "excludes": ["*.tmp"],
            },
            "test-sftp": {
                "protocol": "sftp",
                "hostname": "sftp.example.com",
                "port": 22,
                "username": "sftpuser",
                "password": "sftppass",
                "local_basepath": "/tmp/local",
                "remote_basepath": "/home/user/public_html",
            },
        },
    }


@pytest.fixture
def config_file(temp_dir: Path, sample_config: Dict[str, Any]) -> Path:
    """Create a temporary config file."""
    config_path = temp_dir / ".gsupload.json"
    with open(config_path, "w") as f:
        json.dump(sample_config, f)
    return config_path


@pytest.fixture
def sample_file_structure(temp_dir: Path) -> Path:
    """Create a sample file structure for testing."""
    # Create directories
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "components").mkdir()
    (temp_dir / "assets").mkdir()

    # Create files
    (temp_dir / "index.html").write_text("<html></html>")
    (temp_dir / "style.css").write_text("body {}")
    (temp_dir / "src" / "app.js").write_text("console.log('app');")
    (temp_dir / "src" / "components" / "header.js").write_text("// header")
    (temp_dir / "assets" / "logo.png").write_bytes(b"\x89PNG")

    # Create files that should be excluded
    (temp_dir / "__pycache__").mkdir()
    (temp_dir / "__pycache__" / "module.pyc").write_bytes(b"")
    (temp_dir / "temp.tmp").write_text("temporary")

    return temp_dir
