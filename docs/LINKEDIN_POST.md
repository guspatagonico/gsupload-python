# Safe, fast SFTP/FTP deploys without a full CI/CD platform: "gsupload"

If you still have workflows that end with "just upload these files to the server" (FTP/SFTP), you already know the failure modes:

- someone uploads from the wrong folder
- excludes differ per machine
- `node_modules/` or build artifacts slip in
- you overwrite something you didn't mean to

I built **gsupload** to make those uploads *repeatable, deterministic, and fast*.

Repository: https://github.com/guspatagonico/gsupload-python

---

## Motivation

This started as a personal pain point: **partial deployments in full-stack repos**.

Same codebase, different deployment endpoints:

- frontend build output → one server/path (often SFTP)
- backend or CMS assets → another server/path (sometimes only FTP)
- and sometimes **non-standard ports** because of hosting panels, firewalls, or legacy constraints

With **bindings** + **layered config merge**, that stops living in scattered notes and becomes an explicit, repeatable model.

---

## The killer feature: configuration is discovered and merged

This is the part that makes the tool scale from "one folder" to "many projects / subfolders" without turning into a mess.

The "magic" is that you don’t pass a big pile of flags every time. You just run `gsupload` from wherever you are in the repo, and it:

- discovers global + project `.gsupload.json` layers automatically
- merges them deterministically (shallow → deep)
- selects the right target without you needing to remember which server/path applies

`gsupload` **discovers multiple config layers and merges them**:

- Optional global base:
  - `~/.gsupload/gsupload.json` or `~/.config/gsupload/gsupload.json`
- Project layers:
  - it walks up from your current directory and collects every `.gsupload.json`
  - merges them from shallowest → deepest (root → cwd)

Merge rules (pragmatic, predictable):

- `global_excludes`: **additive** (combined across layers)
- `bindings`: **deep merge per binding alias** (deeper wins, unspecified keys inherit)
- other keys: **deepest wins**

The result: teams can keep secrets in a global config, keep repo defaults in `.gsupload.json`, and override per-subfolder when needed.

### The abstraction: "bindings"

A **binding** is an ad-hoc but powerful abstraction: a named deployment target (alias) that describes *where* uploads go and *how*.

In practice a binding is:

- protocol: `ftp` or `sftp`
- host + port (not necessarily 21/22)
- auth (password, key, agent)
- `local_basepath` (what local folder is considered "root")
- `remote_basepath` (remote root folder)

And because bindings are merged across config layers, you can define a base binding once (globally) and only override what changes per repo or subfolder.

Bonus: when you don’t pass `-b`, `gsupload` can auto-detect the binding by comparing your current directory with each binding’s `local_basepath`.

---

## Performance: built for "many small web assets"

I didn't want "safe" to mean "slow". A few optimizations make it practical:

- **Parallel uploads** via `ThreadPoolExecutor`
  - default workers: `binding.max_workers` (or 5)
  - `--max-workers` overrides config for a single run
- **SSH compression for SFTP** (`compress=True`)
  - big wins for HTML/CSS/JS/JSON
  - some retry paths may temporarily disable compression for compatibility
- **Directory creation caching**
  - avoids repeated `mkdir/stat` calls across threads
- **FTP passive mode by default (PASV)**
  - works better behind NAT/firewalls
  - `--ftp-active` when you explicitly need it

Quick rule-of-thumb:

- SFTP: try 5-10 workers
- FTP: keep it conservative (1-3) depending on the server

---

## What it feels like to use

Once your repo is described with bindings, the daily workflow is intentionally boring (in a good way):

- `gsupload` finds and merges config layers for the directory you’re in
- it can auto-select the right binding based on `local_basepath`
- it expands your patterns, applies excludes, shows a pre-flight diff, then uploads in parallel

Conceptual example of a single repo with two destinations (different protocols and non-standard ports):

```json
{
  "global_excludes": [".git", "node_modules", ".DS_Store"],
  "bindings": {
    "frontend-sftp": {
      "protocol": "sftp",
      "hostname": "frontend.example.com",
      "port": 2222,
      "username": "deploy",
      "key_filename": "~/.ssh/id_ed25519",
      "local_basepath": "./frontend",
      "remote_basepath": "/var/www/html"
    },
    "backend-ftp": {
      "protocol": "ftp",
      "hostname": "legacy.example.com",
      "port": 2121,
      "username": "ftpuser",
      "local_basepath": "./backend/public",
      "remote_basepath": "/public_html"
    }
  }
}
```

In practice that means you can `cd frontend/` (or `cd backend/public/`) and run the same command shape, without re-learning “which server/path is this?” every time.

If you ever want to verify what `gsupload` thinks it will do:

```bash
# show the merged config and where each value came from
gsupload --show-config

# show what is being excluded (config + .gsupload_ignore)
gsupload --show-ignored
```

Pre-flight safety net gives you a "diff before deploy":

- NEW → doesn't exist remotely
- OVERWRITE → exists and will be replaced
- REMOTE ONLY → exists on server but not locally (in complete mode)

Typical commands:

```bash
# safest default: complete pre-flight comparison + confirm
gsupload "dist/**/*"

# changes-only comparison
gsupload -vc "dist/**/*"

# automation / CI: fastest mode (no remote scan, no prompt)
gsupload -f -b=frontend-sftp "dist/**/*"

# tune parallelism per run (overrides config)
gsupload --max-workers=10 -b=frontend-sftp "dist/**/*"
```

(Always quote globs so your shell doesn't expand them before `gsupload` sees them.)

---

## If you're into tooling like this

I'm open to collaborations and networking around pragmatic deployment tooling.

If you've got real-world constraints (hosting panels, chrooted SFTP, FTP quirks, CI needs), I'd love to hear them—open an issue or PR and let's improve it together:

https://github.com/guspatagonico/gsupload-python

Contact:

- GitHub: https://github.com/guspatagonico
- Website: https://gustavosalvini.com.ar
- Email: gsalvini@ecimtech.com
