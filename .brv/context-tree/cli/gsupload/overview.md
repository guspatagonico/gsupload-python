---
title: Overview
summary: The gsupload CLI merges layered configs, enumerates ignore patterns, lists remote files via FTP/SFTP, and uploads files with cached directory creation.
tags: []
keywords: []
importance: 62
recency: 1
maturity: draft
accessCount: 4
createdAt: '2026-04-14T03:49:37.867Z'
updatedAt: '2026-04-14T03:49:37.867Z'
---
## Reason
Document src/gsupload.py functionality, flow, and dependencies for the FTP/SFTP sync CLI

## Raw Concept
**Task:**
Document the gsupload CLI architecture and operational flow described in src/gsupload.py.

**Changes:**
- Captured configuration hierarchy and binding resolution behavior
- Summarized FTP and SFTP remote enumeration strategies and upload threads
- Recorded ignore file collection and exclusion-rule evaluation

**Files:**
- src/gsupload.py

**Flow:**
load_config_with_sources -> auto_detect_binding -> gather ignore files -> list remote via FTP/SFTP -> upload files with cached directories

**Timestamp:** 2026-04-14

**Author:** Gustavo Adrián Salvini

## Narrative
### Structure
CLI entry points manage config loading through load_config_with_sources, which finds layered .gsupload.json files, resolves binding-specific local_basepath, and tracks global excludes before delegating to remote listing/upload routines.

### Dependencies
Relies on click, paramiko, ftplib, fnmatch, ThreadPoolExecutor, and Lock for CLI interactions, SSH uploads, FTP/session management, pattern matching, and concurrent uploads.

### Highlights
Remote listing performs BFS with MLSD/NLST fallbacks (FTP) or listdir_attr/listdir (SFTP) while honoring timeouts; uploads use per-thread sessions, compressed Paramiko transports, and directory caches to reduce redundant mkdir calls; ignore handling aggregates upward traversal of .gsupload_ignore files, anchoring patterns to local_basepath.

### Rules
Rule: keep CLI prompts, error messages, and file-resolution strings exactly as implemented in src/gsupload.py.

### Examples
Config merging example: load_config_with_sources walks from the current working directory to root, merging bindings with deeper files taking precedence and listing the source file for each binding property.

## Facts
- **gsupload_tool**: The gsupload CLI syncs files to FTP or SFTP hosts. [project]
- **gsupload_version**: Version 1.0.1b2 is the current release described here. [project]
- **license**: The CLI is MIT licensed with standard warranty disclaimers. [project]
- **default_max_depth**: DEFAULT_MAX_DEPTH for traversals is 20. [project]
