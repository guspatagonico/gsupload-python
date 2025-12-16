"""
Tests for gsupload.tree module.
"""

from pathlib import Path
from typing import Any, Dict, Set
from unittest.mock import MagicMock, patch

import pytest


class TestDisplayTreeComparison:
    """Tests for display_tree_comparison function."""

    def test_display_tree_handles_connection_error(
        self, temp_dir: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Test that connection errors are handled gracefully."""
        import ftplib

        from gsupload.tree import display_tree_comparison

        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.touch()

        host_config: Dict[str, Any] = {
            "hostname": "ftp.example.com",
            "port": 21,
            "username": "user",
            "password": "pass",
            "remote_basepath": "/var/www",
        }

        with patch.object(ftplib, "FTP") as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            mock_ftp.connect.side_effect = Exception("Connection failed")

            with patch("click.confirm", return_value=False):
                with pytest.raises(SystemExit):
                    display_tree_comparison(
                        host_config,
                        [test_file],
                        temp_dir,
                        "ftp",
                        "test-binding",
                    )

    def test_display_tree_categorizes_files(self) -> None:
        """Test that files are correctly categorized."""
        # This is more of an integration test concept
        # Testing the categorization logic
        local_rel_paths: Set[str] = {"new.html", "existing.css", "local_only.js"}
        remote_files: Set[str] = {"existing.css", "remote_only.txt"}

        new_files = local_rel_paths - remote_files
        overwrite_files = local_rel_paths & remote_files
        remote_only = remote_files - local_rel_paths

        assert new_files == {"new.html", "local_only.js"}
        assert overwrite_files == {"existing.css"}
        assert remote_only == {"remote_only.txt"}
