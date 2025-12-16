"""
Tests for gsupload.utils module.
"""

from pathlib import Path
from typing import List

import pytest

from gsupload.utils import calculate_remote_path, expand_patterns


class TestCalculateRemotePath:
    """Tests for calculate_remote_path function."""

    def test_simple_path(self, temp_dir: Path) -> None:
        """Test simple path calculation."""
        local_file = temp_dir / "index.html"
        local_file.touch()

        remote_path = calculate_remote_path(local_file, temp_dir, "/var/www")

        assert remote_path == "/var/www/index.html"

    def test_nested_path(self, temp_dir: Path) -> None:
        """Test nested path calculation."""
        subdir = temp_dir / "src" / "components"
        subdir.mkdir(parents=True)
        local_file = subdir / "header.js"
        local_file.touch()

        remote_path = calculate_remote_path(local_file, temp_dir, "/var/www")

        assert remote_path == "/var/www/src/components/header.js"

    def test_remote_basepath_with_trailing_slash(self, temp_dir: Path) -> None:
        """Test that trailing slash is handled."""
        local_file = temp_dir / "style.css"
        local_file.touch()

        remote_path = calculate_remote_path(local_file, temp_dir, "/var/www/")

        assert remote_path == "/var/www/style.css"

    def test_file_outside_basepath_exits(self, temp_dir: Path) -> None:
        """Test that file outside basepath causes exit."""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as f:
            other_file = Path(f.name)

        with pytest.raises(SystemExit):
            calculate_remote_path(other_file, temp_dir, "/var/www")

        other_file.unlink()


class TestExpandPatterns:
    """Tests for expand_patterns function."""

    def test_expand_specific_file(self, sample_file_structure: Path) -> None:
        """Test expanding a specific filename."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_file_structure)
            files = expand_patterns(
                ["index.html"], [], sample_file_structure, recursive=False
            )
            filenames = [f.name for f in files]

            assert "index.html" in filenames
        finally:
            os.chdir(original_cwd)

    def test_expand_glob_pattern(self, sample_file_structure: Path) -> None:
        """Test expanding a glob pattern."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_file_structure)
            files = expand_patterns(
                ["*.css"], [], sample_file_structure, recursive=False
            )
            filenames = [f.name for f in files]

            assert "style.css" in filenames
        finally:
            os.chdir(original_cwd)

    def test_expand_recursive(self, sample_file_structure: Path) -> None:
        """Test recursive pattern expansion."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_file_structure)
            files = expand_patterns(["*.js"], [], sample_file_structure, recursive=True)
            filenames = [f.name for f in files]

            assert "app.js" in filenames
            assert "header.js" in filenames
        finally:
            os.chdir(original_cwd)

    def test_expand_with_excludes(self, sample_file_structure: Path) -> None:
        """Test pattern expansion with excludes."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_file_structure)
            # Test that directory expansion respects excludes
            # The src directory should be walked but __pycache__ excluded
            files = expand_patterns(
                ["src"], ["__pycache__/"], sample_file_structure, recursive=False
            )
            filenames = [f.name for f in files]

            # Should have JS files but not pyc files
            assert "app.js" in filenames
            assert "header.js" in filenames
        finally:
            os.chdir(original_cwd)

    def test_expand_directory(self, sample_file_structure: Path) -> None:
        """Test expanding a directory path."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(sample_file_structure)
            files = expand_patterns(["src"], [], sample_file_structure, recursive=False)
            filenames = [f.name for f in files]

            assert "app.js" in filenames
            assert "header.js" in filenames
        finally:
            os.chdir(original_cwd)

    def test_expand_nonexistent_pattern_warns(
        self, sample_file_structure: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Test that nonexistent pattern produces warning."""
        files = expand_patterns(
            ["nonexistent*.xyz"], [], sample_file_structure, recursive=False
        )

        assert len(files) == 0
        captured = capsys.readouterr()
        assert "Warning" in captured.err or "nonexistent" in captured.err
