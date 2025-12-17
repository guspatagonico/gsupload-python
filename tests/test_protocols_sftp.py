"""
Tests for gsupload.protocols.sftp module.
"""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch


class TestListRemoteSftp:
    """Tests for list_remote_sftp function."""

    def test_list_remote_sftp_empty_dir(self) -> None:
        """Test listing an empty remote directory."""
        from gsupload.protocols.sftp import list_remote_sftp

        mock_sftp = MagicMock()
        mock_sftp.listdir_attr.return_value = []
        mock_sftp.get_channel.return_value = None

        files = list_remote_sftp(mock_sftp, "/home/user")

        assert files == set()

    def test_list_remote_sftp_with_files(self) -> None:
        """Test listing remote directory with files."""
        from gsupload.protocols.sftp import list_remote_sftp

        mock_sftp = MagicMock()

        # Create mock file attributes
        mock_file1 = MagicMock()
        mock_file1.filename = "index.html"
        mock_file1.st_mode = 0o100644  # Regular file

        mock_file2 = MagicMock()
        mock_file2.filename = "style.css"
        mock_file2.st_mode = 0o100644  # Regular file

        mock_sftp.listdir_attr.return_value = [mock_file1, mock_file2]
        mock_sftp.get_channel.return_value = None

        files = list_remote_sftp(mock_sftp, "/home/user")

        assert "index.html" in files
        assert "style.css" in files


class TestUploadSftp:
    """Tests for upload_sftp function."""

    def test_upload_sftp_creates_directories(self, temp_dir: Path) -> None:
        """Test that upload_sftp creates remote directories."""
        from gsupload.protocols.sftp import upload_sftp

        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        host_config: Dict[str, Any] = {
            "hostname": "sftp.example.com",
            "port": 22,
            "username": "user",
            "password": "pass",
            "remote_basepath": "/home/user/public_html",
            "max_workers": 1,
        }

        with patch("gsupload.protocols.sftp.paramiko.SSHClient") as mock_ssh_class:
            mock_ssh = MagicMock()
            mock_ssh_class.return_value = mock_ssh
            mock_sftp = MagicMock()
            mock_ssh.open_sftp.return_value = mock_sftp

            upload_sftp(host_config, [test_file], temp_dir)

            # Verify connection was attempted
            mock_ssh.connect.assert_called_once()
            mock_ssh.open_sftp.assert_called_once()

    def test_upload_sftp_with_key_file(self, temp_dir: Path) -> None:
        """Test SFTP upload with key file authentication."""
        from gsupload.protocols.sftp import upload_sftp

        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        host_config: Dict[str, Any] = {
            "hostname": "sftp.example.com",
            "port": 22,
            "username": "user",
            "key_filename": "/path/to/key",
            "remote_basepath": "/home/user/public_html",
            "max_workers": 1,
        }

        with patch("gsupload.protocols.sftp.paramiko.SSHClient") as mock_ssh_class:
            mock_ssh = MagicMock()
            mock_ssh_class.return_value = mock_ssh
            mock_sftp = MagicMock()
            mock_ssh.open_sftp.return_value = mock_sftp

            upload_sftp(host_config, [test_file], temp_dir)

            # Verify key_filename was passed
            call_kwargs = mock_ssh.connect.call_args[1]
            assert call_kwargs.get("key_filename") == "/path/to/key"
