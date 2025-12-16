"""
Protocols subpackage for gsupload.

Re-exports FTP and SFTP protocol functions.
"""

from gsupload.protocols.ftp import list_remote_ftp, upload_ftp
from gsupload.protocols.sftp import list_remote_sftp, upload_sftp

__all__ = [
    "list_remote_ftp",
    "upload_ftp",
    "list_remote_sftp",
    "upload_sftp",
]
