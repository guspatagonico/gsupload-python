"""
gsupload - Sync files and folders to remote FTP/SFTP servers

Author: Gustavo Adrián Salvini
Email: gsalvini@ecimtech.com
GitHub: https://github.com/guspatagonico

License: MIT License
Copyright (c) 2025 Gustavo Adrián Salvini
"""

__version__ = "1.0.1b2"
DEFAULT_MAX_DEPTH = 20

# Public API exports
from gsupload.config import load_config, load_config_with_sources, get_host_config
from gsupload.protocols.ftp import upload_ftp, list_remote_ftp
from gsupload.protocols.sftp import upload_sftp, list_remote_sftp

__all__ = [
    "__version__",
    "DEFAULT_MAX_DEPTH",
    "load_config",
    "load_config_with_sources",
    "get_host_config",
    "upload_ftp",
    "upload_sftp",
    "list_remote_ftp",
    "list_remote_sftp",
]
