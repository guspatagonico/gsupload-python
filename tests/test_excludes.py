"""
Tests for gsupload.excludes module.
"""

from pathlib import Path

from gsupload.excludes import (
    collect_ignore_patterns,
    is_excluded,
    load_ignore_file,
    walk_directory,
)


class TestLoadIgnoreFile:
    """Tests for load_ignore_file function."""

    def test_load_existing_ignore_file(self, temp_dir: Path) -> None:
        """Test loading an existing ignore file."""
        ignore_file = temp_dir / ".gsupload_ignore"
        ignore_file.write_text("*.log\n# comment\nnode_modules/\n")

        patterns = load_ignore_file(ignore_file)

        assert patterns == ["*.log", "node_modules/"]

    def test_load_nonexistent_file_returns_empty(self, temp_dir: Path) -> None:
        """Test that loading nonexistent file returns empty list."""
        patterns = load_ignore_file(temp_dir / "nonexistent")
        assert patterns == []

    def test_load_empty_file(self, temp_dir: Path) -> None:
        """Test loading an empty ignore file."""
        ignore_file = temp_dir / ".gsupload_ignore"
        ignore_file.write_text("")

        patterns = load_ignore_file(ignore_file)
        assert patterns == []


class TestIsExcluded:
    """Tests for is_excluded function."""

    def test_simple_pattern_match(self, temp_dir: Path) -> None:
        """Test simple filename pattern matching."""
        test_file = temp_dir / "test.log"
        test_file.touch()

        excludes = ["*.log"]
        assert is_excluded(test_file, excludes, temp_dir) is True

    def test_simple_pattern_no_match(self, temp_dir: Path) -> None:
        """Test simple filename pattern not matching."""
        test_file = temp_dir / "test.txt"
        test_file.touch()

        excludes = ["*.log"]
        assert is_excluded(test_file, excludes, temp_dir) is False

    def test_directory_pattern(self, temp_dir: Path) -> None:
        """Test directory pattern matching."""
        node_modules = temp_dir / "node_modules"
        node_modules.mkdir()

        excludes = ["node_modules/"]
        assert is_excluded(node_modules, excludes, temp_dir) is True

    def test_path_pattern(self, temp_dir: Path) -> None:
        """Test path-based pattern matching."""
        subdir = temp_dir / "src"
        subdir.mkdir()
        test_file = subdir / "test.tmp"
        test_file.touch()

        excludes = ["/src/*.tmp"]
        assert is_excluded(test_file, excludes, temp_dir) is True

    def test_file_outside_basepath(self, temp_dir: Path) -> None:
        """Test file outside basepath is not excluded."""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as f:
            other_file = Path(f.name)

        excludes = ["*"]
        assert is_excluded(other_file, excludes, temp_dir) is False

        other_file.unlink()


class TestWalkDirectory:
    """Tests for walk_directory function."""

    def test_walk_excludes_patterns(self, sample_file_structure: Path) -> None:
        """Test that walk_directory excludes matching patterns."""
        excludes = ["*.pyc", "__pycache__/", "*.tmp"]

        files = walk_directory(sample_file_structure, excludes, sample_file_structure)
        filenames = [f.name for f in files]

        assert "index.html" in filenames
        assert "style.css" in filenames
        assert "app.js" in filenames
        assert "module.pyc" not in filenames
        assert "temp.tmp" not in filenames

    def test_walk_empty_excludes(self, sample_file_structure: Path) -> None:
        """Test walking with no excludes."""
        files = walk_directory(sample_file_structure, [], sample_file_structure)

        # Should include all files
        assert len(files) > 0


class TestCollectIgnorePatterns:
    """Tests for collect_ignore_patterns function."""

    def test_collect_from_single_file(self, temp_dir: Path) -> None:
        """Test collecting patterns from a single ignore file."""
        ignore_file = temp_dir / ".gsupload_ignore"
        ignore_file.write_text("*.log\n*.tmp\n")

        patterns = collect_ignore_patterns(temp_dir, temp_dir)

        assert "*.log" in patterns
        assert "*.tmp" in patterns

    def test_collect_walks_up_directories(self, temp_dir: Path) -> None:
        """Test that patterns are collected walking up directories."""
        subdir = temp_dir / "sub"
        subdir.mkdir()

        # Create ignore file in parent
        (temp_dir / ".gsupload_ignore").write_text("*.log\n")

        patterns = collect_ignore_patterns(subdir, temp_dir)

        assert "*.log" in patterns
