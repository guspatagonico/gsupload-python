---
tags: []
keywords: []
importance: 56
recency: 1
maturity: draft
accessCount: 2
---
# gsupload (domain-level structural summary)

- **Primary scope (see `context.md`):** Describes the gsupload CLI workflow from config discovery through ignore-pattern resolution to remote listing and uploads, emphasizing layered config merging, FTP/SFTP traversal, threaded uploads with directory caching, and ignore pattern aggregation.
- **Configuration and flow (see `overview.md`):** `load_config_with_sources` walks upward from the working directory, layering `.gsupload.json` files and recording binding sources; `auto_detect_binding` resolves `local_basepath` and excludes; ignore files (`.gsupload_ignore`) are collected via upward traversal and anchored to `local_basepath`; remote listing uses BFS with MLSd/NLST (FTP) or `listdir_attr`/`listdir` (SFTP); uploads run per-thread sessions with cached directories to minimize `mkdir` calls.
- **Dependencies and runtime behavior (from `overview.md` highlights):** CLI relies on `click`, `paramiko`, `ftplib`, `fnmatch`, `ThreadPoolExecutor`, and `Lock`; FTP/SFTP listing honors timeouts; uploads use compressed Paramiko transports; ignore handling merges patterns from nested directories.
- **Key facts preserved (see `overview.md` facts block):** gsupload tool syncs to FTP/SFTP hosts; current version 1.0.1b2; MIT license; traversal depth capped by `DEFAULT_MAX_DEPTH = 20`.
- **Related drill-down topics:** `cli/gsupload/configuration`, `cli/gsupload/upload_workflow` for deeper coverage of binding resolution and upload mechanics.