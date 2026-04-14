# Domain: cli

## Purpose
Document the gsupload FTP/SFTP sync CLI, including configuration resolution, remote enumeration, uploading, and exclude management.

## Scope
Included in this domain:
- Configuration loading hierarchy for gsupload
- Remote traversal and upload workflows for FTP/SFTP
- Ignore file discovery and exclusion logic
- CLI helpers for output, prompts, and bindings

Excluded from this domain:
- Third-party CLI tools unrelated to gsupload
- Lower-level protocols outside FTP/SFTP

## Usage
Use this domain to capture knowledge about how gsupload loads configs, detects bindings, scans remotes, and uploads files for FTP/SFTP targets.
