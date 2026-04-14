---
tags: []
keywords: []
importance: 56
recency: 1
maturity: draft
accessCount: 2
---
### cli domain structural overview
- **Purpose & scope (see `context.md`):** Documents gsupload’s FTP/SFTP sync CLI, covering configuration resolution, remote enumeration/upload workflows, and ignore/exclusion logic. Excludes unrelated CLI tools and non-FTP/SFTP protocols. Use this domain for understanding gsupload’s config loading, binding detection, ignore discovery, and remote traversal/upload helpers.
- **Configuration and binding flow (drill into `cli/gsupload/configuration`):** Configuration merges `.gsupload.json` files while recording binding sources; `auto_detect_binding` resolves `local_basepath` and excludes; ignore files (`.gsupload_ignore`) are discovered upward from the working directory and anchored to the resolved base path. Key API surfaces include `load_config_with_sources` for layered config resolution and binding detection.
- **Remote enumeration and upload workflow (drill into `cli/gsupload/upload_workflow`):** Remote listing uses MLSd/NLST for FTP and `listdir_attr`/`listdir` for SFTP with BFS traversal capped by `DEFAULT_MAX_DEPTH = 20`; uploads are performed via per-thread sessions with cached directories to reduce `mkdir` calls, and ignore handling merges nested ignore lists. Upload stack relies on `click`, `paramiko`, `ftplib`, `fnmatch`, `ThreadPoolExecutor`, and locking primitives, with Paramiko transports compressed for efficiency.
- **Key facts preserved (from `gsupload/_index.md` summary):** gsupload syncs to FTP/SFTP hosts, current release `1.0.1b2` under MIT license, timeout-aware remote listing, ignore aggregation, and depth-limited traversal.