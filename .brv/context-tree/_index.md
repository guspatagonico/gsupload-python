---
children_hash: 2d2cca9a1c362f0b12e72a5c038cf3c495b3e5f73685462e46a5f3af296a1113
compression_ratio: 0.6652360515021459
condensation_order: 3
covers: [cli/_index.md]
covers_token_total: 466
summary_level: d3
token_count: 310
type: summary
---
### cli domain overview (see `cli/_index.md`)
- **Purpose & scope:** Captures gsupload’s FTP/SFTP sync CLI, covering configuration loading (`cli/gsupload/configuration`), binding detection, ignore resolution, remote enumeration, and upload orchestration; excludes unrelated CLIs or non-FTP/SFTP protocols.
- **Configuration & binding (see `cli/gsupload/configuration`):** `.gsupload.json` layers are merged via `load_config_with_sources`, `auto_detect_binding` determines `local_basepath` and excludes, and `.gsupload_ignore` files are discovered upward and anchored to the resolved base path before upload.
- **Remote traversal & upload workflow (see `cli/gsupload/upload_workflow`):** FTP listing uses MLSd/NLST, SFTP uses `listdir_attr`/`listdir`, both with BFS depth capped by `DEFAULT_MAX_DEPTH = 20`; multi-threaded uploads reuse cached directories, minimize `mkdir`, and merge nested ignore lists; stack relies on `click`, `paramiko`, `ftplib`, `fnmatch`, `ThreadPoolExecutor`, and locking, with compressed Paramiko transports.
- **Key facts (see `cli/gsupload/_index.md`):** gsupload syncs to FTP/SFTP hosts, at release `1.0.1b2`, MIT licensed, supports timeout-aware remote listing, aggregated ignores, and depth-limited traversal.