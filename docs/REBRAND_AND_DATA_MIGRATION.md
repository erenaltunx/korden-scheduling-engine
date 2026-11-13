# Optera rename and existing data safety

The former project was named **KORDEN**. This document is intentionally the
only user-facing reference to that historical name. The new product is **Optera**
(`optera` Python package, `OPTERA_DATA_DIR` and `OPTERA_PUBLIC_DEMO`).

## Local experiment history

Existing history is NOT renamed or deleted automatically.

- New installs use `~/.optera/experiments.sqlite3`.
- If `~/.korden/experiments.sqlite3` already exists and no new archive exists,
  Optera continues to use the legacy archive in place.
- Existing `KORDEN_DATA_DIR` settings continue to work, unless an explicit
  `OPTERA_DATA_DIR` is set; the new variable takes precedence.
- If *both* old and new archives exist, the newer product archive is chosen.
  Neither archive is merged or erased. Back up both before changing paths.
- To migrate the old data to a new location, first stop all writers, make a
  consistent backup with `python backup.py --out <fresh-backup-path>`, and
  restore that backup to a new path only after confirming `PRAGMA integrity_check`
  reports `ok` and experiment records can be opened.

## Docker volumes

Docker Compose creates a separate project namespace per directory. Renaming
folders, services or volumes can cause a previously created volume to appear
missing even though the data still exists. **Do not run `docker compose down -v`**.
List old volumes with `docker volume ls`; retain backups of existing named
volumes. When upgrading, explicitly mount the old volume or migrate its data
using SQLite's backup API, and verify the experiment count before retiring it.

## GitHub repository slug

Code is published first to the existing repository. GitHub repository rename
requires **Settings → General → Repository name**; change it to `optera`.
GitHub normally redirects old repository links after a rename, but update any
local clone `origin` URLs and external integrations explicitly.

The historical Git commits are retained. Never force-push or delete the old
repository to rebrand it.
