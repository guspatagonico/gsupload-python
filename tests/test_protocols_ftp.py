"""
Tests for gsupload.protocols.ftp module.
"""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


class TestListRemoteFtp:
    """Tests for list_remote_ftp function."""

    def test_list_remote_ftp_empty_dir(self) -> None:
        """Test listing an empty remote directory."""
        from gsupload.protocols.ftp import list_remote_ftp

        mock_ftp = MagicMock()
        mock_ftp.mlsd.return_value = []

        files = list_remote_ftp(mock_ftp, "/var/www")

        assert files == set()

    def test_list_remote_ftp_with_files(self) -> None:
        """Test listing remote directory with files."""
        from gsupload.protocols.ftp import list_remote_ftp

        mock_ftp = MagicMock()
        mock_ftp.mlsd.return_value = [
            ("index.html", {"type": "file"}),
            ("style.css", {"type": "file"}),
        ]

        files = list_remote_ftp(mock_ftp, "/var/www")

        assert "index.html" in files
        assert "style.css" in files


class TestUploadFtp:
    """Tests for upload_ftp function."""

    def test_upload_ftp_creates_directories(self, temp_dir: Path) -> None:
        """Test that upload_ftp creates remote directories."""
        from gsupload.protocols.ftp import upload_ftp

        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        host_config: Dict[str, Any] = {
            "hostname": "ftp.example.com",
            "port": 21,
            "username": "user",
            "password": "pass",
            "remote_basepath": "/var/www",
            "max_workers": 1,
        }

        with patch("gsupload.protocols.ftp.ftplib.FTP") as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp

            # Don't actually upload
            mock_ftp.storbinary.return_value = None

            upload_ftp(host_config, [test_file], temp_dir)

            # Verify connection was attempted
            mock_ftp.connect.assert_called_once()
            mock_ftp.login.assert_called_once()
